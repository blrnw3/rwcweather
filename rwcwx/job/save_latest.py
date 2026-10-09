import json
import logging
import logging.handlers
import os
import signal
import sys
import time
from datetime import date, datetime, timedelta
from typing import Optional
from statistics import mean

import click
from sqlalchemy.dialects.mysql import insert

from rwcwx import logger
from rwcwx.calc.avg_extreme import DaySummary
from rwcwx.config import AQI_FILE_NAME
from rwcwx.model.cumulus import CumulusObs
from rwcwx.models import db, m
from rwcwx.util import DateUtil

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_LOG_FILE = os.path.join(REPO_ROOT, "log", "save_latest.log")
LOG_FORMAT = "%(asctime)s :: %(levelname)s :: %(process)d :: %(module)s:%(lineno)d :: %(message)s"


def setup_logging(log_file: str, max_bytes: int, backups: int, verbose: bool) -> None:
    """
    Log to a size-rotated file (max_bytes x backups) instead of stderr, which the start script only keeps as a
    fallback for crashes before logging is configured. log_file "-" keeps logging on stderr only.
    """
    root = logging.getLogger()
    if log_file != "-":
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backups)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        for h in list(root.handlers):  # drop the stderr handler from rwcwx/__init__ (basicConfig)
            root.removeHandler(h)
        root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    # rwcwx.model.db turns SQL echo on (useful for the API); here it would log every insert
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class CumulusObsImporter:

    AIR_AGE_THRESHOLD = timedelta(seconds=3600)
    AVG_EXT_INTERVAL = timedelta(minutes=1)
    HEARTBEAT_INTERVAL = timedelta(minutes=15)

    def __init__(self, obs_path: str, external_root: str) -> None:
        self.obs_path = obs_path
        self.external_root = external_root

        self.err_cnt = 0
        self.obs_last_mod = 0
        self.current_dt = None
        self.max_gust = 0

        self.last_avg_ext_update = datetime.now() - self.AVG_EXT_INTERVAL

        # Counters for the periodic heartbeat (routine per-update messages are DEBUG only)
        self.last_heartbeat = datetime.now()
        self.n_saved = 0
        self.n_avg_ext = 0
        self.n_errors = 0
        self.n_air_missing = 0
        self.last_obs_dt = None
        self.air_ok = True

    def run(self):
        while True:
            try:
                self.get_and_save_latest()
                if datetime.now() >= (self.last_avg_ext_update + self.AVG_EXT_INTERVAL):
                    logger.debug("Updating averages/extremes")
                    self.update_avg_ext()
                    self.n_avg_ext += 1
                    self.last_avg_ext_update = datetime.now()
            except Exception as e:
                self.err_cnt += 1
                self.n_errors += 1
                logger.exception(f"Error getting/saving latest cumulus data (consecutive errors: {self.err_cnt})",
                                 exc_info=e)
                time.sleep(self.err_cnt * 5)
            else:
                if self.err_cnt:
                    logger.info(f"Recovered after {self.err_cnt} consecutive errors")
                self.err_cnt = 0
            self.maybe_heartbeat()
            time.sleep(1)

    def maybe_heartbeat(self) -> None:
        now = datetime.now()
        if now - self.last_heartbeat < self.HEARTBEAT_INTERVAL:
            return
        mins = (now - self.last_heartbeat).total_seconds() / 60
        logger.info(f"Heartbeat: last {mins:.0f} min saved {self.n_saved} updates, {self.n_avg_ext} avg/ext refreshes, "
                    f"{self.n_errors} errors, {self.n_air_missing} without air data; latest obs {self.last_obs_dt}")
        if self.n_saved == 0:
            logger.warning(f"No new observations in the last {mins:.0f} min; is {self.obs_path} still being updated?")
        self.last_heartbeat = now
        self.n_saved = self.n_avg_ext = self.n_errors = self.n_air_missing = 0

    def get_and_save_latest(self) -> None:
        last_mod = os.path.getmtime(self.obs_path)
        if last_mod == self.obs_last_mod:
            return
        logger.debug(f"File updated at {last_mod}")
        self.obs_last_mod = last_mod

        obs = CumulusObs(self.obs_path)
        # logger.warn(f"minute: {obs.dt.minute}. curr_dt: {self.current_dt}. Gust: {obs.gust}. Max gust: {self.max_gust}")
        if obs.dt.minute == self.current_dt:
            self.max_gust = max(self.max_gust, obs.gust)
            # logger.warn("Updating max_gust")
        else:
            # logger.warn("RESETTING")
            self.max_gust = obs.gust

        self.current_dt = obs.dt_minute.minute
        obs.gust = self.max_gust

        obs_db_params = obs.as_obs_table_params()
        obs_db_params.update(dict(
            pm2=self.get_pm2_5()
        ))
        save_obs = insert(m.obs).values(
            **obs_db_params
        ).on_duplicate_key_update(
            **obs_db_params,
            t_mod=datetime.utcnow()
        )
        logger.debug(f"Inputting data at time {obs.dt} (record: {obs.dt_minute})")
        db.execute(save_obs)
        self.n_saved += 1
        self.last_obs_dt = obs.dt

    def get_pm2_5(self) -> Optional[float]:
        aqi_path = os.path.join(self.external_root, AQI_FILE_NAME)
        try:
            with open(aqi_path) as f:
                air_data = json.load(f)
                last_seen = datetime.fromtimestamp(air_data["data_time_stamp"])
                age = datetime.now() - last_seen
                if age > self.AIR_AGE_THRESHOLD:
                    self._air_missing(f"Air data out of date. Age: {age}")
                    return None
                pm2_5s = [air_data["sensor"]["pm2.5"]]
                logger.debug(f"Air data: pm2.5 {pm2_5s} updated {age.total_seconds()} s ago")
                if not self.air_ok:
                    logger.info("Air data available again")
                    self.air_ok = True
                return mean(pm2_5s)
        except Exception as e:
            self._air_missing(f"Failed extracting air q data: {e!r}", exc=e)
            return None

    def _air_missing(self, msg: str, exc: Optional[Exception] = None) -> None:
        """Log the first failure in a run of air-data failures; later ones only count towards the heartbeat."""
        self.n_air_missing += 1
        if self.air_ok:
            logger.error(msg + " (further air data failures are counted in the heartbeat)", exc_info=exc)
            self.air_ok = False
        else:
            logger.debug(msg)

    @staticmethod
    def update_avg_ext(d: date = None) -> None:
        if d is None:
            d = DateUtil.now().date()
        logger.debug(f"Avg/extr update date: {d}")
        try:
            day_summary = DaySummary(d).stats()
        except ValueError:
            logger.debug("No records for day (yet)")
            return

        records = []
        for obsVar, summary in day_summary.items():
            params = dict(
                d=d,
                var=obsVar.db_field,
                period="day",
                t_mod=datetime.utcnow(),
                cnt=summary.count
            )

            for typ, val, at in [
                ("avg", summary.avg, None),
                ("total", summary.total, None),
                ("min", summary.min_val, summary.min_at),
                ("max", summary.max_val, summary.max_at),
            ]:
                if val is None:
                    logger.debug(f"Skipping null value {obsVar.name}-{typ}")
                    continue
                all_params = dict(type=typ, val=val, at=at)
                all_params.update(params)
                # TODO: don't override already overidden entries (check first)
                records.append(
                    insert(m.avg_extreme).values(
                        **all_params,
                    ).on_duplicate_key_update(
                        **all_params
                    )
                )
        db.execute_batch(records)


def _exit_on_sigterm(signum, frame):
    raise SystemExit(f"Received signal {signum}")


@click.command()
@click.option("-o", "--obs_path", required=True)
@click.option("-e", "--external_root", required=True)
@click.option("--log-file", envvar="SAVE_LATEST_LOG", default=DEFAULT_LOG_FILE, show_default=True,
              help="Rotating log file ('-' for stderr only). Env: SAVE_LATEST_LOG")
@click.option("--log-max-bytes", envvar="SAVE_LATEST_LOG_MAX_BYTES", type=int, default=5 * 1024 * 1024,
              show_default=True, help="Rotate the log at this size. Env: SAVE_LATEST_LOG_MAX_BYTES")
@click.option("--log-backups", envvar="SAVE_LATEST_LOG_BACKUPS", type=int, default=5, show_default=True,
              help="Rotated log files to keep. Env: SAVE_LATEST_LOG_BACKUPS")
@click.option("-v", "--verbose", is_flag=True, help="Log every update (DEBUG)")
def main(obs_path: str, external_root: str, log_file: str, log_max_bytes: int, log_backups: int,
         verbose: bool) -> None:
    setup_logging(log_file, log_max_bytes, log_backups, verbose)
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    logger.info(f"Starting save_latest (pid {os.getpid()}): obs_path={obs_path} external_root={external_root} "
                f"log={log_file} ({log_max_bytes} bytes x {log_backups})")
    try:
        CumulusObsImporter(obs_path, external_root).run()
    except SystemExit as e:
        logger.info(f"Stopping save_latest: {e}")
        raise
    except BaseException:
        logger.critical("save_latest crashed", exc_info=True)
        raise


if __name__ == "__main__":
    main()

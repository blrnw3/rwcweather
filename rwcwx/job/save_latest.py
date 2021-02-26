import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional
from statistics import mean

import click
from dateutil.tz import UTC
from sqlalchemy.dialects.mysql import insert

from rwcwx import logger
from rwcwx.config import AQI_FILE_NAME
from rwcwx.model.cumulus import CumulusObs
from rwcwx.models import db, m


class CumulusObsImporter:

    AIR_AGE_THRESHOLD = timedelta(seconds=3600)

    def __init__(self, obs_path: str, external_root: str) -> None:
        self.obs_path = obs_path
        self.external_root = external_root

        self.err_cnt = 0
        self.obs_last_mod = 0
        self.current_dt = None
        self.max_gust = 0

    def run(self):
        while True:
            try:
                self.get_and_save_latest()
            except Exception as e:
                self.err_cnt += 1
                logger.exception("Error getting/saving latest cumulus data", exc_info=e)
                logger.warning(f"Error cnt: {self.err_cnt}")
                time.sleep(self.err_cnt * 5)
            else:
                self.err_cnt = 0
            time.sleep(1)

    def get_and_save_latest(self):
        last_mod = os.path.getmtime(self.obs_path)
        if last_mod == self.obs_last_mod:
            return
        logger.info(f"File updated at {last_mod}")
        self.obs_last_mod = last_mod

        obs = CumulusObs(self.obs_path)
        if obs.dt.minute == self.current_dt:
            self.max_gust = max(self.max_gust, obs.gust)
        else:
            self.max_gust = obs.gust

        self.current_dt = obs.dt_minute
        obs.gust = self.max_gust

        obs_db_params = obs.as_obs_table_params()
        obs_db_params.update(dict(
            pm2=self.get_pm2_5()
        ))
        save_obs = insert(m.obs).values(
            **obs_db_params
        ).on_duplicate_key_update(
            **obs_db_params,
            t_mod=datetime.now().replace(tzinfo=UTC)
        )
        logger.info(f"Inputting data at time {obs.dt} (record: {obs.dt_minute})")
        db.execute(save_obs)

    def get_pm2_5(self) -> Optional[float]:
        aqi_path = os.path.join(self.external_root, AQI_FILE_NAME)
        try:
            with open(aqi_path) as f:
                air_data = json.load(f)
                last_seen = datetime.fromtimestamp(air_data["results"][0]["LastSeen"])
                age = datetime.now() - last_seen
                if age > self.AIR_AGE_THRESHOLD:
                    logger.error(f"Air data out of date. Age: {age}")
                    return None
                pm2_5s = [float(r["PM2_5Value"]) for r in air_data["results"]]
                logger.info(f"Air data: pm2.5 {pm2_5s} updated {age.total_seconds()} s ago")
                return mean(pm2_5s)
        except Exception as e:
            logger.exception("Failed extracting air q data", exc_info=e)
            return None


@click.command()
@click.option("-o", "--obs_path", required=True)
@click.option("-e", "--external_root", required=True)
def main(obs_path: str, external_root: str) -> None:
    obs_importer = CumulusObsImporter(obs_path, external_root)
    obs_importer.run()


if __name__ == "__main__":
    main()

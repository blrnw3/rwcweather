"""
Classify webcam frames as sunny / not sunny, write per-minute rows to obs_inferred (kind='sunny'), the daily total
to avg_extreme and a health JSON.

Run every 15 min from cron via scripts/run_sun_classify.sh (flock + nice + memory cap). Each run:
  * lists the per-minute sky_lg frames for the local day (filenames are UTC YYYYMMDD_HHMM.jpg),
  * classifies only frames not already in the per-day cache (one frame in memory at a time),
  * re-applies the gates / low-sun rule R3 / median filter to the whole day (R3 needs later frames to settle the
    morning low-sun minutes, so earlier minutes can change on later runs), and
  * upserts every daylight minute of the day. Rows with source='manual' are never overwritten.
  * writes the daily total to avg_extreme (var='sun', type='total') per the coverage rule (rollup.py), never
    touching rows with overridden=1, and
  * writes a health JSON (frame age, coverage, gate counts, camera shift) for monitoring.

  python rwcwx/job/sun_classify.py                       # today (and yesterday until 00:30 local)
  python rwcwx/job/sun_classify.py -d 2026-10-09 --dry-run --csv /tmp/out.csv
"""
import csv
import gc
import hashlib
import json
import os
import resource
import sys
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

os.environ["TZ"] = "UTC"     # rwcwx.astronomy uses time.mktime: run in UTC so its naive datetimes are UTC
time.tzset()

import click
from dateutil.tz import UTC

from rwcwx import logger
from rwcwx.config import TZ
from rwcwx.sun.features import feats, load_small
from rwcwx.sun.model import LrModel
from rwcwx.sun.rollup import daily_total
from rwcwx.sun.rules import GLITCH_PINK, Frame, Minute, classify_day, summary
from rwcwx.sun.solar import solar_pos

FRAMES_DIR = "/var/www/rwc/html/cumulus/camdump/sky_lg"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(REPO_ROOT, "out_prod", "sun_cache")
HEALTH_PATH = os.path.join(REPO_ROOT, "out_prod", "sun_health.json")
CACHE_SCHEMA = 2
KIND = "sunny"
LAT, LNG = 37.470, -122.265


def sun_times_utc(day: date):
    """Sunrise/sunset (naive UTC) for a local day, same call the site makes (rwcwx.astronomy.get_all_times_rwc)."""
    from rwcwx.astronomy import getTimes
    st = getTimes(datetime(day.year, day.month, day.day, 12), LAT, LNG)
    return st["sunrise"], st["sunset"]


def local_day_bounds_utc(day: date):
    a = datetime(day.year, day.month, day.day, tzinfo=TZ).astimezone(UTC).replace(tzinfo=None)
    b = datetime.combine(day + timedelta(days=1), datetime.min.time()).replace(tzinfo=TZ).astimezone(UTC).replace(tzinfo=None)
    return a, b


def list_frames(frames_dir: str, t0: datetime, t1: datetime) -> Dict[datetime, str]:
    out = {}
    for d in {t0.date(), t1.date()}:
        prefix = d.strftime("%Y%m%d_")
        try:
            names = [n for n in os.listdir(frames_dir) if n.startswith(prefix) and n.endswith(".jpg")]
        except FileNotFoundError:
            return out
        for n in names:
            try:
                t = datetime.strptime(n[:13], "%Y%m%d_%H%M")
            except ValueError:
                continue
            if t0 <= t <= t1:
                out[t] = os.path.join(frames_dir, n)
    return out


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


class Classifier:
    def __init__(self):
        self.main = LrModel.load("sunny_lr_v1")
        self.sky = LrModel.load("skyclear_lr_v1")
        self.version = self.main.version

    def frame(self, path: str, t: datetime) -> Optional[dict]:
        try:
            f = feats(load_small(path))
        except Exception as e:          # truncated / unreadable frame -> treated as missing
            logger.warning(f"Unreadable frame {path}: {e}")
            return None
        f["el"], f["az"] = solar_pos(t)
        return dict(p=round(self.main.prob(f), 4), ps=round(self.sky.prob(f), 4), smean=round(f["Smean"], 4),
                    pink=round(f["pink_bot"], 4), el=round(f["el"], 2), md5=_md5(path))


def load_cache(path: str, version: str) -> dict:
    try:
        with open(path) as fh:
            c = json.load(fh)
        if c.get("version") == version and c.get("schema") == CACHE_SCHEMA:
            return c
    except (OSError, ValueError):
        pass
    return {"version": version, "schema": CACHE_SCHEMA, "frames": {}}


def save_cache(path: str, cache: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(cache, fh, separators=(",", ":"))
    os.replace(tmp, path)


def process_day(day: date, clf: Classifier, frames_dir: str, cache_dir: str, max_new: int):
    sunrise, sunset = sun_times_utc(day)
    frames = list_frames(frames_dir, sunrise - timedelta(minutes=10), sunset + timedelta(minutes=10))
    cache_path = os.path.join(cache_dir, f"{day.isoformat()}.json")
    cache = load_cache(cache_path, clf.version)
    fc = cache["frames"]
    new = 0
    for t in sorted(frames):
        key = t.strftime("%Y%m%d_%H%M")
        if key in fc or new >= max_new:
            continue
        fc[key] = clf.frame(frames[t], t)
        new += 1
        gc.collect()
    if new:
        save_cache(cache_path, cache)

    seq: List[Frame] = []
    prev_md5 = None
    for key in sorted(fc):
        r = fc[key]
        if r is None:
            continue
        seq.append(Frame(t=datetime.strptime(key, "%Y%m%d_%H%M"), p=r["p"], ps=r["ps"], smean=r["smean"],
                         stale=(r["md5"] == prev_md5), glitch=r["pink"] > GLITCH_PINK))
        prev_md5 = r["md5"]
    grid = classify_day(seq, sunrise, sunset)
    logger.info(f"{day}: {len(frames)} frames ({new} new), sunrise {sunrise:%H:%M:%S} sunset {sunset:%H:%M:%S} UTC, "
                f"{summary(grid)}")
    return grid, frames, fc


def rows_for(grid: List[Minute], version: str, now: Optional[datetime] = None) -> List[dict]:
    """One row per completed daylight minute (minute end <= now). Future minutes are never written, so the table
    never holds placeholder 'missing' rows for time that has not happened yet."""
    now = now or datetime.utcnow().replace(microsecond=0)
    return [dict(t=m.t, kind=KIND, value=m.value, prob=None if m.p is None else round(m.p, 3), minutes=1,
                 source="live", flags=",".join(sorted(m.flags)) or None, model_version=version, t_mod=now)
            for m in grid if m.t + timedelta(minutes=1) <= now]


UPSERT = """
INSERT INTO obs_inferred (t, kind, value, prob, minutes, source, flags, model_version, t_mod)
VALUES (:t, :kind, :value, :prob, :minutes, :source, :flags, :model_version, :t_mod)
ON DUPLICATE KEY UPDATE
  value = IF(source = 'manual', value, VALUES(value)),
  prob = IF(source = 'manual', prob, VALUES(prob)),
  flags = IF(source = 'manual', flags, VALUES(flags)),
  model_version = IF(source = 'manual', model_version, VALUES(model_version)),
  t_mod = IF(source = 'manual', t_mod, VALUES(t_mod))
"""


UPSERT_TOTAL = """
INSERT INTO avg_extreme (d, var, type, period, val, at, cnt, t_mod, overridden, comment)
VALUES (:d, 'sun', 'total', 'day', :val, NULL, :cnt, :t_mod, 0, :comment)
ON DUPLICATE KEY UPDATE
  val = IF(overridden = 1, val, VALUES(val)),
  cnt = IF(overridden = 1, cnt, VALUES(cnt)),
  comment = IF(overridden = 1, comment, VALUES(comment)),
  t_mod = IF(overridden = 1, t_mod, VALUES(t_mod))
"""


def write_db(rows: List[dict], totals: List[dict]) -> None:
    from sqlalchemy import create_engine, text
    url = os.environ["MYSQL_URL"]
    engine = create_engine(f"mysql://{url}", pool_pre_ping=True)
    try:
        with engine.begin() as conn:
            if rows:
                conn.execute(text(UPSERT), rows)
            if totals:
                conn.execute(text(UPSERT_TOTAL), totals)
    finally:
        engine.dispose()


def check_camera(frames: Dict[datetime, str], fc: dict) -> Optional[dict]:
    """Phase-correlate up to 3 recent good daylight frames against the reference view; moved only if all agree."""
    from PIL import Image
    from rwcwx.sun.shift import camera_shift
    cands = [t for t in sorted(frames, reverse=True)
             if (fc.get(t.strftime("%Y%m%d_%H%M")) or {}).get("el", -90) > 15
             and fc[t.strftime("%Y%m%d_%H%M")]["pink"] <= GLITCH_PINK][:3]
    res = []
    for t in cands:
        try:
            with Image.open(frames[t]) as im:
                r = camera_shift(im)
        except Exception:
            continue
        r["t"] = t.isoformat()
        res.append(r)
    if not res:
        return None
    return dict(checks=res, moved=all(r["moved"] for r in res))


def write_health(path: str, health: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(health, fh, indent=1, default=str)
    os.replace(tmp, path)


def write_csv(path: str, rows: List[dict]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


@click.command()
@click.option("-d", "--day", "days", multiple=True, help="Local day YYYY-MM-DD (repeatable). Default: today, "
              "plus yesterday until 00:30 local")
@click.option("--frames-dir", default=FRAMES_DIR, show_default=True)
@click.option("--cache-dir", default=CACHE_DIR, show_default=True)
@click.option("--max-new", type=int, default=900, show_default=True, help="Cap on frames classified per day per run")
@click.option("--dry-run", is_flag=True, help="Do not write to the DB")
@click.option("--csv", "csv_path", default=None, help="Also write the rows to this CSV")
@click.option("--health", "health_path", default=HEALTH_PATH, show_default=True, help="Health JSON path ('' = off)")
def main(days, frames_dir, cache_dir, max_new, dry_run, csv_path, health_path):
    t_start = time.time()
    if days:
        todo = [datetime.strptime(d, "%Y-%m-%d").date() for d in days]
    else:
        now_local = datetime.now(TZ)
        todo = [now_local.date()]
        if now_local.hour == 0 and now_local.minute < 30:
            todo.insert(0, now_local.date() - timedelta(days=1))
    clf = Classifier()
    rows: List[dict] = []
    totals: List[dict] = []
    now = datetime.utcnow().replace(microsecond=0)
    health = dict(t_run=now.isoformat() + "Z", model_version=clf.version, days={})
    for d in todo:
        grid, frames, fc = process_day(d, clf, frames_dir, cache_dir, max_new)
        rows += rows_for(grid, clf.version, now)
        tot = daily_total(grid, now)
        if tot:
            totals.append(dict(d=d, val=tot["val"], cnt=tot["cnt"], comment=tot["comment"], t_mod=now))
        flags: Dict[str, int] = {}
        for m in grid:
            if m.t < now:
                for fl in m.flags:
                    flags[fl] = flags.get(fl, 0) + 1
        last = max(frames) if frames else None
        health["days"][d.isoformat()] = dict(
            frames=len(frames), last_frame=last.isoformat() + "Z" if last else None,
            summary_so_far=summary([m for m in grid if m.t < now]), total=tot, flag_minutes=flags)
        if d == todo[-1]:
            health["last_frame_age_min"] = round((now - last).total_seconds() / 60, 1) if last else None
            health["camera"] = check_camera(frames, fc)
    logger.info(f"daily totals: {[(str(t['d']), t['val'], t['comment']) for t in totals]}")
    if csv_path and rows:
        write_csv(csv_path, rows)
    if not dry_run and (rows or totals):
        write_db(rows, totals)
    cam = health.get("camera") or {}
    age = health.get("last_frame_age_min")
    warn = []
    if cam.get("moved"):
        warn.append("camera view moved vs reference")
    if age is not None and age > 30 and any(m.t < now for m in grid) and grid and now < grid[-1].t:
        warn.append(f"no new frame for {age} min in daylight")
    health["status"] = "warn" if warn else "ok"
    health["warnings"] = warn
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    health["run_s"], health["max_rss_mb"] = round(time.time() - t_start, 1), rss
    if health_path and not dry_run:
        write_health(health_path, health)
    elif health_path:
        logger.info(f"[dry-run] health: {json.dumps(health, default=str)[:600]}")
    for w in warn:
        logger.warning(w)
    logger.info(f"{'[dry-run] ' if dry_run else ''}{len(rows)} rows, {len(totals)} totals, "
                f"{time.time() - t_start:.1f}s, max RSS {rss} MB")


if __name__ == "__main__":
    main()

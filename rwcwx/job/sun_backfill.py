"""
Backfill webcam sunshine from the 30-minute sky_lg archive (2021-09-09 onwards), PLAN.md section 3.5.

Writes, per local day:
  * obs_inferred rows kind='sunny', source='backfill', minutes=30: one per snapshot, t = start of the
    30-minute period the snapshot stands for (snapshot - 15 min), value 1/0/NULL, flags as the live job;
  * avg_extreme (var='sun', type='total') with the same coverage rule as live, comment
    "estimated from 30-min snapshots; coverage NN%" (the site shows these days as estimated).

Never overwrites: obs_inferred rows whose source is not 'backfill' (live/manual), avg_extreme rows with
overridden=1, or sun totals the live job wrote (comment starting "webcam"). It does replace a weather-API
estimate total ("API estimate ...") when the archive gives a total. Days that have any live rows are
skipped entirely, and by default the run stops before the first live day.

Low impact and resumable:
  * one frame in memory at a time; run it under scripts/run_sun_backfill.sh (flock, nice 19, ionice idle,
    memory cap, timeout);
  * --max-frames caps the work per run (default 2000, ~2-3 min); progress is the last completed day in a
    state file, so each run continues where the last stopped. Writes are idempotent upserts, so a re-run
    of a day is harmless.
  * --dry-run classifies and reports totals but writes nothing (no DB, no state file).

  python rwcwx/job/sun_backfill.py --start 2022-06-01 --end 2022-08-31 --dry-run --csv /tmp/bf.csv
"""
import csv
import gc
import json
import os
import resource
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set

from dateutil import tz
from dateutil.tz import UTC

from rwcwx.job.sun_classify import (FRAMES_DIR, KIND, REPO_ROOT, Classifier, local_day_bounds_utc,  # noqa: E402
                                    sun_times_utc)

import click  # noqa: E402

from rwcwx import logger  # noqa: E402
from rwcwx.sun.rollup import daily_total  # noqa: E402
from rwcwx.sun.rules import GLITCH_PINK, Frame, classify_day, summary  # noqa: E402

ARCHIVE_START = date(2021, 9, 9)
PERIOD_MIN = 30
TOLERANCE_S = 15 * 60
LABEL = "estimated from 30-min snapshots"
STATE_PATH = os.path.join(REPO_ROOT, "out_prod", "sun_backfill_state.json")
# Station time zone (dateutil: prod runs Python 3.8, which has no zoneinfo).
LOCAL_TZ = tz.gettz("America/Los_Angeles")

UPSERT = """
INSERT INTO obs_inferred (t, kind, value, prob, minutes, source, flags, model_version, t_mod)
VALUES (:t, :kind, :value, :prob, :minutes, 'backfill', :flags, :model_version, :t_mod)
ON DUPLICATE KEY UPDATE
  value = IF(source = 'backfill', VALUES(value), value),
  prob = IF(source = 'backfill', VALUES(prob), prob),
  minutes = IF(source = 'backfill', VALUES(minutes), minutes),
  flags = IF(source = 'backfill', VALUES(flags), flags),
  model_version = IF(source = 'backfill', VALUES(model_version), model_version),
  t_mod = IF(source = 'backfill', VALUES(t_mod), t_mod)
"""

# A backfill total may replace an earlier backfill estimate or the weather-API estimate (the webcam archive is
# better evidence), but never an overridden row or a total the live webcam job wrote ("webcam; ...").
KEEP_TOTAL = "(overridden = 1 OR (comment NOT LIKE 'estimated%' AND comment NOT LIKE 'API estimate%'))"
UPSERT_TOTAL = f"""
INSERT INTO avg_extreme (d, var, type, period, val, at, cnt, t_mod, overridden, comment)
VALUES (:d, 'sun', 'total', 'day', :val, NULL, :cnt, :t_mod, 0, :comment)
ON DUPLICATE KEY UPDATE
  val = IF({KEEP_TOTAL}, val, VALUES(val)),
  cnt = IF({KEEP_TOTAL}, cnt, VALUES(cnt)),
  t_mod = IF({KEEP_TOTAL}, t_mod, VALUES(t_mod)),
  comment = IF({KEEP_TOTAL}, comment, VALUES(comment))
"""


def index_archive(frames_dir: str) -> Dict[date, Dict[datetime, str]]:
    """One listdir of the archive, grouped by UTC date of the filename (YYYYMMDD_HHMM.jpg)."""
    by_utc_day: Dict[date, Dict[datetime, str]] = defaultdict(dict)
    with os.scandir(frames_dir) as it:
        for e in it:
            n = e.name
            if not n.endswith(".jpg") or len(n) < 17:
                continue
            try:
                t = datetime.strptime(n[:13], "%Y%m%d_%H%M")
            except ValueError:
                continue
            by_utc_day[t.date()][t] = e.path
    return by_utc_day


def frames_for(index, t0: datetime, t1: datetime) -> Dict[datetime, str]:
    out = {}
    d = t0.date()
    while d <= t1.date():
        for t, p in index.get(d, {}).items():
            if t0 <= t <= t1:
                out[t] = p
        d += timedelta(days=1)
    return out


def classify_backfill_day(day: date, clf: Classifier, index) -> dict:
    sunrise, sunset = sun_times_utc(day)
    frames = frames_for(index, sunrise - timedelta(minutes=PERIOD_MIN), sunset + timedelta(minutes=PERIOD_MIN))
    # The 30-min archive only; if a day also has per-minute frames (recent days), keep the :00/:30 ones.
    frames = {t: p for t, p in frames.items() if t.minute % PERIOD_MIN == 0}
    seq: List[Frame] = []
    snaps = []
    prev_md5 = None
    for t in sorted(frames):
        r = clf.frame(frames[t], t)
        gc.collect()
        if r is None:
            continue
        f = Frame(t=t, p=r["p"], ps=r["ps"], smean=r["smean"], stale=(r["md5"] == prev_md5),
                  glitch=r["pink"] > GLITCH_PINK, pink=r["pink"])
        prev_md5 = r["md5"]
        seq.append(f)
        snaps.append(f)
    grid = classify_day(seq, sunrise, sunset, tolerance_s=TOLERANCE_S)
    by_t = {m.t: m for m in grid}
    rows = []
    for f in snaps:
        m = by_t.get(f.t)
        if m is None:           # snapshot outside daylight
            continue
        rows.append(dict(t=f.t - timedelta(minutes=PERIOD_MIN // 2), kind=KIND, value=m.value,
                         prob=round(f.p, 3), minutes=PERIOD_MIN, flags=",".join(sorted(m.flags)) or None,
                         model_version=clf.version))
    tot = daily_total(grid, label=LABEL)
    return dict(day=day, frames=len(frames), rows=rows, total=tot, summary=summary(grid))


def local_days(ts_utc: Iterable[datetime]) -> Set[date]:
    """Station-local (America/Los_Angeles) dates of naive-UTC timestamps, DST-aware."""
    return {t.replace(tzinfo=UTC).astimezone(LOCAL_TZ).date() for t in ts_utc if t is not None}


def live_days(engine) -> set:
    """Local days that have any live rows. Converted in Python: prod MySQL has no time-zone tables, so
    CONVERT_TZ returns NULL there (the old 'UTC date and the day before' fallback wrongly skipped 2026-10-10).
    Rows are bucketed by UTC hour first; LA offsets are whole hours, so each bucket has one local date."""
    from sqlalchemy import text
    with engine.connect() as c:
        res = c.execute(text("SELECT DISTINCT DATE(t), HOUR(t) FROM obs_inferred "
                             "WHERE kind = :k AND source = 'live'"), k=KIND)
        return local_days(datetime.combine(d, datetime.min.time()) + timedelta(hours=h)
                          for d, h in res if d is not None)


def write_day(engine, res: dict, now: datetime) -> None:
    from sqlalchemy import text
    with engine.begin() as c:
        if res["rows"]:
            c.execute(text(UPSERT), [dict(r, t_mod=now) for r in res["rows"]])
        if res["total"]:
            t = res["total"]
            c.execute(text(UPSERT_TOTAL), dict(d=res["day"], val=t["val"], cnt=t["cnt"], comment=t["comment"],
                                               t_mod=now))


def load_state(path: str) -> dict:
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(path: str, state: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(state, fh, indent=1, default=str)
    os.replace(tmp, path)


@click.command()
@click.option("--start", default=None, help="First local day YYYY-MM-DD (default: day after the state file's last "
              f"completed day, else {ARCHIVE_START})")
@click.option("--end", default=None, help="Last local day (default: the day before the first live day, else yesterday)")
@click.option("--max-frames", type=int, default=2000, show_default=True, help="Stop after the day that crosses this")
@click.option("--frames-dir", default=FRAMES_DIR, show_default=True)
@click.option("--state", "state_path", default=STATE_PATH, show_default=True)
@click.option("--dry-run", is_flag=True, help="Classify and report only: no DB, no state file")
@click.option("--csv", "csv_path", default=None, help="Write per-day totals to this CSV")
def main(start, end, max_frames, frames_dir, state_path, dry_run, csv_path):
    t_start = time.time()
    state = {} if dry_run else load_state(state_path)
    engine = None
    if not dry_run:
        from sqlalchemy import create_engine
        engine = create_engine(f"mysql://{os.environ['MYSQL_URL']}", pool_pre_ping=True)
    skip = live_days(engine) if engine is not None else set()

    if start:
        d0 = datetime.strptime(start, "%Y-%m-%d").date()
    elif state.get("last_day"):
        d0 = datetime.strptime(state["last_day"], "%Y-%m-%d").date() + timedelta(days=1)
    else:
        d0 = ARCHIVE_START
    if end:
        d1 = datetime.strptime(end, "%Y-%m-%d").date()
    else:
        d1 = (min(skip) - timedelta(days=1)) if skip else date.today() - timedelta(days=1)

    t_idx = time.time()
    index = index_archive(frames_dir)
    logger.info(f"archive index: {sum(len(v) for v in index.values())} frames in {time.time() - t_idx:.1f}s; "
                f"days {d0} .. {d1}{' (dry run)' if dry_run else ''}")
    clf = Classifier()
    out = []
    n_frames = 0
    d = d0
    while d <= d1 and n_frames < max_frames:
        if d in skip:
            logger.info(f"{d}: has live rows, skipped")
        else:
            t_day = time.time()
            res = classify_backfill_day(d, clf, index)
            n_frames += res["frames"]
            if engine is not None:
                write_day(engine, res, datetime.utcnow().replace(microsecond=0))
            tot = res["total"]
            out.append(dict(day=d.isoformat(), frames=res["frames"], rows=len(res["rows"]),
                            hours=tot["val"] if tot else None, coverage=res["summary"]["coverage"],
                            daylight_h=round(res["summary"]["daylight_min"] / 60, 2),
                            comment=tot["comment"] if tot else "no total (coverage < 50%)",
                            secs=round(time.time() - t_day, 2)))
            logger.info(f"{d}: {res['frames']} frames, {out[-1]['hours']} h, cov {res['summary']['coverage']:.0%}")
        if not dry_run:
            state.update(last_day=d.isoformat(), t=datetime.utcnow().isoformat() + "Z")
            save_state(state_path, state)
        d += timedelta(days=1)

    if csv_path and out:
        with open(csv_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
    el = time.time() - t_start
    with_total = [o for o in out if o["hours"] is not None]
    logger.info(f"{'[dry-run] ' if dry_run else ''}{len(out)} days, {n_frames} frames, {len(with_total)} totals, "
                f"{sum(o['rows'] for o in out)} rows, {el:.1f}s ({1000 * el / max(n_frames, 1):.0f} ms/frame), "
                f"max RSS {rss} MB; next start {d}")
    if engine is not None:
        engine.dispose()


if __name__ == "__main__":
    main()

"""
Backfill derived wet minutes (obs.wet) and daily wet hours (avg_extreme var='wet', type='total') from obs.rain.

Rules in rwcwx/wet/rules.py (30 min window, lone tip = 30 min, tips after data gaps unknown). Idempotent: a re-run
recomputes the same flags; only obs rows whose flag changes are written, and avg_extreme rows with overridden=1 keep
their value. --dry-run computes and reports, writing nothing.

  python rwcwx/job/wet_backfill.py --start 2020-12-21 --end 2026-10-12 --dry-run --csv /tmp/wet.csv
"""
import csv
import os
import time
from datetime import date, datetime, timedelta

import click

os.environ["TZ"] = "UTC"
time.tzset()

from rwcwx import logger  # noqa: E402
from rwcwx.wet import store  # noqa: E402


@click.command()
@click.option("--start", required=True, type=click.DateTime(["%Y-%m-%d"]))
@click.option("--end", default=None, type=click.DateTime(["%Y-%m-%d"]), help="Inclusive; default yesterday")
@click.option("--dry-run", is_flag=True)
@click.option("--csv", "csv_path", default=None, help="Write one row per day")
@click.option("--sleep", default=0.0, help="Seconds between days (go easy on prod)")
def main(start: datetime, end: datetime, dry_run: bool, csv_path: str, sleep: float) -> None:
    d, last = start.date(), (end.date() if end else date.today() - timedelta(days=1))
    out = csv.writer(open(csv_path, "w")) if csv_path else None
    if out:
        out.writerow(["d", "wet_h", "spells", "lone", "longest_h", "rain", "unknown_tips", "observed_h", "rows_changed"])
    tot_h = tot_rows = days = 0
    while d <= last:
        wd, times, flags = store.compute_day(d)
        changed = 0 if dry_run or not times else store.write_day(d, wd, times, flags)
        s = wd.summary()
        if out:
            out.writerow([d, s["wet_h"], s["spells"], sum(x["lone"] for x in s["spell_list"]), s["longest_h"], s["rain"],
                          s["unknown_tips"], s["observed_h"], changed])
        tot_h += wd.wet_min / 60
        tot_rows += changed
        days += 1
        if d.day == 1:
            logger.info(f"{d}: running total {tot_h:.0f} wet h over {days} days")
        d += timedelta(days=1)
        if sleep:
            time.sleep(sleep)
    logger.info(f"{'DRY RUN ' if dry_run else ''}done: {days} days, {tot_h:.1f} wet hours, {tot_rows} obs rows changed")


if __name__ == "__main__":
    main()

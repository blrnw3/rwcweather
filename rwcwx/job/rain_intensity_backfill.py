"""
Backfill daily max 10 / 60-minute rain (avg_extreme var 'rain10' / 'rain60', type 'max', at = time reached) from
obs.rain tips. Needs data/migrations/20261014_avg_extreme_rain10_rain60.sql applied first. Idempotent upserts;
rows with overridden=1 keep their values. --dry-run computes and reports, writing nothing.

  python rwcwx/job/rain_intensity_backfill.py --start 2020-12-21 --end 2026-10-13 --dry-run --csv /tmp/ri.csv
"""
import csv
import os
import time
from datetime import date, datetime, timedelta

import click

os.environ["TZ"] = "UTC"
time.tzset()

from rwcwx import logger  # noqa: E402
from rwcwx.wet import intensity_store  # noqa: E402


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
        out.writerow(["d", "rain10", "rain10_at_utc", "rain60", "rain60_at_utc", "n_obs"])
    days = written = 0
    while d <= last:
        res, n = intensity_store.compute_day(d)
        if not dry_run and n:
            intensity_store.write_day(d, res, n)
            written += 1
        if out:
            out.writerow([d, res["rain10"][0], res["rain10"][1] or "", res["rain60"][0], res["rain60"][1] or "", n])
        days += 1
        d += timedelta(days=1)
        if sleep:
            time.sleep(sleep)
    logger.info(f"{'DRY RUN ' if dry_run else ''}done: {days} days, {written} days written")


if __name__ == "__main__":
    main()

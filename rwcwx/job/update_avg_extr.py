"""
Batch (re)computation of daily average/extremes
"""

import os
import time
from datetime import datetime, timedelta

import click

from rwcwx import logger
from rwcwx.job.save_latest import CumulusObsImporter
from rwcwx.util import DateStampConverter

os.environ["TZ"] = "UTC"
time.tzset()


@click.command()
@click.option("-s", "--datestamp-start", required=True)
@click.option("-e", "--datestamp-end", default="")
def main(datestamp_start: str, datestamp_end: str) -> None:
    # TODO: don't override already overridden entries
    d_start = datetime.strptime(datestamp_start, DateStampConverter.FMAT)
    d_end = datetime.strptime(datestamp_end, DateStampConverter.FMAT) if datestamp_end else d_start
    d = d_start
    while d <= d_end:
        logger.info(f"Processing {d}")
        CumulusObsImporter.update_avg_ext(d)
        d += timedelta(days=1)


if __name__ == "__main__":
    main()

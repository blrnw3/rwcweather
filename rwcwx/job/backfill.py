"""
Backfill the obs table with optional value interpolation
e.g. backfill -s 20230129-2059 -e 20230129-2359 --obs="temp:6.9_6,wind:1,gust:1,wdir:0,humi:80,pres:1013,pm2:4,rain:0.02"
"""

from datetime import datetime, timedelta

import click
from dateutil import tz
from sqlalchemy.dialects.mysql import insert

from rwcwx import logger
from rwcwx.config import TZ
from rwcwx.models import db, m
from rwcwx.util import DatetimeConverter


# os.environ["TZ"] = "UTC"
# time.tzset()


def create_entry(d: datetime, obs: dict) -> None:
    save_obs = insert(m.obs).values(
        **obs
    ).on_duplicate_key_update(
        **obs,
        t_mod=datetime.utcnow()
    )
    logger.info(f"Inputting data at time {d} (record: {obs})")
    db.execute(save_obs)


def parse_obs_str(obs_str: str) -> dict:
    obs_split = obs_str.split(",")
    obs = {}
    for ob in obs_split:
        name, valstr = ob.split(":")
        if "_" in valstr:
            v1, v2 = valstr.split("_")
        else:
            v1, v2 = valstr, valstr
        obs[name] = (float(v1), float(v2))
    return obs


@click.command()
@click.option("-s", "--datetime-start", required=True)
@click.option("-e", "--datetime-end", default="")
@click.option("-o", "--obs-raw", required=True)
@click.option("--wet", is_flag=True)
def main(datetime_start: str, datetime_end: str, obs_raw: str, wet: bool) -> None:
    d_start = datetime.strptime(datetime_start, DatetimeConverter.FMAT).replace(tzinfo=TZ)
    d_end = datetime.strptime(datetime_end, DatetimeConverter.FMAT).replace(tzinfo=TZ) if datetime_end else d_start
    duration = (d_end - d_start).total_seconds() / 60
    obs = parse_obs_str(obs_raw)
    d = d_start

    print(f"Range: {datetime_start} -> {datetime_end} ({duration} mins)")
    print("Parsed obs input:")
    print(obs)
    if not wet:
        print("DRY RUN. Pass --wet to proceed")
        return

    i = 0
    while d <= d_end:
        obs_now = dict(
            t=d.astimezone(tz.UTC),
            src="backfill",
            t_obs=d.astimezone(tz.UTC)
        )
        for o, (v1, v2) in obs.items():
            obs_now[o] = v1 + (((v2 - v1) / duration) * i)
        create_entry(d, obs_now)
        d += timedelta(minutes=1)
        i += 1


if __name__ == "__main__":
    main()

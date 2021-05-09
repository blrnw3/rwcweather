from datetime import date, datetime
from typing import Any, Dict, List, Union

from dateutil.tz import UTC
from flask import request

from rwcwx.calc.avg_extreme import DaySummary
from rwcwx.config import TZ
from rwcwx.model.obs import ObsQ
from rwcwx.models import db, m, Obs
from rwcwx.util import DateUtil


def todo():
    return "API docs TODO"


def lol():
    return {"lol": 42}


def current():
    q = ObsQ.latest(1)[0]
    # t = q.t_obs.replace(tzinfo=UTC).astimezone(TZ)
    return _wrap_result(
        q.dict_,
        # t_obs_pretty_date=t.strftime("%A %d %B %Y"),
        # t_obs_pretty_time=t.strftime("%H:%M:%S %Z")
    )


def dashboard():
    """
    Amalgamates all useful data for a live dashboard to reduce number of http calls
    """
    return _wrap_result(
        dict(
            now=ObsQ.latest(1)[0],
            trends=ObsQ.trend([10, 60, 1440]),
            today=DaySummary(DateUtil.now().date()).stats_json(),
            # yesterday=DaySummary(DateUtil.yesterday().date()).stats_json(),
            last_rain=ObsQ.last_rain()
        )
    )


def day_summary(d: date = None):
    summary = DaySummary(d)
    return _wrap_result(
        summary.stats_json(),
        date=summary.day
    )


def obs_latest():
    mins = int(request.args.get("d", "60"))
    assert 1 < mins <= 1500
    return _wrap_result(
        ObsQ.latest(mins),
        duration=mins
    )


def trend_live():
    periods_raw = request.args.get("p", "60")
    try:
        periods = [int(p) for p in periods_raw.split(",")]
    except ValueError:
        return {
            "error": "Misformatted periods. Must be ints"
        }
    return _wrap_result(
        ObsQ.trend(periods),
        periods=periods
    )


def _wrap_result(res, **extras) -> dict:
    return {
        "result": _dictify_obs_result(res),
        "server": dict(
            datetime=DateUtil.now(),
            epoch=DateUtil.now().timestamp(),
            localtime=DateUtil.now_local_string()
        ),
        **extras
    }


def _dictify_obs_result(res):
    if isinstance(res, dict):
        return {k: _dictify_obs_result(v) for k, v in res.items()}
    elif isinstance(res, list):
        return [_dictify_obs_result(o) for o in res]
    elif isinstance(res, Obs):
        return res.dict_
    return res

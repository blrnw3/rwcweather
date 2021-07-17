from datetime import date, datetime
from typing import Any, Dict, List, Union

from dateutil.tz import UTC
from flask import request

from rwcwx.astronomy import get_all_times_rwc, getTimes
from rwcwx.calc.avg_extreme import MonthSummary, ObsVarMatrix, DaySummary, YearSummary
from rwcwx.config import TZ
from rwcwx.model.avgext import AvgExtQ
from rwcwx.model.obs import ObsQ
from rwcwx.models import Base, db, m, Obs
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


def dashboard_live():
    """
    Amalgamates all useful data for a live dashboard to reduce number of http calls
    """
    return _wrap_result(
        dict(
            now=ObsQ.latest(1)[0],
            trends=ObsQ.trend([10, 60, 1440]),
            today=DaySummary(DateUtil.now().date()).stats_json(),
            last_rain=ObsQ.last_rain(),
        )
    )


def dashboard_summary():
    """
    Amalgamates all useful data for a live dashboard to reduce number of http calls
    """
    return _wrap_result(
        dict(
            yesterday=DaySummary(DateUtil.yesterday().date()).stats_json(),
            month=MonthSummary.for_this_month().stats(),
            year=YearSummary.for_this_year().stats(),
            astronomy=get_all_times_rwc(),
        )
    )


def day_summary(d: date = None):
    summary = DaySummary(d)
    return _wrap_result(
        summary.stats_json(),
        date=summary.day
    )


def month_summary(mnth: date = None):
    summary = MonthSummary(mnth)
    return _wrap_result(
        summary.stats(),
        date=summary.month,
        month=summary.month.month,
        year=summary.month.year
    )


def year_summary(yr: int = None):
    summary = YearSummary(yr)
    return _wrap_result(
        summary.stats(),
        year=summary.year
    )


def avg_extreme(var: str, typ: str):
    return _wrap_result(ObsVarMatrix(var, typ).daily())


def obs_var_summary_month(var: str, typ: str):
    return _wrap_result(ObsVarMatrix(var, typ).monthly())


def obs_var_matrix(var: str, typ: str):
    return _wrap_result(ObsVarMatrix(var, typ).all_summaries())


def obs_latest():
    mins = int(request.args.get("d", "60"))
    assert 1 < mins <= 10080
    return _wrap_result(
        ObsQ.latest(mins),
        duration=mins
    )


def astronomy():
    times = get_all_times_rwc()
    return _wrap_result(times)


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
    elif isinstance(res, Base):
        return res.dict_
    return res

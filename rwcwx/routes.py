from datetime import date

from flask import request

from rwcwx.calc.avg_extreme import DaySummary
from rwcwx.model.obs import ObsQ
from rwcwx.models import db, m, Obs
from rwcwx.util import DateUtil


def todo():
    return "API docs TODO"


def lol():
    return {"lol": 42}


def current():
    q = db.s.query(Obs).order_by(Obs.t.desc())[0]
    return _wrap_result(
        q.json_
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
        [o.json_ for o in ObsQ.latest(mins)],
        duration=mins
    )


def _wrap_result(res, **extras) -> dict:
    return {
        "result": res,
        "server": dict(
            datetime=DateUtil.now(),
            epoch=DateUtil.now().timestamp()
        ),
        **extras
    }



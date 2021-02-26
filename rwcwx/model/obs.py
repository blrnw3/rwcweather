from datetime import datetime, timedelta, date
from typing import List

from dateutil.tz import UTC

from rwcwx.config import TZ
from rwcwx.models import db, Obs
from rwcwx.util import DateUtil


class ObsQ:

    @staticmethod
    def day(d: date) -> List[Obs]:
        st = datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(UTC)
        en = st + timedelta(days=1)
        q = db.s.query(Obs).filter(Obs.t.between(st, en))
        return q.order_by(Obs.t.asc()).all()

    @staticmethod
    def latest(mins: int) -> List[Obs]:
        st = DateUtil.utc_now() - timedelta(minutes=mins)
        q = db.s.query(Obs).filter(Obs.t >= st)
        return q.order_by(Obs.t.desc()).all()


"""
select * FROM obs WHERE obs.t >= %s ORDER BY obs.t DESC
"""
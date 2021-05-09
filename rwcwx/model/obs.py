from datetime import datetime, timedelta, date
from typing import Dict, List

from dateutil.tz import UTC
from sqlalchemy import text

from rwcwx.config import TZ
from rwcwx.models import db, Obs
from rwcwx.util import DateUtil


class ObsQ:

    @staticmethod
    def day(d: date) -> List[Obs]:
        """ All records for a given day """
        st = datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(UTC)
        en = st + timedelta(days=1)
        q = db.s.query(Obs).filter(Obs.t.between(st, en))
        return q.order_by(Obs.t.asc()).all()

    @staticmethod
    def latest(mins: int) -> List[Obs]:
        """ Most recent :mins: records, most recent first """
        return db.s.query(Obs).order_by(Obs.t.desc())[:mins]

    @staticmethod
    def trend(periods: List[int]) -> Dict[int, Obs]:
        """
        Get all records for the specific :periods:, each representing the obs from n records ago
        NB: To avoid nulls and preserve data during downtime, the periods are not computed using n-mins ago logic,
        so if there are gaps in the data, trends won't be exactly n mins ago.
        Either logic has its trade-offs but should operate the same in normal times
        """
        base_query = "(select * from obs order by t desc limit 1)"
        trend_queries = [f"(select * from obs order by t desc limit {int(p)}, 1)" for p in periods]
        full_query = " UNION ".join([base_query] + trend_queries)
        trend_result = db.s.query(Obs).from_statement(text(full_query)).all()

        return dict(zip([0] + periods, trend_result))

    @staticmethod
    def last_rain() -> datetime:
        return db.s.query(Obs).filter(Obs.rain > 0).order_by(Obs.t.desc())[0].t

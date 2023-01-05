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
    def latest(mins: int, optimized=False) -> List[Obs]:
        """
        Most recent :mins: records, most recent first
        Caps the oldest data
        """
        if mins >= 60:
            st = DateUtil.utc_now() - timedelta(minutes=mins * 1.05)  # Get slightly more data
            q = db.s.query(Obs).filter(Obs.t > st).order_by(Obs.t.desc())
            if optimized and mins > 720:
                # Get every nth record for efficiency
                nth = min(max(round(mins / 2000), 2), 15)
                nth_filter = text(f"(unix_timestamp(t) / 60) % {nth} = 0")
                q = q.filter(nth_filter)
            q = q.all()
        else:
            q = db.s.query(Obs).order_by(Obs.t.desc())[:mins]
        return q

    @staticmethod
    def trend(periods: List[int], var: str = None) -> Dict[int, Obs]:
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
        q = """
         select t, diff
          from (
            select t, rain, (rain - lag(rain) over w) as diff
            from obs
            where t > '2023-01-03' and rain > 0
            window w as (order by t)
            ) x
            where diff != 0
            order by t desc
            limit 1
         """
        if "test" in db._database_url:
            # TODO: update test mysql to support window fns
            q = "select t from obs where rain > 0 order by t desc limit 1"
        return db.s.execute(q).fetchone()[0]

    @staticmethod
    def rain_last_n_mins(mins: int) -> float:
        st = DateUtil.utc_now() - timedelta(minutes=mins)
        return sum((o.rain for o in db.s.query(Obs.rain).filter(Obs.t > st).all()))

    @staticmethod
    def rain_24hrs() -> float:
        now = DateUtil.utc_now().replace(second=0, microsecond=0)
        day_ago = now - timedelta(hours=24)
        yest_end = DateUtil.yesterday().replace(hour=23, minute=59, second=0, microsecond=0)
        amounts = db.s.query(Obs).filter(Obs.t.in_((day_ago, yest_end, now))).order_by(Obs.t.desc()).all()
        # return amounts
        try:
            return amounts[0].rain + amounts[1].rain - amounts[2].rain
        except IndexError:
            return None

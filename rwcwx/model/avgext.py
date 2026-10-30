from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Dict, List, Tuple

from dateutil.tz import UTC
from sqlalchemy import text
from sqlalchemy.sql import func

from rwcwx.config import TZ
from rwcwx.models import db, AvgExt
from rwcwx.util import DateUtil


class AvgExtQ:

    @staticmethod
    def for_var_between_dates(var: str, typ: str, start_date: date = None, end_date: date = None) -> List[AvgExt]:
        q = db.s.query(AvgExt).filter(AvgExt.var == var).filter(AvgExt.type == typ)
        if start_date:
            q = q.filter(AvgExt.d >= start_date)
        if end_date:
            q = q.filter(AvgExt.d <= end_date)
        return q.order_by(AvgExt.d.desc(), AvgExt.type.asc()).all()

    @staticmethod
    def daily_values(var: str, typ: str) -> List[Tuple[date, float]]:
        """(date, value) for every day of one variable/statistic; served by the var_type_d index."""
        q = (db.s.query(AvgExt.d, AvgExt.val)
             .filter(AvgExt.var == var).filter(AvgExt.type == typ).filter(AvgExt.period == "day"))
        return [(d, v) for d, v in q.order_by(AvgExt.d.asc()).all()]

    @staticmethod
    def daily_rows(var: str, typ: str) -> list:
        """Rows with .d .val .comment for every day of one variable/statistic (inputs of derived daily values)."""
        q = (db.s.query(AvgExt.d, AvgExt.val, AvgExt.comment)
             .filter(AvgExt.var == var).filter(AvgExt.type == typ).filter(AvgExt.period == "day"))
        return q.order_by(AvgExt.d.asc()).all()

    @staticmethod
    def for_var_and_year(var: str, typ: str, year: int) -> List[AvgExt]:
        start_date, end_date = DateUtil.year_start_end_dates(year)
        q = (db.s.query(AvgExt).filter(AvgExt.var == var).filter(AvgExt.type == typ)
             .filter(AvgExt.d >= start_date).filter(AvgExt.d <= end_date))
        return q.order_by(AvgExt.d.desc(), AvgExt.type.asc()).all()

    @staticmethod
    def all_for_month(month: date) -> List[AvgExt]:
        start_date = month.replace(day=1)
        end_date = DateUtil.last_date_of_month(month)
        return AvgExtQ._light_between(start_date, end_date)

    # Summary tables only read these columns. Selecting them as plain rows instead of hydrating
    # full AvgExt ORM objects is several times faster for a year's ~11k rows.
    _LIGHT_COLS = (AvgExt.d, AvgExt.var, AvgExt.type, AvgExt.period, AvgExt.val, AvgExt.cnt, AvgExt.comment)

    @staticmethod
    def _light_between(start_date: date, end_date: date) -> list:
        """Rows with .d .var .type .period .val .cnt .comment (read-only, not ORM objects)."""
        q = db.s.query(*AvgExtQ._LIGHT_COLS).filter(AvgExt.d >= start_date).filter(AvgExt.d <= end_date)
        return q.all()

    @staticmethod
    def all_for_day_of_year(month: int, day: int, exclude_date: date = None) -> List[AvgExt]:
        q = (db.s.query(AvgExt)
             .filter(func.month(AvgExt.d) == month)
             .filter(func.day(AvgExt.d) == day)
             .filter(AvgExt.period == "day"))
        if exclude_date:
            q = q.filter(AvgExt.d != exclude_date)
        return q.order_by(AvgExt.d.desc()).all()

    @staticmethod
    def all_for_year(year: int) -> List[AvgExt]:
        start_date, end_date = DateUtil.year_start_end_dates(year)
        return AvgExtQ._light_between(start_date, end_date)

    @staticmethod
    def rain_for_water_year(year: int) -> List[AvgExt]:
        start_date, end_date = DateUtil.water_year_start_end_dates(year)
        q = db.s.query(AvgExt).filter(AvgExt.d >= start_date).filter(AvgExt.d <= end_date).filter(AvgExt.var.in_(("rain", "wet")))
        return q.all()

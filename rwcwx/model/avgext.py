from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Dict, List

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
    def for_var_and_year(var: str, typ: str, year: int) -> List[AvgExt]:
        start_date, end_date = DateUtil.year_start_end_dates(year)
        q = (db.s.query(AvgExt).filter(AvgExt.var == var).filter(AvgExt.type == typ)
             .filter(AvgExt.d >= start_date).filter(AvgExt.d <= end_date))
        return q.order_by(AvgExt.d.desc(), AvgExt.type.asc()).all()

    @staticmethod
    def all_for_month(month: date) -> List[AvgExt]:
        start_date = month.replace(day=1)
        end_date = DateUtil.last_date_of_month(month)
        q = db.s.query(AvgExt).filter(AvgExt.d >= start_date).filter(AvgExt.d <= end_date)
        return q.all()

    @staticmethod
    def all_for_year(year: int) -> List[AvgExt]:
        start_date, end_date = DateUtil.year_start_end_dates(year)
        q = db.s.query(AvgExt).filter(AvgExt.d >= start_date).filter(AvgExt.d <= end_date)
        return q.all()

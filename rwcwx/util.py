from calendar import monthrange
from datetime import datetime, timedelta, date
from typing import List

from dateutil.tz import UTC
from werkzeug.routing import BaseConverter

from rwcwx.config import TZ


class DateUtil:

    @staticmethod
    def now() -> datetime:
        return datetime.now(TZ)

    @staticmethod
    def now_local_string() -> str:
        return datetime.now(TZ).isoformat()

    @staticmethod
    def utc_now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def yesterday() -> datetime:
        return datetime.now(TZ) - timedelta(days=1)

    @staticmethod
    def last_date_of_month(month: date) -> date:
        return month.replace(day=monthrange(month.year, month.month)[1])


class DateStampConverter(BaseConverter):
    FMAT = "%Y%m%d"

    def to_python(self, value: str) -> date:
        return datetime.strptime(value, self.FMAT)

    def to_url(self, value: date) -> str:
        return value.strftime(self.FMAT)
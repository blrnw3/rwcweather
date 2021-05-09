from datetime import datetime, timedelta, date
from typing import List

from dateutil.tz import UTC

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

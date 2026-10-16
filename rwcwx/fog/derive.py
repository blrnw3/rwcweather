"""Fog days, derived at query time from the stored daily fog hours (avg_extreme var='fog'): 1 if fog hours > 0."""
from typing import Iterable, List, Tuple

from rwcwx.model.sun import DerivedDay

DAY_VAR, DAY_TYPE = "fogday", "total"


def fog_days(fog_avg_exts) -> List[DerivedDay]:
    return [DerivedDay(d=ae.d, val=1 if (ae.val or 0) > 0 else 0, hours=ae.val, cnt=ae.cnt, comment=ae.comment)
            for ae in fog_avg_exts]


def fog_day_values(values: Iterable[Tuple]) -> List[Tuple]:
    return [(d, 1 if (v or 0) > 0 else 0) for d, v in values]

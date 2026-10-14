"""Average rain rate when wet = daily rain / daily wet hours (in. per hour), derived at query time.

API var "wetrate", type "avg". Days without wet hours have no rate (left out, shown blank). Periods (months, years,
water years) use total rain / total wet hours, i.e. the wet-hours-weighted mean of the daily rates.
"""
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

RATE_VAR, RATE_TYPE = "wetrate", "avg"


@dataclass
class RateDay:
    """Duck-types the parts of AvgExt the aggregators use (d, val, at, dict_, simple_dict_)."""
    d: date
    val: float
    rain: float
    wet_h: float
    cnt: Optional[int] = None
    at = None
    comment = None

    @property
    def dict_(self) -> dict:
        return dict(d=(self.d.year, self.d.month, self.d.day), val=self.val, rain=self.rain, wet_h=self.wet_h,
                    var=RATE_VAR, type=RATE_TYPE)

    @property
    def simple_dict_(self) -> dict:
        # w = weight (wet hours): the client weights water-year means by it so they equal rain / wet hours
        return dict(d=(self.d.year, self.d.month, self.d.day), val=self.val, w=self.wet_h)


def rate(rain: Optional[float], wet_h: Optional[float]) -> Optional[float]:
    if rain is None or not wet_h or wet_h <= 0:
        return None
    return round(rain / wet_h, 4)


def rate_days(rain_aes: Iterable, wet_aes: Iterable) -> List[RateDay]:
    """rain/total and wet/total rows -> one RateDay per day with wet hours (newest first, like the queries)."""
    rain = {ae.d: ae.val for ae in rain_aes}
    out = []
    for ae in wet_aes:
        r = rate(rain.get(ae.d), ae.val)
        if r is not None:
            out.append(RateDay(d=ae.d, val=r, rain=rain[ae.d], wet_h=ae.val, cnt=ae.cnt))
    return sorted(out, key=lambda x: x.d, reverse=True)


def period_rate(days: List) -> Optional[float]:
    return rate(sum(x.rain for x in days), sum(x.wet_h for x in days))

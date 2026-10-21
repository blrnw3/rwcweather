"""Daily variables derived at query time from the stored daily rows (avg_extreme), never stored themselves.

  temprange / humirange / presrange / dewptrange   daily max - daily min of temp, humi, pres, dewpt (type "avg";
                                                    periods average the daily ranges)
  et0                                               reference evapotranspiration, mm/day (type "total"; periods sum
                                                    it), FAO-56 Penman-Monteith or Hargreaves-Samani (rwcwx.calc.et0)

The inputs are the same local-day rows as every other daily value, so day boundaries match. avg_extreme's var
column is an enum, and each value is a cheap function of a handful of daily rows, so nothing is stored or backfilled.

ET0 uses Penman-Monteith when the day has webcam sunshine with at least MIN_SUN_COVERAGE of daylight classified
(sun rows from the API estimate backfill do not count), plus the daily mean wind and a dew point (or RH max/min);
otherwise Hargreaves-Samani. Each ET0 day carries its method ("pm" / "hs"). Today is left out of ET0: its sunshine
and temperature extremes are still partial.
"""
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from rwcwx.calc import et0 as et0_mod

RANGE_VARS: Dict[str, str] = {"temprange": "temp", "humirange": "humi", "presrange": "pres", "dewptrange": "dewpt"}
RANGE_TYPE = "avg"
ET0_VAR, ET0_TYPE = "et0", "total"
DERIVED: Dict[str, str] = {**{v: RANGE_TYPE for v in RANGE_VARS}, ET0_VAR: ET0_TYPE}

MIN_SUN_COVERAGE = 0.75
ET0_INPUTS: Tuple[Tuple[str, str], ...] = (("temp", "max"), ("temp", "min"), ("dewpt", "avg"), ("humi", "max"),
                                          ("humi", "min"), ("wind", "avg"), ("sun", "total"))


def is_derived(var: str, typ: Optional[str] = None) -> bool:
    return var in DERIVED and (typ is None or DERIVED[var] == typ)


def inputs_for(var: str) -> Tuple[Tuple[str, str], ...]:
    if var in RANGE_VARS:
        return (RANGE_VARS[var], "max"), (RANGE_VARS[var], "min")
    return ET0_INPUTS


@dataclass
class DerivedDay:
    """Duck-types the parts of AvgExt the aggregators use (d, val, at, dict_, simple_dict_)."""
    d: date
    val: float
    var: str
    type: str
    method: Optional[str] = None      # ET0 only: "pm" (Penman-Monteith) or "hs" (Hargreaves-Samani)
    at = None
    cnt = None
    comment = None

    @property
    def simple_dict_(self) -> dict:
        out = dict(d=(self.d.year, self.d.month, self.d.day), val=self.val)
        if self.method:
            out["method"] = self.method
        return out

    @property
    def dict_(self) -> dict:
        return dict(self.simple_dict_, var=self.var, type=self.type)


def sun_usable(comment: Optional[str]) -> bool:
    """Webcam sunshine with enough of daylight classified; API estimates and low-coverage days are not used."""
    if not comment or comment.startswith("estimated") or comment.startswith("API estimate"):
        return False
    m = re.search(r"coverage ([\d.]+)%", comment)
    return m is None or float(m.group(1)) / 100 >= MIN_SUN_COVERAGE


def _by_day(rows) -> Dict[date, object]:
    return {r.d: r for r in rows if r is not None and r.val is not None}


def range_days(maxes, mins, var: str) -> List[DerivedDay]:
    lo = _by_day(mins)
    out = []
    for d, hi in sorted(_by_day(maxes).items()):
        if d in lo:
            out.append(DerivedDay(d=d, val=round(hi.val - lo[d].val, 3), var=var, type=RANGE_TYPE))
    return out


def et0_days(series: Dict[Tuple[str, str], Iterable], today: Optional[date] = None,
             wind_factor: float = et0_mod.WIND_TO_U2) -> List[DerivedDay]:
    """series: {(var, type): AvgExt-like rows}; -> one DerivedDay per day with a daily max and min temperature."""
    s = {k: _by_day(series.get(k, [])) for k in ET0_INPUTS}
    tmax, tmin = s[("temp", "max")], s[("temp", "min")]
    out = []
    for d in sorted(tmax):
        if d not in tmin or (today is not None and d >= today):
            continue
        val = lambda k: s[k][d].val if d in s[k] else None   # noqa: E731
        sun = s[("sun", "total")].get(d)
        sun_h = sun.val if sun is not None and sun_usable(getattr(sun, "comment", None)) else None
        res = et0_mod.daily_et0(d, tmax[d].val, tmin[d].val, dewpt=val(("dewpt", "avg")),
                                rh_max=val(("humi", "max")), rh_min=val(("humi", "min")),
                                wind_mph=val(("wind", "avg")), sun_h=sun_h, wind_factor=wind_factor)
        if res is not None:
            out.append(DerivedDay(d=d, val=res[0], var=ET0_VAR, type=ET0_TYPE, method=res[1]))
    return out


def derive(var: str, fetch: Callable[[str, str], Iterable], today: Optional[date] = None) -> List[DerivedDay]:
    """fetch(var, type) -> that input's daily rows (any date window); -> the derived days in the same window."""
    if var in RANGE_VARS:
        return range_days(fetch(RANGE_VARS[var], "max"), fetch(RANGE_VARS[var], "min"), var)
    if var == ET0_VAR:
        return et0_days({k: fetch(*k) for k in ET0_INPUTS}, today)
    raise ValueError(f"not a derived variable: {var}")


def add_to_summary(stats: dict, by_type: Dict[Tuple[str, str], list], summarise: Callable[[list], dict],
                   today: Optional[date] = None) -> None:
    """Month / year / day-of-year summaries: add "<var>_<type>" for each derived variable with data."""
    for var in DERIVED:
        days = derive(var, lambda v, t: by_type.get((v, t), []), today)
        if days:
            stats[f"{var}_{DERIVED[var]}"] = summarise(days)
            if var == ET0_VAR:
                stats[f"{var}_{DERIVED[var]}"]["methods"] = method_counts(days)


def method_counts(days: Iterable[DerivedDay]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for x in days:
        if x.method:
            counts[x.method] += 1
    return dict(counts)

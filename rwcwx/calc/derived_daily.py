"""Daily variables derived at query time from the stored daily rows (avg_extreme), never stored themselves.

  temprange / humirange / presrange / dewptrange   daily max - daily min of temp, humi, pres, dewpt (type "avg";
                                                    periods average the daily ranges)
  et0                                               reference evapotranspiration, mm/day (type "total"; periods sum
                                                    it), FAO-56 Penman-Monteith or Hargreaves-Samani (rwcwx.calc.et0)

The inputs are the same local-day rows as every other daily value, so day boundaries match. avg_extreme's var
column is an enum, and each value is a cheap function of a handful of daily rows, so nothing is stored or backfilled.

ET0 uses Penman-Monteith when the day has webcam sunshine with at least MIN_SUN_COVERAGE of daylight classified
(live or from the 30-min archive snapshots; totals from the weather-API estimate do not count), plus the daily mean
wind and a dew point (or RH max/min);
otherwise Hargreaves-Samani. Each ET0 day carries its method ("pm" / "hs"). Today is left out of ET0: its sunshine
and temperature extremes are still partial.

Hargreaves-Samani days are calibrated to Penman-Monteith month by month: for each calendar month, the ratio
sum(PM) / sum(HS) over every PM-eligible day of that month in the record (both computed for the same days) scales
the HS fallback days of that month (hs_ratios). The ratios come from the whole record at query time, cached per
station day (default_hs_ratios), so nothing is stored; a month with fewer than MIN_RATIO_DAYS PM days stays at 1.
"""
import logging
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
MIN_RATIO_DAYS = 20
RATIO_LIMITS = (0.5, 1.5)
ET0_INPUTS: Tuple[Tuple[str, str], ...] = (
    ("temp", "max"), ("temp", "min"), ("dewpt", "avg"), ("humi", "max"), ("humi", "min"), ("wind", "avg"),
    ("sun", "total"))


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
    cal: Optional[float] = None       # ET0 "hs" days: the month's PM/HS calibration ratio applied (None: uncalibrated)
    at = None
    cnt = None
    comment = None

    @property
    def simple_dict_(self) -> dict:
        out = dict(d=(self.d.year, self.d.month, self.d.day), val=self.val)
        if self.method:
            out["method"] = self.method
        if self.cal is not None:
            out["cal"] = self.cal
        return out

    @property
    def dict_(self) -> dict:
        return dict(self.simple_dict_, var=self.var, type=self.type)


def sun_usable(comment: Optional[str]) -> bool:
    """Webcam sunshine (live, or backfilled from the 30-min archive snapshots) with enough of daylight classified.
    Totals from the weather-API estimate (no or too little webcam coverage) are not used."""
    if not comment or comment.startswith("API estimate"):
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


def _et0_inputs(series: Dict[Tuple[str, str], Iterable], today: Optional[date]):
    """-> (day, daily_et0 keyword arguments) for each day with a daily max and min temperature, before today."""
    s = {k: _by_day(series.get(k, [])) for k in ET0_INPUTS}
    tmax, tmin = s[("temp", "max")], s[("temp", "min")]
    for d in sorted(tmax):
        if d not in tmin or (today is not None and d >= today):
            continue
        val = lambda k: s[k][d].val if d in s[k] else None   # noqa: E731
        sun = s[("sun", "total")].get(d)
        sun_h = sun.val if sun is not None and sun_usable(getattr(sun, "comment", None)) else None
        yield d, dict(tmax=tmax[d].val, tmin=tmin[d].val, dewpt=val(("dewpt", "avg")), rh_max=val(("humi", "max")),
                      rh_min=val(("humi", "min")), wind_mph=val(("wind", "avg")), sun_h=sun_h)


def et0_days(series: Dict[Tuple[str, str], Iterable], today: Optional[date] = None,
             wind_factor: float = et0_mod.WIND_TO_U2, ratios: Optional[Dict[int, float]] = None) -> List[DerivedDay]:
    """series: {(var, type): AvgExt-like rows}; -> one DerivedDay per day with a daily max and min temperature.
    ratios: {calendar month: PM/HS ratio} to calibrate the Hargreaves-Samani days (see hs_ratios); None: raw HS."""
    out = []
    for d, kw in _et0_inputs(series, today):
        res = et0_mod.daily_et0(d, wind_factor=wind_factor, **kw)
        if res is None:
            continue
        val, method = res
        cal = None
        if method == "hs" and ratios and d.month in ratios:
            cal = ratios[d.month]
            val = round(val * cal, 2)
        out.append(DerivedDay(d=d, val=val, var=ET0_VAR, type=ET0_TYPE, method=method, cal=cal))
    return out


def hs_ratios(series: Dict[Tuple[str, str], Iterable], today: Optional[date] = None,
              wind_factor: float = et0_mod.WIND_TO_U2) -> Dict[int, float]:
    """{calendar month: sum(PM) / sum(HS)} over the PM-eligible days (Hargreaves-Samani computed for the same days).
    Months with fewer than MIN_RATIO_DAYS such days are left out (no calibration); ratios are clamped to
    RATIO_LIMITS."""
    pm: Dict[int, float] = defaultdict(float)
    hs: Dict[int, float] = defaultdict(float)
    n: Dict[int, int] = defaultdict(int)
    for d, kw in _et0_inputs(series, today):
        res = et0_mod.daily_et0(d, wind_factor=wind_factor, **kw)
        if res is None or res[1] != "pm":
            continue
        raw_hs = et0_mod.hargreaves(kw["tmax"], kw["tmin"], et0_mod.solar_geometry(d.timetuple().tm_yday)[0])
        pm[d.month] += res[0]
        hs[d.month] += max(raw_hs, 0.0)
        n[d.month] += 1
    lo, hi = RATIO_LIMITS
    return {m: round(min(max(pm[m] / hs[m], lo), hi), 3) for m in n if n[m] >= MIN_RATIO_DAYS and hs[m] > 0}


_RATIO_CACHE: Dict[date, Dict[int, float]] = {}


def default_hs_ratios(today: date) -> Dict[int, float]:
    """The month ratios from the whole stored record, computed once per station day (needs the app's DB session);
    {} (raw Hargreaves-Samani) if they cannot be computed."""
    if today not in _RATIO_CACHE:
        try:
            from rwcwx.model.avgext import AvgExtQ
            ratios = hs_ratios({k: AvgExtQ.daily_rows(*k) for k in ET0_INPUTS}, today)
        except Exception as e:   # noqa: BLE001 - ET0 still works uncalibrated
            logging.warning("ET0 Hargreaves calibration unavailable: %s", e)
            return {}
        _RATIO_CACHE.clear()
        _RATIO_CACHE[today] = ratios
    return _RATIO_CACHE[today]


def derive(var: str, fetch: Callable[[str, str], Iterable], today: Optional[date] = None,
           ratios: Optional[Dict[int, float]] = None) -> List[DerivedDay]:
    """fetch(var, type) -> that input's daily rows (any date window); -> the derived days in the same window.
    ratios: ET0's Hargreaves-Samani calibration (hs_ratios / default_hs_ratios); None leaves HS days raw."""
    if var in RANGE_VARS:
        return range_days(fetch(RANGE_VARS[var], "max"), fetch(RANGE_VARS[var], "min"), var)
    if var == ET0_VAR:
        return et0_days({k: fetch(*k) for k in ET0_INPUTS}, today, ratios=ratios)
    raise ValueError(f"not a derived variable: {var}")


def add_to_summary(stats: dict, by_type: Dict[Tuple[str, str], list], summarise: Callable[[list], dict],
                   today: Optional[date] = None, ratios: Optional[Dict[int, float]] = None) -> None:
    """Month / year / day-of-year summaries: add "<var>_<type>" for each derived variable with data."""
    for var in DERIVED:
        days = derive(var, lambda v, t: by_type.get((v, t), []), today, ratios=ratios)
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

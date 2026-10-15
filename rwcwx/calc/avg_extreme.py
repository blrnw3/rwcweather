from __future__ import annotations
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Collection, Dict, Iterable, List, Optional, Tuple, Type

from rwcwx.model.avgext import AvgExtQ
from rwcwx.model.obs import ObsQ
from rwcwx.models import AvgExt, Obs
from rwcwx.util import DateUtil


class Unit(Enum):
    inch = "in."
    degc = "C"
    degf = "F"
    pct = "%"
    mm = "mm"
    hpa = "hPa"
    ppm = "ppm"
    mph = "mph"
    degs = "degrees"
    hours = "h"


@dataclass
class SummaryStats:
    count: int
    total: float
    min_val: float
    max_val: float
    min_at: datetime
    max_at: datetime

    @property
    def avg(self) -> float:
        return self.total / self.count if self.count else None

    @property
    def as_dict(self) -> dict:
        return {"avg": self.avg, **asdict(self)}


class ObsVar(ABC):

    # More options to try: https://stackoverflow.com/questions/2736255/abstract-attributes-in-python

    name: str
    unit: Unit
    db_field: str

    # @property
    # @classmethod
    # @abstractmethod
    # def name(cls) -> str:
    #     raise NotImplementedError
    #

    # def __init__(self, name: str, unit: str, db_field: str):
    #     self.name: str = name
    #     self.unit: str = unit
    #     self.db_field: str = db_field

    @classmethod
    def summary_stats(cls, obs: List[Obs]) -> SummaryStats:
        cnt, total = 0, 0
        min_val, min_at = None, None
        max_val, max_at = None, None

        for o in obs:
            val = getattr(o, cls.db_field)
            if val is None:
                continue
            cnt += 1
            total += val
            if min_val is None or val < min_val:
                min_val = val
                min_at = o.t
            if max_val is None or val > max_val:
                max_val = val
                max_at = o.t

        return SummaryStats(
            count=cnt,
            total=total,
            min_val=min_val,
            max_val=max_val,
            min_at=min_at,
            max_at=max_at
        )

    @classmethod
    def multiday_summary(cls, avg_exts: List[AvgExt]) -> SummaryStats:
        cnt, total = 0, 0
        min_val, min_at = None, None
        max_val, max_at = None, None

        for ae in avg_exts:
            cnt += 1
            total += ae.val
            if min_val is None or ae.val < min_val:
                min_val = ae.val
                min_at = ae.d
            if max_val is None or ae.val > max_val:
                max_val = ae.val
                max_at = ae.d

        return SummaryStats(
            count=cnt,
            total=total,
            min_val=min_val,
            max_val=max_val,
            min_at=min_at,
            max_at=max_at
        )


ObsVarT = Type[ObsVar]


class Rain(ObsVar):
    name = "rain"
    unit = Unit.inch
    db_field = "rain"

    @classmethod
    def summary_stats(cls, obs: List[Obs]) -> SummaryStats:
        stats = super().summary_stats(obs)
        stats.total = stats.max_val
        return stats


class Temp(ObsVar):
    name = "temperature"
    unit = Unit.degc
    db_field = "temp"


class Humi(ObsVar):
    name = "humidity"
    unit = Unit.pct
    db_field = "humi"


class Dewpt(ObsVar):
    name = "dew_point"
    unit = Unit.degc
    db_field = "dewpt"


class Pm2(ObsVar):
    name = "pm2_5_level"
    unit = Unit.ppm
    db_field = "pm2"


class Aqi(ObsVar):
    name = "aqi"
    unit = Unit.ppm
    db_field = "aqi"


class Wind(ObsVar):
    name = "wind_speed"
    unit = Unit.mph
    db_field = "wind"


class Gust(ObsVar):
    name = "gust_speed"
    unit = Unit.mph
    db_field = "gust"


class Pres(ObsVar):
    name = "pressure"
    unit = Unit.hpa
    db_field = "pres"


class Wdir(ObsVar):
    name = "wind_direction"
    unit = Unit.hpa
    db_field = "wdir"


class InTemp(ObsVar):
    name = "pressure"
    unit = Unit.degc
    db_field = "intemp"


class Sun(ObsVar):
    """Webcam sunshine hours. Only daily totals exist (avg_extreme var='sun'), there are no obs minutes."""
    name = "sunshine"
    unit = Unit.hours
    db_field = "sun"


class SunPct(ObsVar):
    """Derived from Sun: daily sunshine as % of possible (sunrise to sunset). Aggregates as the mean of days."""
    name = "sunshine (% of possible)"
    unit = Unit.pct
    db_field = "sunpct"


class Wet(ObsVar):
    """Derived from rain-gauge tips (rwcwx/wet): daily wet hours in avg_extreme var='wet', type='total'."""
    name = "wet hours"
    unit = Unit.hours
    db_field = "wet"


class WetRate(ObsVar):
    """Average rain rate when wet: rain / wet hours (rwcwx/wet/rate.py). Period mean = total rain / total wet hours."""
    name = "rain rate (when wet)"
    unit = Unit.inch
    db_field = "wetrate"

    @classmethod
    def multiday_summary(cls, avg_exts) -> SummaryStats:
        from rwcwx.wet.rate import period_rate
        stats = super().multiday_summary(avg_exts)
        r = period_rate(avg_exts)
        if r is not None and stats.count:
            stats.total = r * stats.count       # so .avg == rain / wet hours
        return stats
class Rain10(ObsVar):
    """Daily max rain in any 10 minutes, from gauge tips (rwcwx/wet/intensity.py); avg_extreme type 'max'."""
    name = "max 10-min rain"
    unit = Unit.inch
    db_field = "rain10"


class Rain60(ObsVar):
    """Daily max rain in any 60 minutes, from gauge tips; avg_extreme type 'max'."""
    name = "max 60-min rain"
    unit = Unit.inch
    db_field = "rain60"


class ObsVarGroup:
    ALL: Iterable[ObsVarT] = (Rain, Temp, Humi, Wind, Gust, Pres, Wdir, Aqi, Dewpt)


OBS_VAR_MAP = {o.db_field: o for o in (
    (Rain, Temp, Humi, Wind, Gust, Pres, Wdir, Aqi, Dewpt, Sun, SunPct, Wet, WetRate, Rain10, Rain60)
)}


class DaySummary:

    def __init__(self, day: Optional[date]) -> None:
        if day is None:
            day = DateUtil.now()
        self.day: date = day

    @classmethod
    def for_today(cls) -> DaySummary:
        return DaySummary(DateUtil.now().date())

    @classmethod
    def for_yesterday(cls) -> DaySummary:
        return DaySummary(DateUtil.now().date())

    def stats(self, day_obs: Optional[List[Obs]] = None) -> Dict[ObsVarT, SummaryStats]:
        if day_obs is None:
            day_obs = ObsQ.day(self.day)
        total_cnt = len(day_obs)
        # if total_cnt == 0:
        #     raise ValueError(f"No obs for {self.day}")
        stats = {}
        for f in ObsVarGroup.ALL:
            stats[f] = f.summary_stats(day_obs)
        return stats

    def stats_json(self, day_obs: Optional[List[Obs]] = None):
        return {k.name: v.as_dict for k, v in self.stats(day_obs).items()}


class MonthSummary:

    def __init__(self, month: Optional[date]) -> None:
        if month is None:
            month = DateUtil.now().date()
        self.month: date = month

    @classmethod
    def for_this_month(cls) -> MonthSummary:
        return MonthSummary(None)

    def stats(self) -> Dict[str, Dict]:
        by_type = defaultdict(list)
        for ae in AvgExtQ.all_for_month(self.month):
            by_type[(ae.var, ae.type)].append(ae)
        stats = {}
        for (var, typ), aes in by_type.items():
            stats[f"{var}_{typ}"] = ObsVar.multiday_summary(aes).as_dict
        if ("sun", "total") in by_type:
            # Sunshine as % of possible: mean of the daily %s, as in the reports (#24).
            from rwcwx.model import sun as sun_model
            pct = sun_model.pct_days(by_type[("sun", "total")])
            stats[f"{sun_model.PCT_VAR}_{sun_model.PCT_TYPE}"] = ObsVar.multiday_summary(pct).as_dict
        _add_rate(stats, by_type)
        return stats


def _add_rate(stats: dict, by_type: dict) -> None:
    from rwcwx.wet.rate import RATE_TYPE, RATE_VAR, rate_days
    days = rate_days(by_type.get(("rain", "total"), []), by_type.get(("wet", "total"), []))
    if days:
        stats[f"{RATE_VAR}_{RATE_TYPE}"] = WetRate.multiday_summary(days).as_dict


class YearSummary:

    def __init__(self, year: Optional[int]) -> None:
        if year is None:
            year = DateUtil.now().year
        self.year: int = year

    @classmethod
    def for_this_year(cls) -> YearSummary:
        return YearSummary(None)

    def stats(self) -> Dict[str, Dict]:
        by_type = defaultdict(list)
        for ae in AvgExtQ.all_for_year(self.year):
            by_type[(ae.var, ae.type)].append(ae)
        stats = {}
        for (var, typ), aes in by_type.items():
            stats[f"{var}_{typ}"] = ObsVar.multiday_summary(aes).as_dict
        _add_rate(stats, by_type)
        return stats


class WaterYearRainSummary:

    def __init__(self, year: Optional[int]) -> None:
        if year is None:
            year = (1 if DateUtil.now().month >= 10 else 0) + DateUtil.now().year
        self.year: int = year

    @classmethod
    def for_this_year(cls) -> WaterYearRainSummary:
        return WaterYearRainSummary(None)

    def stats(self) -> Dict[str, Dict]:
        by_type = defaultdict(list)
        for ae in AvgExtQ.rain_for_water_year(self.year):
            by_type[(ae.var, ae.type)].append(ae)
        stats = {}
        for (var, typ), aes in by_type.items():
            stats[f"{var}_{typ}"] = ObsVar.multiday_summary(aes).as_dict
        _add_rate(stats, by_type)
        return stats


class DayOfYearSummary:

    def __init__(self, day: Optional[date] = None) -> None:
        self.day: date = day or DateUtil.now().date()

    @classmethod
    def for_today(cls) -> DayOfYearSummary:
        return DayOfYearSummary(None)

    def stats(self) -> Dict[str, Dict]:
        by_type = defaultdict(list)
        for ae in AvgExtQ.all_for_day_of_year(self.day.month, self.day.day, exclude_date=self.day):
            by_type[(ae.var, ae.type)].append(ae)
        stats = {}
        for (var, typ), aes in by_type.items():
            s = ObsVar.multiday_summary(aes).as_dict
            if isinstance(s.get("min_at"), date):
                s["min_yr"] = s["min_at"].year
                s["min_at"] = (s["min_at"].year, s["min_at"].month, s["min_at"].day)
            if isinstance(s.get("max_at"), date):
                s["max_yr"] = s["max_at"].year
                s["max_at"] = (s["max_at"].year, s["max_at"].month, s["max_at"].day)
            stats[f"{var}_{typ}"] = s
        if ("sun", "total") in by_type:
            from rwcwx.model import sun as sun_model
            pct = sun_model.pct_days(by_type[("sun", "total")])
            s = ObsVar.multiday_summary(pct).as_dict
            if isinstance(s.get("min_at"), date):
                s["min_yr"] = s["min_at"].year
                s["min_at"] = (s["min_at"].year, s["min_at"].month, s["min_at"].day)
            if isinstance(s.get("max_at"), date):
                s["max_yr"] = s["max_at"].year
                s["max_at"] = (s["max_at"].year, s["max_at"].month, s["max_at"].day)
            stats[f"{sun_model.PCT_VAR}_{sun_model.PCT_TYPE}"] = s
        return stats


class AvgExtAggregator:

    @staticmethod
    def daily(avg_exts: List[AvgExt], var: str):
        return [ae.simple_dict_ for ae in avg_exts]

    @staticmethod
    def monthly(avg_exts: List[AvgExt], var: str):
        by_month = defaultdict(list)
        for ae in avg_exts:
            by_month[(ae.d.year, ae.d.month)].append(ae)

        return [
            dict(
                summary=OBS_VAR_MAP[var].multiday_summary(aes).as_dict,
                m=period
            )
            for period, aes in by_month.items()
        ]

    @staticmethod
    def annual(avg_exts: List[AvgExt], var: str):
        by_yr = defaultdict(list)
        for ae in avg_exts:
            by_yr[ae.d.year].append(ae)

        return [
            dict(
                summary=OBS_VAR_MAP[var].multiday_summary(aes).as_dict,
                m=yr
            )
            for yr, aes in by_yr.items()
        ]

    @staticmethod
    def all_summaries(avg_ext: List[AvgExt], var: str):
        return dict(
            daily=AvgExtAggregator.daily(avg_ext, var),
            monthly=AvgExtAggregator.monthly(avg_ext, var),
            yearly=AvgExtAggregator.annual(avg_ext, var),
        )

from __future__ import annotations
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import date, datetime
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
        return self.total / self.count

    @property
    def as_dict(self) -> dict:
        return {"avg": self.avg, **asdict(self)}


@dataclass
class MonthlySummary:
    summary: SummaryStats


@dataclass
class AnnualSummary:
    summary: SummaryStats


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
    def month_summary(cls, avg_exts: List[AvgExt]) -> MonthlySummary:
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

        summary = SummaryStats(
            count=cnt,
            total=total,
            min_val=min_val,
            max_val=max_val,
            min_at=min_at,
            max_at=max_at
        )
        return MonthlySummary(summary=summary)

    @classmethod
    def year_summary(cls, avg_exts: List[AvgExt]) -> AnnualSummary:
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

        summary = SummaryStats(
            count=cnt,
            total=total,
            min_val=min_val,
            max_val=max_val,
            min_at=min_at,
            max_at=max_at
        )
        return AnnualSummary(summary=summary)


ObsVarT = Type[ObsVar]


class Rain(ObsVar):

    name = "rain"
    unit = Unit.inch
    db_field = "rain"

    # def __init__(self):
    #     super().__init__(name="rain", unit="in", db_field="rain")

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO

    @classmethod
    def summary_stats(cls, obs: List[Obs]) -> SummaryStats:
        stats = super().summary_stats(obs)
        stats.total = stats.max_val
        return stats


class Temp(ObsVar):
    name = "temperature"
    unit = Unit.degc
    db_field = "temp"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Humi(ObsVar):
    name = "humidity"
    unit = Unit.pct
    db_field = "humi"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Dewpt(ObsVar):
    name = "dew_point"
    unit = Unit.degc
    db_field = "dewpt"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Pm2(ObsVar):
    name = "pm2_5_level"
    unit = Unit.ppm
    db_field = "pm2"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Aqi(ObsVar):
    name = "aqi"
    unit = Unit.ppm
    db_field = "aqi"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Wind(ObsVar):
    name = "wind_speed"
    unit = Unit.mph
    db_field = "wind"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Gust(ObsVar):
    name = "gust_speed"
    unit = Unit.mph
    db_field = "gust"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Pres(ObsVar):
    name = "pressure"
    unit = Unit.hpa
    db_field = "pres"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class Wdir(ObsVar):
    name = "wind_direction"
    unit = Unit.hpa
    db_field = "wdir"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class InTemp(ObsVar):
    name = "pressure"
    unit = Unit.degc
    db_field = "intemp"

    @classmethod
    def conv(cls, val: float) -> float:
        pass  # TODO


class ObsVarGroup:
    ALL: Iterable[ObsVarT] = (Rain, Temp, Humi, Wind, Gust, Pres, Wdir, Aqi, Dewpt)


OBS_VAR_MAP = {o.db_field: o for o in (
    (Rain, Temp, Humi, Wind, Gust, Pres, Wdir, Aqi, Dewpt)
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

    def stats(self) -> Dict[ObsVarT, SummaryStats]:
        day_obs = ObsQ.day(self.day)
        total_cnt = len(day_obs)
        if total_cnt == 0:
            raise ValueError(f"No obs for {self.day}")
        stats = {}
        for f in ObsVarGroup.ALL:
            stats[f] = f.summary_stats(day_obs)
        return stats

    def stats_json(self):
        return {k.name: v.as_dict for k, v in self.stats().items()}


class MonthSummary:

    def __init__(self, month: Optional[date]) -> None:
        if month is None:
            month = DateUtil.now()
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
            stats[f"{var}_{typ}"] = ObsVar.month_summary(aes).summary.as_dict
        return stats


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
            stats[f"{var}_{typ}"] = ObsVar.year_summary(aes).summary.as_dict
        return stats


class ObsVarMatrix:

    def __init__(self, var: str, typ: str, year: int = None) -> None:
        self.var: ObsVarT = OBS_VAR_MAP[var]
        self.typ = typ  # todo: enum
        self.avg_exts = AvgExtQ.for_var_between_dates(self.var.db_field, self.typ)

    def daily(self):
        return [ae.simple_dict_ for ae in self.avg_exts]

    def monthly(self):
        by_month = defaultdict(list)
        for ae in self.avg_exts:
            by_month[(ae.d.year, ae.d.month)].append(ae)

        return [
            dict(
                summary=self.var.month_summary(aes).summary.as_dict,
                m=period
            )
            for period, aes in by_month.items()
        ]

    def annual(self):
        by_yr = defaultdict(list)
        for ae in self.avg_exts:
            by_yr[ae.d.year].append(ae)

        return [
            dict(
                summary=self.var.year_summary(aes).summary.as_dict,
                m=yr
            )
            for yr, aes in by_yr.items()
        ]

    def all_summaries(self):
        return dict(
            daily=self.daily(),
            monthly=self.monthly(),
            yearly=self.annual()
        )

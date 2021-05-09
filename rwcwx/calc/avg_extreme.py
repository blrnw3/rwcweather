from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import date, datetime
from enum import Enum
from typing import Collection, Dict, Iterable, List, Optional, Tuple, Type


from rwcwx.model.obs import ObsQ
from rwcwx.models import Obs
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

#
# @dataclass
# class ObsVariable:
#     name: str
#     unit: str
#     db_field: str


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
    @abstractmethod
    def conv(cls, val: float) -> float:
        raise NotImplementedError("abstract")


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
    ALL: Iterable[ObsVarT] = (Rain, Temp, Humi, Wind, Gust, Pres, Wdir, Pm2, Dewpt)


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

"""Derived wet minutes from rain-gauge tips (pure functions, no DB).

A tip is an increase in obs.rain, the gauge's daily running total, which resets at local midnight.
  * Tips less than 2*WINDOW apart belong to one spell, wet from WINDOW before its first tip to WINDOW after its last.
  * A lone tip (a spell of one single 0.01 in. tip) counts as WINDOW minutes in total, centred on the tip.
  * A tip that arrives straight after a data gap (> GAP_MIN without obs) can't be placed in time: it is unknown,
    so it starts no spell (the rain still counts towards the rain total, just not towards wet time).
  * Only observed minutes can be wet: minutes inside a data gap are unknown, never wet.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

from dateutil.tz import UTC

from rwcwx.config import TZ

WINDOW_MIN = 30
GAP_MIN = 10            # obs are minutely; a longer silence is a data gap
TIP_IN = 0.01           # one bucket tip
_EPS = 0.0049


@dataclass
class Tip:
    t: datetime          # naive UTC, as obs.t
    amount: float


@dataclass
class Spell:
    start: datetime      # naive UTC, inclusive
    end: datetime        # naive UTC, exclusive
    tips: List[Tip] = field(default_factory=list)
    wet_min: float = 0.0     # observed wet minutes within the day being computed
    span: Optional[Tuple[datetime, datetime]] = None   # the spell clipped to that day

    @property
    def n_tips(self) -> int:
        return int(round(sum(t.amount for t in self.tips) / TIP_IN))

    @property
    def amount(self) -> float:
        return round(sum(t.amount for t in self.tips), 3)

    @property
    def lone(self) -> bool:
        return len(self.tips) == 1 and self.n_tips == 1


def _local_date(t: datetime) -> date:
    return t.replace(tzinfo=UTC).astimezone(TZ).date()


def find_tips(rows: Sequence[Tuple[datetime, Optional[float]]], gap_min: int = GAP_MIN) -> Tuple[List[Tip], List[Tip]]:
    """(tips, unknown_tips) from (t, rain) rows in time order. Unknown = first reading after a data gap."""
    tips, unknown = [], []
    prev_t, prev_r = None, None
    for t, r in rows:
        if r is None:
            continue
        r = float(r)
        if prev_t is None:
            prev_t, prev_r = t, r
            continue
        same_day = _local_date(t) == _local_date(prev_t)
        if not same_day:
            delta = r                       # midnight reset: the first reading is the total since midnight
        elif r < prev_r - _EPS:
            delta = 0.0                     # mid-day drop (logger glitch / manual reset): not rain
        else:
            delta = r - prev_r
        if delta > _EPS:
            tip = Tip(t, round(delta, 3))
            (unknown if (t - prev_t) > timedelta(minutes=gap_min) else tips).append(tip)
        prev_t, prev_r = t, r
    return tips, unknown


def spells_from_tips(tips: Iterable[Tip], window: int = WINDOW_MIN) -> List[Spell]:
    w = timedelta(minutes=window)
    spells: List[Spell] = []
    for tip in tips:
        if spells and tip.t - spells[-1].tips[-1].t <= 2 * w:
            spells[-1].tips.append(tip)
            spells[-1].end = tip.t + w
        else:
            spells.append(Spell(tip.t - w, tip.t + w, [tip]))
    for s in spells:
        if s.lone:                          # lone tip: WINDOW minutes in total, centred on it
            s.start, s.end = s.tips[0].t - w / 2, s.tips[0].t + w / 2
    return spells


def observed_minutes(times: Sequence[datetime], gap_min: int = GAP_MIN) -> List[Tuple[datetime, datetime]]:
    """Covered [start, end) intervals: each obs minute, plus short gaps between obs (<= gap_min) bridged."""
    out: List[Tuple[datetime, datetime]] = []
    one = timedelta(minutes=1)
    for t in times:
        if out and t - out[-1][1] <= timedelta(minutes=gap_min) - one:
            out[-1] = (out[-1][0], t + one)
        else:
            out.append((t, t + one))
    return out


def _overlap_min(a: Tuple[datetime, datetime], b: Tuple[datetime, datetime]) -> float:
    st, en = max(a[0], b[0]), min(a[1], b[1])
    return max((en - st).total_seconds() / 60, 0.0)


@dataclass
class WetDay:
    d: date
    wet_min: float
    spells: List[Spell]                       # spells touching the day (clipped values below)
    observed_min: float
    unknown_tips: int
    rain: float
    day_start: Optional[datetime] = None   # naive UTC bounds of the local day
    day_end: Optional[datetime] = None

    def summary(self, now_utc: Optional[datetime] = None) -> dict:
        longest = max((s.wet_min for s in self.spells), default=0) if self.spells else 0
        wet_now = bool(now_utc and any(s.start <= now_utc < s.end for s in self.spells))
        return dict(
            wet_h=round(self.wet_min / 60, 2),
            spells=len(self.spells),
            longest_h=round(longest / 60, 2),
            rate=round(self.rain / (self.wet_min / 60), 3) if self.wet_min >= 1 else None,   # in. per wet hour
            rain=round(self.rain, 2),
            unknown_tips=self.unknown_tips,
            observed_h=round(self.observed_min / 60, 2),
            wet_now=wet_now,
            day_start=_ms(self.day_start), day_end=_ms(self.day_end),
            spell_list=[dict(start=_ms((s.span or (s.start, s.end))[0]), end=_ms((s.span or (s.start, s.end))[1]),
                             wet_h=round(s.wet_min / 60, 2), tips=s.n_tips, lone=s.lone) for s in self.spells],
        )


def _ms(t: Optional[datetime]) -> Optional[int]:
    return int(t.replace(tzinfo=UTC).timestamp() * 1000) if t else None


def day_bounds_utc(d: date) -> Tuple[datetime, datetime]:
    st = datetime(d.year, d.month, d.day, tzinfo=TZ)
    en = datetime.combine(d + timedelta(days=1), datetime.min.time()).replace(tzinfo=TZ)
    return st.astimezone(UTC).replace(tzinfo=None), en.astimezone(UTC).replace(tzinfo=None)


def wet_day(d: date, rows: Sequence[Tuple[datetime, Optional[float]]], window: int = WINDOW_MIN,
            gap_min: int = GAP_MIN) -> WetDay:
    """rows must cover the local day plus at least 2*window of context either side."""
    st, en = day_bounds_utc(d)
    tips, unknown = find_tips(rows, gap_min)
    spells = spells_from_tips(tips, window)
    covered = [c for c in observed_minutes([t for t, _ in rows], gap_min) if c[1] > st and c[0] < en]
    day = (st, en)
    kept = []
    for s in spells:
        span = (max(s.start, st), min(s.end, en))
        if span[1] <= span[0]:
            continue
        s.wet_min = sum(_overlap_min(span, c) for c in covered)
        s.span = span
        if s.wet_min > 0:
            kept.append(s)
    rain = sum(t.amount for t in tips + unknown if st <= t.t < en)
    return WetDay(d=d, wet_min=sum(s.wet_min for s in kept), spells=kept,
                  observed_min=sum(_overlap_min(day, c) for c in covered),
                  unknown_tips=sum(1 for t in unknown if st <= t.t < en), rain=rain, day_start=st, day_end=en)


def wet_flags(times: Iterable[datetime], spells: Sequence[Spell]) -> List[int]:
    """1 for each obs minute inside a spell, else 0."""
    return [int(any(s.start <= t < s.end for s in spells)) for t in times]

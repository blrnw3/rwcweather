"""Turn per-frame probabilities into per-minute sunshine for one local day.

Pipeline (PLAN 3.1/3.2), identical to the research evaluation (eval/sunday.py, rule R3):
  1. grid: every UTC minute overlapping [sunrise, sunset]; weight w = overlap fraction (so a cloudless day sums to
     exactly the astronomical daylight length, rwcwx.astronomy convention: sun centre at -0.833 deg).
  2. gates: missing (no frame within +-5 min), stale (frame identical to the previous one), ir (night/IR mode,
     Smean < 0.03 while el > 3). Gated minutes are unclassified (value NULL).
  3. main model state = p >= 0.5.
  4. low sun (el < 8 deg): carry the nearest confident main-model state (el >= 8, p < .25 or > .75) on the same side
     of solar noon (morning: next one, evening: previous one), vetoed to 0 if sky-clarity prob < 0.3. Flag 'lowsun'.
  5. median-5 over the classified minutes.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from rwcwx.sun.solar import solar_pos

LOW_EL = 8.0
CARRY_CONF = 0.25
VETO = 0.3
TOLERANCE_S = 300
IR_SMEAN = 0.03
IR_MIN_EL = 3.0


@dataclass
class Frame:
    t: datetime                 # UTC, from the filename (minute resolution)
    p: float                    # main model P(sunny)
    ps: float                   # sky-clarity P(clear), used for low sun
    smean: float
    stale: bool = False


@dataclass
class Minute:
    t: datetime                 # UTC minute start
    w: float                    # daylight weight 0..1
    el: float
    p: Optional[float] = None
    ps: Optional[float] = None
    res_s: Optional[float] = None
    flags: Set[str] = field(default_factory=set)
    value: Optional[int] = None

    @property
    def ok(self) -> bool:
        return not (self.flags & {"missing", "stale", "ir", "glitch"})


def daylight_grid(sunrise: datetime, sunset: datetime) -> List[Minute]:
    out = []
    t = sunrise.replace(second=0, microsecond=0)
    while t < sunset:
        a = min(max((t + timedelta(minutes=1) - sunrise).total_seconds(), 0), 60)
        b = min(max((sunset - t).total_seconds(), 0), 60)
        w = min(a, b) / 60.0
        if w > 0:
            out.append(Minute(t=t, w=w, el=solar_pos(t + timedelta(seconds=30))[0]))
        t += timedelta(minutes=1)
    return out


def _nearest(frames: List[Frame], t: datetime) -> Optional[Frame]:
    # frames sorted by t; small lists (<= ~800), bisect would be overkill but cheap anyway
    import bisect
    keys = [f.t for f in frames]
    i = bisect.bisect_left(keys, t)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(frames):
            d = abs((frames[j].t - t).total_seconds())
            if d <= TOLERANCE_S and (best is None or d < abs((best.t - t).total_seconds())):
                best = frames[j]
    return best


def _median5(vals: List[int]) -> List[int]:
    n = len(vals)
    out = []
    for i in range(n):
        win = [vals[min(max(k, 0), n - 1)] for k in range(i - 2, i + 3)]
        out.append(sorted(win)[2])
    return out


def classify_day(frames: List[Frame], sunrise: datetime, sunset: datetime) -> List[Minute]:
    frames = sorted(frames, key=lambda f: f.t)
    grid = daylight_grid(sunrise, sunset)
    for m in grid:
        f = _nearest(frames, m.t)
        if f is None:
            m.flags.add("missing")
            continue
        m.p, m.ps, m.res_s = f.p, f.ps, abs((m.t - f.t).total_seconds())
        if f.stale:
            m.flags.add("stale")
        elif f.smean < IR_SMEAN and m.el > IR_MIN_EL:
            m.flags.add("ir")
    if not grid:
        return grid

    main: List[Optional[int]] = [int(m.p >= 0.5) if m.ok else None for m in grid]
    conf = [main[i] if (m.ok and m.el >= LOW_EL and (m.p < CARRY_CONF or m.p > 1 - CARRY_CONF)) else None
            for i, m in enumerate(grid)]
    noon = max(range(len(grid)), key=lambda i: grid[i].el)
    carry: List[Optional[int]] = [None] * len(grid)
    nxt = None
    for i in range(noon, -1, -1):          # morning: next confident state
        if conf[i] is not None:
            nxt = conf[i]
        carry[i] = nxt
    prev = None
    for i in range(noon, len(grid)):       # evening: previous confident state (noon minute itself as morning)
        if conf[i] is not None:
            prev = conf[i]
        if i > noon:
            carry[i] = prev

    raw: Dict[int, int] = {}
    for i, m in enumerate(grid):
        if not m.ok:
            continue
        if m.el < LOW_EL:
            m.flags.add("lowsun")
            v = carry[i] or 0
            raw[i] = v if m.ps >= VETO else 0
        else:
            raw[i] = main[i]
    idx = sorted(raw)
    for i, v in zip(idx, _median5([raw[i] for i in idx])):
        grid[i].value = v
    return grid


def summary(grid: List[Minute]) -> dict:
    daylight = sum(m.w for m in grid)
    classified = sum(m.w for m in grid if m.value is not None)
    sun = sum(m.w for m in grid if m.value == 1)
    return dict(daylight_min=round(daylight, 2), sun_min=round(sun, 2), classified_min=round(classified, 2),
                coverage=round(classified / daylight, 4) if daylight else 0.0)

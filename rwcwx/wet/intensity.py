"""Max rolling rain per local day from rain-gauge tips: the most rain in any 10 / 60 minutes.

Tips come from rwcwx.wet.rules.find_tips (obs.rain is a daily running total reset at local midnight; a reset is
not rain). A tip that arrives straight after a data gap lumps together rain from an unknown span, so it is left
out (it would inflate the intensity), as is any single step above SPIKE_IN. Window = (t - W, t] over tip times; the day's value is stored in
avg_extreme as var 'rain10' / 'rain60', type 'max', val = inches, at = the time the max was first reached.
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from rwcwx.wet.rules import Tip, day_bounds_utc, find_tips

WINDOWS: Dict[str, int] = {"rain10": 10, "rain60": 60}
# A single reading step above this is a logger catch-up / reset artefact, not rain (the heaviest real bursts in the
# 2021-2026 record are ~0.06 in. per minute; e.g. 2025-11-20 jumps 0.57 in. in one minute after a stuck reading).
SPIKE_IN = 0.10


def max_window(tips: Sequence[Tip], minutes: int) -> Tuple[float, Optional[datetime]]:
    """(max rain in any `minutes` window ending at a tip, when it was first reached)."""
    w = timedelta(minutes=minutes)
    best, at, s, i = 0.0, None, 0.0, 0
    for j, tip in enumerate(tips):
        s += tip.amount
        while tips[i].t <= tip.t - w:
            s -= tips[i].amount
            i += 1
        if round(s, 3) > round(best, 3):
            best, at = s, tip.t
    return round(best, 3), at


def day_intensity(d: date, rows: Sequence[Tuple[datetime, Optional[float]]]) -> Dict[str, Tuple[float, Optional[datetime]]]:
    """rows: (t, rain) covering the local day (plus any context); only tips inside the day count."""
    st, en = day_bounds_utc(d)
    tips, _unknown = find_tips(rows)
    tips = [t for t in tips if st <= t.t < en and t.amount <= SPIKE_IN]
    return {var: max_window(tips, m) for var, m in WINDOWS.items()}

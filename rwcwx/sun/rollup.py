"""Daily sunshine total for avg_extreme (var='sun', type='total') with the PLAN 3.4 coverage rule.

coverage = classified daylight minutes / daylight minutes so far (whole day once the sun has set)
  >= 0.9        store hours as computed
  0.5 .. 0.9    store hours / coverage, comment says it was scaled
  < 0.5         store nothing
"""
from datetime import datetime
from typing import List, Optional

from rwcwx.sun.rules import Minute

FULL_COV = 0.9
MIN_COV = 0.5


def daily_total(grid: List[Minute], now_utc: Optional[datetime] = None, label: str = "webcam") -> Optional[dict]:
    if now_utc is not None:
        grid = [m for m in grid if m.t < now_utc]
    daylight = sum(m.w for m in grid)
    if daylight <= 0:
        return None
    classified = sum(m.w for m in grid if m.value is not None)
    sun_h = sum(m.w for m in grid if m.value == 1) / 60.0
    cov = classified / daylight
    if cov < MIN_COV:
        return None
    comment = f"{label}; coverage {cov:.1%}"
    if cov < FULL_COV:
        sun_h /= cov
        comment += "; scaled"
    return dict(val=round(sun_h, 2), cnt=int(round(classified)), coverage=round(cov, 4), comment=comment)

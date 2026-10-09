"""
Rankings of N consecutive days ("multi-day periods"), e.g. the wettest 3-day
spells or the warmest week of daily highs.

Computed from the daily avg_extreme rows only (one indexed query per variable
and daily statistic, ~2,100 rows), never from minute observations. Windows are
built with a running sum in plain Python, so the cost is O(days) plus a sort.

Rules:
- Windows are N consecutive calendar days ending on any day with data.
- Coverage: a window needs data for at least 90% of its days (rounded up), i.e.
  3 of 3, 7 of 7, 13 of 14 and 27 of 30. Rain totals add up the days present
  (so a gappy window can only be under-counted); means average the days present.
- Rain totals may include today (they only grow during the day); means do not,
  because a partial day would skew the spell.
- Results don't overlap: the best window is taken, every window sharing a day
  with it is dropped, and so on. That way a single storm or heatwave is listed
  once, instead of again for each shifted window.
"""
import math
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

ROLLING_DAYS = (3, 7, 14, 30)
MIN_COVERAGE = 0.9

# variable -> {daily statistic -> how the N daily values are combined}
ROLLING_VARS: Dict[str, Dict[str, str]] = {
    "rain": {"total": "sum"},
    "temp": {"avg": "mean", "max": "mean", "min": "mean"},
}


def min_days_required(n: int) -> int:
    return math.ceil(n * MIN_COVERAGE - 1e-9)


def rolling_windows(daily: Iterable[Tuple[date, float]], n: int, how: str, last_day: Optional[date] = None) -> List[dict]:
    """All N-day windows meeting the coverage rule, keyed by their last day."""
    values = {d: v for d, v in daily if v is not None and (last_day is None or d <= last_day)}
    if not values:
        return []
    first, last = min(values), max(values)
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    need = min_days_required(n)

    windows = []
    total, count = 0.0, 0
    for i, d in enumerate(days):
        if d in values:
            total += values[d]
            count += 1
        if i >= n:
            dropped = days[i - n]
            if dropped in values:
                total -= values[dropped]
                count -= 1
        if i >= n - 1 and count >= need:
            val = total if how == "sum" else total / count
            windows.append(dict(start=days[i - n + 1], end=d, val=round(val, 4), days=count, n=n, idx=i))
    return windows


def rank_non_overlapping(windows: List[dict], order: str = "highest", limit: int = 25) -> List[dict]:
    """Greedy pick: best window first, then the best window not sharing a day with any picked one."""
    reverse = order == "highest"
    # Ties: most recent first, as elsewhere in the rankings.
    ordered = sorted(windows, key=lambda w: (w["val"] if reverse else -w["val"], w["idx"]), reverse=True)
    taken: List[Tuple[int, int]] = []
    picked = []
    for w in ordered:
        lo, hi = w["idx"] - w["n"] + 1, w["idx"]
        if any(lo <= t_hi and t_lo <= hi for t_lo, t_hi in taken):
            continue
        taken.append((lo, hi))
        picked.append(w)
        if len(picked) >= limit:
            break
    return picked


def rolling_ranking(daily: Iterable[Tuple[date, float]], var: str, typ: str, n: int,
                    order: str = "highest", limit: int = 25, today: Optional[date] = None) -> List[dict]:
    how = ROLLING_VARS[var][typ]
    last_day = None
    if how == "mean" and today is not None:
        last_day = today - timedelta(days=1)
    picked = rank_non_overlapping(rolling_windows(daily, n, how, last_day), order, limit)
    return [
        dict(
            start=(w["start"].year, w["start"].month, w["start"].day),
            end=(w["end"].year, w["end"].month, w["end"].day),
            val=w["val"],
            days=w["days"],
            n=w["n"],
        )
        for w in picked
    ]

"""All-years statistics for each calendar day (Jan 1 .. Dec 31), for the Year Charts overlay.

For one variable and daily statistic (e.g. temp/max), every calendar day gets the average, lowest and highest of
that daily value over all years of records, with the years of the extremes and the number of values:
  max temp on 14 Jul: avg = mean daily max on 14 Jul, min = lowest daily max on 14 Jul, max = record daily max.

Today is left out (its value is still partial). Feb 29 has only one or two values of its own, so its statistics pool
Feb 28, Feb 29 and Mar 1 of every year; this keeps the leap-day point in line with its neighbours.

Cumulative mode (totals such as rain and sunshine) gives envelopes of running totals instead: for each year (calendar
or water year Oct-Sep) that starts within the record, the total from the year's first day up to and including each
day; then the mean, lowest and highest of those running totals at each day. Years still in progress count up to their
last complete day. A missing day adds nothing to the running total. Feb 29 in a non-leap year is that year's running
total at the end of February.

The input is the variable's daily (date, value) series (one indexed query on avg_extreme), so this is all Python over
~2k rows.
"""
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

LEAP = 2000                                    # any leap year: the calendar of month/day keys
DAYS: List[Tuple[int, int]] = []
_d = date(LEAP, 1, 1)
while _d.year == LEAP:
    DAYS.append((_d.month, _d.day))
    _d += timedelta(days=1)
FEB29 = (2, 29)
_FEB29_POOL = {(2, 28), (2, 29), (3, 1)}


def _summ(vals: List[Tuple[float, int]], md: Tuple[int, int]) -> dict:
    out = dict(m=md[0], d=md[1], n=len(vals), avg=None, min=None, max=None, min_year=None, max_year=None)
    if vals:
        lo = min(vals, key=lambda x: (x[0], x[1]))
        hi = max(vals, key=lambda x: (x[0], -x[1]))      # ties: the earliest year holds the record
        out.update(avg=round(sum(v for v, _ in vals) / len(vals), 4), min=round(lo[0], 4), max=round(hi[0], 4),
                   min_year=lo[1], max_year=hi[1])
    return out


def daily_stats(values: Iterable[Tuple[date, Optional[float]]], today: date) -> List[dict]:
    """Per calendar day (366, Jan 1 first): avg/min/max of the daily values over all years before `today`."""
    by_md: Dict[Tuple[int, int], List[Tuple[float, int]]] = defaultdict(list)
    for d, v in values:
        if v is None or d >= today:
            continue
        by_md[(d.month, d.day)].append((float(v), d.year))
    feb29 = [x for md in _FEB29_POOL for x in by_md.get(md, [])]
    return [_summ(feb29 if md == FEB29 else by_md.get(md, []), md) for md in DAYS]


def period_start(year: int, water: bool) -> date:
    """First day of calendar year `year`, or of water year `year` (1 Oct year-1 .. 30 Sep year)."""
    return date(year - 1, 10, 1) if water else date(year, 1, 1)


def _period_end(year: int, water: bool) -> date:
    return date(year, 9, 30) if water else date(year, 12, 31)


def cumulative_stats(values: Iterable[Tuple[date, Optional[float]]], today: date, water: bool = False) -> List[dict]:
    """Per calendar day (366): mean/lowest/highest running total from the start of each year (or water year)."""
    vals = {d: float(v) for d, v in values if v is not None and d < today}
    if not vals:
        return [_summ([], md) for md in DAYS]
    first, last = min(vals), max(vals)
    last = min(last, today - timedelta(days=1))
    by_md: Dict[Tuple[int, int], List[Tuple[float, int]]] = defaultdict(list)
    year = first.year + (1 if water and first.month >= 10 else 0)
    while period_start(year, water) <= last:
        start = period_start(year, water)
        if start >= first:
            run, d = 0.0, start
            end = min(_period_end(year, water), last)
            while d <= end:
                run += vals.get(d, 0.0)
                by_md[(d.month, d.day)].append((run, year))
                if (d.month, d.day) == (2, 28) and not _is_leap(d.year):
                    by_md[FEB29].append((run, year))
                d += timedelta(days=1)
        year += 1
    return [_summ(by_md.get(md, []), md) for md in DAYS]


def _is_leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)

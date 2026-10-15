"""Calendar-day windows for ranking days near a chosen centre date in any year.

A window of 10 means ±5 days (11 calendar days including the centre); 30 means ±15.
Expansion uses a leap-year calendar so 29 February is a valid centre and appears in
windows that cover it; non-leap years simply have no Feb 29 row to match.
Year wrap (late December / early January) is handled by walking timedelta across Dec/Jan.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional, Set, Tuple

# Leap year used only to expand (month, day) ranges; the year never appears in results.
_REF_YEAR = 2024

WINDOW_RADIUS = {10: 5, 30: 15}


def parse_mmdd(mmdd: str) -> Optional[Tuple[int, int]]:
    """'MMDD' -> (month, day), or None if invalid (incl. 0230, 0001, 1301)."""
    if not mmdd or len(mmdd) != 4 or not mmdd.isdigit():
        return None
    month, day = int(mmdd[:2]), int(mmdd[2:])
    try:
        date(_REF_YEAR, month, day)
    except ValueError:
        return None
    return month, day


def format_mmdd(month: int, day: int) -> str:
    return f"{month:02d}{day:02d}"


def md_set(centre_month: int, centre_day: int, radius: int) -> Set[Tuple[int, int]]:
    """(month, day) pairs within ±radius days of the centre (inclusive)."""
    centre = date(_REF_YEAR, centre_month, centre_day)
    return {
        ((centre + timedelta(days=d)).month, (centre + timedelta(days=d)).day)
        for d in range(-radius, radius + 1)
    }


def matches_day_window(month: int, day: int, centre_month: int, centre_day: int, window: int) -> bool:
    """True if (month, day) falls in the window around the centre. window is 10 or 30."""
    radius = WINDOW_RADIUS.get(int(window))
    if radius is None:
        return True
    return (month, day) in md_set(centre_month, centre_day, radius)


def filter_daily_dates(dates: Iterable[Tuple[int, int, int]], centre_mmdd: str, window: int):
    """Keep (y, m, d) rows whose calendar day is in the window; empty centre/window = all."""
    parsed = parse_mmdd(centre_mmdd)
    if not parsed or int(window) not in WINDOW_RADIUS:
        return list(dates)
    cm, cd = parsed
    return [row for row in dates if matches_day_window(row[1], row[2], cm, cd, int(window))]

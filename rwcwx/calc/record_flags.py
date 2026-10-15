"""Today-vs-record status for the home climate/records card.

Directions that can only move further from the record are flagged as soon as they
cross it (hottest high, coldest low). Directions that can still reverse are shown
as on_track until a confirmation time, then as record/tie.

Ties (exact equality with the existing record) are labelled separately from breaks.
"""
from __future__ import annotations

from datetime import time
from typing import Optional

# Local civil times (station TZ) after which the overnight low / daytime high are treated as final.
MORNING_MIN_DONE = time(10, 0)
EVENING_MAX_DONE = time(18, 0)

# Status strings consumed by the home card.
RECORD = "record"
TIE = "tie"
ON_TRACK = "on_track"


def _cmp_break(today: Optional[float], record: Optional[float], want_above: bool) -> Optional[str]:
    if today is None or record is None:
        return None
    if want_above:
        if today > record:
            return RECORD
        if today == record:
            return TIE
        return None
    if today < record:
        return RECORD
    if today == record:
        return TIE
    return None


def hottest_high(today_max: Optional[float], record_max: Optional[float]) -> Optional[str]:
    """Record high of daily highs — final as soon as exceeded."""
    return _cmp_break(today_max, record_max, want_above=True)


def coldest_low(today_min: Optional[float], record_min: Optional[float]) -> Optional[str]:
    """Record low of daily lows — final as soon as exceeded."""
    return _cmp_break(today_min, record_min, want_above=False)


def warmest_low(today_min: Optional[float], record_warm_min: Optional[float],
                local_time: time, morning_done: bool = None) -> Optional[str]:
    """Record high of daily lows. Pending until ~10:00 local (overnight min settled)."""
    if today_min is None or record_warm_min is None:
        return None
    if today_min < record_warm_min:
        return None  # already too cold to set a warmest-low record
    confirmed = morning_done if morning_done is not None else local_time >= MORNING_MIN_DONE
    if not confirmed:
        return ON_TRACK
    return RECORD if today_min > record_warm_min else TIE


def coldest_high(today_max: Optional[float], record_cold_max: Optional[float],
                 local_time: time, evening_done: bool = None) -> Optional[str]:
    """Record low of daily highs. Pending until ~18:00 local (daytime max settled)."""
    if today_max is None or record_cold_max is None:
        return None
    if today_max > record_cold_max:
        return None  # already too warm to set a coldest-high record
    confirmed = evening_done if evening_done is not None else local_time >= EVENING_MAX_DONE
    if not confirmed:
        return ON_TRACK
    return RECORD if today_max < record_cold_max else TIE

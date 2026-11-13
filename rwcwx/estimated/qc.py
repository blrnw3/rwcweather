"""Quality-control checks on Pulgas Ridge (PUGC1) primary values.

A Pulgas rain total above RAIN_MIN_IN is rejected when it is more than
RAIN_RATIO times the larger of the same-day COOP and SFO raw totals, or when
both of those stations are dry (at most RAIN_DRY_IN). A Pulgas temperature
is rejected when it differs by more than TEMP_MAX_DIFF_C from the COOP (else
SFO) converted estimate for the same day. Rejected days are filled from the
usual secondary chain (COOP, then SFO).

Comparisons for rain use source inches (before conversion). Temperature
comparisons use this site's converted °C estimates.
"""
from __future__ import annotations

from typing import Optional, Tuple

# Pulgas rain (inches, raw) must exceed this before the spike check applies.
RAIN_MIN_IN = 1.0
# Reject if Pulgas raw rain is greater than this multiple of max(COOP, SFO).
RAIN_RATIO = 3.0
# Treat a comparison station as dry at or below this (inches).
RAIN_DRY_IN = 0.01
# Reject Pulgas temp if |Pulgas estimate − COOP/SFO estimate| exceeds this (°C).
TEMP_MAX_DIFF_C = 8.0


def rain_is_bogus(pugc1_raw: Optional[float], coop_raw: Optional[float],
                  sfo_raw: Optional[float]) -> bool:
    """True if a Pulgas rain total should be discarded in favour of a secondary."""
    if pugc1_raw is None or pugc1_raw <= RAIN_MIN_IN:
        return False
    others = [x for x in (coop_raw, sfo_raw) if x is not None]
    if not others:
        return False
    mx = max(others)
    if mx <= RAIN_DRY_IN:
        return True
    return pugc1_raw > RAIN_RATIO * mx


def temp_is_bogus(pugc1_est: Optional[float], coop_est: Optional[float],
                  sfo_est: Optional[float]) -> bool:
    """True if a Pulgas temperature should be discarded in favour of a secondary."""
    if pugc1_est is None:
        return False
    alt = coop_est if coop_est is not None else sfo_est
    if alt is None:
        return False
    return abs(pugc1_est - alt) > TEMP_MAX_DIFF_C


def pulgas_is_bogus(var: str, pugc1_raw: Optional[float], pugc1_val: Optional[float],
                    coop_raw: Optional[float], coop_val: Optional[float],
                    sfo_raw: Optional[float], sfo_val: Optional[float]) -> Tuple[bool, Optional[str]]:
    """Return (rejected, reason) for a Pulgas primary candidate."""
    if var == "rain":
        if rain_is_bogus(pugc1_raw, coop_raw, sfo_raw):
            return True, "rain_spike"
        return False, None
    if var == "temp":
        if temp_is_bogus(pugc1_val, coop_val, sfo_val):
            return True, "temp_outlier"
        return False, None
    return False, None

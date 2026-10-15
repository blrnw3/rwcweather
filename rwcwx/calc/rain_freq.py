"""Measurable-rain frequency for a calendar date (home climate card 'normal')."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from rwcwx.calc.day_window import md_set

# Station rain is stored in inches; matches the wet-day threshold used elsewhere.
MEASURABLE_IN = 0.01
# With only a few years of history, widen to ±SMOOTH_RADIUS days and count day-samples.
MIN_YEARS_EXACT = 5
SMOOTH_RADIUS = 3


def _wet(val: Optional[float]) -> bool:
    return val is not None and val >= MEASURABLE_IN


def frequency_from_rows(rows: Sequence[Tuple[date, float]], centre: date,
                        exclude: Optional[date] = None,
                        min_years_exact: int = MIN_YEARS_EXACT,
                        smooth_radius: int = SMOOTH_RADIUS) -> Dict:
    """rows: (d, rain_total) for candidate days. exclude is omitted (today).

    Prefer exact calendar date (year count). If fewer than min_years_exact distinct
    years, fall back to ±smooth_radius day-samples and report days instead of years.
    """
    exact = [(d, v) for d, v in rows
             if d.month == centre.month and d.day == centre.day and d != exclude]
    by_year: Dict[int, float] = {}
    for d, v in exact:
        # one value per year (latest wins if duplicates)
        by_year[d.year] = v
    years = sorted(by_year)
    if len(years) >= min_years_exact or smooth_radius <= 0:
        wet = sum(1 for y in years if _wet(by_year[y]))
        n = len(years)
        return dict(wet=wet, n=n, pct=round(100.0 * wet / n, 1) if n else None,
                    smoothed=False, unit="years")

    window = md_set(centre.month, centre.day, smooth_radius)
    samples = [(d, v) for d, v in rows
               if (d.month, d.day) in window and d != exclude]
    wet = sum(1 for _, v in samples if _wet(v))
    n = len(samples)
    return dict(wet=wet, n=n, pct=round(100.0 * wet / n, 1) if n else None,
                smoothed=True, radius=smooth_radius, unit="days")

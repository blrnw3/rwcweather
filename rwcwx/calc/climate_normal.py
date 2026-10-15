"""PRISM 1991-2020 daily normals for the station (same numbers as web/app/data/climate.js).

Daily averages are linearly interpolated between mid-month monthly normals, matching
web/app/components/climate.js dailyNormal().
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Dict, List, Optional

# degC — keep in lockstep with CLIMATE_NORMALS.normals.temp in climate.js
TEMP_MONTHLY: Dict[str, List[float]] = {
    "min": [7.12, 7.71, 8.32, 9.13, 10.98, 12.52, 13.79, 14.01, 13.42, 11.93, 9.03, 6.97],
    "max": [15.40, 16.84, 18.68, 20.24, 22.84, 26.13, 27.15, 27.50, 27.74, 24.95, 19.08, 15.28],
    "avg": [10.88, 11.80, 12.88, 13.72, 15.89, 18.13, 19.15, 19.48, 19.53, 17.73, 13.70, 10.84],
}


def days_in_month(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def _mid_ordinal(year: int, month: int) -> float:
    return date(year, month, 1).toordinal() + days_in_month(year, month) / 2.0


def daily_temp_normal(stat: str, d: date) -> Optional[float]:
    """Interpolated daily normal for temp min/max/avg on date d, in °C."""
    monthly = TEMP_MONTHLY.get(stat)
    if not monthly:
        return None
    t = d.toordinal()
    y0, m0 = d.year, d.month
    if t < _mid_ordinal(d.year, d.month):
        m0 = d.month - 1
        if m0 == 0:
            m0, y0 = 12, d.year - 1
    y1, m1 = y0, m0 + 1
    if m1 == 13:
        m1, y1 = 1, y0 + 1
    t0, t1 = _mid_ordinal(y0, m0), _mid_ordinal(y1, m1)
    f = (t - t0) / (t1 - t0)
    return monthly[m0 - 1] + f * (monthly[m1 - 1] - monthly[m0 - 1])

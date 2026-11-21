"""Estimated daily history (Tmax, Tmin, daily mean, rain) from Pulgas Ridge, with COOP/SFO gap-fill and quality control, 2011-01-01 to 2020-12-26.

Daily mean is (Tmax+Tmin)/2 plus a monthly offset (v5-midrange-month). See rwcwx/estimated/conversions.py for the versioned models,
data/migrations/20261112_daily_estimated.sql for the table, and
data/migrations/20261121_daily_estimated_avg.sql to allow type=avg.
Estimates are only merged into reports when the request includes est=1.
"""

from rwcwx.estimated.conversions import VERSION

__all__ = ["VERSION"]

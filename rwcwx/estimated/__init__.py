"""Estimated daily history (Tmax, Tmin, rain) from Pulgas Ridge, with COOP/SFO gap-fill, 2011-01-01 to 2020-12-26.

See rwcwx/estimated/conversions.py for the versioned models, and data/migrations/20261112_daily_estimated.sql
for the table. Estimates are only merged into reports when the request includes est=1.
"""

from rwcwx.estimated.conversions import VERSION

__all__ = ["VERSION"]

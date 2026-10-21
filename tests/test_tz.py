"""Time-zone invariants: these must hold whatever the process TZ is (see conftest.py)."""
import time
from datetime import date, datetime, timezone

import pytest

try:
    from rwcwx.model.sun import local_day_bounds_utc, sun_times
except Exception:  # no dev DB (deploy pre-check): rwcwx.models reflects tables at import; these tests don't query
    import sys
    import types
    sys.modules["rwcwx.models"] = types.SimpleNamespace(db=None, is_api_estimate=lambda comment: False)
    sys.modules.pop("rwcwx.model.sun", None)
    from rwcwx.model.sun import local_day_bounds_utc, sun_times

# NOAA solar calculator, Redwood City (37.470, -122.265), UTC; sun centre at -0.833 deg. Tolerance 3 min.
KNOWN = {
    date(2026, 3, 8): ("14:31", "02:10"),    # US DST starts
    date(2026, 6, 21): ("12:49", "03:34"),
    date(2026, 10, 12): ("14:15", "01:38"),
    date(2026, 11, 1): ("14:35", "01:12"),   # US DST ends
    date(2026, 12, 21): ("15:21", "00:55"),
}


def _utc_hm(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


@pytest.mark.parametrize("d", sorted(KNOWN))
def test_sun_times_absolute_instants(d):
    t = sun_times(d)
    for key, hm in zip(("sunrise", "sunset"), KNOWN[d]):
        got = _utc_hm(t[key])
        h, m = map(int, hm.split(":"))
        want = got.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = abs((got - want).total_seconds())
        diff = min(diff, abs(diff - 86400))
        assert diff < 180, (d, key, got, hm, time.tzname)


def test_local_day_bounds_cover_dst_days():
    a, b = local_day_bounds_utc(date(2026, 3, 8))
    assert (b - a).total_seconds() == 23 * 3600
    a, b = local_day_bounds_utc(date(2026, 11, 1))
    assert (b - a).total_seconds() == 25 * 3600
    a, b = local_day_bounds_utc(date(2026, 10, 12))
    assert a == datetime(2026, 10, 12, 7, 0) and b == datetime(2026, 10, 13, 7, 0)

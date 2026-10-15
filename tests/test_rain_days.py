from types import SimpleNamespace

import pytest

try:
    from rwcwx.calc.avg_extreme import _add_rain_days
except Exception:  # noqa: BLE001
    _add_rain_days = None

needs = pytest.mark.skipif(_add_rain_days is None, reason="MySQL driver unavailable")


@needs
def test_add_rain_days_counts_measurable():
    rains = [
        SimpleNamespace(val=0.0),
        SimpleNamespace(val=0.01),
        SimpleNamespace(val=0.005),
        SimpleNamespace(val=0.2),
        SimpleNamespace(val=None),
    ]
    stats = {}
    _add_rain_days(stats, {("rain", "total"): rains})
    assert stats["rain_days"] == {"count": 2, "of": 5}


@needs
def test_add_rain_days_noop_without_rain():
    stats = {}
    _add_rain_days(stats, {})
    assert "rain_days" not in stats

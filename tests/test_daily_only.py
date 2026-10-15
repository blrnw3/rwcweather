from datetime import date
from types import SimpleNamespace
from unittest import mock

import pytest

from rwcwx.calc.rolling import ROLLING_VARS
from rwcwx.calc.spells import SPELL_VARS

try:  # avg_extreme pulls in the MySQL driver, which the deploy pre-check venv may lack
    from rwcwx.calc import avg_extreme
    from rwcwx.calc.avg_extreme import AvgExtAggregator, DAILY_ONLY_VARS, DayOfYearSummary
except Exception:  # noqa: BLE001 (ImportError, or NameError from MySQLdb)
    avg_extreme = None

needs_avg_extreme = pytest.mark.skipif(avg_extreme is None, reason="MySQL driver unavailable")


def test_wind_direction_has_no_multiday_rankings():
    assert "wdir" not in ROLLING_VARS
    assert not [k for k in SPELL_VARS if k[0] == "wdir"]


@needs_avg_extreme
def test_wind_direction_has_no_monthly_or_annual_summaries():
    ae = SimpleNamespace(d=date(2024, 1, 1), var="wdir", type="avg", simple_dict_={"x": 1})
    assert "wdir" in DAILY_ONLY_VARS
    assert AvgExtAggregator.monthly([ae], "wdir") == []
    assert AvgExtAggregator.annual([ae], "wdir") == []
    assert AvgExtAggregator.daily([ae], "wdir") == [{"x": 1}]


@needs_avg_extreme
def test_day_of_year_summary_cached_per_day():
    DayOfYearSummary._cache.clear()
    with mock.patch.object(avg_extreme.AvgExtQ, "all_for_day_of_year", return_value=[]) as q:
        DayOfYearSummary(date(2026, 10, 14)).stats()
        DayOfYearSummary(date(2026, 10, 14)).stats()
        assert q.call_count == 1
        DayOfYearSummary(date(2026, 10, 15)).stats()
        assert q.call_count == 2
        assert list(DayOfYearSummary._cache) == [date(2026, 10, 15)]
    DayOfYearSummary._cache.clear()

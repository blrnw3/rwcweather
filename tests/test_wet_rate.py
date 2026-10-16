"""Average rain rate when wet (rain / wet hours), derived at query time."""
from datetime import date
from types import SimpleNamespace as NS

import pytest
from rwcwx.wet.rate import period_rate, rate, rate_days


def test_rate_is_blank_without_wet_hours():
    assert rate(0.2, 0) is None and rate(None, 2) is None and rate(0.2, 4) == 0.05


@pytest.mark.skipif(bool(__import__("os").environ.get("RWC_TEST_NO_DB")), reason="period_rate imports avg_extreme (needs MySQL)")
def test_days_and_period_use_total_rain_over_total_wet_hours():
    rain = [NS(d=date(2026, 1, i), val=v) for i, v in ((1, 0.5), (2, 0.1), (3, 0.0))]
    wet = [NS(d=date(2026, 1, i), val=v, cnt=1) for i, v in ((1, 5.0), (2, 0.5), (3, 0.0))]
    days = rate_days(rain, wet)
    assert [x.d.day for x in days] == [2, 1]                     # day 3 has no wet hours: left out
    assert [x.val for x in days] == [0.2, 0.1]
    assert period_rate(days) == round(0.6 / 5.5, 4)
    assert days[0].simple_dict_["w"] == 0.5
    WetRate = pytest.importorskip("rwcwx.calc.avg_extreme").WetRate   # needs the DB models
    s = WetRate.multiday_summary(days)
    assert round(s.avg, 4) == round(0.6 / 5.5, 4) and s.max_val == 0.2 and s.min_val == 0.1


def test_days_with_wet_hours_but_no_rain_have_no_rate():
    from datetime import date
    from types import SimpleNamespace as NS
    d1, d2 = date(2026, 1, 7), date(2026, 1, 8)
    rain = [NS(d=d1, val=0.5), NS(d=d2, val=0.0)]
    wet = [NS(d=d1, val=4.0, cnt=None), NS(d=d2, val=0.5, cnt=None)]
    days = rate_days(rain, wet)
    assert [x.d for x in days] == [d1]
    assert period_rate(days) == 0.125

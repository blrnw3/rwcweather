from datetime import date
from types import SimpleNamespace

from rwcwx.calc.rolling import SEASON_NAMES, next_season, season_bounds, season_of
from rwcwx.calc.spells import spell_grid

try:
    from rwcwx.calc.avg_extreme import AvgExtAggregator, DAILY_ONLY_VARS
except Exception:  # noqa: BLE001
    AvgExtAggregator = None
    DAILY_ONLY_VARS = None

import pytest

needs_avg_extreme = pytest.mark.skipif(AvgExtAggregator is None, reason="MySQL driver unavailable")


def test_season_of_labels_winter_by_the_january_year():
    assert season_of(date(2023, 12, 1)) == (2024, "winter")
    assert season_of(date(2023, 12, 31)) == (2024, "winter")
    assert season_of(date(2024, 1, 1)) == (2024, "winter")
    assert season_of(date(2024, 2, 29)) == (2024, "winter")  # leap year
    assert season_of(date(2023, 2, 28)) == (2023, "winter")
    assert season_of(date(2024, 3, 1)) == (2024, "spring")
    assert season_of(date(2024, 5, 31)) == (2024, "spring")
    assert season_of(date(2024, 6, 1)) == (2024, "summer")
    assert season_of(date(2024, 8, 31)) == (2024, "summer")
    assert season_of(date(2024, 9, 1)) == (2024, "autumn")
    assert season_of(date(2024, 11, 30)) == (2024, "autumn")


def test_season_bounds_include_leap_day_and_preceding_december():
    lo, hi = season_bounds(2024, "winter")
    assert lo == date(2023, 12, 1) and hi == date(2024, 2, 29)
    lo, hi = season_bounds(2023, "winter")
    assert lo == date(2022, 12, 1) and hi == date(2023, 2, 28)
    assert season_bounds(2024, "spring") == (date(2024, 3, 1), date(2024, 5, 31))
    assert season_bounds(2024, "summer") == (date(2024, 6, 1), date(2024, 8, 31))
    assert season_bounds(2024, "autumn") == (date(2024, 9, 1), date(2024, 11, 30))
    assert season_bounds(2024, "fall") == season_bounds(2024, "autumn")


def test_next_season_wraps_autumn_to_the_following_winter():
    assert next_season(2024, "autumn") == (2025, "winter")
    assert next_season(2024, "winter") == (2024, "spring")
    assert SEASON_NAMES == ("winter", "spring", "summer", "autumn")



def test_december_values_group_into_the_following_winter():
    days = [date(2023, 12, 15), date(2023, 12, 31), date(2024, 1, 10), date(2024, 2, 10), date(2024, 3, 10)]
    groups = {}
    for d in days:
        groups.setdefault(season_of(d), []).append(d)
    assert set(groups) == {(2024, "winter"), (2024, "spring")}
    assert len(groups[(2024, "winter")]) == 4
    assert groups[(2024, "spring")] == [date(2024, 3, 10)]


def _grid_row(rows, key):
    for row in rows:
        if row["m"] == key:
            return row
    return None


def dry_span(start, end):
    n = (end - start).days + 1
    from datetime import timedelta
    return [(start + timedelta(days=i), 0) for i in range(n)]


def test_spell_grid_winter_spell_stays_in_one_labelled_season():
    # 20 Dec 2023 – 10 Feb 2024 is entirely Winter 2024 (53 days).
    data = dry_span(date(2023, 12, 20), date(2024, 2, 10))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    winter = _grid_row(g["seasonal"], [2024, "winter"])
    assert winter["val"] == 53
    assert "shared" not in winter
    assert _grid_row(g["seasonal"], [2023, "winter"]) is None
    assert _grid_row(g["seasonal"], [2023, "autumn"]) is None
    assert _grid_row(g["yearly"], 2023)["val"] == 12  # 20–31 Dec, clipped (home is 2024)


def test_spell_grid_autumn_into_winter_home_and_clip():
    # 20 Nov 2023 – 10 Jan 2024: Autumn overlap 11 (20–30 Nov), Winter 41
    # (1 Dec – 10 Jan). Home is Winter 2024 at full length 52; Autumn is clipped to 11.
    data = dry_span(date(2023, 11, 20), date(2024, 1, 10))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    autumn = _grid_row(g["seasonal"], [2023, "autumn"])
    winter = _grid_row(g["seasonal"], [2024, "winter"])
    assert autumn["val"] == 11 and autumn.get("shared") is True
    assert winter["val"] == 52 and winter.get("shared") is True


def test_spell_grid_2024_dry_spell_homes_in_summer():
    # 6 May – 30 Oct 2024, 178 days. Spring 26, Summer 92, Autumn 60.
    # Home is Summer; Spring and Autumn are clipped and starred.
    data = dry_span(date(2024, 5, 6), date(2024, 10, 30))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    spring = _grid_row(g["seasonal"], [2024, "spring"])
    summer = _grid_row(g["seasonal"], [2024, "summer"])
    autumn = _grid_row(g["seasonal"], [2024, "autumn"])
    assert spring["val"] == 26 and spring.get("shared") is True
    assert summer["val"] == 178 and summer.get("shared") is True
    assert autumn["val"] == 60 and autumn.get("shared") is True


def test_spell_grid_contained_summer_spell_is_not_starred():
    data = dry_span(date(2024, 6, 10), date(2024, 7, 20))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    summer = _grid_row(g["seasonal"], [2024, "summer"])
    assert summer["val"] == 41 and "shared" not in summer


def _ae(d, val, estimated=False):
    return SimpleNamespace(d=d, val=val, is_estimated=estimated)


@needs_avg_extreme
def test_seasonal_summaries_put_december_in_the_following_winter():
    # Dec 2023 + Jan/Feb 2024 rain totals belong to Winter 2024, not Winter 2023.
    rows = [
        _ae(date(2023, 12, 15), 1.0),
        _ae(date(2023, 12, 31), 2.0),
        _ae(date(2024, 1, 10), 3.0),
        _ae(date(2024, 2, 10), 4.0),
        _ae(date(2024, 3, 10), 10.0),
    ]
    seasonal = AvgExtAggregator.seasonal(rows, "rain")
    by = {tuple(r["m"]): r["summary"] for r in seasonal}
    assert set(by) == {(2024, "winter"), (2024, "spring")}
    assert by[(2024, "winter")]["total"] == 10.0
    assert by[(2024, "winter")]["count"] == 4
    assert by[(2024, "spring")]["total"] == 10.0
    # December still sits in calendar year 2023 monthly / annual totals.
    monthly = {(r["m"] if not isinstance(r["m"], tuple) else tuple(r["m"])): r for r in AvgExtAggregator.monthly(rows, "rain")}
    # period is (year, month) tuple
    dec = next(r for r in AvgExtAggregator.monthly(rows, "rain") if r["m"] == (2023, 12))
    assert dec["summary"]["total"] == 3.0
    annual = {r["m"]: r["summary"]["total"] for r in AvgExtAggregator.annual(rows, "rain")}
    assert annual[2023] == 3.0
    assert annual[2024] == 17.0


@needs_avg_extreme
def test_all_summaries_includes_seasonal_without_a_second_input_scan_api():
    rows = [_ae(date(2024, 6, 1), 1.0)]
    out = AvgExtAggregator.all_summaries(rows, "rain")
    assert "seasonal" in out and "monthly" in out and "yearly" in out and "daily" in out
    assert out["seasonal"][0]["m"] == [2024, "summer"]
    assert out["seasonal"][0]["summary"]["total"] == 1.0


@needs_avg_extreme
def test_wind_direction_has_no_seasonal_summary():
    assert "wdir" in DAILY_ONLY_VARS
    ae = SimpleNamespace(d=date(2024, 1, 1), var="wdir", type="avg", simple_dict_={"x": 1})
    assert AvgExtAggregator.seasonal([ae], "wdir") == []

from datetime import date, timedelta

from rwcwx.calc.spells import find_spells, spell_grid, spell_ranking, stored_threshold

D0 = date(2024, 1, 1)


def series(vals, start=D0):
    return [(start + timedelta(days=i), v) for i, v in enumerate(vals)]


def test_dry_spells_below_threshold():
    s = find_spells(series([0, 0, 0.2, 0, 0, 0, 0.01, 0]), 0.01, "below")
    assert [(x["start"].day, x["length"]) for x in s] == [(1, 2), (4, 3), (8, 1)]


def test_wet_spells_above_inclusive_and_stats():
    s = find_spells(series([0.01, 0.5, 0, 0.25]), 0.01, "above")
    assert s[0]["length"] == 2 and s[0]["total"] == 0.51 and s[0]["max"] == 0.5 and s[0]["min"] == 0.01
    assert s[1]["length"] == 1


def test_missing_day_breaks_spell():
    data = series([0, 0, None, 0, 0, 0])
    assert [x["length"] for x in find_spells(data, 0.01, "below")] == [2, 3]
    data = [(D0, 0), (D0 + timedelta(days=2), 0)]  # gap: row absent
    assert [x["length"] for x in find_spells(data, 0.01, "below")] == [1, 1]


def test_month_and_season_filter_and_start_year():
    data = series([0] * 70, date(2023, 12, 20))  # 20 Dec 2023 .. 27 Feb 2024
    # Any spell overlapping the month/season is returned in full (not cut at month boundaries).
    assert [x["length"] for x in find_spells(data, 0.01, "below", month=1)] == [70]
    assert [x["length"] for x in find_spells(data, 0.01, "below", month="winter")] == [70]
    assert find_spells(data, 0.01, "below", month="summer") == []
    assert find_spells(data, 0.01, "below", start_year=2024)[0]["start"] == date(2024, 1, 1)


def test_fahrenheit_thresholds():
    assert abs(stored_threshold("temp", "max", 90) - 32.2222) < 1e-3
    assert stored_threshold("rain", "total", 0.5) == 0.5
    r = spell_ranking(series([32.3, 32.3, 31.0, 33]), "temp", "max", 90, "above")
    assert [x["length"] for x in r["result"]] == [2, 1]


def test_ranking_order_ties_most_recent_first_and_limit():
    r = spell_ranking(series([0, 1, 0, 1, 0, 0]), "rain", "total", 0.01, "below", limit=2)
    assert [(x["start"][2], x["length"]) for x in r["result"]] == [(5, 2), (3, 1)]
    assert r["found"] == 3 and r["stat"] == "total"


def test_current_dry_spell_includes_today():
    today = D0 + timedelta(days=4)
    r = spell_ranking(series([0, 0, 0, 1, 0]), "rain", "total", 0.01, "below", today=today)
    assert r["current"]["length"] == 1 and r["current"]["status"] == "today" and r["current"]["rank"] == 2


def test_current_wet_spell_pending_today():
    today = D0 + timedelta(days=3)
    r = spell_ranking(series([0, 0.3, 0.2, 0]), "rain", "total", 0.1, "above", today=today)
    assert r["current"]["length"] == 2 and r["current"]["status"] == "pending"
    # A dry spell broken by today's rain isn't running
    r = spell_ranking(series([0, 0, 0, 0.5]), "rain", "total", 0.01, "below", today=today)
    assert r["current"] is None


def test_temperature_stops_at_yesterday():
    today = D0 + timedelta(days=3)
    r = spell_ranking(series([33, 33, 33, 10]), "temp", "max", 90, "above", today=today)
    assert r["result"][0]["length"] == 3 and r["current"]["length"] == 3 and r["current"]["status"] == "yesterday"


def test_celsius_thresholds_accepted_as_fahrenheit():
    from rwcwx.calc.spells import SPELL_VARS
    assert 86 in SPELL_VARS[("temp", "max")]["thresholds"]  # 30 °C
    assert 95 in SPELL_VARS[("temp", "max")]["thresholds"]  # 35 °C
    assert {32, 41, 50, 59} <= set(SPELL_VARS[("temp", "min")]["thresholds"])
    assert abs(stored_threshold("temp", "max", 86) - 30) < 1e-9


def test_metric_rain_thresholds_accepted_as_inches():
    from rwcwx.calc.spells import SPELL_VARS
    rain_thresholds = set(SPELL_VARS[("rain", "total")]["thresholds"])
    for mm in (0.2, 2, 5, 10, 25):
        inch_val = round(mm / 25.4, 4)
        assert inch_val in rain_thresholds
        assert stored_threshold("rain", "total", inch_val) == inch_val



def _grid_val(rows, key):
    for row in rows:
        if row["m"] == key or (isinstance(key, list) and row["m"] == key):
            return row["val"]
    return None


def _grid_row(rows, key):
    for row in rows:
        if row["m"] == key or (isinstance(key, list) and row["m"] == key):
            return row
    return None


def test_spell_grid_dec_jan_assigned_by_midpoint():
    # 20 Dec 2023 – 10 Jan 2024: 22 dry days. Midpoint = 20 Dec + 10 = 30 Dec,
    # so the full 22-day length goes to December / 2023 / WY2024, not January.
    data = series([0] * 22, date(2023, 12, 20))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2023, 12]) == 22
    assert _grid_val(g["monthly"], [2024, 1]) == 0
    assert _grid_val(g["yearly"], 2023) == 22
    assert _grid_val(g["yearly"], 2024) == 0
    assert _grid_val(g["wateryear"], 2024) == 22
    assert _grid_val(g["wateryear"], 2025) is None


def test_spell_grid_covers_a_whole_month_at_full_length():
    # 20 May – 10 July 2024: 52 days, midpoint = 20 May + 25 = 14 June.
    # June is fully covered, so it gets the full 52, not 30. May and July do not.
    data = series([0] * 52, date(2024, 5, 20))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 5]) == 0
    assert _grid_val(g["monthly"], [2024, 6]) == 52
    assert _grid_val(g["monthly"], [2024, 7]) == 0
    assert _grid_val(g["yearly"], 2024) == 52


def test_spell_grid_even_length_midpoint_is_the_earlier_middle_day():
    # 4-day run 30 Jan – 2 Feb: midpoint = 30 Jan + 1 = 31 Jan -> January.
    data = series([0] * 4, date(2024, 1, 30))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 4
    assert _grid_val(g["monthly"], [2024, 2]) == 0
    # 4-day run 31 Jan – 3 Feb: midpoint = 31 Jan + 1 = 1 Feb -> February.
    data = series([0] * 4, date(2024, 1, 31))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 0
    assert _grid_val(g["monthly"], [2024, 2]) == 4
    # 2-day run 31 Jan – 1 Feb: midpoint = 31 Jan -> January.
    data = series([0] * 2, date(2024, 1, 31))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 2
    assert _grid_val(g["monthly"], [2024, 2]) == 0


def test_spell_grid_water_year_boundary_follows_midpoint():
    # 25 Sep – 10 Oct 2024: 16 days, midpoint = 25 Sep + 7 = 2 Oct, in WY2025.
    data = series([0] * 16, date(2024, 9, 25))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 9]) == 0
    assert _grid_val(g["monthly"], [2024, 10]) == 16
    assert _grid_val(g["yearly"], 2024) == 16
    assert _grid_val(g["wateryear"], 2024) == 0
    assert _grid_val(g["wateryear"], 2025) == 16


def test_spell_grid_zero_when_month_has_data_but_no_match():
    data = series([1, 1, 1], date(2024, 1, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 0
    assert _grid_val(g["yearly"], 2024) == 0
    # A month with no rows at all is omitted (not a zero).
    assert _grid_val(g["monthly"], [2024, 2]) is None


def test_spell_grid_picks_longest_qualifying_spell_in_the_month():
    # Jan 1-3 dry, Jan 5-20 dry (16 days), then a 5-day run from 31 Jan into February
    # (midpoint 2 Feb, so February gets the full 5). Longest in January is 16.
    vals = [0, 0, 0, 1] + [0] * 16 + [1] * 10 + [0] * 5  # Jan 1 .. Feb 4
    data = series(vals, date(2024, 1, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 16
    assert _grid_val(g["monthly"], [2024, 2]) == 5
    assert _grid_val(g["yearly"], 2024) == 16


def test_spell_grid_temperature_excludes_today():
    today = date(2024, 1, 4)
    data = series([33, 33, 33, 33], date(2024, 1, 1))  # 33 °C is above 90 °F
    g = spell_grid(data, "temp", "max", 90, "above", today=today)
    assert _grid_val(g["monthly"], [2024, 1]) == 3


def test_spell_grid_rain_includes_today():
    today = date(2024, 1, 4)
    data = series([0, 0, 0, 0], date(2024, 1, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below", today=today)
    assert _grid_val(g["monthly"], [2024, 1]) == 4


def test_spell_grid_est_flag_only_when_max_run_includes_estimated_day():
    data = series([0] * 5 + [1] + [0] * 2, date(2024, 1, 1))
    # Longest is Jan 1–5; an estimated day on the short later run should not flag the month.
    g = spell_grid(data, "rain", "total", 0.01, "below", est_dates={date(2024, 1, 7)})
    jan = next(r for r in g["monthly"] if r["m"] == [2024, 1])
    assert jan["val"] == 5
    assert "est" not in jan
    # An estimated day inside the longest run does flag the cell.
    g = spell_grid(data, "rain", "total", 0.01, "below", est_dates={date(2024, 1, 2)})
    jan = next(r for r in g["monthly"] if r["m"] == [2024, 1])
    assert jan["val"] == 5 and jan.get("est") is True


def test_spell_grid_ongoing_spell_counts_current_length_and_covers_period_to_date():
    # Still running on 20 Nov: 1 Oct – 20 Nov is 51 days, midpoint = 1 Oct + 25 = 26 Oct.
    # October is fully covered (complete month) and November-to-date is fully covered,
    # so both cells get the current length, 51.
    today = date(2024, 11, 20)
    data = series([0] * 51, date(2024, 10, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below", today=today)
    assert _grid_val(g["monthly"], [2024, 10]) == 51
    assert _grid_val(g["monthly"], [2024, 11]) == 51
    assert _grid_val(g["yearly"], 2024) == 51
    assert _grid_val(g["wateryear"], 2025) == 51
    # A run that only starts mid-October does not cover October and has its midpoint
    # in November, so only November (in progress) gets the current length.
    data = series([0] * 37, date(2024, 10, 15))  # 15 Oct – 20 Nov
    g = spell_grid(data, "rain", "total", 0.01, "below", today=today)
    assert _grid_val(g["monthly"], [2024, 10]) == 0
    assert _grid_val(g["monthly"], [2024, 11]) == 37


def test_spell_grid_water_year_status_and_note():
    data = series([0] * 10, date(2024, 10, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below", today=date(2024, 10, 15))
    wy = next(r for r in g["wateryear"] if r["m"] == 2025)
    assert wy["val"] == 10 and wy["status"] == "current"
    assert wy["note"] == "WY2025 to date: 1 Oct 2024 – 15 Oct 2024"

    # A mid-year start after 1 Oct is a partial water year once that year has ended.
    data = series([0] * 5, date(2020, 12, 27))
    g = spell_grid(data, "rain", "total", 0.01, "below", today=date(2022, 1, 1))
    wy = next(r for r in g["wateryear"] if r["m"] == 2021)
    assert wy["status"] == "partial"
    assert wy["note"] == "WY2021 partial: records start 27 Dec 2020"



def test_spell_grid_shared_when_same_spell_counts_in_several_months():
    # 20 May – 10 July 2024: only June qualifies (fully covered), so June is not shared.
    data = series([0] * 52, date(2024, 5, 20))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_row(g["monthly"], [2024, 6])["val"] == 52
    assert "shared" not in _grid_row(g["monthly"], [2024, 6])
    assert "shared" not in (_grid_row(g["monthly"], [2024, 5]) or {})
    assert "shared" not in (_grid_row(g["monthly"], [2024, 7]) or {})

    # 1 May – 31 July 2024 fully covers May, June and July (92 days, midpoint 15 June).
    data = series([0] * 92, date(2024, 5, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    for month in (5, 6, 7):
        row = _grid_row(g["monthly"], [2024, month])
        assert row["val"] == 92 and row.get("shared") is True
    # The year is only 2024, so the annual cell is not shared.
    assert _grid_row(g["yearly"], 2024)["val"] == 92
    assert "shared" not in _grid_row(g["yearly"], 2024)


def test_spell_grid_midpoint_only_month_is_not_shared():
    # 20 Dec 2023 – 10 Jan 2024 goes only to December (midpoint 30 Dec). January is 0, not starred.
    data = series([0] * 22, date(2023, 12, 20))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_row(g["monthly"], [2023, 12])["val"] == 22
    assert "shared" not in _grid_row(g["monthly"], [2023, 12])
    assert _grid_row(g["monthly"], [2024, 1])["val"] == 0
    assert "shared" not in _grid_row(g["monthly"], [2024, 1])
    assert "shared" not in _grid_row(g["yearly"], 2023)
    assert "shared" not in _grid_row(g["yearly"], 2024)


def test_spell_grid_shared_across_calendar_years():
    # 1 Jan 2023 – 31 Dec 2024 fully covers both calendar years.
    data = series([0] * 731, date(2023, 1, 1))  # 2024 is a leap year
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_row(g["yearly"], 2023)["val"] == 731 and _grid_row(g["yearly"], 2023).get("shared") is True
    assert _grid_row(g["yearly"], 2024)["val"] == 731 and _grid_row(g["yearly"], 2024).get("shared") is True


def test_spell_grid_shared_across_water_years():
    # 1 Oct 2022 – 30 Sep 2024 fully covers WY2023 and WY2024.
    data = series([0] * 731, date(2022, 10, 1))  # includes 29 Feb 2024
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_row(g["wateryear"], 2023)["val"] == 731 and _grid_row(g["wateryear"], 2023).get("shared") is True
    assert _grid_row(g["wateryear"], 2024)["val"] == 731 and _grid_row(g["wateryear"], 2024).get("shared") is True


def test_spell_grid_ongoing_spell_shared_across_months():
    # 1 Oct – 20 Nov, still running: both October and November-to-date get 51, so both are shared.
    data = series([0] * 51, date(2024, 10, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below", today=date(2024, 11, 20))
    assert _grid_row(g["monthly"], [2024, 10]).get("shared") is True
    assert _grid_row(g["monthly"], [2024, 11]).get("shared") is True
    assert _grid_row(g["monthly"], [2024, 10])["val"] == 51
    # Only one calendar year / water year is involved.
    assert "shared" not in _grid_row(g["yearly"], 2024)
    assert "shared" not in _grid_row(g["wateryear"], 2025)

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
    # 1 mm and 2.5 mm are the current metric options; 2 mm remains accepted for older links.
    for mm in (0.2, 1, 2, 2.5, 5, 10, 25):
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


def _shared(row):
    return bool(row and row.get("shared"))


def dry_span(start, end):
    """Inclusive dry (0) series from start to end."""
    n = (end - start).days + 1
    return series([0] * n, start)


def test_spell_grid_jan_feb_example_full_in_home_clipped_elsewhere():
    # 25 Jan – 14 Feb 2024: 21 days. February has more overlap (14 vs 7), so
    # February gets the full length and January only the days inside January.
    data = dry_span(date(2024, 1, 25), date(2024, 2, 14))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    jan, feb = _grid_row(g["monthly"], [2024, 1]), _grid_row(g["monthly"], [2024, 2])
    assert jan["val"] == 7 and _shared(jan)
    assert feb["val"] == 21 and _shared(feb)
    assert _grid_val(g["yearly"], 2024) == 21
    assert "shared" not in _grid_row(g["yearly"], 2024)

    # A longer spell wholly in January wins that cell; no asterisk (it does not cross).
    vals = [0] * 10 + [1] * 14 + [0] * 21  # 1–10 Jan dry, 11–24 wet, 25 Jan – 14 Feb dry
    g = spell_grid(series(vals, date(2024, 1, 1)), "rain", "total", 0.01, "below")
    jan, feb = _grid_row(g["monthly"], [2024, 1]), _grid_row(g["monthly"], [2024, 2])
    assert jan["val"] == 10 and not _shared(jan)
    assert feb["val"] == 21 and _shared(feb)


def test_spell_grid_tie_break_is_the_month_containing_the_midpoint():
    # Equal overlap (10 and 10), 22 Jan – 10 Feb. Midpoint = 22 Jan + 9 = 31 Jan,
    # so January is the home and shows the full 20; February is clipped to 10.
    data = dry_span(date(2024, 1, 22), date(2024, 2, 10))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    jan, feb = _grid_row(g["monthly"], [2024, 1]), _grid_row(g["monthly"], [2024, 2])
    assert jan["val"] == 20 and _shared(jan)
    assert feb["val"] == 10 and _shared(feb)

    # 1 Jun – 31 Aug: June 30, July 31, August 31. July and August tie; midpoint
    # = 1 Jun + 45 = 16 July, so July is home (full 92) and August is clipped to 31.
    data = dry_span(date(2024, 6, 1), date(2024, 8, 31))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    jun, jul, aug = (_grid_row(g["monthly"], [2024, 6]),
                     _grid_row(g["monthly"], [2024, 7]),
                     _grid_row(g["monthly"], [2024, 8]))
    assert jun["val"] == 30 and _shared(jun)
    assert jul["val"] == 92 and _shared(jul)
    assert aug["val"] == 31 and _shared(aug)
    assert _grid_val(g["yearly"], 2024) == 92
    assert "shared" not in _grid_row(g["yearly"], 2024)


def test_spell_grid_2021_193_day_dry_spell_home_is_july():
    # 7 Apr – 16 Oct 2021 is 193 days. Overlap: Apr 24, May 31, Jun 30, Jul 31,
    # Aug 31, Sep 30, Oct 16. May/Jul/Aug tie at 31; midpoint = 7 Apr + 96 = 12 Jul,
    # so July is the home and shows 193. Other months are clipped to their overlap.
    data = dry_span(date(2021, 4, 7), date(2021, 10, 16))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    expected = {(2021, 4): 24, (2021, 5): 31, (2021, 6): 30, (2021, 7): 193,
                (2021, 8): 31, (2021, 9): 30, (2021, 10): 16}
    for (y, m), val in expected.items():
        row = _grid_row(g["monthly"], [y, m])
        assert row["val"] == val and _shared(row), (m, row)
    annual = _grid_row(g["yearly"], 2021)
    assert annual["val"] == 193 and not _shared(annual)
    wy2021, wy2022 = _grid_row(g["wateryear"], 2021), _grid_row(g["wateryear"], 2022)
    assert wy2021["val"] == 193 and _shared(wy2021)  # continues into October (WY2022)
    assert wy2022["val"] == 16 and _shared(wy2022)


def test_spell_grid_may_2024_dry_spell_is_clipped_in_may():
    # Real 2024 dry spell: 6 May – 30 Oct (178 days). Overlap: May 26, Jun 30,
    # Jul 31, Aug 31, Sep 30, Oct 30. July and August tie at 31; midpoint =
    # 6 May + 88 = 2 Aug, so August is home (178) and May shows the 26 days
    # inside May, not 0.
    data = dry_span(date(2024, 5, 6), date(2024, 10, 30))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    expected = {(2024, 5): 26, (2024, 6): 30, (2024, 7): 31, (2024, 8): 178,
                (2024, 9): 30, (2024, 10): 30}
    for (y, m), val in expected.items():
        row = _grid_row(g["monthly"], [y, m])
        assert row["val"] == val and _shared(row), (m, row)
    annual = _grid_row(g["yearly"], 2024)
    assert annual["val"] == 178 and not _shared(annual)
    wy2024, wy2025 = _grid_row(g["wateryear"], 2024), _grid_row(g["wateryear"], 2025)
    assert wy2024["val"] == 178 and _shared(wy2024)
    assert wy2025["val"] == 30 and _shared(wy2025)


def test_spell_grid_dec_jan_home_december_january_clipped():
    # 20 Dec 2023 – 10 Jan 2024: 22 days. December overlap 12 > January 10, so
    # December / 2023 get the full 22; January / 2024 are clipped to 10.
    data = dry_span(date(2023, 12, 20), date(2024, 1, 10))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    dec, jan = _grid_row(g["monthly"], [2023, 12]), _grid_row(g["monthly"], [2024, 1])
    assert dec["val"] == 22 and _shared(dec)
    assert jan["val"] == 10 and _shared(jan)
    y2023, y2024 = _grid_row(g["yearly"], 2023), _grid_row(g["yearly"], 2024)
    assert y2023["val"] == 22 and _shared(y2023)
    assert y2024["val"] == 10 and _shared(y2024)
    # The whole spell sits inside WY2024 (1 Oct 2023 – 30 Sep 2024).
    assert _grid_val(g["wateryear"], 2024) == 22
    assert "shared" not in _grid_row(g["wateryear"], 2024)
    assert _grid_val(g["wateryear"], 2025) is None


def test_spell_grid_even_length_tie_uses_earlier_middle_day():
    # 4-day run 30 Jan – 2 Feb: overlap 2 and 2. Midpoint = 30 Jan + 1 = 31 Jan
    # -> January is home.
    data = dry_span(date(2024, 1, 30), date(2024, 2, 2))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 4 and _shared(_grid_row(g["monthly"], [2024, 1]))
    assert _grid_val(g["monthly"], [2024, 2]) == 2 and _shared(_grid_row(g["monthly"], [2024, 2]))
    # 4-day run 31 Jan – 3 Feb: January overlap 1 < February 3, so February is home.
    data = dry_span(date(2024, 1, 31), date(2024, 2, 3))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 1 and _shared(_grid_row(g["monthly"], [2024, 1]))
    assert _grid_val(g["monthly"], [2024, 2]) == 4 and _shared(_grid_row(g["monthly"], [2024, 2]))
    # 2-day run 31 Jan – 1 Feb: overlap 1 and 1. Midpoint = 31 Jan -> January is home.
    data = dry_span(date(2024, 1, 31), date(2024, 2, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 2 and _shared(_grid_row(g["monthly"], [2024, 1]))
    assert _grid_val(g["monthly"], [2024, 2]) == 1 and _shared(_grid_row(g["monthly"], [2024, 2]))


def test_spell_grid_water_year_home_by_overlap():
    # 25 Sep – 10 Oct 2024: 16 days. October overlap 10 > September 6, so October
    # / WY2025 get the full 16; September / WY2024 are clipped to 6. The spell
    # stays inside calendar 2024, so the annual cell is not starred.
    data = dry_span(date(2024, 9, 25), date(2024, 10, 10))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    sep, oct_ = _grid_row(g["monthly"], [2024, 9]), _grid_row(g["monthly"], [2024, 10])
    assert sep["val"] == 6 and _shared(sep)
    assert oct_["val"] == 16 and _shared(oct_)
    assert _grid_val(g["yearly"], 2024) == 16
    assert "shared" not in _grid_row(g["yearly"], 2024)
    wy2024, wy2025 = _grid_row(g["wateryear"], 2024), _grid_row(g["wateryear"], 2025)
    assert wy2024["val"] == 6 and _shared(wy2024)
    assert wy2025["val"] == 16 and _shared(wy2025)


def test_spell_grid_zero_when_month_has_data_but_no_match():
    data = series([1, 1, 1], date(2024, 1, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    assert _grid_val(g["monthly"], [2024, 1]) == 0
    assert "shared" not in _grid_row(g["monthly"], [2024, 1])
    assert _grid_val(g["yearly"], 2024) == 0
    assert _grid_val(g["monthly"], [2024, 2]) is None


def test_spell_grid_picks_longest_candidate_in_the_month():
    # Jan 1-3 dry, Jan 5-20 dry (16 days, contained), then a 5-day run from 31 Jan
    # into February (home February). January keeps 16; the one clipped day does not win.
    vals = [0, 0, 0, 1] + [0] * 16 + [1] * 10 + [0] * 5  # Jan 1 .. Feb 4
    data = series(vals, date(2024, 1, 1))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    jan, feb = _grid_row(g["monthly"], [2024, 1]), _grid_row(g["monthly"], [2024, 2])
    assert jan["val"] == 16 and not _shared(jan)
    assert feb["val"] == 5 and _shared(feb)
    assert _grid_val(g["yearly"], 2024) == 16
    assert "shared" not in _grid_row(g["yearly"], 2024)


def test_spell_grid_contained_spell_is_not_starred():
    data = dry_span(date(2024, 1, 5), date(2024, 1, 14))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    jan = _grid_row(g["monthly"], [2024, 1])
    assert jan["val"] == 10 and not _shared(jan)
    assert "shared" not in _grid_row(g["yearly"], 2024)


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


def test_spell_grid_ongoing_spell_counts_current_length():
    # Still running on 20 Nov: 1 Oct – 20 Nov is 51 days. October overlap 31 >
    # November-to-date 20, so October is home (full 51) and November is clipped to 20.
    today = date(2024, 11, 20)
    data = dry_span(date(2024, 10, 1), date(2024, 11, 20))
    g = spell_grid(data, "rain", "total", 0.01, "below", today=today)
    oct_, nov = _grid_row(g["monthly"], [2024, 10]), _grid_row(g["monthly"], [2024, 11])
    assert oct_["val"] == 51 and _shared(oct_)
    assert nov["val"] == 20 and _shared(nov)
    assert _grid_val(g["yearly"], 2024) == 51
    assert "shared" not in _grid_row(g["yearly"], 2024)
    assert _grid_val(g["wateryear"], 2025) == 51
    assert "shared" not in _grid_row(g["wateryear"], 2025)

    # 15 Oct – 20 Nov (37 days): November-to-date 20 > October 17, so November is
    # home (full 37) and October is clipped to 17.
    data = dry_span(date(2024, 10, 15), date(2024, 11, 20))
    g = spell_grid(data, "rain", "total", 0.01, "below", today=today)
    oct_, nov = _grid_row(g["monthly"], [2024, 10]), _grid_row(g["monthly"], [2024, 11])
    assert oct_["val"] == 17 and _shared(oct_)
    assert nov["val"] == 37 and _shared(nov)


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


def test_spell_grid_shared_across_calendar_years():
    # 1 Jan 2023 – 31 Dec 2024 (731 days; 2024 is a leap year). 2024 overlap 366
    # > 2023 overlap 365, so 2024 is home at full length and 2023 is clipped.
    data = dry_span(date(2023, 1, 1), date(2024, 12, 31))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    y2023, y2024 = _grid_row(g["yearly"], 2023), _grid_row(g["yearly"], 2024)
    assert y2023["val"] == 365 and _shared(y2023)
    assert y2024["val"] == 731 and _shared(y2024)


def test_spell_grid_shared_across_water_years():
    # 1 Oct 2022 – 30 Sep 2024 (731 days, including 29 Feb 2024). WY2024 overlap
    # 366 > WY2023 overlap 365, so WY2024 is home at full length and WY2023 is clipped.
    data = dry_span(date(2022, 10, 1), date(2024, 9, 30))
    g = spell_grid(data, "rain", "total", 0.01, "below")
    wy2023, wy2024 = _grid_row(g["wateryear"], 2023), _grid_row(g["wateryear"], 2024)
    assert wy2023["val"] == 365 and _shared(wy2023)
    assert wy2024["val"] == 731 and _shared(wy2024)

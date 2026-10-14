from datetime import date, timedelta

from rwcwx.calc.spells import find_spells, spell_ranking, stored_threshold

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


def test_month_filter_and_start_year():
    data = series([0] * 70, date(2023, 12, 20))  # 20 Dec 2023 .. 27 Feb 2024
    assert [x["length"] for x in find_spells(data, 0.01, "below", month=1)] == [31]
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

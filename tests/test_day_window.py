from rwcwx.calc.day_window import (
    WINDOW_RADIUS, filter_daily_dates, format_mmdd, matches_day_window, md_set, parse_mmdd,
)


def test_parse_and_format_mmdd():
    assert parse_mmdd("1015") == (10, 15)
    assert parse_mmdd("0229") == (2, 29)
    assert parse_mmdd("0230") is None
    assert parse_mmdd("0001") is None
    assert parse_mmdd("101") is None
    assert format_mmdd(10, 5) == "1005"


def test_oct15_window_10():
    days = md_set(10, 15, WINDOW_RADIUS[10])
    assert len(days) == 11
    assert (10, 10) in days and (10, 15) in days and (10, 20) in days
    assert (10, 9) not in days and (10, 21) not in days


def test_year_wrap_around_new_year():
    days = md_set(12, 28, 5)
    assert (12, 23) in days and (12, 31) in days
    assert (1, 1) in days and (1, 2) in days
    assert (1, 3) not in days and (12, 22) not in days


def test_feb29_centre_and_neighbours():
    days = md_set(2, 29, 2)
    assert (2, 27) in days and (2, 28) in days and (2, 29) in days
    assert (3, 1) in days and (3, 2) in days
    # Non-leap-year rows still match the non-29 members.
    assert matches_day_window(2, 28, 2, 29, 10)
    # Mar 1 ±5 on a leap calendar is Feb 25 – Mar 6, so Feb 29 is included; non-leap years just omit that day.
    assert matches_day_window(2, 29, 3, 1, 10)


def test_filter_daily_dates():
    rows = [(2024, 10, 15), (2023, 10, 12), (2022, 10, 21), (2021, 1, 1)]
    assert filter_daily_dates(rows, "1015", 10) == [(2024, 10, 15), (2023, 10, 12)]
    assert filter_daily_dates(rows, "1015", 0) == rows  # unknown window = no filter
    assert filter_daily_dates(rows, "bad", 10) == rows

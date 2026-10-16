"""Daylight change vs yesterday: sign, magnitude, and DST transition days (local day is 23/25h long)."""
from datetime import date

import pytest

from rwcwx.sun import daylight as sun


def test_daylight_s_reasonable():
    assert 14 * 3600 < sun.daylight_s(date(2026, 6, 21)) < 15 * 3600
    assert 9 * 3600 < sun.daylight_s(date(2026, 12, 21)) < 10 * 3600


def test_change_sign_by_season():
    assert sun.daylight_change_s(date(2026, 3, 20)) > 0     # spring: lengthening (~+2m)
    assert sun.daylight_change_s(date(2026, 10, 16)) < 0    # autumn: shortening (~-2m)
    assert 60 < sun.daylight_change_s(date(2026, 3, 20)) < 180
    assert -180 < sun.daylight_change_s(date(2026, 10, 16)) < -60


def test_solstice_change_tiny():
    assert abs(sun.daylight_change_s(date(2026, 6, 21))) < 15
    assert abs(sun.daylight_change_s(date(2026, 12, 21))) < 15


@pytest.mark.parametrize("d", [date(2026, 3, 8), date(2026, 3, 9), date(2026, 11, 1), date(2026, 11, 2)])
def test_dst_days_not_skewed_by_clock_change(d):
    # A naive local-clock diff would be off by ~3600s on DST days; real change is ~1-2 minutes.
    ch = sun.daylight_change_s(d)
    assert 30 < abs(ch) < 180
    assert (ch > 0) == (d.month == 3)


def test_change_is_diff_of_lengths():
    d = date(2026, 10, 16)
    assert sun.daylight_change_s(d) == sun.daylight_s(d) - sun.daylight_s(date(2026, 10, 15))

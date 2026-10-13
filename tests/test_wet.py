"""Derived wet minutes from rain tips (rwcwx/wet/rules.py)."""
from datetime import date, datetime, timedelta

from rwcwx.wet.rules import find_tips, spells_from_tips, wet_day

D = date(2026, 1, 15)                     # PST: local midnight = 08:00 UTC
T0 = datetime(2026, 1, 15, 8, 0)


def series(tips_at, minutes=24 * 60, start=T0, gaps=()):
    """Minute rows for the local day; tips_at = {minute offset: inches}; gaps = [(from, to)) offsets with no rows."""
    rows, total = [], 0.0
    for i in range(-120, minutes + 120):
        if any(a <= i < b for a, b in gaps):
            total += tips_at.get(i, 0)
            continue
        if i % 1440 == 0:
            total = 0.0                   # midnight reset
        total += tips_at.get(i, 0)
        rows.append((start + timedelta(minutes=i), round(total, 2)))
    return rows


def test_no_rain_is_dry():
    wd = wet_day(D, series({}))
    assert wd.wet_min == 0 and wd.spells == [] and wd.observed_min == 24 * 60


def test_lone_tip_counts_30_minutes():
    wd = wet_day(D, series({600: 0.01}))
    assert wd.wet_min == 30
    assert wd.spells[0].lone


def test_spell_is_30_before_first_to_30_after_last():
    wd = wet_day(D, series({600: 0.01, 620: 0.01, 650: 0.02}))
    assert len(wd.spells) == 1
    assert wd.wet_min == (650 + 30) - (600 - 30)
    assert wd.rain == 0.04


def test_tips_up_to_an_hour_apart_join_and_longer_split():
    assert len(wet_day(D, series({600: 0.01, 660: 0.01})).spells) == 1
    wd = wet_day(D, series({600: 0.01, 661: 0.01, 662: 0.01}))
    assert len(wd.spells) == 2
    assert wd.wet_min == 30 + (662 + 30 - (661 - 30))


def test_tip_after_data_gap_is_unknown_and_gap_is_not_wet():
    wd = wet_day(D, series({700: 0.05}, gaps=[(640, 700)]))
    assert wd.unknown_tips == 1 and wd.wet_min == 0
    assert wd.observed_min == 24 * 60 - 60


def test_spell_minutes_in_gap_are_not_wet():
    wd = wet_day(D, series({600: 0.01, 630: 0.01, 660: 0.01}, gaps=[(605, 625)]))
    assert wd.wet_min == (660 + 30 - 570) - 20


def test_midnight_reset_is_not_a_tip_and_lead_in_is_clipped_to_the_day():
    rows = series({10: 0.01, 20: 0.01})
    wd = wet_day(D, rows)
    assert wd.wet_min == 50                # 00:00-00:50; the lead-in before midnight belongs to yesterday
    yest = wet_day(D - timedelta(days=1), rows)
    assert yest.wet_min == 20 and yest.rain == 0


def test_find_tips_counts_multi_tip_minutes():
    tips, unknown = find_tips(series({300: 0.03}))
    assert [round(t.amount, 2) for t in tips] == [0.03] and not unknown
    assert not spells_from_tips(tips)[0].lone

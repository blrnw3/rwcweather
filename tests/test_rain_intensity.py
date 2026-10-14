"""Daily max 10 / 60-minute rain from gauge tips (rwcwx/wet/intensity.py)."""
from datetime import date, datetime, timedelta

from rwcwx.wet.intensity import day_intensity, max_window
from rwcwx.wet.rules import Tip

D = date(2026, 1, 15)
T0 = datetime(2026, 1, 15, 8, 0)          # local midnight (PST) in UTC


def rows(tips_at, gaps=()):
    out, total = [], 0.0
    for i in range(-30, 24 * 60 + 30):
        if i % 1440 == 0:
            total = 0.0
        total += tips_at.get(i, 0)
        if not any(a <= i < b for a, b in gaps):
            out.append((T0 + timedelta(minutes=i), round(total, 2)))
    return out


def test_window_sums_and_time_reached():
    tips = [Tip(T0 + timedelta(minutes=m), a) for m, a in ((0, 0.01), (5, 0.02), (9, 0.01), (10, 0.01), (70, 0.03))]
    assert max_window(tips, 10) == (0.04, T0 + timedelta(minutes=9))    # first reached at 0:09 (0.01+0.02+0.01)
    assert max_window(tips, 60)[0] == 0.05


def test_day_values_reset_and_gaps():
    r = day_intensity(D, rows({100: 0.02, 105: 0.03, 140: 0.05, 600: 0.2}, gaps=[(560, 600)]))
    assert r["rain10"][0] == 0.05 and r["rain60"][0] == 0.1           # the 0.2 lump after a gap is left out
    assert r["rain60"][1] == T0 + timedelta(minutes=140)
    assert day_intensity(D, rows({}))["rain10"] == (0.0, None)
    # yesterday's total before midnight doesn't count as a tip after the reset
    assert day_intensity(D, rows({-10: 0.3, 5: 0.01}))["rain10"][0] == 0.01


def test_single_minute_spike_is_not_rain():
    assert day_intensity(D, rows({100: 0.01, 101: 0.57}))["rain10"][0] == 0.01

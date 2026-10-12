"""Short no-data gaps are interpolated (rules.fill_short_gaps, step 6)."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.sun.rules import MAX_GAP_MIN, Frame, Minute, classify_day, fill_short_gaps  # noqa: E402

T0 = datetime(2026, 10, 12, 18, 0)


def _grid(values, gap_flag="glitch"):
    g = []
    for i, v in enumerate(values):
        m = Minute(t=T0 + timedelta(minutes=i), w=1.0, el=40.0, value=v)
        if v is None:
            m.flags.add(gap_flag)
        g.append(m)
    return g


def test_same_state_both_sides_is_filled():
    g = _grid([1] * 5 + [None] * 13 + [1] * 5)
    assert fill_short_gaps(g) == 13
    assert all(m.value == 1 for m in g)
    assert all({"glitch", "interp"} <= m.flags for m in g[5:18])
    assert not any("interp" in m.flags for m in g[:5] + g[18:])


def test_different_states_split_at_midpoint():
    g = _grid([1] * 3 + [None] * 4 + [0] * 3)
    fill_short_gaps(g)
    assert [m.value for m in g[3:7]] == [1, 1, 0, 0]
    g = _grid([0] * 3 + [None] * 5 + [1] * 3)
    fill_short_gaps(g)
    assert [m.value for m in g[3:8]] == [0, 0, 0, 1, 1]


def test_long_gap_and_edges_stay_unknown():
    g = _grid([1] * 3 + [None] * (MAX_GAP_MIN + 1) + [1] * 3)
    assert fill_short_gaps(g) == 0
    g = _grid([None] * 5 + [1] * 10 + [None] * 5, gap_flag="missing")
    assert fill_short_gaps(g) == 0
    assert g[0].value is None and g[-1].value is None


def test_exactly_max_gap_is_filled():
    g = _grid([0] * 2 + [None] * MAX_GAP_MIN + [0] * 2, gap_flag="stale")
    assert fill_short_gaps(g) == MAX_GAP_MIN


def test_classify_day_fills_a_glitch_burst():
    sunrise, sunset = T0, T0 + timedelta(hours=2)
    frames = [Frame(t=T0 + timedelta(minutes=i), p=0.95, ps=0.9, smean=0.5,
                    glitch=(30 <= i < 43)) for i in range(0, 121)]
    grid = classify_day(frames, sunrise, sunset)
    burst = [m for m in grid if 30 <= (m.t - T0).total_seconds() / 60 < 43]
    assert burst and all(m.value == 1 and "interp" in m.flags for m in burst)
    grid = classify_day(frames, sunrise, sunset, max_gap_min=0)      # off switch
    assert all(m.value is None for m in grid if 30 <= (m.t - T0).total_seconds() / 60 < 43)

"""Camera smear episodes (rules.mark_glitch_episodes) and the longer glitch-only fill: clear dawns count fully."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.sun.rules import (MAX_GAP_MIN, MAX_GLITCH_GAP_MIN, Frame, Minute, classify_day,  # noqa: E402
                             fill_short_gaps, mark_glitch_episodes)

T0 = datetime(2026, 10, 13, 14, 30)
# 2026-10-13 14:38-14:51Z pink_bot ramp (real values), clean before and after
RAMP = [0.005, 0.009, 0.013, 0.017, 0.022, 0.029, 0.033, 0.036, 0.04, 0.042, 0.044, 0.043, 0.044, 0.044]


def _frames(pinks, p=0.95, ps=0.9, step_min=1):
    return [Frame(t=T0 + timedelta(minutes=i * step_min), p=p, ps=ps, smean=0.4, pink=x) for i, x in enumerate(pinks)]


def test_ramp_below_old_threshold_is_one_episode():
    fr = _frames([0.0] * 8 + RAMP + [0.0] * 8)
    assert mark_glitch_episodes(fr) == len(RAMP)
    assert [f.glitch for f in fr] == [False] * 8 + [True] * len(RAMP) + [False] * 8


def test_low_noise_without_seed_is_not_a_glitch():
    fr = _frames([0.0, 0.005, 0.008, 0.006, 0.0, 0.0])
    assert mark_glitch_episodes(fr) == 0


def test_episode_needs_consecutive_frames():
    fr = _frames([0.006, 0.02, 0.006], step_min=30)     # 30-min archive: only the seed frame itself
    mark_glitch_episodes(fr)
    assert [f.glitch for f in fr] == [False, True, False]


def test_no_pink_keeps_old_behaviour():
    fr = [Frame(t=T0, p=0.9, ps=0.9, smean=0.4, glitch=True), Frame(t=T0 + timedelta(minutes=1), p=0.9, ps=0.9, smean=0.4)]
    mark_glitch_episodes(fr)
    assert [f.glitch for f in fr] == [True, False]


def _grid(n_gap, flag, left=1, right=1):
    g = [Minute(t=T0 + timedelta(minutes=i), w=1.0, el=30.0, value=left) for i in range(3)]
    g += [Minute(t=T0 + timedelta(minutes=3 + i), w=1.0, el=30.0, flags={flag}) for i in range(n_gap)]
    g += [Minute(t=T0 + timedelta(minutes=3 + n_gap + i), w=1.0, el=30.0, value=right) for i in range(3)]
    return g


def test_long_glitch_run_filled_only_when_sides_agree():
    assert fill_short_gaps(_grid(30, "glitch")) == 30
    assert fill_short_gaps(_grid(MAX_GLITCH_GAP_MIN + 1, "glitch")) == 0
    assert fill_short_gaps(_grid(30, "glitch", left=1, right=0)) == 0
    assert fill_short_gaps(_grid(30, "missing")) == 0
    assert fill_short_gaps(_grid(MAX_GAP_MIN, "glitch", left=1, right=0)) == MAX_GAP_MIN


def test_clear_dawn_with_smear_counts_fully():
    """Oct 12/13 shape: clear sky from sunrise, smear ramps during low sun and drags sky-clarity under the veto."""
    sunrise = T0
    sunset = T0 + timedelta(hours=11)
    n = 11 * 60
    pinks = [0.0] * n
    ps = [0.9] * n
    for i, x in enumerate(RAMP * 2):       # 28-min episode starting 20 min after sunrise (el < 8)
        pinks[20 + i] = x
        ps[20 + i] = 0.1
    frames = [Frame(t=T0 + timedelta(minutes=i), p=0.99 if i >= 25 else 0.05, ps=ps[i], smean=0.4, pink=pinks[i])
              for i in range(n)]
    grid = classify_day(frames, sunrise, sunset)
    dawn = [m for m in grid if m.t < T0 + timedelta(minutes=90)]
    assert all(m.value == 1 for m in dawn)


def test_foggy_dawn_stays_dark():
    """Oct 9 shape: fog until mid-morning; the main model is confidently not-sunny when the sun is up."""
    sunrise, sunset = T0, T0 + timedelta(hours=11)
    n = 11 * 60
    frames = [Frame(t=T0 + timedelta(minutes=i), p=0.02 if i < 180 else 0.99, ps=0.1 if i < 180 else 0.9,
                    smean=0.3, pink=0.0) for i in range(n)]
    grid = classify_day(frames, sunrise, sunset)
    assert all(m.value == 0 for m in grid if m.t < T0 + timedelta(minutes=170))


def test_backfill_tolerance_does_not_use_long_glitch_fill():
    sunrise, sunset = T0, T0 + timedelta(hours=3)
    frames = _frames([0.0, 0.0, 0.0, 0.03, 0.0, 0.0, 0.0], step_min=30)
    grid = classify_day(frames, sunrise, sunset, tolerance_s=15 * 60)
    assert any(m.value is None for m in grid if "glitch" in m.flags)

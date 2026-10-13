"""Low sun on 30-min archive snapshots (March): the carried state uses frame elevations, and a clear sky with the
sun behind the trees counts as low sun. Fog and overcast stay not sunny."""
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.job.sun_classify import sun_times_utc  # noqa: E402
from rwcwx.sun.rollup import daily_total  # noqa: E402
from rwcwx.sun.rules import Frame, classify_day  # noqa: E402

ARCHIVE_TOL = 15 * 60


def _day(d, edge, mid=(0.99, 0.99)):
    """30-min snapshots over one day; `edge` maps 'HH:MM' UTC to real (p, ps) values, the rest get `mid`."""
    sr, ss = sun_times_utc(d)
    t = sr.replace(minute=0, second=0) - timedelta(hours=1)
    fr = []
    while t <= ss + timedelta(minutes=30):
        p, ps = edge.get(t.strftime("%H:%M"), mid)
        fr.append(Frame(t=t, p=p, ps=ps, smean=0.33))
        t += timedelta(minutes=30)
    g = classify_day(fr, sr, ss, tolerance_s=ARCHIVE_TOL)
    daylight = sum(m.w for m in g) / 60
    return daily_total(g)["val"], round(daylight, 2), g


# Real snapshot values (p, ps), sky_lg archive
MAR09 = {"14:30": (0.002, 0.932), "15:00": (0.106, 0.973), "15:30": (0.993, 0.994),
         "01:00": (0.93, 0.96), "01:30": (0.298, 0.937), "02:00": (0.002, 0.853)}
MAR16 = {"14:30": (0.01, 0.95), "15:00": (0.066, 0.953), "15:30": (0.225, 0.871),
         "01:00": (0.984, 0.972), "01:30": (0.592, 0.926), "02:00": (0.006, 0.889)}


def test_clear_march_day_counts_fully():
    hours, daylight, _ = _day(date(2026, 3, 9), MAR09)
    assert hours == daylight          # was 10.76 of 11.69: the 15:00 snapshot (el 5) set the carried state


def test_sun_behind_trees_with_clear_sky_counts():
    hours, daylight, g = _day(date(2026, 3, 16), MAR16)
    assert hours == daylight          # was 10.54 of 11.97; the 15:30 snapshot is at el 13, sun behind the tree
    m = next(m for m in g if m.t == datetime(2026, 3, 16, 15, 30))
    assert m.value == 1 and "lowsun" in m.flags


def test_fog_morning_stays_not_sunny():
    fog = {k: (0.01, 0.05) for k in ["14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00", "17:30"]}
    _, _, g = _day(date(2026, 3, 9), fog)
    am = [m for m in g if m.t < datetime(2026, 3, 9, 17, 45)]
    assert all(m.value == 0 for m in am)


def test_overcast_day_is_zero():
    hours, _, _ = _day(date(2026, 3, 9), {}, mid=(0.02, 0.02))
    assert hours == 0


def test_low_clear_sky_frame_is_not_a_carry_source():
    # morning clear sky, sun hidden until 16:00 (el ~16); a later cloudy spell must not be carried back
    edge = {"14:30": (0.01, 0.95), "15:00": (0.05, 0.95), "15:30": (0.1, 0.95), "16:00": (0.02, 0.1)}
    _, _, g = _day(date(2026, 3, 16), edge)
    assert all(m.value == 0 for m in g if m.t < datetime(2026, 3, 16, 15, 45))

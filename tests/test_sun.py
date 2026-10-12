"""Sunshine classifier: features/model on real (downscaled) webcam frames, and the per-minute rules."""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.sun.features import feats, load_small  # noqa: E402
from rwcwx.sun.model import LrModel  # noqa: E402
from rwcwx.sun.rules import Frame, classify_day, summary  # noqa: E402
from rwcwx.sun.solar import solar_pos  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sun")


def _p(name):
    t = datetime.strptime(name, "%Y%m%d_%H%M")
    f = feats(load_small(os.path.join(FIX, name + ".jpg")))
    f["el"], f["az"] = solar_pos(t)
    return LrModel.load("sunny_lr_v1").prob(f), f


def test_feature_vector_complete():
    _, f = _p("20261009_2000")
    for name in ("sunny_lr_v1", "skyclear_lr_v1"):
        m = LrModel.load(name)
        assert set(m.features) <= set(f)
        assert len(m.mean) == len(m.scale) == len(m.coef) == len(m.features)


def test_real_frames():
    assert _p("20261009_1600")[0] < 0.1     # marine layer, 08:00 PDT
    assert _p("20261009_1700")[0] < 0.1     # still overcast, 09:00 PDT
    assert _p("20261009_2000")[0] > 0.9     # burnt off, 12:00 PDT
    assert _p("20261011_2100")[0] > 0.9     # clear day
    assert _p("20261010_0300")[1]["Smean"] < 0.03   # night IR frame (gated as ir if it appeared by day)


def test_solar_noon_elevation():
    el, az = solar_pos(datetime(2026, 10, 9, 20, 0))
    assert 45 < el < 47 and 170 < az < 200


SR = datetime(2026, 10, 9, 14, 12, 44)
SS = datetime(2026, 10, 10, 1, 42, 11)


def _frames(p=0.99, ps=0.9, smean=0.3):
    out, t = [], SR.replace(second=0) - timedelta(minutes=10)
    while t <= SS + timedelta(minutes=10):
        out.append(Frame(t=t, p=p(t) if callable(p) else p, ps=ps, smean=smean))
        t += timedelta(minutes=1)
    return out


def test_clear_day_equals_daylight():
    g = classify_day(_frames(), SR, SS)
    s = summary(g)
    assert s["sun_min"] == s["daylight_min"] == round((SS - SR).total_seconds() / 60, 2)
    assert s["coverage"] == 1.0
    assert any("lowsun" in m.flags for m in g)


def test_overcast_day_zero():
    s = summary(classify_day(_frames(p=0.01), SR, SS))
    assert s["sun_min"] == 0 and s["coverage"] == 1.0


def test_lowsun_veto_and_carry():
    # foggy morning (sky-clarity low) but sunny afterwards: low-sun morning minutes vetoed to 0
    fr = _frames()
    for f in fr:
        if f.t < SR + timedelta(minutes=60):
            f.ps = 0.1
    g = classify_day(fr, SR, SS)
    assert all(m.value == 0 for m in g if "lowsun" in m.flags and m.t < SR + timedelta(minutes=50))
    assert all(m.value == 1 for m in g if "lowsun" in m.flags and m.t > SS - timedelta(minutes=50))


def test_missing_and_stale_gates():
    fr = [f for f in _frames() if not (SR + timedelta(hours=3) <= f.t < SR + timedelta(hours=4))]
    for f in fr:
        if SR + timedelta(hours=5) <= f.t < SR + timedelta(hours=5, minutes=30):
            f.stale = True
    g = classify_day(fr, SR, SS)
    miss = [m for m in g if "missing" in m.flags]
    stale = [m for m in g if "stale" in m.flags]
    assert 45 <= len(miss) <= 50 and len(stale) == 30
    assert all(m.value is None for m in miss + stale)
    assert 0.85 < summary(g)["coverage"] < 0.9


def test_ir_gate():
    g = classify_day(_frames(smean=0.01), SR, SS)
    assert all("ir" in m.flags for m in g if m.el > 3)

"""Ensemble rain totals, accumulation and previous-run trend. No network, no DB."""
from datetime import datetime, timedelta

import pytest

from rwcwx.config import TZ
from rwcwx.forecast import ensemble as ens
from rwcwx.forecast.api import build_ensemble
from rwcwx.forecast import openmeteo


def _hours(start, n, step=1):
    return [(start + timedelta(hours=i * step)).strftime("%Y-%m-%dT%H:%M") for i in range(n)]


def _ens(start, n=24, control=None, members=None):
    times = _hours(start.replace(tzinfo=None), n)
    hourly = {"time": times, "precipitation": control or ([0.1] * n)}
    for i, series in enumerate(members or [], start=1):
        hourly[f"precipitation_member{i:02d}"] = series
    return {"latitude": 37.47, "longitude": -122.265, "hourly": hourly}


def test_member_series_names_control_and_members():
    s = ens.member_series({"time": ["t"], "precipitation": [1], "precipitation_member01": [2],
                           "precipitation_member12": [3]})
    assert set(s) == {"control", "m01", "m12"}
    assert s["m01"] == [2]


def test_window_total_coverage_gate():
    start = datetime(2026, 11, 17, 0, 0, tzinfo=TZ)
    times = [start + timedelta(hours=i) for i in range(10)]
    vals = [1.0] * 10
    total, cov = ens.window_total(times, vals, start, start + timedelta(hours=10))
    assert total == pytest.approx(10.0) and cov == 1.0
    # Too many missing hours -> no total
    sparse = [1.0 if i < 2 else None for i in range(10)]
    total, cov = ens.window_total(times, sparse, start, start + timedelta(hours=10))
    assert total is None and cov == pytest.approx(0.2)
    # Empty window
    assert ens.window_total(times, vals, start + timedelta(days=2), start + timedelta(days=3)) == (None, 0.0)


def test_percentiles_and_mean():
    # 0, 10, 20, ..., 100
    stats = ens.percentiles([float(i) for i in range(0, 101, 10)])
    assert stats["min"] == 0 and stats["max"] == 100 and stats["mean"] == pytest.approx(50)
    assert stats["p10"] == pytest.approx(10)
    assert stats["p50"] == pytest.approx(50)
    assert stats["p90"] == pytest.approx(90)
    assert ens.percentiles([]) == {}
    assert ens.percentiles([4.0])["p50"] == 4.0


def test_totals_and_accumulation_for_a_model():
    start = datetime(2026, 11, 17, 12, 0, tzinfo=TZ)
    # 10 days of hourly data; control 0.1 mm/h; one wet member 0.5; one dry 0.0
    n = 240
    raw = _ens(start, n=n, control=[0.1] * n,
               members=[[0.5] * n, [0.0] * n])
    shaped = ens.shape_model("gefs", raw, None, start, start.isoformat())
    assert shaped["id"] == "gfs025" and shaped["n_members"] == 2
    t7 = shaped["windows"]["168"]
    assert t7["control"] == pytest.approx(16.8)   # 0.1 * 168
    assert t7["mean"] == pytest.approx((84.0 + 0.0) / 2)
    assert t7["min"] == 0.0 and t7["max"] == pytest.approx(84.0)
    acc = shaped["accumulation"]
    assert acc["times"][0] == int(start.timestamp() * 1000)
    assert acc["control"][-1] == pytest.approx(24.0)   # 0.1 * 240
    assert acc["members"]["m01"][-1] == pytest.approx(120.0)
    assert acc["mean"][-1] == pytest.approx((24.0 + 120.0 + 0.0) / 3)


def test_previous_run_totals_same_valid_window():
    start = datetime(2026, 11, 17, 0, 0, tzinfo=TZ)
    n = 24
    hourly = {
        "time": _hours(start.replace(tzinfo=None), n),
        "precipitation": [1.0] * n,
        "precipitation_previous_day1": [2.0] * n,
        "precipitation_previous_day2": [0.5] * n,
    }
    runs = ens.previous_run_totals({"hourly": hourly}, start, start + timedelta(hours=24))
    by_lead = {r["lead_days"]: r["total"] for r in runs}
    assert by_lead[0] == pytest.approx(24.0)
    assert by_lead[1] == pytest.approx(48.0)
    assert by_lead[2] == pytest.approx(12.0)


def test_build_ensemble_endpoint_shape(monkeypatch):
    start = datetime(2026, 11, 17, 12, 0, tzinfo=TZ)
    n = 240
    gefs = _ens(start, n=n, control=[0.2] * n, members=[[0.1] * n])
    ecm = _ens(start, n=n, control=[0.05] * n, members=[[0.0] * n, [0.4] * n])
    prev = {"hourly": {"time": _hours(start.replace(tzinfo=None), n),
                       "precipitation": [0.2] * n,
                       "precipitation_previous_day1": [0.3] * n}}

    monkeypatch.setattr(openmeteo, "ensemble", lambda model: gefs if "gfs" in model else ecm)
    monkeypatch.setattr(openmeteo, "previous_runs", lambda model: prev)
    monkeypatch.setattr(openmeteo, "run_slots", lambda *a, **k: [])
    monkeypatch.setattr(openmeteo, "fetch_runs", lambda *a, **k: {})
    monkeypatch.setattr(openmeteo, "single_run", lambda *a, **k: None)

    out = build_ensemble(start)
    assert set(out["models"]) == {"gefs", "ecmwf"}
    assert [w["hours"] for w in out["windows"]] == [120, 168, 240]
    assert out["models"]["gefs"]["windows"]["168"]["control"] == pytest.approx(0.2 * 168)
    assert out["models"]["ecmwf"]["n_members"] == 2
    assert "run_history" in out and "heatmap" in out and "member_heatmap" in out
    assert "Single Runs" in out["source"]
    assert out["source_url"] == "https://open-meteo.com/"


def test_build_ensemble_degrades_when_a_model_is_down(monkeypatch):
    start = datetime(2026, 11, 17, 12, 0, tzinfo=TZ)
    gefs = _ens(start, n=240, control=[0.1] * 240, members=[[0.1] * 240])
    monkeypatch.setattr(openmeteo, "ensemble", lambda model: gefs if "gfs" in model else None)
    monkeypatch.setattr(openmeteo, "previous_runs", lambda model: None)
    monkeypatch.setattr(openmeteo, "run_slots", lambda *a, **k: [])
    monkeypatch.setattr(openmeteo, "fetch_runs", lambda *a, **k: {})
    monkeypatch.setattr(openmeteo, "single_run", lambda *a, **k: None)
    out = build_ensemble(start)
    assert "gefs" in out["models"] and "ecmwf" not in out["models"]

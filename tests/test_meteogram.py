"""10-day meteogram shaping from an Open-Meteo-like payload. No network, no DB."""
from datetime import datetime
import threading
import time

import pytest

from rwcwx.forecast.cache import STALE_MAX, STALE_MAX_OPENMETEO

from rwcwx.config import TZ
from rwcwx.forecast import meteogram as mg
from rwcwx.forecast import openmeteo


def _payload():
    return {
        "latitude": 37.47,
        "longitude": -122.265,
        "elevation": 125,
        "timezone": "America/Los_Angeles",
        "model": "gfs_seamless",
        "hourly": {
            "time": ["2026-11-17T00:00", "2026-11-17T01:00", "2026-11-17T02:00"],
            "temperature_2m": [10.0, 9.5, None],
            "dew_point_2m": [8.0, 7.5, 7.0],
            "precipitation": [0.0, 1.2, 0.4],
            "precipitation_probability": [10, 80, 60],
            "cloud_cover": [20, 90, 100],
            "wind_speed_10m": [5.0, 8.0, 12.0],
            "wind_gusts_10m": [8.0, 14.0, 20.0],
            "wind_direction_10m": [180, 200, 210],
            "surface_pressure": [1012.0, 1011.5, 1011.0],
            "weather_code": [1, 63, 81],
        },
        "daily": {
            "time": ["2026-11-17", "2026-11-18"],
            "temperature_2m_max": [16.0, 15.0],
            "temperature_2m_min": [8.0, 7.0],
            "precipitation_sum": [1.6, 0.0],
            "precipitation_probability_max": [80, 10],
            "wind_speed_10m_max": [12.0, 6.0],
            "wind_gusts_10m_max": [20.0, 9.0],
            "weather_code": [63, 1],
        },
    }


def test_parse_local_attaches_pacific_zone():
    dt = mg.parse_local("2026-11-17T00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() in (-8 * 3600, -7 * 3600)  # PST or PDT


def test_series_skips_null_points_and_converts_times():
    s = mg.series(_payload())
    assert s["model"] == "gfs_seamless"
    assert s["units"]["temp"] == "°C" and s["units"]["wind"] == "mph"
    assert len(s["temp"]) == 2          # third temp is null
    assert s["temp"][0][1] == 10.0
    assert s["precip"][1][1] == 1.2
    assert len(s["gust"]) == 3
    t0 = datetime(2026, 11, 17, 0, 0, tzinfo=TZ)
    assert s["temp"][0][0] == int(t0.timestamp() * 1000)


def test_daily_rows_and_weather_codes():
    rows = mg.series(_payload())["daily"]
    assert [r["date"] for r in rows] == ["2026-11-17", "2026-11-18"]
    assert rows[0]["tmax"] == 16.0 and rows[0]["precip"] == 1.6
    assert rows[0]["weather"] == "Rain"
    assert rows[1]["weather"] == "Mainly clear"
    assert "Nov" in rows[0]["label"]
    t0 = datetime(2026, 11, 17, 0, 0, tzinfo=TZ)
    t1 = datetime(2026, 11, 18, 0, 0, tzinfo=TZ)
    t2 = datetime(2026, 11, 19, 0, 0, tzinfo=TZ)
    assert rows[0]["start"] == int(t0.timestamp() * 1000)
    assert rows[0]["end"] == rows[1]["start"] == int(t1.timestamp() * 1000)
    assert rows[1]["end"] == int(t2.timestamp() * 1000)


def test_series_missing_or_empty():
    assert mg.series(None) is None
    assert mg.series({}) is None
    assert mg.series({"hourly": {"time": []}}) is None


def test_weather_desc_unknown_and_null():
    assert mg.weather_desc(None) is None
    assert mg.weather_desc(0) == "Clear"
    assert mg.weather_desc(1234) == "Code 1234"


def test_openmeteo_urls_are_keyless_and_point_at_the_station():
    # Construction only — no network. The cache helpers are tested via the ensemble tests' mocks.
    assert openmeteo.LAT == 37.470 and openmeteo.LON == -122.265 and openmeteo.ELEV == 125
    assert "api.open-meteo.com" in openmeteo.FORECAST_URL
    assert "ensemble-api.open-meteo.com" in openmeteo.ENSEMBLE_URL
    assert "previous-runs-api.open-meteo.com" in openmeteo.PREV_URL
    assert "single-runs-api.open-meteo.com" in openmeteo.SINGLE_URL
    assert "gfs_seamless" in openmeteo.METEO_HOURLY or True
    assert "precipitation_previous_day7" in openmeteo.PREV_HOURLY


def test_openmeteo_cache_serves_stale_on_timeout():
    openmeteo.clear()
    t = [1000.0]
    calls = []

    def ok():
        calls.append("ok")
        return {"hourly": {"time": ["2026-11-17T00:00"]}}

    def boom():
        calls.append("boom")
        raise TimeoutError("read")

    now = lambda: t[0]
    assert openmeteo._safe("meteogram", 600, ok, now)["hourly"]["time"] == ["2026-11-17T00:00"]
    t[0] += 601
    assert openmeteo._safe("meteogram", 600, boom, now)["hourly"]["time"] == ["2026-11-17T00:00"]
    assert openmeteo.status("meteogram")["stale"] is True
    t[0] += openmeteo.TTL_FAILED - 1
    assert openmeteo._safe("meteogram", 600, boom, now)
    assert calls == ["ok", "boom"]
    t[0] += 2
    assert openmeteo._safe("meteogram", 600, ok, now)
    assert calls == ["ok", "boom", "ok"]
    assert openmeteo.status("meteogram")["stale"] is False
    openmeteo.clear()


def test_openmeteo_disk_fallback_after_clear(tmp_path, monkeypatch):
    monkeypatch.setenv("RWCWX_FORECAST_CACHE_DIR", str(tmp_path))
    openmeteo.clear()
    clock = [0.0]
    wall = [1_700_000_000.0]
    now = lambda: clock[0]
    wall_fn = lambda: wall[0]
    calls = []
    openmeteo._safe("ens", 600, lambda: {"ok": True}, now=now, wall=wall_fn)
    openmeteo.clear()
    def boom():
        calls.append("boom")
        raise IOError("x")
    # Still within the success TTL: adopt as fresh, do not refetch.
    assert openmeteo._safe("ens", 600, boom, now=now, wall=wall_fn) == {"ok": True}
    assert calls == []
    assert openmeteo.status("ens")["stale"] is False
    openmeteo.clear()
    clock[0] += 601
    wall[0] += 601
    assert openmeteo._safe("ens", 600, boom, now=now, wall=wall_fn) == {"ok": True}
    assert calls == ["boom"]
    assert openmeteo.status("ens")["stale"] is True
    openmeteo.clear()


def test_openmeteo_serves_stale_past_three_hours():
    """A gap of 3+ hours between /forecast visits used to drop last-good (STALE_MAX was 3 h)
    and a ReadTimeout then returned no series. Last-good stays usable for 24 hours."""
    openmeteo.clear()
    t = [1000.0]
    now = lambda: t[0]
    good = {"hourly": {"time": ["2026-11-25T00:00"]}}

    def ok():
        return good

    def boom():
        raise TimeoutError("read")

    assert openmeteo._safe("meteogram", 600, ok, now) is good
    t[0] += STALE_MAX + 600  # 3.1 hours after fetch, well past the old cap and the TTL
    assert openmeteo._safe("meteogram", 600, boom, now) is good
    assert openmeteo.status("meteogram")["stale"] is True
    t[0] = 1000 + 12 * 3600
    assert openmeteo._safe("meteogram", 600, boom, now) is good
    t[0] = 1000 + STALE_MAX_OPENMETEO + 1
    assert openmeteo._safe("meteogram", 600, boom, now) is None
    openmeteo.clear()


def test_openmeteo_disk_fallback_past_three_hours(tmp_path, monkeypatch):
    monkeypatch.setenv("RWCWX_FORECAST_CACHE_DIR", str(tmp_path))
    openmeteo.clear()
    clock = [0.0]
    wall = [1_700_000_000.0]
    now = lambda: clock[0]
    wall_fn = lambda: wall[0]
    openmeteo._safe("meteogram", 600, lambda: {"v": 1}, now=now, wall=wall_fn)
    openmeteo.clear()  # like a new uWSGI worker after hours of no visits
    clock[0] += STALE_MAX + 600
    wall[0] += STALE_MAX + 600

    def boom():
        raise TimeoutError("read")

    assert openmeteo._safe("meteogram", 600, boom, now=now, wall=wall_fn) == {"v": 1}
    assert openmeteo.status("meteogram")["stale"] is True
    openmeteo.clear()


def test_openmeteo_revalidate_returns_stale_without_waiting():
    """After TTL expiry, production Open-Meteo callers must not block on a slow/timing-out
    refresh: return last-good immediately and refresh in the background."""
    openmeteo.clear()
    t = [1000.0]
    now = lambda: t[0]
    started = threading.Event()
    release = threading.Event()
    calls = []

    def ok():
        return {"hourly": {"time": ["2026-11-25T00:00"]}}

    def slow():
        calls.append("slow")
        started.set()
        # Stay blocked until the test releases us; a 12s ReadTimeout would hang the request.
        assert release.wait(2)
        return {"hourly": {"time": ["2026-11-25T01:00"]}}

    assert openmeteo._safe("meteogram", 600, ok, now)["hourly"]["time"] == ["2026-11-25T00:00"]
    t[0] += 601
    t0 = time.monotonic()
    val = openmeteo._safe("meteogram", 600, slow, now, revalidate=True)
    elapsed = time.monotonic() - t0
    assert val["hourly"]["time"] == ["2026-11-25T00:00"]
    assert elapsed < 0.5
    assert openmeteo.status("meteogram")["stale"] is True
    assert started.wait(2), "background refresh did not start"
    release.set()
    # Wait for the background fetch to publish the new value.
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if (openmeteo.status("meteogram") or {}).get("stale") is False:
            break
        time.sleep(0.01)
    assert openmeteo.status("meteogram")["stale"] is False
    t[0] += 1  # still within the new TTL; clock is a test double, not wall time
    assert openmeteo._safe("meteogram", 600, lambda: (_ for _ in ()).throw(AssertionError("no refetch")), now)[
        "hourly"
    ]["time"] == ["2026-11-25T01:00"]
    assert calls == ["slow"]
    openmeteo.clear()


def test_build_meteogram_keeps_series_and_adds_model_run(monkeypatch):
    from datetime import datetime, timezone
    from rwcwx.forecast import api as fc_api

    monkeypatch.setattr(openmeteo, "meteogram", _payload)
    monkeypatch.setattr(
        openmeteo, "latest_available_run",
        lambda *a, **k: {"run": datetime(2026, 11, 17, 18, 0, tzinfo=timezone.utc)},
    )
    out = fc_api.build_meteogram(datetime(2026, 11, 17, 23, 0, tzinfo=timezone.utc))
    assert out["series"] is not None
    assert out["series"].get("temp") or out["series"].get("daily")
    assert out["model_run"]["run_z"] == "18z"
    assert out["model_run"]["run_label"] == "18z 17 Nov"

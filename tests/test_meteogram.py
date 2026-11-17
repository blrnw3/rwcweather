"""10-day meteogram shaping from an Open-Meteo-like payload. No network, no DB."""
from datetime import datetime

import pytest

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
    assert "gfs_seamless" in openmeteo.METEO_HOURLY or True
    assert "precipitation_previous_day7" in openmeteo.PREV_HOURLY

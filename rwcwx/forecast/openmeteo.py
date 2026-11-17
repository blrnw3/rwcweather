"""Open-Meteo client for the forecast page (10-day meteogram, ensembles, previous runs).

Keyless public APIs, fetched server-side with an identifying User-Agent and cached per process so
the page does not hammer upstream. Each request fails on its own: a failure returns None and is
retried after a short back-off; a recent good value is served meanwhile.
"""
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlencode

import requests

from rwcwx import logger
from rwcwx.config import TZ_NAME
from rwcwx.forecast import nws as nws_mod

LAT, LON, ELEV = nws_mod.LAT, nws_mod.LON, 125
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
PREV_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
USER_AGENT = os.getenv("RWC_NWS_USER_AGENT", "rwcweather.com (bmr@nw3weather.co.uk)")
TIMEOUT = 15

TTL_FORECAST = 20 * 60
TTL_ENSEMBLE = 30 * 60
TTL_FAILED = 3 * 60
STALE_MAX = 3 * 3600

_lock = threading.Lock()
_cache: Dict[str, Tuple[float, Any]] = {}
_good: Dict[str, Tuple[float, Any]] = {}


def get_json(url: str) -> Any:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(data.get("reason") or "Open-Meteo error")
    return data


def _safe(name: str, ttl: float, fn: Callable[[], Any], now: Optional[Callable[[], float]] = None) -> Optional[Any]:
    t = (now or time.monotonic)()
    with _lock:
        hit = _cache.get(name)
    if hit is not None and t < hit[0]:
        return hit[1]
    try:
        val = fn()
        entry = (t + ttl, val)
        with _lock:
            _good[name] = (t, val)
    except Exception as e:
        logger.warning(f"Open-Meteo {name} fetch failed: {type(e).__name__}")
        with _lock:
            good = _good.get(name)
        if good is not None and t - good[0] < STALE_MAX:
            entry = (min(t + TTL_FAILED, good[0] + STALE_MAX), good[1])
        else:
            entry = (t + TTL_FAILED, None)
    with _lock:
        _cache[name] = entry
    return entry[1]


def clear() -> None:
    with _lock:
        _cache.clear()
        _good.clear()


def _url(base: str, params: dict) -> str:
    return base + "?" + urlencode(params, doseq=True)


# Hourly + daily fields for the 10-day meteogram (GFS seamless: HRRR in the near term, GFS after).
METEO_HOURLY = ",".join([
    "temperature_2m", "dew_point_2m", "precipitation", "precipitation_probability",
    "cloud_cover", "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
    "surface_pressure", "weather_code",
])
METEO_DAILY = ",".join([
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "precipitation_probability_max", "wind_speed_10m_max", "wind_gusts_10m_max", "weather_code",
])
PREV_HOURLY = "precipitation," + ",".join(f"precipitation_previous_day{i}" for i in range(1, 8))


def meteogram() -> Optional[dict]:
    params = dict(
        latitude=LAT, longitude=LON, elevation=ELEV, timezone=TZ_NAME,
        forecast_days=10, wind_speed_unit="mph",
        hourly=METEO_HOURLY, daily=METEO_DAILY,
        models="gfs_seamless",
    )
    return _safe("meteogram", TTL_FORECAST, lambda: get_json(_url(FORECAST_URL, params)))


def ensemble(model: str) -> Optional[dict]:
    params = dict(
        latitude=LAT, longitude=LON, elevation=ELEV, timezone=TZ_NAME,
        forecast_days=10, hourly="precipitation", models=model,
    )
    return _safe("ensemble:" + model, TTL_ENSEMBLE, lambda: get_json(_url(ENSEMBLE_URL, params)))


def previous_runs(model: str) -> Optional[dict]:
    params = dict(
        latitude=LAT, longitude=LON, elevation=ELEV, timezone=TZ_NAME,
        forecast_days=10, hourly=PREV_HOURLY, models=model,
    )
    return _safe("previous:" + model, TTL_ENSEMBLE, lambda: get_json(_url(PREV_URL, params)))

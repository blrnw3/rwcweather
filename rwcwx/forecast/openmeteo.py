"""Open-Meteo client for the forecast page (10-day meteogram, ensembles, previous runs).

Keyless public APIs, fetched server-side with an identifying User-Agent and cached per process
(and last-good on disk) so the page does not hammer upstream. A failed or timed-out fetch is
retried after a short back-off; the last good payload is served in the meantime instead of None.
"""
from typing import Any, Callable, Optional
from urllib.parse import urlencode

from rwcwx.config import TZ_NAME
from rwcwx.forecast import nws as nws_mod
from rwcwx.forecast.cache import STALE_MAX, UpstreamCache
from rwcwx.forecast.http import CONNECT_TIMEOUT, get_json as http_get_json

LAT, LON, ELEV = nws_mod.LAT, nws_mod.LON, 125
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
PREV_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
TIMEOUT = (CONNECT_TIMEOUT, 12)

TTL_FORECAST = 20 * 60
TTL_ENSEMBLE = 30 * 60
TTL_FAILED = 60

_store = UpstreamCache("openmeteo", "Open-Meteo")


def get_json(url: str) -> Any:
    return http_get_json(url, accept="application/json", timeout=TIMEOUT)


def _safe(name: str, ttl: float, fn: Callable[[], Any], now: Optional[Callable[[], float]] = None,
          wall: Optional[Callable[[], float]] = None) -> Optional[Any]:
    return _store.safe(name, ttl, fn, now=now, wall=wall, failed_ttl=TTL_FAILED, stale_max=STALE_MAX)


def clear() -> None:
    _store.clear()


def status(name: str) -> Optional[dict]:
    return _store.status(name)


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

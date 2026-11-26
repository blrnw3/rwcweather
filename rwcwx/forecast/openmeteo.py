"""Open-Meteo client for the forecast page (10-day meteogram, ensembles, previous runs).

Keyless public APIs, fetched server-side with an identifying User-Agent and cached per process
(and last-good on disk) so the page does not hammer upstream. A failed or timed-out fetch is
retried after a short back-off; the last good payload is served in the meantime instead of None,
for up to 24 hours (the forecast page is hit infrequently). Production callers also return
that last-good payload immediately and refresh in the background, so a ReadTimeout does not
blank the 10-day meteogram or hold the request long enough for the browser to abort.
"""
from typing import Any, Callable, Optional
from urllib.parse import urlencode

from rwcwx.config import TZ_NAME
from rwcwx.forecast import nws as nws_mod
from rwcwx.forecast.cache import STALE_MAX_OPENMETEO, UpstreamCache
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
          wall: Optional[Callable[[], float]] = None, failed_ttl: Optional[float] = None,
          revalidate: bool = False) -> Optional[Any]:
    return _store.safe(name, ttl, fn, now=now, wall=wall,
                       failed_ttl=TTL_FAILED if failed_ttl is None else failed_ttl,
                       stale_max=STALE_MAX_OPENMETEO, revalidate=revalidate)


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
    return _safe("meteogram", TTL_FORECAST, lambda: get_json(_url(FORECAST_URL, params)), revalidate=True)


def ensemble(model: str) -> Optional[dict]:
    params = dict(
        latitude=LAT, longitude=LON, elevation=ELEV, timezone=TZ_NAME,
        forecast_days=10, hourly="precipitation", models=model,
    )
    return _safe("ensemble:" + model, TTL_ENSEMBLE, lambda: get_json(_url(ENSEMBLE_URL, params)), revalidate=True)


def previous_runs(model: str) -> Optional[dict]:
    params = dict(
        latitude=LAT, longitude=LON, elevation=ELEV, timezone=TZ_NAME,
        forecast_days=10, hourly=PREV_HOURLY, models=model,
    )
    return _safe("previous:" + model, TTL_ENSEMBLE, lambda: get_json(_url(PREV_URL, params)), revalidate=True)


SINGLE_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
# Historical single runs do not change once issued. Cache completed runs for
# hours so a page view does not re-fetch ~40 cycles; retry missing recent
# cycles a bit more often (they appear 4–8 h after init).
TTL_SINGLE_RECENT = 30 * 60
TTL_SINGLE_OLD = 6 * 3600
TTL_SINGLE_MISSING = 15 * 60
RUN_LOOKBACK_DAYS = 5
RUN_CYCLES = (0, 6, 12, 18)
# Hours after init before a global run is typically published. Used only to
# pick a slightly longer "missing" cache for cycles that are not yet due.
RUN_PUBLISH_LAG_HOURS = 6

# Cached stand-in for a 400 "run is not available" (not an upstream failure).
_MISSING = {"_unavailable": True}

SINGLE_MODELS = {
    "gfs_seamless": "gfs_seamless",
    "ecmwf_ifs025": "ecmwf_ifs025",
}


def run_key(run_utc: "datetime") -> str:
    from datetime import timezone as _tz
    return run_utc.astimezone(_tz.utc).strftime("%Y-%m-%dT%H:%M")


def run_slots(now_utc, days: int = RUN_LOOKBACK_DAYS):
    """UTC init times at 00/06/12/18z, from the latest cycle back `days` days."""
    from datetime import datetime, timedelta, timezone as _tz
    now_utc = now_utc.astimezone(_tz.utc)
    hour = (now_utc.hour // 6) * 6
    latest = now_utc.replace(hour=hour, minute=0, second=0, microsecond=0)
    oldest = latest - timedelta(days=days)
    slots = []
    t = latest
    while t >= oldest:
        slots.append(t)
        t -= timedelta(hours=6)
    return slots


def _single_ttl(run_utc, now_utc=None) -> float:
    from datetime import datetime, timezone as _tz
    now_utc = now_utc or datetime.now(_tz.utc)
    age_h = (now_utc - run_utc.astimezone(_tz.utc)).total_seconds() / 3600.0
    return TTL_SINGLE_OLD if age_h >= (RUN_PUBLISH_LAG_HOURS + 2) else TTL_SINGLE_RECENT


def single_run(model: str, run_utc, now_utc=None) -> Optional[dict]:
    """One Open-Meteo Single Runs payload for `model` at UTC init `run_utc`, or None if missing."""
    from datetime import datetime, timezone as _tz
    import requests

    run_utc = run_utc.astimezone(_tz.utc)
    key = run_key(run_utc)
    name = "single:" + model + ":" + key
    ttl = _single_ttl(run_utc, now_utc)
    params = dict(
        latitude=LAT, longitude=LON, elevation=ELEV, timezone="UTC",
        forecast_days=10, hourly="precipitation", models=model, run=key,
    )
    url = _url(SINGLE_URL, params)

    def fetch():
        try:
            return get_json(url)
        except requests.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 400:
                return _MISSING
            raise
        except RuntimeError as e:
            if "not available" in str(e).lower():
                return _MISSING
            raise

    val = _safe(name, ttl, fetch, failed_ttl=TTL_SINGLE_MISSING, revalidate=True)
    if not val or (isinstance(val, dict) and val.get("_unavailable")):
        return None
    return val


def fetch_runs(model: str, slots, now_utc=None) -> dict:
    """Map each slot datetime to a payload or None. Parallel, cached per run."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not slots:
        return {}
    out = {}
    workers = min(4, len(slots))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(single_run, model, t, now_utc): t for t in slots}
        for fut in as_completed(futs):
            slot = futs[fut]
            try:
                out[slot] = fut.result()
            except Exception:
                out[slot] = None
    return out


def latest_available_run(model: str, now_utc, slots=None) -> Optional[dict]:
    """Newest slot that returns data, trying newest-first and stopping at the first hit."""
    slots = list(slots if slots is not None else run_slots(now_utc))
    for t in slots:  # already newest first
        data = single_run(model, t, now_utc)
        if data and isinstance(data.get("hourly"), dict):
            return dict(model=model, run=t, data=data)
    return None

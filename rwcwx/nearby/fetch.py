"""HTTP fetches for the Weather nearby card, with per-station caching.

The cache follows the forecast-module pattern (including the #98 fix): a successful
fetch is served for its full TTL; STALE_MAX only limits how long a last-good value is
served after a *failed* fetch. Each station (and each upstream for that station) is
cached on its own, so one outage does not blank the others.
"""
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from rwcwx import logger

USER_AGENT = os.getenv("RWC_NWS_USER_AGENT", "rwcweather.com (bmr@nw3weather.co.uk)")
TIMEOUT = 8
TTL = 10 * 60
TTL_FAILED = 2 * 60
STALE_MAX = 3 * 3600

IEM_CURRENT = "https://mesonet.agron.iastate.edu/json/current.py"
NWS_OBS = "https://api.weather.gov/stations/{id}/observations/latest"
WL_STATION = "https://www.weatherlink.com/map/data/station/{id}"
WL_EMBED = "https://www.weatherlink.com/embeddablePage/summaryData/{id}"


def get_json(url: str, accept: str = "application/json") -> Any:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": accept}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


_lock = threading.Lock()
_cache: Dict[str, Tuple[float, Any]] = {}
_good: Dict[str, Tuple[float, Any]] = {}


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
    except Exception as e:      # network, HTTP, JSON or shape errors; never echo the response
        logger.warning(f"nearby {name} fetch failed: {type(e).__name__}")
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


def nws_latest(station_id: str) -> Optional[dict]:
    def fetch():
        data = get_json(NWS_OBS.format(id=station_id), accept="application/geo+json")
        return data["properties"] if isinstance(data, dict) else data
    return _safe("nws_" + station_id, TTL, fetch)


def iem_current(station_id: str, network: str) -> Optional[dict]:
    def fetch():
        data = get_json(f"{IEM_CURRENT}?station={station_id}&network={network}")
        ob = (data or {}).get("last_ob")
        if not isinstance(ob, dict):
            raise ValueError("iem shape")
        return ob
    return _safe("iem_" + network + "_" + station_id, TTL, fetch)


def weatherlink(station_id: str) -> Optional[dict]:
    def fetch():
        data = get_json(WL_STATION.format(id=station_id))
        if not isinstance(data, dict) or not data.get("sStation"):
            raise ValueError("weatherlink shape")
        return data
    return _safe("wl_" + station_id, TTL, fetch)


def weatherlink_embed(token: str) -> Optional[dict]:
    def fetch():
        data = get_json(WL_EMBED.format(id=token))
        if not isinstance(data, dict):
            raise ValueError("weatherlink embed shape")
        return data
    return _safe("wl_embed_" + token, TTL, fetch)

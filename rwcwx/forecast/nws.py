"""NWS (api.weather.gov) client for the home-page forecast card.

Everything is fetched server-side with an identifying User-Agent and cached per process, so browsers never hit
NWS directly. Each part (forecast, discussion, alerts) is cached and fails on its own: a failure returns None and
is retried after a short back-off rather than on every request.
"""
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import requests

from rwcwx import logger

LAT, LON = 37.470, -122.265
BASE = "https://api.weather.gov"
USER_AGENT = os.getenv("RWC_NWS_USER_AGENT", "rwcweather.com (bmr@nw3weather.co.uk)")
TIMEOUT = 8

TTL_POINT = 24 * 3600
TTL_FORECAST = 20 * 60
TTL_AFD = 20 * 60
TTL_ALERTS = 5 * 60
TTL_FAILED = 2 * 60


def get_json(url: str, accept: str = "application/geo+json") -> Any:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": accept}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


_lock = threading.Lock()
_cache: Dict[str, Tuple[float, float, Any]] = {}     # name -> (next check due, last good fetch, value)
STALE_MAX = 3 * 3600


def _safe(name: str, ttl: float, fn: Callable[[], Any], now: Callable[[], float] = time.monotonic) -> Optional[Any]:
    """fn()'s value, cached for ttl seconds. A failed fetch is retried after TTL_FAILED, and meanwhile the last
    good value (if under STALE_MAX old) is served, so a brief NWS outage doesn't blank the card."""
    t = now()
    with _lock:
        hit = _cache.get(name)
    if hit is not None and t < hit[0]:
        return hit[2] if hit[1] is not None and t - hit[1] < STALE_MAX else None
    try:
        entry = (t + ttl, t, fn())
    except Exception as e:      # network, HTTP, JSON or shape errors; never echo the response
        logger.warning(f"NWS {name} fetch failed: {type(e).__name__}")
        good = hit if hit is not None and hit[1] is not None and t - hit[1] < STALE_MAX else None
        entry = (t + TTL_FAILED, good[1], good[2]) if good else (t + TTL_FAILED, None, None)
    with _lock:
        _cache[name] = entry
    return entry[2]


def clear() -> None:
    with _lock:
        _cache.clear()


def point() -> Optional[dict]:
    return _safe("point", TTL_POINT, lambda: get_json(f"{BASE}/points/{LAT:.4f},{LON:.4f}")["properties"])


def forecast() -> Optional[dict]:
    p = point()
    if not p:
        return None
    return _safe("forecast", TTL_FORECAST, lambda: get_json(p["forecast"])["properties"])


def afd() -> Optional[dict]:
    p = point()
    office = (p or {}).get("gridId") or "MTR"

    def fetch():
        listing = get_json(f"{BASE}/products/types/AFD/locations/{office}", accept="application/ld+json")
        latest = listing["@graph"][0]
        return get_json(latest["@id"], accept="application/ld+json")
    return _safe("afd", TTL_AFD, fetch)


def alerts() -> Optional[list]:
    return _safe("alerts", TTL_ALERTS,
                 lambda: get_json(f"{BASE}/alerts/active?point={LAT:.4f},{LON:.4f}")["features"])

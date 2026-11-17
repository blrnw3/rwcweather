"""NWS (api.weather.gov) client for the home-page forecast card.

Everything is fetched server-side with an identifying User-Agent and cached per process (and last-good on disk),
so browsers never hit NWS directly. Each part (forecast, discussion, alerts) is cached and fails on its own:
a failed fetch is retried after a short back-off, and the last good payload is served in the meantime.
"""
import os
from typing import Any, Callable, Optional

import requests

from rwcwx.forecast.cache import STALE_MAX, UpstreamCache

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


# Last-good stale window after a failure. A successful fetch is served for its full ttl even when
# that is longer (the 24 h /points lookup).
_store = UpstreamCache("nws", "NWS")


def _safe(name: str, ttl: float, fn: Callable[[], Any], now: Optional[Callable[[], float]] = None,
          wall: Optional[Callable[[], float]] = None) -> Optional[Any]:
    """fn()'s value, cached for ttl seconds. A failed fetch is retried after TTL_FAILED, and meanwhile the last
    good value (if under STALE_MAX old) is served, so a brief NWS outage doesn't blank the card.

    STALE_MAX only limits how long a last-good value is served *after a failure*; a successful fetch is served for
    its full ttl even when that is longer (the 24 h /points lookup)."""
    return _store.safe(name, ttl, fn, now=now, wall=wall, failed_ttl=TTL_FAILED, stale_max=STALE_MAX)


def clear() -> None:
    _store.clear()


def status(name: str) -> Optional[dict]:
    return _store.status(name)


def point() -> Optional[dict]:
    return _safe("point", TTL_POINT, lambda: get_json(f"{BASE}/points/{LAT:.4f},{LON:.4f}")["properties"])


def forecast() -> Optional[dict]:
    p = point()
    if not p:
        return None
    return _safe("forecast", TTL_FORECAST, lambda: get_json(p["forecast"])["properties"])


def gridpoint() -> Optional[dict]:
    """Raw gridpoint data (for quantitativePrecipitation); same cache and failure handling as the forecast."""
    p = point()
    if not p or not p.get("forecastGridData"):
        return None
    return _safe("gridpoint", TTL_FORECAST, lambda: get_json(p["forecastGridData"])["properties"])


def forecast_hourly() -> Optional[dict]:
    """Hourly forecast at the station grid point (for the 72-hour table)."""
    p = point()
    if not p or not p.get("forecastHourly"):
        return None
    return _safe("forecast_hourly", TTL_FORECAST, lambda: get_json(p["forecastHourly"])["properties"])


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

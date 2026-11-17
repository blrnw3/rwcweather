"""Outbound HTTP for forecast upstreams (Open-Meteo and api.weather.gov).

Production has no global IPv6 route, but some Open-Meteo hosts publish AAAA
records. Prefer IPv4 so a worker does not spend its timeout budget on an
unroutable connect. A short connect timeout plus one retry covers a stalled
first read: after a uWSGI reload the meteogram endpoint has been seen to
hit a 15 s ReadTimeout, while a later attempt on the same URL finishes in
well under a second (and a same-host curl is ~0.08 s).
"""
from __future__ import annotations

import os
import socket
import threading
from typing import Any, Optional, Tuple, Union

import requests

USER_AGENT = os.getenv("RWC_NWS_USER_AGENT", "rwcweather.com (bmr@nw3weather.co.uk)")
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 12.0
ATTEMPTS = 2

Timeout = Union[float, Tuple[float, float]]

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()
_ipv4_applied = False


def prefer_ipv4() -> None:
    """Ask urllib3 to resolve A records only. Safe to call more than once."""
    global _ipv4_applied
    if _ipv4_applied:
        return
    try:
        import urllib3.util.connection as u3c
    except ImportError:
        return
    if getattr(u3c, "allowed_gai_family", None) is None:
        return
    u3c.allowed_gai_family = lambda: socket.AF_INET
    _ipv4_applied = True


def _make_session() -> requests.Session:
    prefer_ipv4()
    sess = requests.Session()
    sess.headers.update({"User-Agent": USER_AGENT})
    adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=8, max_retries=0)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def session() -> requests.Session:
    """Lazy per-process Session, created after uWSGI fork (lazy-apps)."""
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is None:
            _session = _make_session()
    return _session


def reset_session() -> None:
    """Tests: drop the shared session so a later call builds a new one."""
    global _session
    with _session_lock:
        if _session is not None:
            try:
                _session.close()
            except Exception:
                pass
            _session = None


def get_json(url: str, accept: str = "application/json",
             timeout: Optional[Timeout] = None, attempts: int = ATTEMPTS) -> Any:
    """GET JSON, retrying once on a timeout or connection error."""
    if timeout is None:
        timeout = (CONNECT_TIMEOUT, READ_TIMEOUT)
    headers = {"Accept": accept}
    last_err: Optional[BaseException] = None
    tries = max(1, int(attempts))
    for i in range(tries):
        try:
            resp = session().get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("error"):
                raise RuntimeError(data.get("reason") or "upstream error")
            return data
        except (requests.Timeout, requests.ConnectionError) as e:
            last_err = e
            if i + 1 >= tries:
                raise
            continue
    if last_err:
        raise last_err
    raise RuntimeError("get_json failed")

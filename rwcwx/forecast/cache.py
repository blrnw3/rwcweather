"""In-process cache for forecast upstream clients, with a last-good fallback.

A successful fetch is served for its TTL. A failed or timed-out fetch is retried
after a short back-off; until then the last good payload is served (marked stale)
instead of caching None, as long as it is under STALE_MAX old.

An optional on-disk last-good store (repo/cache/forecast, overridable with
RWCWX_FORECAST_CACHE_DIR) lets a new uWSGI worker serve stale data after a reload
when the first upstream call times out. Set the env var to an empty string to
disable the disk store (tests do this by default).
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

from rwcwx import logger

STALE_MAX = 3 * 3600
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9._-]+")


def cache_dir() -> Optional[str]:
    raw = os.environ.get("RWCWX_FORECAST_CACHE_DIR", None)
    if raw == "":
        return None
    if raw:
        return raw
    d = os.path.join(_REPO_ROOT, "cache", "forecast")
    try:
        os.makedirs(d, exist_ok=True)
        if os.access(d, os.W_OK):
            return d
    except OSError:
        pass
    return None


def _disk_path(prefix: str, name: str) -> Optional[str]:
    root = cache_dir()
    if not root:
        return None
    safe = _SAFE_NAME.sub("_", f"{prefix}-{name}")[:80]
    return os.path.join(root, f"v1-{safe}.json")


def _read_disk(path: str) -> Optional[Tuple[float, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            rec = json.load(f)
        fetched = rec.get("fetched_at")
        if fetched is None or "value" not in rec:
            return None
        return float(fetched), rec["value"]
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _write_disk(path: str, fetched_at: float, value: Any) -> None:
    directory = os.path.dirname(path)
    try:
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"fetched_at": fetched_at, "value": value}, f)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except (OSError, TypeError, ValueError):
        pass


class UpstreamCache:
    """One cache (memory + optional disk) shared by a single client module."""

    def __init__(self, prefix: str, log_name: str):
        self.prefix = prefix
        self.log_name = log_name
        self._lock = threading.Lock()
        # name -> (due_monotonic, value, stale, fetched_at_unix)
        self._cache: Dict[str, Tuple[float, Any, bool, Optional[float]]] = {}
        # name -> (fetched_monotonic, fetched_at_unix, value)
        self._good: Dict[str, Tuple[float, float, Any]] = {}

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._good.clear()

    def status(self, name: str) -> Optional[dict]:
        with self._lock:
            hit = self._cache.get(name)
        if not hit:
            return None
        _due, _val, stale, fetched_at = hit
        return dict(stale=bool(stale), fetched_at=fetched_at)

    def safe(self, name: str, ttl: float, fn: Callable[[], Any],
             now: Optional[Callable[[], float]] = None,
             wall: Optional[Callable[[], float]] = None,
             failed_ttl: float = 120,
             stale_max: float = STALE_MAX) -> Optional[Any]:
        t = (now or time.monotonic)()
        wall_t = (wall or time.time)()
        persist = cache_dir() is not None
        with self._lock:
            hit = self._cache.get(name)
        if hit is not None and t < hit[0]:
            return hit[1]
        try:
            val = fn()
            entry = (t + ttl, val, False, wall_t)
            with self._lock:
                self._good[name] = (t, wall_t, val)
            if persist:
                path = _disk_path(self.prefix, name)
                if path:
                    _write_disk(path, wall_t, val)
        except Exception as e:
            logger.warning(f"{self.log_name} {name} fetch failed: {type(e).__name__}")
            entry = self._fallback(name, t, wall_t, failed_ttl, stale_max, persist)
        with self._lock:
            self._cache[name] = entry
        return entry[1]

    def _fallback(self, name, t, wall_t, failed_ttl, stale_max, persist):
        with self._lock:
            good = self._good.get(name)
        if good is not None and t - good[0] < stale_max:
            fetched_mono, fetched_at, val = good
            due = min(t + failed_ttl, fetched_mono + stale_max)
            return (due, val, True, fetched_at)
        if persist:
            path = _disk_path(self.prefix, name)
            rec = _read_disk(path) if path else None
            if rec is not None and wall_t - rec[0] < stale_max:
                fetched_at, val = rec
                with self._lock:
                    self._good[name] = (t - (wall_t - fetched_at), fetched_at, val)
                due = min(t + failed_ttl, t + (stale_max - (wall_t - fetched_at)))
                return (due, val, True, fetched_at)
        return (t + failed_ttl, None, False, None)


def iso_utc(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def merge_status(*statuses: Optional[dict]) -> dict:
    found = [s for s in statuses if s]
    if not found:
        return dict(stale=False, fetched_at=None)
    times = [s["fetched_at"] for s in found if s.get("fetched_at") is not None]
    return dict(
        stale=any(s.get("stale") for s in found),
        fetched_at=iso_utc(min(times)) if times else None,
    )

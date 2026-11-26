"""In-process cache for forecast upstream clients, with a last-good fallback.

A successful fetch is served for its TTL. A failed or timed-out fetch is retried
after a short back-off; until then the last good payload is served (marked stale)
instead of caching None, as long as it is under the stale window (STALE_MAX, or
a longer cap such as STALE_MAX_OPENMETEO).

When revalidate=True and a last-good value is still inside that window, safe()
returns it immediately and refreshes in a background thread, so a slow upstream
does not block the HTTP request (or wait long enough for the browser to abort).

An optional on-disk store (repo/cache/forecast, overridable with
RWCWX_FORECAST_CACHE_DIR) is used in two ways: a value still within its success
TTL is adopted as fresh after a worker reload (so a HUP does not stampede
upstream), and an older last-good value (under STALE_MAX) is served if a fetch
fails. Concurrent callers for the same key share one in-flight fetch (and a
file lock across processes when the disk store is on). Set the env var to an
empty string to disable the disk store (tests do this by default).
"""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, Optional, Tuple

from rwcwx import logger

STALE_MAX = 3 * 3600
# Open-Meteo (meteogram / ensemble) is requested only when someone opens /forecast.
# A 3-hour cap dropped last-good data before the next visit, so a ReadTimeout
# returned no series. 24 hours is still a useful 10-day forecast.
STALE_MAX_OPENMETEO = 24 * 3600
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




@contextmanager
def _interprocess_lock(prefix: str, name: str, persist: bool, deadline: float = 25.0) -> Iterator[None]:
    """Exclusive lock so only one uWSGI worker fetches a given key at a time."""
    path = _disk_path(prefix, name) if persist else None
    if not path:
        yield
        return
    lock_path = path + ".lock"
    directory = os.path.dirname(lock_path)
    try:
        os.makedirs(directory, exist_ok=True)
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o660)
    except OSError:
        yield
        return
    locked = False
    try:
        end = time.time() + deadline
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except BlockingIOError:
                if time.time() >= end:
                    break
                time.sleep(0.05)
        yield
    finally:
        if locked:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
        try:
            os.close(fd)
        except OSError:
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
        self._flights: Dict[str, threading.Lock] = {}
        self._refreshing: set = set()

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._good.clear()
            self._refreshing.clear()

    def status(self, name: str) -> Optional[dict]:
        with self._lock:
            hit = self._cache.get(name)
        if not hit:
            return None
        _due, _val, stale, fetched_at = hit
        return dict(stale=bool(stale), fetched_at=fetched_at)

    def _flight_lock(self, name: str) -> threading.Lock:
        with self._lock:
            return self._flights.setdefault(name, threading.Lock())

    def _memory_hit(self, name: str, t: float) -> Optional[Any]:
        with self._lock:
            hit = self._cache.get(name)
        if hit is not None and t < hit[0]:
            return hit[1]
        return None

    def _adopt_fresh_disk(self, name: str, ttl: float, t: float, wall_t: float) -> Optional[Any]:
        path = _disk_path(self.prefix, name)
        rec = _read_disk(path) if path else None
        if rec is None:
            return None
        fetched_at, val = rec
        age = wall_t - fetched_at
        if age < 0:
            age = 0
        if age >= ttl:
            return None
        entry = (t + (ttl - age), val, False, fetched_at)
        with self._lock:
            self._good[name] = (t - age, fetched_at, val)
            self._cache[name] = entry
        return val

    def _peek_last_good(self, name: str, t: float, wall_t: float,
                        stale_max: float, persist: bool):
        """Return (fetched_monotonic, fetched_at_unix, value) if usable, else None."""
        with self._lock:
            good = self._good.get(name)
        if good is not None and t - good[0] < stale_max:
            return good
        if persist:
            path = _disk_path(self.prefix, name)
            rec = _read_disk(path) if path else None
            if rec is not None and wall_t - rec[0] < stale_max:
                fetched_at, val = rec
                return (t - (wall_t - fetched_at), fetched_at, val)
        return None

    def _store_stale(self, name: str, good, t: float, failed_ttl: float, stale_max: float):
        fetched_mono, fetched_at, val = good
        due = min(t + failed_ttl, fetched_mono + stale_max)
        with self._lock:
            self._good[name] = good
            self._cache[name] = (due, val, True, fetched_at)
        return val

    def _schedule_refresh(self, name: str, ttl: float, fn: Callable[[], Any],
                          now, wall, failed_ttl: float, stale_max: float, persist: bool) -> None:
        with self._lock:
            if name in self._refreshing:
                return
            self._refreshing.add(name)

        def run():
            try:
                with self._flight_lock(name):
                    with _interprocess_lock(self.prefix, name, persist):
                        self._fetch_and_store(
                            name, ttl, fn, now, wall, failed_ttl, stale_max, persist,
                        )
            finally:
                with self._lock:
                    self._refreshing.discard(name)

        threading.Thread(
            target=run, name=f"rwcwx-refresh-{self.prefix}-{name}", daemon=True,
        ).start()

    def _fetch_and_store(self, name: str, ttl: float, fn: Callable[[], Any],
                         now, wall, failed_ttl: float, stale_max: float, persist: bool):
        """Call fn() and update memory/disk. Caller must hold the flight (and file) lock."""
        try:
            val = fn()
            wall_t = (wall or time.time)()
            t = (now or time.monotonic)()
            entry = (t + ttl, val, False, wall_t)
            with self._lock:
                self._good[name] = (t, wall_t, val)
            if persist:
                path = _disk_path(self.prefix, name)
                if path:
                    _write_disk(path, wall_t, val)
        except Exception as e:
            logger.warning(f"{self.log_name} {name} fetch failed: {type(e).__name__}")
            t = (now or time.monotonic)()
            wall_t = (wall or time.time)()
            entry = self._fallback(name, t, wall_t, failed_ttl, stale_max, persist)
        with self._lock:
            self._cache[name] = entry
        return entry[1]

    def safe(self, name: str, ttl: float, fn: Callable[[], Any],
             now: Optional[Callable[[], float]] = None,
             wall: Optional[Callable[[], float]] = None,
             failed_ttl: float = 120,
             stale_max: float = STALE_MAX,
             revalidate: bool = False) -> Optional[Any]:
        t = (now or time.monotonic)()
        persist = cache_dir() is not None
        hit = self._memory_hit(name, t)
        if hit is not None:
            return hit
        refresh = None
        with self._flight_lock(name):
            t = (now or time.monotonic)()
            wall_t = (wall or time.time)()
            hit = self._memory_hit(name, t)
            if hit is not None:
                return hit
            if revalidate:
                good = self._peek_last_good(name, t, wall_t, stale_max, persist)
                if good is not None:
                    val = self._store_stale(name, good, t, failed_ttl, stale_max)
                    refresh = val
            if refresh is None:
                with _interprocess_lock(self.prefix, name, persist):
                    t = (now or time.monotonic)()
                    wall_t = (wall or time.time)()
                    hit = self._memory_hit(name, t)
                    if hit is not None:
                        return hit
                    if persist:
                        adopted = self._adopt_fresh_disk(name, ttl, t, wall_t)
                        if adopted is not None:
                            return adopted
                    return self._fetch_and_store(
                        name, ttl, fn, now, wall, failed_ttl, stale_max, persist,
                    )
        if refresh is not None:
            self._schedule_refresh(name, ttl, fn, now, wall, failed_ttl, stale_max, persist)
            return refresh
        return None

    def _fallback(self, name, t, wall_t, failed_ttl, stale_max, persist):
        good = self._peek_last_good(name, t, wall_t, stale_max, persist)
        if good is not None:
            fetched_mono, fetched_at, val = good
            with self._lock:
                self._good[name] = good
            due = min(t + failed_ttl, fetched_mono + stale_max)
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

"""Tiny per-process TTL cache for expensive, read-only dashboard aggregates."""
import threading
import time
from typing import Any, Callable, Dict, Hashable, Tuple

_lock = threading.Lock()
_store: Dict[Hashable, Tuple[float, Any]] = {}


def cached(key: Hashable, ttl_secs: float, fn: Callable[[], Any], now: Callable[[], float] = time.monotonic) -> Any:
    """Return fn()'s value for key, recomputing once it is older than ttl_secs.

    Keys should include the date they describe, so a new day never serves yesterday's value.
    Entries whose key differs only in that date are dropped as they are replaced (bounded size).
    """
    t = now()
    with _lock:
        hit = _store.get(key)
        if hit is not None and t - hit[0] < ttl_secs:
            return hit[1]
    val = fn()
    with _lock:
        name = key[0] if isinstance(key, tuple) and key else key
        for k in [k for k in _store if (k[0] if isinstance(k, tuple) and k else k) == name]:
            del _store[k]
        _store[key] = (t, val)
    return val


def clear() -> None:
    with _lock:
        _store.clear()

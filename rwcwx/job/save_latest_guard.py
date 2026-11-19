"""Helpers for the long-running save_latest daemon: ORM identity-map release, RSS, in-process restart.

The ingest process holds a process-wide SQLAlchemy Session (db.s). DaySummary -> ObsQ.day loads every
observation for the local day into that Session each minute and never expunges it, so the identity map
grew across days (~420 MiB RSS after 35 days) until the kernel OOM-killed the daemon.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import Optional

# Defaults leave headroom on the 1 GiB droplet (healthy start is ~40–60 MiB) and cap lifetime
# even if a new leak appears. 0 disables a limit.
DEFAULT_MAX_RSS_MB = 200
DEFAULT_MAX_AGE_DAYS = 7


def rss_bytes(pid: Optional[int] = None) -> Optional[int]:
    """Current RSS in bytes from /proc, or None if unavailable."""
    path = f"/proc/{pid or 'self'}/status"
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    # kB
                    return int(parts[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def should_restart(
    rss: Optional[int],
    started_at: datetime,
    now: Optional[datetime] = None,
    max_rss_mb: Optional[int] = None,
    max_age_days: Optional[int] = None,
) -> Optional[str]:
    """Return a short reason to restart, or None to keep running. 0 / negative limits are off."""
    if max_rss_mb is None:
        max_rss_mb = env_int("SAVE_LATEST_MAX_RSS_MB", DEFAULT_MAX_RSS_MB)
    if max_age_days is None:
        max_age_days = env_int("SAVE_LATEST_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS)
    now = now or datetime.now()
    if max_rss_mb > 0 and rss is not None and rss >= max_rss_mb * 1024 * 1024:
        return f"RSS {rss / (1024 * 1024):.0f} MiB >= {max_rss_mb} MiB"
    if max_age_days > 0 and now - started_at >= timedelta(days=max_age_days):
        age = now - started_at
        return f"uptime {age.days}d {age.seconds // 3600}h >= {max_age_days}d"
    return None


def release_orm_session(session) -> int:
    """Drop cached ORM instances on a long-lived Session. Returns identity-map size before release."""
    if session is None:
        return 0
    try:
        n = len(session.identity_map)
    except Exception:
        n = 0
    try:
        session.expunge_all()
    except Exception:
        try:
            session.expire_all()
        except Exception:
            pass
    return n


def restart_in_place() -> None:
    """Replace this process with the same Python + argv (keeps the pid, no sudo)."""
    os.execv(sys.executable, [sys.executable] + sys.argv)

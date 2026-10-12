"""Read side of the webcam sunshine data: obs_inferred (kind='sunny') minutes and the daily avg_extreme total."""
from datetime import date, datetime, timedelta
from typing import List, Optional

from dateutil.tz import UTC
from sqlalchemy import text

from rwcwx.astronomy import get_all_times_rwc
from rwcwx.config import TZ
from rwcwx.models import db

KIND = "sunny"
NOW_MAX_AGE_MIN = 20
BAD_FLAGS = ("missing", "stale", "ir", "glitch")


def _ms(dt: datetime) -> int:
    return int(dt.replace(tzinfo=UTC).timestamp() * 1000)


def local_day_bounds_utc(d: date):
    st = datetime(d.year, d.month, d.day, tzinfo=TZ)
    en = st + timedelta(days=1)
    return st.astimezone(UTC).replace(tzinfo=None), en.astimezone(UTC).replace(tzinfo=None)


def sun_times(d: date) -> dict:
    """Sunrise/sunset as epoch ms, same convention as the classifier (sun centre at -0.833 deg)."""
    # Naive noon, like get_all_times_rwc's own default: astronomy uses time.mktime, and an aware
    # datetime carries tm_isdst=1 in summer, which glibc rejects when the process zone is UTC (prod).
    times = get_all_times_rwc(datetime(d.year, d.month, d.day, 12))
    sr, ss = times["sunrise"], times["sunset"]
    # astronomy returns naive datetimes in the process's local zone; .timestamp() interprets them the same way
    return dict(sunrise=int(sr.timestamp() * 1000), sunset=int(ss.timestamp() * 1000),
                daylight_h=round(times["daylight_secs"] / 3600, 2))


def state_of(value, flags: Optional[str]) -> str:
    if value is None:
        return "unknown"
    return "sun" if value >= 0.5 else "nosun"


def spells(rows: List[dict]) -> List[dict]:
    """Collapse consecutive minutes with the same state into [start, end) spells (epoch ms)."""
    out: List[dict] = []
    for r in rows:
        st = state_of(r["value"], r["flags"])
        t0 = _ms(r["t"])
        t1 = t0 + int(r["minutes"] or 1) * 60000
        if out and out[-1]["state"] == st and out[-1]["end"] == t0:
            out[-1]["end"] = t1
            out[-1]["minutes"] += int(r["minutes"] or 1)
        else:
            out.append(dict(start=t0, end=t1, state=st, minutes=int(r["minutes"] or 1)))
    return out


class SunQ:

    @staticmethod
    def minutes(d: date) -> List[dict]:
        st, en = local_day_bounds_utc(d)
        res = db.execute(text(
            "SELECT t, value, minutes, flags, source FROM obs_inferred "
            "WHERE kind = :k AND t >= :st AND t < :en ORDER BY t"), k=KIND, st=st, en=en)
        return [dict(r._mapping) if hasattr(r, "_mapping") else dict(r) for r in res]

    @staticmethod
    def total(d: date) -> Optional[dict]:
        res = db.execute(text(
            "SELECT val, cnt, comment FROM avg_extreme WHERE d = :d AND var = 'sun' AND type = 'total' "
            "AND period = 'day'"), d=d).fetchone()
        return dict(hours=res[0], minutes=res[1], comment=res[2]) if res else None

    @staticmethod
    def latest() -> Optional[dict]:
        res = db.execute(text(
            "SELECT t, value, flags FROM obs_inferred WHERE kind = :k ORDER BY t DESC LIMIT 1"), k=KIND).fetchone()
        return dict(t=res[0], value=res[1], flags=res[2]) if res else None


def now_state(latest: Optional[dict], now_utc: datetime) -> Optional[dict]:
    """'Sunny now' badge: only from a fresh (< 20 min) row that was actually classified."""
    if not latest or latest["value"] is None:
        return None
    if (now_utc - latest["t"]).total_seconds() > NOW_MAX_AGE_MIN * 60:
        return None
    if latest["flags"] and any(f in latest["flags"].split(",") for f in BAD_FLAGS):
        return None
    return dict(state=state_of(latest["value"], latest["flags"]), t=_ms(latest["t"]))


def day_report(d: date, now_utc: Optional[datetime] = None) -> dict:
    now_utc = now_utc or datetime.utcnow()
    rows = SunQ.minutes(d)
    times = sun_times(d)
    sun_min = sum((r["minutes"] or 1) for r in rows if r["value"] is not None and r["value"] >= 0.5)
    classified = sum((r["minutes"] or 1) for r in rows if r["value"] is not None)
    elapsed_ms = min(max(_ms(now_utc) - times["sunrise"], 0), times["sunset"] - times["sunrise"])
    return dict(
        date=(d.year, d.month, d.day),
        **times,
        possible_so_far_h=round(elapsed_ms / 3600000, 2),
        total=SunQ.total(d),
        sun_minutes=sun_min,
        classified_minutes=classified,
        backfill=any(r["source"] == "backfill" for r in rows),
        spells=spells(rows),
    )


def dashboard_block(today: date, now_utc: Optional[datetime] = None) -> dict:
    now_utc = now_utc or datetime.utcnow()
    times = sun_times(today)
    tot = SunQ.total(today)
    elapsed_ms = min(max(_ms(now_utc) - times["sunrise"], 0), times["sunset"] - times["sunrise"])
    possible = elapsed_ms / 3600000
    hours = tot["hours"] if tot else None
    return dict(
        today_h=hours,
        possible_so_far_h=round(possible, 2),
        daylight_h=times["daylight_h"],
        pct_of_possible=round(100 * hours / possible) if hours is not None and possible > 0.25 else None,
        comment=tot["comment"] if tot else None,
        now=now_state(SunQ.latest(), now_utc),
    )

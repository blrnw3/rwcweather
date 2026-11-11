"""DB side of the nearby_obs log (data/migrations/20261111_nearby_obs.sql).

Upsert on (station, t_obs). Rows older than KEEP_HOURS are pruned by the logger.
rwcwx.models is imported lazily so parse/api tests can run without MySQL.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import exc, text

from rwcwx.config import TZ

NO_TABLE = 1146
KEEP_HOURS = 48


class TableMissing(RuntimeError):
    pass


def _db():
    from rwcwx.models import db
    return db


def _missing_table(e: exc.DBAPIError) -> bool:
    args = getattr(e.orig, "args", ())
    return bool(args) and args[0] == NO_TABLE


UPSERT = """
INSERT INTO nearby_obs (station, t_obs, temp_c, rain_today_mm, t_log)
VALUES (:station, :t_obs, :temp_c, :rain_today_mm, :t_log)
ON DUPLICATE KEY UPDATE temp_c = VALUES(temp_c), rain_today_mm = VALUES(rain_today_mm), t_log = VALUES(t_log)
"""
PRUNE = "DELETE FROM nearby_obs WHERE t_obs < :cutoff"
SELECT_DAY = """
SELECT station, t_obs, temp_c FROM nearby_obs
WHERE t_obs >= :start AND t_obs < :end AND temp_c IS NOT NULL
ORDER BY station, t_obs
"""


def _aware_utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        from dateutil.tz import UTC
        return t.replace(tzinfo=UTC)
    from dateutil.tz import UTC
    return t.astimezone(UTC)


def upsert_many(rows: List[dict], now_utc: Optional[datetime] = None) -> int:
    """Insert or update by (station, t_obs). Returns the number of rows handed to the DB. 0 if none."""
    if not rows:
        return 0
    now_utc = (now_utc or datetime.utcnow()).replace(microsecond=0)
    db = _db()
    try:
        with db.connect() as conn:
            for rec in rows:
                t_obs = rec["t_obs"]
                if isinstance(t_obs, str):
                    t_obs = datetime.fromisoformat(t_obs.replace("Z", "+00:00")).replace(tzinfo=None)
                elif getattr(t_obs, "tzinfo", None) is not None:
                    t_obs = t_obs.replace(tzinfo=None)
                conn.execute(text(UPSERT), station=rec["station"], t_obs=t_obs,
                             temp_c=rec.get("temp_c"), rain_today_mm=rec.get("rain_today_mm"),
                             t_log=now_utc)
        return len(rows)
    except exc.DBAPIError as e:
        if _missing_table(e):
            raise TableMissing("nearby_obs table does not exist (apply data/migrations/20261111_nearby_obs.sql)")
        raise


def prune(now_utc: Optional[datetime] = None, keep_hours: int = KEEP_HOURS) -> int:
    now_utc = (now_utc or datetime.utcnow()).replace(microsecond=0)
    cutoff = now_utc - timedelta(hours=keep_hours)
    db = _db()
    try:
        with db.connect() as conn:
            res = conn.execute(text(PRUNE), cutoff=cutoff)
        return res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0
    except exc.DBAPIError as e:
        if _missing_table(e):
            raise TableMissing("nearby_obs table does not exist (apply data/migrations/20261111_nearby_obs.sql)")
        raise


def samples_on_day(day) -> Dict[str, List[Tuple[datetime, float]]]:
    """{station: [(aware-UTC t_obs, temp_c), ...]} for the PT calendar day. Empty dict if no table."""
    start_local = datetime(day.year, day.month, day.day, tzinfo=TZ)
    end_local = start_local + timedelta(days=1)
    start, end = _aware_utc(start_local).replace(tzinfo=None), _aware_utc(end_local).replace(tzinfo=None)
    try:
        rows = _db().execute(text(SELECT_DAY), start=start, end=end).fetchall()
    except exc.DBAPIError as e:
        if _missing_table(e):
            return {}
        raise
    except Exception:
        # no MySQL client / no DB in test or a box without the table's driver
        return {}
    from dateutil.tz import UTC
    out: Dict[str, List[Tuple[datetime, float]]] = {}
    for station, t_obs, temp in rows:
        if t_obs is None or temp is None:
            continue
        if t_obs.tzinfo is None:
            t_obs = t_obs.replace(tzinfo=UTC)
        out.setdefault(station, []).append((t_obs, float(temp)))
    return out

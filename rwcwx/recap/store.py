"""DB side of the recap table (data/migrations/20261027_recap.sql). Upsert on (kind, period).

rwcwx.models is imported lazily so that rules/markdown/api can be imported (and tested) without MySQL.
"""
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import exc, text

from rwcwx.recap.rules import KINDS

UPSERT = """
INSERT INTO recap (kind, period, body_md, generated_at, t_mod)
VALUES (:kind, :period, :body_md, :generated_at, :t_mod)
ON DUPLICATE KEY UPDATE body_md = VALUES(body_md), generated_at = VALUES(generated_at), t_mod = VALUES(t_mod)
"""
SELECT_ONE = "SELECT body_md, generated_at FROM recap WHERE kind = :kind AND period = :period"
LATEST = """
SELECT r.kind, r.period, r.body_md, r.generated_at, r.t_mod
FROM recap r JOIN (SELECT kind, MAX(period) AS period FROM recap GROUP BY kind) m
  ON r.kind = m.kind AND r.period = m.period
"""
NO_TABLE = 1146   # MySQL ER_NO_SUCH_TABLE


class TableMissing(RuntimeError):
    pass


def _db():
    from rwcwx.models import db
    return db


def _missing_table(e: exc.DBAPIError) -> bool:
    args = getattr(e.orig, "args", ())
    return bool(args) and args[0] == NO_TABLE


def upsert(rec: dict, now_utc: Optional[datetime] = None) -> str:
    """'inserted', 'updated' or 'unchanged' (same text and generated_at: nothing written)."""
    now_utc = (now_utc or datetime.utcnow()).replace(microsecond=0)
    db = _db()
    try:
        with db.connect() as conn:
            old = conn.execute(text(SELECT_ONE), kind=rec["kind"], period=rec["period"]).fetchone()
            if old is not None and old[0] == rec["body_md"] and old[1] == rec["generated_at"]:
                return "unchanged"
            conn.execute(text(UPSERT), t_mod=now_utc, **{k: rec[k] for k in ("kind", "period", "body_md",
                                                                               "generated_at")})
            return "inserted" if old is None else "updated"
    except exc.DBAPIError as e:
        if _missing_table(e):
            raise TableMissing("recap table does not exist (apply data/migrations/20261027_recap.sql)")
        raise


def latest() -> Optional[Dict[str, dict]]:
    """{kind: row} for the latest period of each kind (kinds with no rows are absent); None if no table."""
    try:
        rows = _db().execute(text(LATEST)).fetchall()
    except exc.DBAPIError as e:
        if _missing_table(e):
            return None
        raise
    return {r[0]: dict(kind=r[0], period=r[1], body_md=r[2], generated_at=r[3], t_mod=r[4])
            for r in rows if r[0] in KINDS}

"""Load estimated daily rows from a CSV fixture or the daily_estimated table.

The CSV path (RWC_ESTIMATED_CSV) is preferred so tests and a local screenshot
backend can serve generated rows without applying the migration. When the table
is missing the query path returns an empty list and the rest of the API is
unchanged.
"""
from __future__ import annotations

import csv
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from typing import List, Optional

from rwcwx.estimated.conversions import VERSION
from rwcwx.estimated.merge import ESTIMATED_VARS

logger = logging.getLogger(__name__)

# Env: absolute or repo-relative path to the generated CSV.
CSV_ENV = "RWC_ESTIMATED_CSV"
VERSION_ENV = "RWC_ESTIMATED_VERSION"


@dataclass
class EstimatedDay:
    d: date
    var: str
    typ: str
    val: float
    source: str
    method: str
    version: str
    confidence: str
    raw_val: Optional[float] = None
    period: str = "day"
    at: Optional[datetime] = None
    cnt: int = 1
    comment: Optional[str] = None
    is_estimated: bool = True

    # AvgExt uses `.type`; keep typ as the constructor name (type is reserved).
    @property
    def type(self) -> str:
        return self.typ

    @property
    def simple_dict_(self) -> dict:
        out = {
            "d": (self.d.year, self.d.month, self.d.day),
            "val": self.val,
            "est": True,
            "src": self.source,
        }
        return out

    @property
    def dict_(self) -> dict:
        return {
            **self.simple_dict_,
            "var": self.var,
            "type": self.typ,
            "period": self.period,
            "confidence": self.confidence,
            "method": self.method,
            "version": self.version,
        }


def current_version() -> str:
    return os.environ.get(VERSION_ENV) or VERSION


def _csv_path() -> Optional[str]:
    path = os.environ.get(CSV_ENV)
    return path if path else None


def _parse_date(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value)
    return date(int(text[0:4]), int(text[5:7]), int(text[8:10]))


@lru_cache(maxsize=4)
def _load_csv(path: str, mtime: int) -> tuple:
    rows = []
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        for rec in reader:
            rows.append(EstimatedDay(
                d=_parse_date(rec["d"]),
                var=rec["var"],
                typ=rec["type"],
                val=float(rec["val"]),
                source=rec["source"],
                method=rec["method"],
                version=rec.get("version") or VERSION,
                confidence=rec.get("confidence") or "A",
                raw_val=float(rec["raw_val"]) if rec.get("raw_val") not in (None, "") else None,
            ))
    return tuple(rows)


def _from_csv(var: str, typ: str, start: Optional[date], end: Optional[date], version: str) -> List[EstimatedDay]:
    path = _csv_path()
    if not path or not os.path.isfile(path):
        return []
    try:
        mtime = int(os.path.getmtime(path))
        rows = _load_csv(os.path.abspath(path), mtime)
    except OSError as exc:
        logger.warning("estimated CSV unreadable (%s): %s", path, exc)
        return []
    out = []
    for row in rows:
        if row.var != var or row.typ != typ or row.version != version:
            continue
        if start and row.d < start:
            continue
        if end and row.d > end:
            continue
        out.append(row)
    return out


def _from_table(var: str, typ: str, start: Optional[date], end: Optional[date], version: str) -> List[EstimatedDay]:
    try:
        from sqlalchemy import text
        from sqlalchemy.exc import OperationalError, ProgrammingError
        from rwcwx.models import db
    except Exception as exc:  # pragma: no cover - import environment
        logger.warning("estimated table unavailable: %s", exc)
        return []
    sql = (
        "SELECT d, var, type, val, source, method, version, confidence, raw_val "
        "FROM daily_estimated WHERE var = :var AND type = :typ AND version = :version"
    )
    params = {"var": var, "typ": typ, "version": version}
    if start is not None:
        sql += " AND d >= :start"
        params["start"] = start
    if end is not None:
        sql += " AND d <= :end"
        params["end"] = end
    sql += " ORDER BY d ASC"
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text(sql), **params)
            records = result.fetchall()
    except (OperationalError, ProgrammingError) as exc:
        logger.warning("daily_estimated table missing or unreadable: %s", exc)
        return []
    rows = []
    for rec in records:
        rows.append(EstimatedDay(
            d=_parse_date(rec[0]),
            var=rec[1],
            typ=rec[2],
            val=float(rec[3]),
            source=rec[4],
            method=rec[5],
            version=rec[6],
            confidence=rec[7],
            raw_val=float(rec[8]) if rec[8] is not None else None,
        ))
    return rows


def fetch(var: str, typ: str, start: Optional[date] = None, end: Optional[date] = None,
          version: Optional[str] = None) -> List[EstimatedDay]:
    """Estimated days for one variable/statistic, oldest first. Empty if unavailable."""
    if (var, typ) not in ESTIMATED_VARS:
        return []
    ver = version or current_version()
    if _csv_path():
        return _from_csv(var, typ, start, end, ver)
    return _from_table(var, typ, start, end, ver)


def fetch_dates(var: str, typ: str) -> set:
    return {row.d for row in fetch(var, typ)}

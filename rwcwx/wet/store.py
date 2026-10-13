"""DB side of derived wet minutes: reads obs (t, rain), writes obs.wet flags and avg_extreme var='wet', type='total'.

obs.wet used to hold Cumulus's "rain in the last hour > 0"; it now holds the derived flag (see rwcwx/wet/rules.py),
written here rather than by the ingest (CumulusObs no longer sends it).
"""
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import text

from rwcwx.models import db
from rwcwx.wet.rules import WINDOW_MIN, WetDay, day_bounds_utc, wet_day

VAR, TYPE = "wet", "total"
CONTEXT = timedelta(minutes=2 * WINDOW_MIN + 15)
LABEL = f"rain-gauge tips, {WINDOW_MIN} min window"

UPSERT_AE = """
INSERT INTO avg_extreme (d, var, type, period, val, at, cnt, t_mod, comment)
VALUES (:d, 'wet', 'total', 'day', :val, NULL, :cnt, :t_mod, :comment)
ON DUPLICATE KEY UPDATE val = IF(overridden = 1, val, VALUES(val)), cnt = IF(overridden = 1, cnt, VALUES(cnt)),
  t_mod = VALUES(t_mod), comment = IF(overridden = 1, comment, VALUES(comment))
"""


def load_rows(st: datetime, en: datetime) -> List[Tuple[datetime, Optional[float]]]:
    q = text("SELECT t, rain FROM obs WHERE t >= :st AND t < :en ORDER BY t")
    return [(r[0], r[1]) for r in db.execute(q, st=st, en=en)]


def compute_day(d: date) -> Tuple[WetDay, List[datetime], List[int]]:
    """WetDay plus the day's obs times and their wet flags (0/1)."""
    st, en = day_bounds_utc(d)
    rows = load_rows(st - CONTEXT, en + CONTEXT)
    wd = wet_day(d, rows)
    times = [t for t, _ in rows if st <= t < en]
    flags = [int(any(s.start <= t < s.end for s in wd.spells)) for t in times]
    return wd, times, flags


def write_day(d: date, wd: WetDay, times: List[datetime], flags: List[int]) -> int:
    """Set obs.wet for the day (only rows that change) and upsert the daily total. Returns obs rows changed."""
    st, en = day_bounds_utc(d)
    changed = 0
    wet_ts = [t for t, f in zip(times, flags) if f]
    with db.connect() as conn:
        if wet_ts:
            changed += conn.execute(_in_update(1, wet_ts)).rowcount
        clear = "UPDATE obs SET wet = 0 WHERE t >= :st AND t < :en AND (wet IS NULL OR wet <> 0)"
        params = dict(st=st, en=en)
        if wet_ts:
            clear += " AND t NOT IN (" + ",".join(f":w{i}" for i in range(len(wet_ts))) + ")"
            params.update({f"w{i}": t for i, t in enumerate(wet_ts)})
        changed += conn.execute(text(clear), **params).rowcount
        if times:
            conn.execute(text(UPSERT_AE), d=d, val=round(wd.wet_min / 60, 2), cnt=len(wd.spells),
                         t_mod=datetime.utcnow(), comment=f"{LABEL}; {wd.unknown_tips} tips after data gaps unknown"
                         if wd.unknown_tips else LABEL)
    return changed


def _in_update(val: int, ts: List[datetime]):
    sql = (f"UPDATE obs SET wet = {int(val)} WHERE t IN (" + ",".join(f":t{i}" for i in range(len(ts))) + ")"
           f" AND (wet IS NULL OR wet <> {int(val)})")
    return text(sql).bindparams(**{f"t{i}": t for i, t in enumerate(ts)})


def update_day(d: date) -> WetDay:
    wd, times, flags = compute_day(d)
    write_day(d, wd, times, flags)
    return wd

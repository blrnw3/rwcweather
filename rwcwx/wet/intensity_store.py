"""DB side of daily max 10 / 60-minute rain (rwcwx/wet/intensity.py): reads obs.rain, upserts avg_extreme."""
from datetime import date, datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import text

from rwcwx.models import db
from rwcwx.wet.intensity import WINDOWS, day_intensity
from rwcwx.wet.rules import day_bounds_utc
from rwcwx.wet.store import load_rows

UPSERT = """
INSERT INTO avg_extreme (d, var, type, period, val, at, cnt, t_mod, comment)
VALUES (:d, :var, 'max', 'day', :val, :at, :cnt, :t_mod, :comment)
ON DUPLICATE KEY UPDATE val = IF(overridden = 1, val, VALUES(val)), at = IF(overridden = 1, at, VALUES(at)),
  cnt = IF(overridden = 1, cnt, VALUES(cnt)), t_mod = VALUES(t_mod), comment = IF(overridden = 1, comment, VALUES(comment))
"""


def compute_day(d: date) -> Tuple[Dict[str, Tuple[float, Optional[datetime]]], int]:
    st, en = day_bounds_utc(d)
    rows = load_rows(st - timedelta(minutes=15), en)        # the row before midnight anchors the first delta
    return day_intensity(d, rows), sum(1 for t, _ in rows if st <= t < en)


def write_day(d: date, res: Dict[str, Tuple[float, Optional[datetime]]], n_obs: int) -> None:
    if not n_obs:
        return
    with db.connect() as conn:
        for var, (val, at) in res.items():
            conn.execute(text(UPSERT), d=d, var=var, val=val, at=at, cnt=n_obs, t_mod=datetime.utcnow(),
                         comment=f"max rain in {WINDOWS[var]} min, from gauge tips")


def update_day(d: date) -> None:
    res, n = compute_day(d)
    write_day(d, res, n)

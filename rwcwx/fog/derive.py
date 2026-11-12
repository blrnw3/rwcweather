"""Fog days, derived at query time from the stored daily fog hours (avg_extreme var='fog'): 1 if fog hours > 0.

Also shapes the daily-report payload (foggy / hours / clearing time) from a stored total and the day's frames.
"""
from datetime import date, datetime
from typing import Iterable, List, Optional, Tuple

from dateutil.tz import UTC

from rwcwx.fog import rules

DAY_VAR, DAY_TYPE = "fogday", "total"


def fog_days(fog_avg_exts):
    from rwcwx.model.sun import DerivedDay
    return [DerivedDay(d=ae.d, val=1 if (ae.val or 0) > 0 else 0, hours=ae.val, cnt=ae.cnt, comment=ae.comment)
            for ae in fog_avg_exts]


def fog_day_values(values: Iterable[Tuple]) -> List[Tuple]:
    return [(d, 1 if (v or 0) > 0 else 0) for d, v in values]


def _iso(t: Optional[datetime]) -> Optional[str]:
    if t is None:
        return None
    if t.tzinfo is not None:
        t = t.astimezone(UTC).replace(tzinfo=None)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def cleared_at(rows: Iterable[dict]) -> Optional[datetime]:
    """Time of the first judged no-fog frame after the last fog frame (UTC, naive).

    None if there was no fog, or if the last judged frame in the dawn–1 pm window was still fog
    (fog had not cleared by the end of the window). Unjudged frames in between are skipped.
    """
    rows = list(rows or [])
    last_fog = None
    for r in rows:
        if r.get("value") == 1:
            last_fog = r.get("t")
    if last_fog is None:
        return None
    for r in rows:
        t = r.get("t")
        if t is not None and t > last_fog and r.get("value") == 0:
            return t
    return None


def report(d: date, total: Optional[dict], rows: Optional[list] = None) -> dict:
    """Daily-report view of one local day.

    `total` is the stored avg_extreme row (fog_h, judged) or None when the day was never stored
    (coverage below the 50% threshold, or before the pipeline).
    """
    rows = list(rows or [])
    expected = len(rules.window_frames(d))
    if total is None:
        return dict(available=False, foggy=None, fog_h=None, cleared_at=None, ended_foggy=None,
                    judged=None, expected=expected)
    fog_h = float(total["fog_h"] if total.get("fog_h") is not None else 0)
    foggy = fog_h > 0
    cleared = cleared_at(rows) if foggy else None
    ended_foggy = bool(foggy and cleared is None and any(r.get("value") == 1 for r in rows))
    return dict(available=True, foggy=foggy, fog_h=round(fog_h, 2), cleared_at=_iso(cleared),
                ended_foggy=ended_foggy, judged=total.get("judged"), expected=expected)

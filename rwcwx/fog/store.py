"""DB side of webcam fog: upsert judged frames into obs_inferred (kind='fog') with the rain veto applied here,
then recompute the local day's avg_extreme var='fog' (hours, type 'total'). Fog days are derived from it at query time.

Idempotent: rows upsert on (kind, t); rows with source='manual' are never overwritten; re-posting a day gives
the same result. The veto is applied server-side so backfills and late-arriving rain data are handled the same way.
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from rwcwx.models import db
from rwcwx.fog import rules
from rwcwx.wet.rules import find_tips

SOURCES = ("live", "backfill")

UPSERT = """
INSERT INTO obs_inferred (kind, t, value, prob, minutes, source, flags, model_version, note, t_mod)
VALUES ('fog', :t, :value, :prob, :minutes, :source, :flags, :model_version, :note, :t_mod)
ON DUPLICATE KEY UPDATE
  value = IF(source = 'manual', value, VALUES(value)),
  prob = IF(source = 'manual', prob, VALUES(prob)),
  minutes = IF(source = 'manual', minutes, VALUES(minutes)),
  flags = IF(source = 'manual', flags, VALUES(flags)),
  model_version = IF(source = 'manual', model_version, VALUES(model_version)),
  note = IF(source = 'manual', note, VALUES(note)),
  t_mod = IF(source = 'manual', t_mod, VALUES(t_mod)),
  source = IF(source = 'manual', source, VALUES(source))
"""

UPSERT_AE = """
INSERT INTO avg_extreme (d, var, type, period, val, at, cnt, t_mod, comment)
VALUES (:d, 'fog', 'total', 'day', :val, NULL, :cnt, :t_mod, :comment)
ON DUPLICATE KEY UPDATE val = IF(overridden = 1, val, VALUES(val)), cnt = IF(overridden = 1, cnt, VALUES(cnt)),
  t_mod = VALUES(t_mod), comment = IF(overridden = 1, comment, VALUES(comment))
"""


def load_tips(st: datetime, en: datetime) -> List[tuple]:
    """(t, amount) rain tips between st and en (naive UTC), including first-after-gap tips: rain is rain."""
    q = text("SELECT t, rain FROM obs WHERE t >= :st AND t < :en ORDER BY t")
    rows = [(r[0], r[1]) for r in db.execute(q, st=st - timedelta(minutes=15), en=en)]
    tips, unknown = find_tips(rows)
    return sorted((tp.t, tp.amount) for tp in tips + unknown)


def ingest(rows: List[dict], model_version: str, source: str = "live", now_utc: Optional[datetime] = None) -> Dict:
    """rows: validated dicts {t (naive UTC), fog (bool|None), confidence (float|None), reason, flags}.
    Returns per-row results and the days recomputed."""
    now_utc = now_utc or datetime.utcnow()
    w = timedelta(minutes=rules.VETO_WINDOW_MIN)
    tips = load_tips(min(r["t"] for r in rows) - w, max(r["t"] for r in rows) + w + timedelta(minutes=1)) if rows else []
    existing = _existing_sources([r["t"] for r in rows])
    results, days = [], set()
    with db.connect() as conn:
        for r in rows:
            n = rules.tips_near(r["t"], tips)
            dec = rules.decide(r.get("fog"), r.get("confidence"), r.get("flags"), n)
            status = "skipped_manual" if existing.get(r["t"]) == "manual" else (
                "updated" if r["t"] in existing else "inserted")
            if status != "skipped_manual":
                conf = r.get("confidence")
                conn.execute(text(UPSERT), t=r["t"], value=dec.value,
                             prob=None if conf is None else round(float(conf), 3), minutes=rules.FRAME_MIN,
                             source=source, flags=dec.flags, model_version=model_version[:32],
                             note=(r.get("reason") or None) and r["reason"][:rules.NOTE_MAX], t_mod=now_utc)
            days.add(rules.local_date_of(r["t"]))
            results.append(dict(t=r["t"], status=status, value=dec.value, flags=dec.flags, tips=n))
    rolled = [update_day(d, now_utc) for d in sorted(days)]
    return dict(rows=results, days=rolled)


def _existing_sources(ts: List[datetime]) -> Dict[datetime, str]:
    if not ts:
        return {}
    q = text("SELECT t, source FROM obs_inferred WHERE kind = 'fog' AND t IN ("
             + ",".join(f":t{i}" for i in range(len(ts))) + ")")
    return {r[0]: r[1] for r in db.execute(q, **{f"t{i}": t for i, t in enumerate(ts)})}


def day_rows(d: date) -> List[dict]:
    frames = rules.window_frames(d)
    if not frames:
        return []
    q = text("SELECT t, value, prob, flags, note, source FROM obs_inferred WHERE kind = 'fog' AND t >= :st AND t <= :en"
             " ORDER BY t")
    return [dict(t=r[0], value=None if r[1] is None else int(r[1]), prob=None if r[2] is None else float(r[2]),
                 flags=r[3], note=r[4], source=r[5]) for r in db.execute(q, st=frames[0], en=frames[-1])]


def update_day(d: date, now_utc: Optional[datetime] = None) -> dict:
    """Recompute and (if coverage allows) upsert the day's fog hours. The veto is re-applied to
    non-manual rows so rain data that arrived after the frames were posted still counts."""
    now_utc = now_utc or datetime.utcnow()
    frames = rules.window_frames(d)
    rows = day_rows(d)
    if frames:
        w = timedelta(minutes=rules.VETO_WINDOW_MIN)
        tips = load_tips(frames[0] - w, frames[-1] + w + timedelta(minutes=1))
        for r in rows:
            if r["source"] != "manual" and r["value"] == 1 and rules.tips_near(r["t"], tips) >= rules.VETO_MIN_TIPS:
                r["value"] = 0
                db.execute(text("UPDATE obs_inferred SET value = 0, flags = :f, t_mod = :m WHERE kind = 'fog' AND t = :t"),
                           f=rules.join_flags(rules.parse_flags(r["flags"]) + [rules.VETO_FLAG]), m=now_utc, t=r["t"])
    fd = rules.rollup(d, [r["value"] for r in rows], expected=len(frames))
    if fd.storable:
        with db.connect() as conn:
            conn.execute(text(UPSERT_AE), d=d, val=fd.fog_h, cnt=fd.judged, t_mod=now_utc, comment=fd.comment)
    return dict(d=d.isoformat(), fog_h=fd.fog_h, judged=fd.judged, expected=fd.expected,
                stored=fd.storable)


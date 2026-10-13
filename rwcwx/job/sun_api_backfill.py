"""Fill historical sunshine days the webcam cannot cover with an API estimate (rwcwx.sun.api_estimate).

Targets: local days from --start up to the day before the first live classifier day that have no sun total, or
whose webcam coverage is below --max-cov % (default 70). Partial days are API-only: their few classified frames
are mostly gated/30-min snapshots, and the estimate is calibrated on whole days.

Writes (unless --dry-run):
  * avg_extreme d/'sun'/'total'/'day', comment 'API estimate (api:<name>; ...); webcam coverage X%'. Only rows that
    are absent, or not overridden and themselves estimates ('estimated ...' backfill or 'API estimate ...'). Live
    ('webcam; ...') and manual/overridden totals are never touched. sun_backfill only rewrites 'estimated%' rows,
    so it will not overwrite these.
  * obs_inferred kind='sun_day', t = local midnight (UTC), value = hours, minutes = 1440, source='api:<name>'.
    Webcam rows (kind 'sunny') are untouched. Needs data/migrations/20261013_obs_inferred_source_varchar.sql.
"""
import csv
import os
import re
import sys
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import click  # noqa: E402

from rwcwx import logger  # noqa: E402
from rwcwx.sun.api_estimate import NAME_FULL, NAME_HRRR, comment_for, estimate, features, fetch, fit  # noqa: E402

KIND = "sun_day"
MODEL_VERSION = "hrrr+asos v1"
TRAIN_MIN_COV = 95.0
FIRST_DAY = date(2021, 9, 9)

SELECT_TOTALS = ("SELECT d, val, cnt, comment, overridden FROM avg_extreme "
                 "WHERE var = 'sun' AND type = 'total' AND period = 'day' ORDER BY d")
SELECT_FIRST_LIVE = "SELECT MIN(t) FROM obs_inferred WHERE kind = 'sunny' AND source = 'live'"

UPSERT_TOTAL = """
INSERT INTO avg_extreme (d, var, type, period, val, at, cnt, t_mod, overridden, comment)
VALUES (:d, 'sun', 'total', 'day', :val, NULL, 0, :t_mod, 0, :comment)
ON DUPLICATE KEY UPDATE
  val = IF(overridden = 0 AND (comment LIKE 'estimated%' OR comment LIKE 'API estimate%'), VALUES(val), val),
  cnt = IF(overridden = 0 AND (comment LIKE 'estimated%' OR comment LIKE 'API estimate%'), VALUES(cnt), cnt),
  t_mod = IF(overridden = 0 AND (comment LIKE 'estimated%' OR comment LIKE 'API estimate%'), VALUES(t_mod), t_mod),
  comment = IF(overridden = 0 AND (comment LIKE 'estimated%' OR comment LIKE 'API estimate%'), VALUES(comment), comment)
"""
UPSERT_ROW = """
INSERT INTO obs_inferred (kind, t, value, prob, minutes, source, flags, model_version, t_mod)
VALUES (:kind, :t, :value, NULL, 1440, :source, NULL, :model_version, :t_mod)
ON DUPLICATE KEY UPDATE
  value = IF(source LIKE 'api:%', VALUES(value), value),
  source = IF(source LIKE 'api:%', VALUES(source), source),
  model_version = IF(source LIKE 'api:%', VALUES(model_version), model_version),
  t_mod = IF(source LIKE 'api:%', VALUES(t_mod), t_mod)
"""


def coverage_of(comment: Optional[str]) -> Optional[float]:
    m = re.search(r"coverage ([\d.]+)%", comment or "")
    return float(m.group(1)) if m else None


def is_estimate(comment: Optional[str]) -> bool:
    return bool(comment) and (comment.startswith("estimated") or comment.startswith("API estimate"))


def plan(totals: Dict[date, dict], start: date, end: date, max_cov: float) -> Dict[date, Optional[float]]:
    """-> {target day: webcam coverage % or None}. Pure; see module docstring for the rules."""
    out: Dict[date, Optional[float]] = {}
    d = start
    while d <= end:
        t = totals.get(d)
        if t is None:
            out[d] = None
        elif not t["overridden"] and is_estimate(t["comment"]):
            cov = coverage_of(t["comment"])
            if t["comment"].startswith("API estimate") or (cov is not None and cov < max_cov):
                out[d] = cov
        d += timedelta(days=1)
    return out


def training_rows(totals: Dict[date, dict], feats: dict, daylight) -> List[dict]:
    rows = []
    for d, t in totals.items():
        cov = coverage_of(t["comment"])
        if t["overridden"] or cov is None or cov < TRAIN_MIN_COV or (t["comment"] or "").startswith("API"):
            continue
        if d in feats:
            rows.append(dict(d=d, hours=t["val"], N=daylight(d), **feats[d]))
    return rows


def local_midnight_utc(d: date) -> datetime:
    from dateutil.tz import UTC
    from rwcwx.config import TZ
    return datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(UTC).replace(tzinfo=None)


@click.command()
@click.option("--start", default=FIRST_DAY.isoformat(), show_default=True)
@click.option("--end", default=None, help="Last local day (default: day before the first live classifier day)")
@click.option("--max-cov", type=float, default=70.0, show_default=True, help="Target webcam coverage below this %")
@click.option("--dry-run", is_flag=True, help="Read-only: fetch, fit and list, no DB writes")
@click.option("--csv", "csv_path", default=None)
def main(start, end, max_cov, dry_run, csv_path):
    from sqlalchemy import create_engine, text
    from rwcwx.model.sun import daylight_h
    engine = create_engine(f"mysql://{os.environ['MYSQL_URL']}", pool_pre_ping=True)
    with engine.connect() as c:
        totals = {r[0]: dict(val=r[1], cnt=r[2], comment=r[3], overridden=r[4])
                  for r in c.execute(text(SELECT_TOTALS))}
        first_live = c.execute(text(SELECT_FIRST_LIVE)).scalar()
    start = date.fromisoformat(start)
    end = date.fromisoformat(end) if end else (
        first_live.date() - timedelta(days=1) if first_live else date.today() - timedelta(days=1))
    targets = plan(totals, start, end, max_cov)
    logger.info(f"{len(targets)} target days {start}..{end} "
                f"({sum(v is None for v in targets.values())} without a total, max_cov {max_cov}%)")
    dni, clear = fetch(start, end)
    days = sorted(set(totals) | set(targets))
    N = {d: daylight_h(d) for d in days}
    feats = features(days, N, dni, clear)
    train = training_rows({d: t for d, t in totals.items() if start <= d <= end}, feats, lambda d: N[d])
    full = fit(train, ("hrrr_f", "asos_clear"), NAME_FULL)
    hrrr = fit(train, ("hrrr_f",), NAME_HRRR)
    for f in (full, hrrr):
        logger.info(f"fit {f.name}: n={f.n} coef={f.coef} CV MAE {f.cv_mae_h} h bias {f.cv_bias_h} h")
    now = datetime.utcnow().replace(microsecond=0)
    out = []
    for d, cov in sorted(targets.items()):
        est = estimate(d, N[d], feats[d], full, hrrr)
        if est is None:
            logger.warning(f"{d}: no HRRR data, skipped")
            continue
        old = totals.get(d)
        out.append(dict(d=d, val=est["val"], source=est["name"], comment=comment_for(est, cov),
                        old=old["val"] if old else None, cov=cov, possible=round(N[d], 2)))
    for r in out:
        logger.info(f"{r['d']}: {r['val']:5.2f} h of {r['possible']:5.2f} ({r['source']}); "
                    f"was {r['old']}, webcam coverage {r['cov']}")
    if csv_path:
        with open(csv_path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0]) if out else ["d"])
            w.writeheader()
            w.writerows(out)
    if dry_run:
        logger.info(f"dry run: {len(out)} days, nothing written")
        return
    with engine.begin() as c:
        c.execute(text(UPSERT_TOTAL), [dict(d=r["d"], val=r["val"], comment=r["comment"], t_mod=now) for r in out])
        c.execute(text(UPSERT_ROW), [dict(kind=KIND, t=local_midnight_utc(r["d"]), value=r["val"], source=r["source"],
                                          model_version=MODEL_VERSION, t_mod=now) for r in out])
    logger.info(f"wrote {len(out)} days")


if __name__ == "__main__":
    main()

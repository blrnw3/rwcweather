"""Backfill missing minute obs from Cumulus interval charts (or a monthly log) and recompute daily stats.

Default is a dry run: no database writes. Apply (after a backup) requires --apply and is refused
without it. obs.rain is the daily running total (reset at local midnight), not a delta, so filling
a gap does not increment rows that save_latest has already written after the gap.

Idempotent: inserts use the same ON DUPLICATE KEY UPDATE as save_latest for the gap minutes only;
daily/avg_extreme rows are recomputed from all observations of that local day (including live rows
after the gap). Re-running with the same source upserts the same values.

Typical sources, in order of preference:
  1. Cumulus website interval JSON under /var/www/rwc/html/cumulus (1-minute, last ~24 hours).
  2. A monthly log (Nov26log.txt) uploaded from the Cumulus PC data folder, if the charts have
     rolled past the gap.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import click
from sqlalchemy import text
from sqlalchemy.dialects.mysql import insert

from rwcwx import logger
from rwcwx.calc.avg_extreme import DaySummary, Rain, Temp
from rwcwx.config import TZ
from rwcwx.cumulus_interval import as_obs_params, load_interval_dir, parse_monthly_log, rows_in_window
from rwcwx.job.save_latest import CumulusObsImporter
from rwcwx.models import db, m
from rwcwx.wet.intensity import day_intensity
from rwcwx.wet.rules import day_bounds_utc, wet_day
from rwcwx.wet.store import CONTEXT as WET_CONTEXT

IN_TO_MM = 25.4

# Default window for the 2026-11-18/19 ingest outage: first missing minute after 22:15 PT,
# last missing minute before the 07:01 PT restart row.
DEFAULT_AFTER = "2026-11-18T22:15:00-08:00"
DEFAULT_BEFORE = "2026-11-19T07:01:00-08:00"
DEFAULT_JSON_DIR = "/var/www/rwc/html/cumulus"

# avg_extreme fields this tool reports / recomputes (sun is owned by the webcam jobs, left alone).
REPORT_AE = (
    ("rain", "total"),
    ("rain", "max"),
    ("rain", "min"),
    ("temp", "min"),
    ("temp", "max"),
    ("temp", "avg"),
    ("rain10", "max"),
    ("rain60", "max"),
    ("wet", "total"),
)


def _parse_aware(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt


def _local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def _fmt(dt) -> str:
    if dt is None:
        return ""
    return _local(dt).strftime("%Y-%m-%d %H:%M %Z") if hasattr(dt, "strftime") else str(dt)


def _mm(inches) -> str:
    if inches is None:
        return ""
    return f"{float(inches) * IN_TO_MM:.1f} mm"


def load_source(json_dir: Optional[Path], monthly_log: Optional[Path], after: datetime, before: datetime) -> List[dict]:
    if monthly_log is not None:
        by_t = {r["t_local"]: r for r in parse_monthly_log(monthly_log)}
        return rows_in_window(by_t, after, before)
    if json_dir is None:
        raise click.ClickException("Provide --json-dir or --monthly-log")
    return rows_in_window(load_interval_dir(json_dir), after, before)


def fetch_obs(st: datetime, en: datetime) -> List[dict]:
    """Read-only obs rows with t in [st, en) as UTC-naive instants stored in the table."""
    q = text("SELECT t, t_obs, temp, humi, wind, gust, wdir, rain, pres, intemp, inhumi, pm2, wet "
             "FROM obs WHERE t >= :st AND t < :en ORDER BY t")
    rows = []
    for r in db.execute(q, st=st.replace(tzinfo=None) if st.tzinfo else st,
                        en=en.replace(tzinfo=None) if en.tzinfo else en):
        rows.append(dict(t=r[0], t_obs=r[1], temp=r[2], humi=r[3], wind=r[4], gust=r[5], wdir=r[6],
                         rain=r[7], pres=r[8], intemp=r[9], inhumi=r[10], pm2=r[11], wet=r[12]))
    return rows


def fetch_ae(days: Sequence[date]) -> Dict[date, Dict[Tuple[str, str], dict]]:
    out: Dict[date, Dict[Tuple[str, str], dict]] = {d: {} for d in days}
    if not days:
        return out
    q = text("SELECT d, var, type, val, at, cnt, t_mod, overridden, comment "
             "FROM avg_extreme WHERE period='day' AND d >= :a AND d <= :b")
    for r in db.execute(q, a=min(days), b=max(days)):
        d, var, typ, val, at, cnt, t_mod, overridden, comment = r
        if (var, typ) in REPORT_AE or var in ("rain", "temp", "rain10", "rain60", "wet"):
            out.setdefault(d, {})[(var, typ)] = dict(val=val, at=at, cnt=cnt, t_mod=t_mod,
                                                     overridden=overridden, comment=comment)
    return out


def existing_times(st: datetime, en: datetime) -> set:
    q = text("SELECT t FROM obs WHERE t > :st AND t < :en")
    return {r[0] for r in db.execute(q, st=st.replace(tzinfo=None), en=en.replace(tzinfo=None))}


def day_obs_objects(rows: Iterable[dict]) -> list:
    return [SimpleNamespace(**{k: r.get(k) for k in
                               ("t", "temp", "humi", "wind", "gust", "wdir", "rain", "pres",
                                "intemp", "inhumi", "pm2", "dewpt", "aqi")})
            for r in rows]


def merge_day(d: date, existing: List[dict], gap_params: List[dict]) -> List[dict]:
    st, en = day_bounds_utc(d)
    st_n, en_n = st.replace(tzinfo=None), en.replace(tzinfo=None)
    by_t = {r["t"]: dict(r) for r in existing if st_n <= r["t"] < en_n}
    for p in gap_params:
        if st_n <= p["t"] < en_n:
            by_t[p["t"]] = dict(p)
    return [by_t[t] for t in sorted(by_t)]


def compute_after(d: date, merged_day: List[dict], with_context: List[dict]) -> Dict[Tuple[str, str], dict]:
    obs_objs = day_obs_objects(merged_day)
    stats = DaySummary(d).stats(obs_objs)
    out = {}
    if Rain in stats and stats[Rain].count:
        s = stats[Rain]
        out[("rain", "total")] = dict(val=s.total, at=None, cnt=s.count)
        out[("rain", "max")] = dict(val=s.max_val, at=s.max_at, cnt=s.count)
        out[("rain", "min")] = dict(val=s.min_val, at=s.min_at, cnt=s.count)
    if Temp in stats and stats[Temp].count:
        s = stats[Temp]
        out[("temp", "avg")] = dict(val=s.avg, at=None, cnt=s.count)
        out[("temp", "max")] = dict(val=s.max_val, at=s.max_at, cnt=s.count)
        out[("temp", "min")] = dict(val=s.min_val, at=s.min_at, cnt=s.count)
    rain_rows = [(r["t"], float(r["rain"]) if r.get("rain") is not None else None) for r in with_context]
    intens = day_intensity(d, rain_rows)
    day_cnt = len(merged_day)
    for var, (val, at) in intens.items():
        out[(var, "max")] = dict(val=val, at=at, cnt=day_cnt)
    wd = wet_day(d, rain_rows)
    out[("wet", "total")] = dict(val=round(wd.wet_min / 60, 2), at=None, cnt=len(wd.spells))
    return out


def format_ae_val(var: str, typ: str, rec: Optional[dict]) -> str:
    if not rec or rec.get("val") is None:
        return "—"
    val = float(rec["val"])
    at = _fmt(rec.get("at")) if rec.get("at") else ""
    extra = f" @ {at}" if at else ""
    cnt = rec.get("cnt")
    cnt_s = f", cnt={cnt}" if cnt is not None else ""
    if var in ("rain", "rain10", "rain60"):
        return f"{val:.3f} in ({_mm(val)}){extra}{cnt_s}"
    if var == "temp":
        return f"{val:.2f} °C{extra}{cnt_s}"
    if var == "wet":
        return f"{val:.2f} h{cnt_s}"
    return f"{val}{extra}{cnt_s}"


def backup_rows(backup_dir: Path, after: datetime, before: datetime, days: Sequence[date]) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    st = after.astimezone(timezone.utc).replace(tzinfo=None)
    en = before.astimezone(timezone.utc).replace(tzinfo=None)
    obs = fetch_obs(st, en)
    # also keep a few boundary rows
    pad = fetch_obs(st - timedelta(minutes=2), st) + fetch_obs(en, en + timedelta(minutes=2))
    obs_path = backup_dir / "obs_gap_and_boundary.csv"
    fields = ["t", "t_obs", "temp", "humi", "wind", "gust", "wdir", "rain", "pres", "intemp", "inhumi", "pm2", "wet"]
    with obs_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in pad + obs:
            w.writerow({k: r.get(k) for k in fields})
    ae = fetch_ae(days)
    ae_path = backup_dir / "avg_extreme_days.csv"
    with ae_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["d", "var", "type", "val", "at", "cnt", "t_mod", "overridden", "comment"])
        q = text("SELECT d, var, type, val, at, cnt, t_mod, overridden, comment "
                 "FROM avg_extreme WHERE period='day' AND d >= :a AND d <= :b ORDER BY d, var, type")
        for r in db.execute(q, a=min(days), b=max(days)):
            w.writerow(list(r))
    logger.info("Backed up %s obs (+ %s boundary) to %s and avg_extreme to %s",
                len(obs), len(pad), obs_path, ae_path)


def apply_gap(params: List[dict]) -> int:
    n = 0
    for p in params:
        stmt = insert(m.obs).values(**p).on_duplicate_key_update(**p, t_mod=datetime.utcnow())
        db.execute(stmt)
        n += 1
    return n


def print_report(
    after: datetime,
    before: datetime,
    source_rows: List[dict],
    to_insert: List[dict],
    already: int,
    before_ae: Dict[date, dict],
    after_ae: Dict[date, dict],
    days: Sequence[date],
    dry_run: bool,
) -> None:
    click.echo(f"{'DRY RUN' if dry_run else 'APPLY'}: gap {_fmt(after)} < t < {_fmt(before)}")
    click.echo(f"Source minutes in window: {len(source_rows)}")
    click.echo(f"Would insert/upsert: {len(to_insert)}  already present: {already}")
    if source_rows:
        click.echo("Sample source (local, temp °C, rain in / mm):")
        samples = source_rows[:3] + (source_rows[-3:] if len(source_rows) > 6 else [])
        # also midnight pair if present
        mid = [r for r in source_rows if r["t_local"].hour == 0 and r["t_local"].minute == 0
               or (r["t_local"].hour == 23 and r["t_local"].minute == 59)]
        seen = set()
        for r in samples + mid:
            key = r["t_local"]
            if key in seen:
                continue
            seen.add(key)
            click.echo(f"  {_fmt(r['t_local'])}  temp={r.get('temp')}  rain={r.get('rain')} in ({_mm(r.get('rain'))})")
    if to_insert:
        click.echo("First/last obs params (t is UTC-naive, as stored):")
        for p in (to_insert[0], to_insert[-1]):
            click.echo(f"  t={p['t']} t_obs={p['t_obs']} temp={p.get('temp')} rain={p.get('rain')} "
                       f"humi={p.get('humi')} pres={p.get('pres')} wind={p.get('wind')} gust={p.get('gust')} "
                       f"wdir={p.get('wdir')}")
    for d in days:
        click.echo(f"\n{d} daily / avg_extreme before -> after:")
        for var, typ in REPORT_AE:
            b = before_ae.get(d, {}).get((var, typ))
            a = after_ae.get(d, {}).get((var, typ))
            click.echo(f"  {var}/{typ}: {format_ae_val(var, typ, b)}  ->  {format_ae_val(var, typ, a)}")
    click.echo("""
Rain / double-counting: obs.rain is a daily running total, reset at local midnight, not a tip delta.
This tool only upserts minutes strictly inside the gap, so it does not change rows save_latest has
already written after the gap (and does not add the 07:01+ rain total on top of the filled hours).
Nov 19 rain/total is max(rain) over the whole local day, so it stays in step with later live rows.

Idempotent: re-running upserts the same gap minutes (ON DUPLICATE KEY UPDATE with the same values)
and recomputes avg_extreme from all obs of each day. It is a no-op on already-filled minutes.

Gust in the charts is the 1-minute chart value, not save_latest's intra-minute max from realtime.txt.
pm2 is left unset (no history in the charts). sun/* is not recomputed.
""")


@click.command()
@click.option("--json-dir", type=click.Path(path_type=Path), default=DEFAULT_JSON_DIR,
              show_default=True, help="Directory of Cumulus interval JSON (tempdata.json, …)")
@click.option("--monthly-log", type=click.Path(exists=True, path_type=Path), default=None,
              help="Optional Cumulus monthly log (e.g. Nov26log.txt) instead of the charts")
@click.option("--after", "after_s", default=DEFAULT_AFTER, show_default=True,
              help="Exclusive start (ISO, station-local or offset)")
@click.option("--before", "before_s", default=DEFAULT_BEFORE, show_default=True,
              help="Exclusive end (ISO)")
@click.option("--apply", "do_apply", is_flag=True, default=False,
              help="Write obs + recompute avg_extreme. Refused unless this flag is set.")
@click.option("--backup-dir", type=click.Path(path_type=Path), default=None,
              help="Directory for CSV backups (required with --apply)")
def main(json_dir: Path, monthly_log: Optional[Path], after_s: str, before_s: str,
         do_apply: bool, backup_dir: Optional[Path]) -> None:
    after, before = _parse_aware(after_s), _parse_aware(before_s)
    if not after < before:
        raise click.ClickException("after must be before before")
    source = load_source(None if monthly_log else json_dir, monthly_log, after, before)
    params = [as_obs_params(r) for r in source]
    already_set = existing_times(
        after.astimezone(timezone.utc), before.astimezone(timezone.utc)
    )
    to_insert, already = [], 0
    for p in params:
        if p["t"] in already_set:
            already += 1
        else:
            to_insert.append(p)

    days = []
    d = after.astimezone(TZ).date()
    last = (before.astimezone(TZ) - timedelta(seconds=1)).date()
    while d <= last:
        days.append(d)
        d += timedelta(days=1)

    # existing full-day obs (plus a little context for wet/intensity at the edges)
    existing_by_day = {}
    for day in days:
        st, en = day_bounds_utc(day)
        existing_by_day[day] = fetch_obs(st - WET_CONTEXT, en + WET_CONTEXT)

    before_ae = fetch_ae(days)
    after_ae = {}
    for day in days:
        # merge only gap params into the day's observations; keep pre-gap and post-gap DB rows
        merged = merge_day(day, existing_by_day[day], params)
        # Keep midnight context from the fetch window, overlaid with gap minutes.
        ctx_by_t = {r["t"]: dict(r) for r in existing_by_day[day]}
        for p in params:
            ctx_by_t[p["t"]] = dict(p)
        ctx = [ctx_by_t[k] for k in sorted(ctx_by_t)]
        after_ae[day] = compute_after(day, merged, ctx)

    print_report(after, before, source, to_insert, already, before_ae, after_ae, days, dry_run=not do_apply)

    if not do_apply:
        return
    if backup_dir is None:
        raise click.ClickException("--apply requires --backup-dir")
    backup_rows(Path(backup_dir), after, before, days)
    n = apply_gap(params)
    logger.info("Upserted %s gap obs rows", n)
    for day in days:
        CumulusObsImporter.update_avg_ext(day)
        logger.info("Recomputed avg_extreme / wet / rain intensity for %s", day)
    click.echo(f"Applied {n} obs upserts and recomputed {', '.join(str(d) for d in days)}.")


if __name__ == "__main__":
    main()

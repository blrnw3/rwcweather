"""Shape Open-Meteo Single Runs payloads into per-cycle totals and a cumulative heatmap.

The Previous Runs API only has daily lead-time offsets. The Single Runs API
exposes each 00/06/12/18z cycle independently (GFS seamless: four full-length
runs per day; ECMWF IFS 0.25°: 00/12z to 10 days, 06/18z about 6 days).
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from rwcwx.config import TZ, TZ_NAME
from rwcwx.forecast.ensemble import window_total
from rwcwx.forecast.meteogram import ms, parse_local
from rwcwx.forecast import openmeteo

OPERATIONAL = {
    "gfs": dict(
        key="gfs",
        model="gfs_seamless",
        label="GFS seamless (HRRR + GFS operational)",
        short="GFS",
    ),
    "ecmwf": dict(
        key="ecmwf",
        model="ecmwf_ifs025",
        label="ECMWF IFS 0.25° operational",
        short="ECMWF",
    ),
}

# Counterpart used to identify the current ensemble control's init time.
ENSEMBLE_MATCH = {
    "gefs": "gfs",
    "ecmwf": "ecmwf",
}

# MAE (mm/h) below which a control series is treated as a match to a cycle.
# Scored only on the first MATCH_WINDOW_HOURS of each run, and only among
# cycles within MATCH_RECENT_HOURS of the newest available operational run.
# GEFS control is not the same model as GFS operational, so it usually will
# not match; we then omit the run label rather than guess.
MATCH_MAE_MAX = 0.10
MATCH_MIN_HOURS = 12
MATCH_WINDOW_HOURS = 36
MATCH_RECENT_HOURS = 12


def run_label(run_utc: datetime, with_date: bool = True) -> str:
    run_utc = run_utc.astimezone(timezone.utc)
    hz = f"{run_utc.hour:02d}z"
    if not with_date:
        return hz
    return f"{hz} {run_utc.day} {run_utc.strftime('%b')}"


def run_iso(run_utc: datetime) -> str:
    return run_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hourly(data: Optional[dict]) -> Tuple[List[Optional[datetime]], List[Optional[float]]]:
    if not data or not isinstance(data.get("hourly"), dict):
        return [], []
    hourly = data["hourly"]
    times = [parse_local(t) for t in (hourly.get("time") or [])]
    vals = list(hourly.get("precipitation") or [])
    # parse_local treats naive stamps as station-local; Single Runs are requested in UTC.
    out_t = []
    for t, raw in zip(times, hourly.get("time") or []):
        if t is None:
            out_t.append(None)
            continue
        # If the upstream said timezone=UTC, re-attach UTC when the stamp has no offset.
        if isinstance(raw, str) and ("Z" in raw or "+" in raw[10:] or raw.endswith("Z")):
            out_t.append(t)
        else:
            # "2026-11-17T12:00" from timezone=UTC must be UTC, not PT.
            try:
                naive = datetime.fromisoformat(raw)
            except ValueError:
                out_t.append(t)
                continue
            if naive.tzinfo is None:
                out_t.append(naive.replace(tzinfo=timezone.utc))
            else:
                out_t.append(naive)
    if len(vals) < len(out_t):
        vals.extend([None] * (len(out_t) - len(vals)))
    return out_t, vals


def six_hour_columns(start: datetime, end: datetime) -> List[datetime]:
    """00/06/12/18 clock hours in the station zone, from the first such time after `start` through `end`."""
    local = start.astimezone(TZ).replace(minute=0, second=0, microsecond=0)
    hour = (local.hour // 6) * 6
    t = local.replace(hour=hour)
    if t <= start.astimezone(TZ):
        t += timedelta(hours=6)
    end_local = end.astimezone(TZ)
    cols = []
    while t <= end_local:
        cols.append(t)
        t += timedelta(hours=6)
    return cols


def cumulative_at(times, values, start: datetime, points: Sequence[datetime]) -> List[Optional[float]]:
    out = []
    for t in points:
        total, cov = window_total(times, values, start, t)
        out.append(total)
    return out


def slot_record(model_meta: dict, run_utc: datetime, data: Optional[dict],
                start: datetime, windows: Sequence[int]) -> Optional[dict]:
    if not data:
        return None
    times, vals = _hourly(data)
    if not times:
        return None
    n_valid = sum(1 for v in vals if v is not None)
    if n_valid == 0:
        return None
    # Horizon of this particular cycle (short 06/18z ECMWF ~144 h).
    idxs = [i for i, v in enumerate(vals) if v is not None]
    first, last = times[idxs[0]], times[idxs[-1]]
    horizon_h = None
    if first is not None and last is not None:
        horizon_h = int(round((last - first).total_seconds() / 3600.0)) + 1
    rec = dict(
        model=model_meta["model"],
        short=model_meta["short"],
        label=model_meta["label"],
        run=run_iso(run_utc),
        run_label=run_label(run_utc),
        run_z=run_label(run_utc, with_date=False),
        horizon_hours=horizon_h,
        totals={},
        times=[ms(t) for t in times],
        precip=[None if v is None else float(v) for v in vals],
    )
    for hours in windows:
        end = start + timedelta(hours=hours)
        total, cov = window_total(times, vals, start, end)
        rec["totals"][str(hours)] = dict(
            total=total,
            coverage=round(cov, 3),
        )
    return rec


def history_for_model(meta: dict, fetched: dict, start: datetime,
                      windows: Sequence[int] = (120, 168, 240)) -> List[dict]:
    out = []
    for run_utc in sorted(fetched, reverse=True):
        rec = slot_record(meta, run_utc, fetched.get(run_utc), start, windows)
        if rec:
            out.append(rec)
    return out


def heatmap(models_runs: Dict[str, List[dict]], start: datetime, hours: int = 240,
            step_hours: int = 6) -> dict:
    end = start + timedelta(hours=hours)
    cols = six_hour_columns(start, end)
    columns = [dict(
        t=ms(t),
        iso=t.isoformat(),
        label=_col_label(t),
    ) for t in cols]
    models = {}
    for key, runs in models_runs.items():
        rows = []
        for rec in runs:  # already newest first
            times = [datetime.fromtimestamp(t / 1000.0, tz=timezone.utc) if t is not None else None
                     for t in rec.get("times") or []]
            vals = rec.get("precip") or []
            rows.append(dict(
                run=rec["run"],
                run_label=rec["run_label"],
                run_z=rec["run_z"],
                horizon_hours=rec.get("horizon_hours"),
                values=cumulative_at(times, vals, start, cols),
            ))
        models[key] = rows
    return dict(
        timezone=TZ_NAME,
        start=start.isoformat(),
        hours=hours,
        step_hours=step_hours,
        columns=columns,
        models=models,
    )


def _col_label(t: datetime) -> str:
    local = t.astimezone(TZ)
    return local.strftime("%a %-d %-I %p").replace(" 0", " ").replace("AM", "AM PT").replace("PM", "PM PT")


def match_run(ens_hourly: Optional[dict], records: List[dict]) -> Optional[dict]:
    """Identify which operational cycle the current ensemble control matches.

    Only recent cycles are considered, and only the first MATCH_WINDOW_HOURS
    after each run's init are scored, so a dry spell in the far past cannot
    masquerade as a match. The newest cycle under MATCH_MAE_MAX wins. Returns
    None when no cycle is close enough — callers must not invent a fallback.
    """
    if not ens_hourly or not records:
        return None
    # Ensemble times are station-local (timezone=TZ_NAME on that request).
    e_times = [parse_local(t) for t in (ens_hourly.get("time") or [])]
    e_vals = list(ens_hourly.get("precipitation") or [])
    e_map = {}
    for t, v in zip(e_times, e_vals):
        if t is None or v is None:
            continue
        e_map[int(t.timestamp() // 3600)] = float(v)

    newest = None
    for rec in records:
        try:
            run_dt = datetime.fromisoformat(rec["run"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        if newest is None or run_dt > newest:
            newest = run_dt
    if newest is None:
        return None
    cutoff = newest - timedelta(hours=MATCH_RECENT_HOURS)

    best = None
    for rec in records:
        try:
            run_dt = datetime.fromisoformat(rec["run"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        if run_dt < cutoff:
            continue
        lo = int(run_dt.timestamp() // 3600)
        hi = lo + MATCH_WINDOW_HOURS
        times = rec.get("times") or []
        vals = rec.get("precip") or []
        diffs = []
        for t_ms, v in zip(times, vals):
            if t_ms is None or v is None:
                continue
            key = int((t_ms / 1000.0) // 3600)
            if key < lo or key >= hi:
                continue
            if key in e_map:
                diffs.append(abs(e_map[key] - float(v)))
        if len(diffs) < MATCH_MIN_HOURS:
            continue
        mae = sum(diffs) / len(diffs)
        if mae > MATCH_MAE_MAX:
            continue
        # Newest qualifying cycle wins (records are usually newest-first).
        if best is None or run_dt > best["_run_dt"]:
            best = dict(
                run=rec["run"],
                run_label=rec["run_label"],
                run_z=rec["run_z"],
                mae=round(mae, 4),
                n=len(diffs),
                matched=True,
                _run_dt=run_dt,
            )
    if not best:
        return None
    best.pop("_run_dt", None)
    return best


def build_history(now_utc: datetime, start: datetime,
                  ensembles: Optional[Dict[str, Optional[dict]]] = None) -> dict:
    """Fetch (cached) single runs for both operational models and shape history + heatmap."""
    slots = openmeteo.run_slots(now_utc)
    windows = (120, 168, 240)
    by_key: Dict[str, List[dict]] = {}
    for key, meta in OPERATIONAL.items():
        fetched = openmeteo.fetch_runs(meta["model"], slots, now_utc)
        by_key[key] = history_for_model(meta, fetched, start, windows)

    # Current ensemble init, by matching control to an operational cycle.
    current = {}
    ensembles = ensembles or {}
    for ens_key, op_key in ENSEMBLE_MATCH.items():
        raw = ensembles.get(ens_key)
        hourly = raw.get("hourly") if isinstance(raw, dict) else None
        matched = match_run(hourly, by_key.get(op_key) or [])
        if matched:
            current[ens_key] = matched

    latest_ops = {}
    for key, recs in by_key.items():
        if recs:
            latest_ops[key] = dict(run=recs[0]["run"], run_label=recs[0]["run_label"],
                                   run_z=recs[0]["run_z"])

    heat = heatmap(by_key, start, hours=240)

    def public_runs(recs):
        return [{k: v for k, v in r.items() if k not in ("times", "precip")} for r in recs]

    return dict(
        source="Open-Meteo Single Runs API",
        source_url="https://open-meteo.com/en/docs/single-runs-api",
        lookback_days=openmeteo.RUN_LOOKBACK_DAYS,
        timezone=TZ_NAME,
        operational={k: dict(model=OPERATIONAL[k]["model"], label=OPERATIONAL[k]["label"],
                             short=OPERATIONAL[k]["short"], runs=public_runs(v))
                     for k, v in by_key.items()},
        current=current,
        latest=latest_ops,
        heatmap=heat,
    )

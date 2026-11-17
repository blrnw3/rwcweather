"""Shape Open-Meteo ensemble and previous-runs payloads into rain-total summaries (no I/O)."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from rwcwx.config import TZ, TZ_NAME
from rwcwx.forecast.meteogram import ms, parse_local

WINDOWS = (168, 240)  # 7-day and 10-day totals, hours
PERCENTILES = (10, 25, 50, 75, 90)

MODELS = {
    "gefs": dict(
        id="gfs025",
        name="GEFS (GFS ensemble, 0.25°)",
        control_label="GEFS control",
        previous_model="gfs_seamless",
        previous_label="GFS seamless (HRRR + GFS operational)",
    ),
    "ecmwf": dict(
        id="ecmwf_ifs025",
        name="ECMWF ENS (IFS 0.25°)",
        control_label="ECMWF control",
        previous_model="ecmwf_ifs025",
        previous_label="ECMWF IFS 0.25° operational",
    ),
}


def _times(hourly: dict) -> List[Optional[datetime]]:
    return [parse_local(t) for t in (hourly.get("time") or [])]


def member_series(hourly: dict) -> Dict[str, List[Optional[float]]]:
    """Map control + members to precipitation series aligned with hourly['time']."""
    out: Dict[str, List[Optional[float]]] = {}
    if "precipitation" in hourly:
        out["control"] = list(hourly["precipitation"])
    for key, vals in hourly.items():
        if not key.startswith("precipitation_member"):
            continue
        tag = "m" + key[len("precipitation_member"):]
        out[tag] = list(vals)
    return out


def window_total(times: Sequence[Optional[datetime]], values: Sequence[Optional[float]],
                 start: datetime, end: datetime) -> Tuple[Optional[float], float]:
    """Sum values in [start, end). Returns (total_or_None, coverage 0-1)."""
    if not times or not values:
        return None, 0.0
    total = 0.0
    covered = 0
    needed = 0
    for t, v in zip(times, values):
        if t is None or t < start or t >= end:
            continue
        needed += 1
        if v is None:
            continue
        total += float(v)
        covered += 1
    if needed == 0:
        return None, 0.0
    coverage = covered / needed
    # Require most of the window (allow a few missing hours).
    if coverage < 0.8:
        return None, coverage
    return round(total, 3), coverage


def percentiles(vals: List[float], ps: Sequence[int] = PERCENTILES) -> Dict[str, float]:
    if not vals:
        return {}
    xs = sorted(vals)
    n = len(xs)
    out = dict(min=round(xs[0], 3), max=round(xs[-1], 3),
               mean=round(sum(xs) / n, 3))
    for p in ps:
        # Linear interpolation, inclusive ranks (Cunnane-ish: (n-1)*p/100).
        if n == 1:
            out["p" + str(p)] = round(xs[0], 3)
            continue
        k = (n - 1) * (p / 100.0)
        lo = int(k)
        hi = min(lo + 1, n - 1)
        frac = k - lo
        out["p" + str(p)] = round(xs[lo] + frac * (xs[hi] - xs[lo]), 3)
    return out


def _cumulative(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    run, out = 0.0, []
    seen = False
    for v in values:
        if v is None:
            out.append(run if seen else None)
            continue
        seen = True
        run += float(v)
        out.append(round(run, 3))
    return out


def _aligned_window(times: Sequence[Optional[datetime]], values: Sequence[Optional[float]],
                    start: datetime, end: datetime) -> Tuple[List[int], List[Optional[float]]]:
    xs, ys = [], []
    for t, v in zip(times, values):
        if t is None or t < start or t >= end:
            continue
        xs.append(ms(t))
        ys.append(None if v is None else float(v))
    return xs, ys


def _accumulation(times, series: Dict[str, List[Optional[float]]], start, end) -> dict:
    # Use control (or first member) times in the window as the shared x-axis.
    base = series.get("control") or next(iter(series.values()), [])
    xs, _ = _aligned_window(times, base, start, end)
    members = {}
    for name, vals in series.items():
        mx, my = _aligned_window(times, vals, start, end)
        if mx != xs:
            # Re-align by timestamp if a series is missing hours (shouldn't happen).
            lookup = dict(zip(mx, my))
            my = [lookup.get(x) for x in xs]
        members[name] = _cumulative(my)
    # Mean / percentiles of the cumulative at each step (members + control).
    names = list(members)
    mean, p10, p90 = [], [], []
    for i in range(len(xs)):
        pts = [members[n][i] for n in names if members[n][i] is not None]
        if not pts:
            mean.append(None); p10.append(None); p90.append(None)
            continue
        stats = percentiles(pts)
        mean.append(stats.get("mean"))
        p10.append(stats.get("p10"))
        p90.append(stats.get("p90"))
    return dict(times=xs, mean=mean, p10=p10, p90=p90,
                control=members.get("control"),
                members={k: v for k, v in members.items() if k != "control"})


def totals_for_window(times, series: Dict[str, List[Optional[float]]],
                      start: datetime, end: datetime) -> dict:
    member_totals = {}
    for name, vals in series.items():
        total, cov = window_total(times, vals, start, end)
        if total is not None:
            member_totals[name] = total
    stats = percentiles([v for k, v in member_totals.items()])
    # percentiles() of all members including control is the ensemble distribution.
    ens_only = [v for k, v in member_totals.items() if k != "control"]
    if ens_only:
        stats = percentiles(ens_only)
    return dict(control=member_totals.get("control"), members=member_totals,
                n=len([k for k in member_totals if k != "control"]),
                **stats)


def previous_run_totals(data: Optional[dict], start: datetime, end: datetime) -> List[dict]:
    """Operational totals for the same valid window from earlier runs (previous_dayN = N days of lead)."""
    if not data or not isinstance(data.get("hourly"), dict):
        return []
    hourly = data["hourly"]
    times = _times(hourly)
    out = []
    for lead in range(0, 8):
        key = "precipitation" if lead == 0 else f"precipitation_previous_day{lead}"
        if key not in hourly:
            continue
        total, cov = window_total(times, hourly[key], start, end)
        if total is None:
            continue
        issued = (start - timedelta(days=lead)).isoformat()
        out.append(dict(lead_days=lead, issued_approx=issued, total=total, coverage=round(cov, 3)))
    return out


def shape_model(key: str, ens: Optional[dict], prev: Optional[dict],
                start: datetime, now_iso: str) -> Optional[dict]:
    meta = MODELS[key]
    if not ens or not isinstance(ens.get("hourly"), dict):
        return None
    times = _times(ens["hourly"])
    series = member_series(ens["hourly"])
    if not series:
        return None
    windows = {}
    acc = {}
    runs = {}
    for hours in WINDOWS:
        end = start + timedelta(hours=hours)
        windows[str(hours)] = totals_for_window(times, series, start, end)
        if hours == 240:
            acc = _accumulation(times, series, start, end)
        runs[str(hours)] = previous_run_totals(prev, start, end)
    return dict(
        id=meta["id"],
        name=meta["name"],
        control_label=meta["control_label"],
        previous_label=meta["previous_label"],
        previous_model=meta["previous_model"],
        n_members=len([k for k in series if k != "control"]),
        windows=windows,
        accumulation=acc,
        runs=runs,
        location=dict(lat=ens.get("latitude"), lon=ens.get("longitude")),
    )


def build(ensembles: Dict[str, Optional[dict]], previous: Dict[str, Optional[dict]],
          now: datetime) -> dict:
    # Align windows to the current local hour so totals are stable across a request.
    local = now.astimezone(TZ).replace(minute=0, second=0, microsecond=0)
    models = {}
    for key in MODELS:
        prev_model = MODELS[key]["previous_model"]
        shaped = shape_model(key, ensembles.get(key), previous.get(prev_model) or previous.get(key), local, now.isoformat())
        if shaped:
            models[key] = shaped
    return dict(
        timezone=TZ_NAME,
        start=local.isoformat(),
        windows=[
            dict(hours=168, label="Next 7 days", end=(local + timedelta(hours=168)).isoformat()),
            dict(hours=240, label="Next 10 days", end=(local + timedelta(hours=240)).isoformat()),
        ],
        models=models,
        source="Open-Meteo Ensemble API and Previous Runs API",
        source_url="https://open-meteo.com/",
    )

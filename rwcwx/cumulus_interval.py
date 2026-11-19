"""Parse Cumulus website interval-chart JSON (tempdata.json, raindata.json, …).

Cumulus MX writes each point's epoch-milliseconds so that the UTC clock numbers
are the station-local clock (America/Los_Angeles), not the true UTC instant.
This matches the Highcharts `Date.UTC(localY, localM, …)` pattern. Cross-checked
against prod `obs` at the 2026-11-18 22:14–22:15 PT and 2026-11-19 07:01+ PT
boundaries (temp and daily rain agree exactly).

obs.rain is the gauge's daily running total in inches, reset at local midnight.
Wind gust here is the chart's 1-minute value, not save_latest's intra-minute max
from the 5-second realtime file.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from rwcwx.config import TZ

# Chart file / series key -> obs column. solardata is not stored on obs.
SERIES = {
    "temp": ("tempdata.json", "temp"),
    "intemp": ("tempdata.json", "intemp"),
    "humi": ("humdata.json", "hum"),
    "inhumi": ("humdata.json", "inhum"),
    "pres": ("pressdata.json", "press"),
    "wind": ("winddata.json", "wspeed"),
    "gust": ("winddata.json", "wgust"),
    "wdir": ("wdirdata.json", "bearing"),
    "rain": ("raindata.json", "rfall"),
}

# Fields written to the obs table (same set as CumulusObs.as_obs_table_params, minus t_obs).
OBS_FIELDS = ("temp", "humi", "wind", "gust", "wdir", "rain", "pres", "intemp", "inhumi")


def chart_ms_to_local(ms: int) -> datetime:
    """Interpret a chart epoch-ms value as station-local time."""
    clock = datetime.fromtimestamp(ms / 1000.0, timezone.utc).replace(tzinfo=None)
    return clock.replace(tzinfo=TZ)


def load_series(path: Path, key: str) -> List[Tuple[datetime, float]]:
    data = json.loads(path.read_text())
    if key not in data:
        raise KeyError(f"{path} has no series {key!r} (keys: {sorted(data)})")
    out = []
    for item in data[key]:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        ms, val = item[0], item[1]
        if val is None:
            continue
        out.append((chart_ms_to_local(int(ms)), float(val)))
    return out


def load_interval_dir(json_dir: Path) -> Dict[datetime, dict]:
    """Merge all known series, keyed by station-local minute."""
    by_t: Dict[datetime, dict] = {}
    for field, (filename, key) in SERIES.items():
        path = json_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Missing interval chart {path}")
        for t, val in load_series(path, key):
            row = by_t.setdefault(t, {"t_local": t})
            row[field] = val
    return by_t


def rows_in_window(
    by_t: Dict[datetime, dict],
    after: datetime,
    before: datetime,
) -> List[dict]:
    """Minutes strictly after `after` and strictly before `before` (both timezone-aware)."""
    if after.tzinfo is None or before.tzinfo is None:
        raise ValueError("after/before must be timezone-aware")
    rows = []
    for t in sorted(by_t):
        if after < t < before:
            row = dict(by_t[t])
            missing = [f for f in ("temp", "rain") if f not in row]
            if missing:
                continue
            rows.append(row)
    return rows


def as_obs_params(row: dict) -> dict:
    """obs insert params in the same shape as CumulusObs.as_obs_table_params (no pm2)."""
    t_local: datetime = row["t_local"]
    t_utc = t_local.astimezone(timezone.utc).replace(second=0, microsecond=0)
    params = {
        "t": t_utc.replace(tzinfo=None),
        "t_obs": t_utc.replace(tzinfo=None),
    }
    for f in OBS_FIELDS:
        if f not in row:
            continue
        val = row[f]
        if f in ("humi", "inhumi", "wind", "gust", "wdir"):
            params[f] = int(round(val))
        else:
            params[f] = val
    return params


def parse_monthly_log(path: Path) -> List[dict]:
    """Parse a Cumulus monthly log (e.g. Nov26log.txt): date,time,temp,hum,dew,wspeed,wgust,wdir,rate,raintoday,pres,…

    Times are station-local. This is the file to upload from the Cumulus PC data folder when the
    24-hour website charts no longer cover a gap.
    """
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 11:
            continue
        try:
            t_local = datetime.strptime(f"{parts[0]} {parts[1]}", "%d/%m/%y %H:%M").replace(tzinfo=TZ)
            row = {
                "t_local": t_local,
                "temp": float(parts[2]),
                "humi": float(parts[3]),
                "wind": float(parts[5]),
                "gust": float(parts[6]),
                "wdir": float(parts[7]),
                "rain": float(parts[9]),
                "pres": float(parts[10]),
            }
        except (ValueError, IndexError):
            continue
        if len(parts) > 22:
            try:
                row["intemp"] = float(parts[22])
            except ValueError:
                pass
        if len(parts) > 23:
            try:
                row["inhumi"] = float(parts[23])
            except ValueError:
                pass
        rows.append(row)
    return rows

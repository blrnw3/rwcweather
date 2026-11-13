"""Build the v5 estimated daily series from IEM and ACIS, or from a local cache.

Writes a CSV (and optionally a batched INSERT SQL file). Does not connect to the
production database unless --insert is given explicitly.

Usage:
  python -m rwcwx.estimated.generate --cache-dir DIR --csv-out OUT.csv
  python -m rwcwx.estimated.generate --fetch --cache-dir DIR --csv-out OUT.csv --sql-out OUT.sql
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rwcwx.estimated.conversions import (
    BLEND,
    CV_RMSE,
    PERIOD_END,
    PERIOD_START,
    VERSION,
    apply,
    confidence_for,
    f_to_c,
    method_label,
)
from rwcwx.estimated.qc import pulgas_is_bogus

logger = logging.getLogger("rwcwx.estimated.generate")

IEM_DAILY = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
ACIS_STNDATA = "https://data.rcc-acis.org/StnData"
USER_AGENT = "rwcweather estimated-daily/v5 (https://rwcweather.com)"
IEM_PAUSE = 2.2

# Cache file names (also accepted from the backfill-research download layout).
CACHE_FILES = {
    "pugc1": "iem_daily_CA_DCP_PUGC1.csv",
    "sfo": "iem_daily_CA_ASOS_SFO.csv",
    "coop": "acis_rwc_coop.json",
}

IEM_STATIONS = {
    "pugc1": ("CA_DCP", "PUGC1"),
    "sfo": ("CA_ASOS", "SFO"),
}

CSV_FIELDS = ["d", "var", "type", "val", "source", "method", "version", "confidence", "raw_val"]


def _parse_iso(s: str) -> date:
    return date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _http_get(url: str, timeout: int = 120) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_post_json(url: str, body: dict, timeout: int = 300) -> dict:
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value != value:  # NaN
            return None
        return float(value)
    text = str(value).strip()
    if text == "" or text.upper() in {"M", "T", "NA", "NAN", "NULL", "-99", "-99.0", "-999", "-9999"}:
        # Trace rain is handled by the caller for precip columns (T -> 0).
        if text.upper() == "T":
            return 0.0
        return None
    # ACIS accumulated flags look like "0.04A"
    if text[-1:].isalpha():
        if text[-1].upper() == "A":
            return None
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def fetch_iem_daily(network: str, station: str, start: date, end: date, dest: Path) -> Path:
    """Download one IEM daily.py CSV. network e.g. CA_DCP, station e.g. PUGC1."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = (
        f"{IEM_DAILY}?network={network}&stations={station}"
        f"&year1={start.year}&month1={start.month}&day1={start.day}"
        f"&year2={end.year}&month2={end.month}&day2={end.day}&na=blank"
    )
    logger.info("fetch IEM daily %s %s", network, station)
    dest.write_bytes(_http_get(url))
    time.sleep(IEM_PAUSE)
    return dest


def fetch_acis_coop(start: date, end: date, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "sid": "USC00047339",
        "sdate": start.isoformat(),
        "edate": end.isoformat(),
        "elems": [
            {"name": "maxt", "add": "t", "prec": 1},
            {"name": "mint", "add": "t", "prec": 1},
            {"name": "pcpn", "add": "t", "prec": 2},
            {"name": "avgt", "prec": 1},
        ],
    }
    logger.info("fetch ACIS USC00047339")
    payload = _http_post_json(ACIS_STNDATA, body)
    dest.write_text(json.dumps(payload))
    return dest


def load_iem_daily(path: Path) -> Dict[date, dict]:
    """Map date -> {tmax_c, tmin_c, rain_in} from an IEM daily CSV."""
    out: Dict[date, dict] = {}
    with path.open(newline="") as fh:
        # Some IEM CSVs start with a comment line
        sample = fh.read(256)
        fh.seek(0)
        if sample.startswith("#"):
            while True:
                pos = fh.tell()
                line = fh.readline()
                if not line or not line.startswith("#"):
                    fh.seek(pos)
                    break
        reader = csv.DictReader(fh)
        for rec in reader:
            day = rec.get("day") or rec.get("valid") or rec.get("date")
            if not day:
                continue
            try:
                d = _parse_iso(day[:10])
            except (TypeError, ValueError):
                continue
            tmax_f = _to_float(rec.get("max_temp_f") or rec.get("max_tmpf"))
            tmin_f = _to_float(rec.get("min_temp_f") or rec.get("min_tmpf"))
            rain = _to_float(rec.get("precip_in") or rec.get("pday"))
            out[d] = {
                "tmax": f_to_c(tmax_f) if tmax_f is not None else None,
                "tmin": f_to_c(tmin_f) if tmin_f is not None else None,
                "rain": rain,
            }
    return out


def load_acis_coop(path: Path) -> Dict[date, dict]:
    """Map date -> {tmax_c, tmin_c, rain_in} from an ACIS StnData JSON (maxt, mint, pcpn, avgt)."""
    payload = json.loads(path.read_text())
    out: Dict[date, dict] = {}
    for row in payload.get("data") or []:
        if not row:
            continue
        try:
            d = _parse_iso(str(row[0])[:10])
        except (TypeError, ValueError, IndexError):
            continue
        def elem(idx):
            if idx >= len(row):
                return None
            cell = row[idx]
            # add:"t" yields [value, tobs] or just a string
            if isinstance(cell, (list, tuple)):
                return _to_float(cell[0] if cell else None)
            return _to_float(cell)
        tmax_f, tmin_f, rain = elem(1), elem(2), elem(3)
        out[d] = {
            "tmax": f_to_c(tmax_f) if tmax_f is not None else None,
            "tmin": f_to_c(tmin_f) if tmin_f is not None else None,
            "rain": rain,
        }
    return out


def resolve_cache(cache_dir: Path, key: str) -> Optional[Path]:
    """Accept both our cache names and the research-download filenames."""
    candidates = [cache_dir / CACHE_FILES[key]]
    if key == "pugc1":
        candidates.append(cache_dir / "iem_daily_CA_DCP_PUGC1.csv")
    if key == "sfo":
        candidates.append(cache_dir / "iem_daily_CA_ASOS_SFO.csv")
    if key == "coop":
        candidates.append(cache_dir / "acis_rwc_coop.json")
        candidates.append(cache_dir / "acis_coop_USC00047339.json")
    for path in candidates:
        if path.is_file():
            return path
    return None


def ensure_sources(cache_dir: Path, start: date, end: date, fetch: bool) -> Dict[str, Dict[date, dict]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    sources = {}
    for key, loader in (("pugc1", load_iem_daily), ("sfo", load_iem_daily), ("coop", load_acis_coop)):
        path = resolve_cache(cache_dir, key)
        if path is None:
            if not fetch:
                raise SystemExit(
                    f"Missing cache for {key} in {cache_dir}. Pass --fetch to download, "
                    f"or copy {CACHE_FILES[key]} into the cache directory."
                )
            dest = cache_dir / CACHE_FILES[key]
            try:
                if key == "coop":
                    # Fetch a little padding so a later rerun can reuse the file.
                    fetch_acis_coop(date(2011, 1, 1), date(2020, 12, 31), dest)
                else:
                    network, station = IEM_STATIONS[key]
                    fetch_iem_daily(network, station, start, end, dest)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                raise SystemExit(f"Failed to fetch {key}: {exc}") from exc
            path = dest
        logger.info("load %s from %s", key, path)
        sources[key] = loader(path)
    return sources


def _candidate(sources: Dict[str, Dict[date, dict]], source_id: str, method: str,
               var: str, typ: str, d: date) -> Optional[dict]:
    """Converted row for one source on one day, or None if missing."""
    series = sources.get(source_id) or {}
    day = series.get(d)
    if not day:
        return None
    key = "tmax" if typ == "max" else "tmin" if typ == "min" else "rain"
    raw = day.get(key)
    val = apply(source_id, var, typ, method, raw, d.month)
    if val is None:
        return None
    return {
        "d": d.isoformat(),
        "var": var,
        "type": typ,
        "val": val,
        "source": source_id,
        "method": method_label(method),
        "version": VERSION,
        "confidence": confidence_for(source_id),
        "raw_val": None if raw is None else round(raw, 4),
    }


def generate_rows(sources: Dict[str, Dict[date, dict]], start: date, end: date,
                  rejections: Optional[List[dict]] = None) -> List[dict]:
    """Build the estimated series, rejecting bogus Pulgas values via quality control.

    If `rejections` is provided, each discarded Pulgas value is appended as a
    dict with the date, variable, raw Pulgas value, reason, and the replacement
    (or None if no secondary was available).
    """
    rows: List[dict] = []
    for d in _daterange(start, end):
        for (var, typ), chain in BLEND.items():
            cands = {}
            for source_id, method in chain:
                cand = _candidate(sources, source_id, method, var, typ, d)
                if cand:
                    cands[source_id] = cand
            chosen = cands.get("pugc1")
            if chosen:
                pug = cands["pugc1"]
                coop = cands.get("coop")
                sfo = cands.get("sfo")
                rejected, reason = pulgas_is_bogus(
                    var, typ,
                    pug.get("raw_val"), pug.get("val"),
                    None if not coop else coop.get("raw_val"),
                    None if not coop else coop.get("val"),
                    None if not sfo else sfo.get("raw_val"),
                    None if not sfo else sfo.get("val"),
                )
                if rejected:
                    chosen = cands.get("coop") or cands.get("sfo")
                    if rejections is not None:
                        repl = chosen
                        rejections.append({
                            "d": pug["d"],
                            "var": var,
                            "type": typ,
                            "rejected_source": "pugc1",
                            "rejected_raw": pug.get("raw_val"),
                            "rejected_val": pug.get("val"),
                            "reason": reason,
                            "replacement_source": None if not repl else repl["source"],
                            "replacement_val": None if not repl else repl["val"],
                            "replacement_raw": None if not repl else repl.get("raw_val"),
                            "replacement_confidence": None if not repl else repl["confidence"],
                        })
                    logger.info(
                        "QC rejected Pulgas %s %s on %s (raw=%s, est=%s, reason=%s); "
                        "replacement %s %s",
                        var, typ, pug["d"], pug.get("raw_val"), pug.get("val"), reason,
                        None if not chosen else chosen["source"],
                        None if not chosen else chosen["val"],
                    )
            else:
                chosen = cands.get("coop") or cands.get("sfo")
            if chosen:
                rows.append(chosen)
    return rows


def write_csv(rows: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    logger.info("wrote %s", path)


def write_sql(rows: List[dict], path: Path, batch: int = 200) -> None:
    """Batched INSERT statements. Safe to re-run (ON DUPLICATE KEY UPDATE)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"-- daily_estimated {VERSION}: {len(rows)} rows, {PERIOD_START} to {PERIOD_END}",
        "-- Apply the migration first, then this file, only with explicit approval:",
        "--   mysql wx < data/migrations/20261112_daily_estimated.sql",
        f"--   mysql wx < {path}",
        "SET NAMES utf8mb4;",
        "",
    ]
    def sql_val(v):
        if v is None:
            return "NULL"
        if isinstance(v, (int, float)):
            return repr(v) if not isinstance(v, float) else format(v, ".6g")
        return "'" + str(v).replace("'", "''") + "'"

    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        lines.append(
            "INSERT INTO daily_estimated "
            "(d, var, type, val, source, method, version, confidence, raw_val) VALUES"
        )
        vals = []
        for r in chunk:
            vals.append(
                "  ({d},{var},{typ},{val},{src},{meth},{ver},{conf},{raw})".format(
                    d=sql_val(r["d"]),
                    var=sql_val(r["var"]),
                    typ=sql_val(r["type"]),
                    val=sql_val(r["val"]),
                    src=sql_val(r["source"]),
                    meth=sql_val(r["method"]),
                    ver=sql_val(r["version"]),
                    conf=sql_val(r["confidence"]),
                    raw=sql_val(r["raw_val"]),
                )
            )
        lines.append(",\n".join(vals))
        lines.append(
            "ON DUPLICATE KEY UPDATE val=VALUES(val), source=VALUES(source), "
            "method=VALUES(method), confidence=VALUES(confidence), raw_val=VALUES(raw_val);"
        )
        lines.append("")
    path.write_text("\n".join(lines) + "\n")
    logger.info("wrote %s", path)


def summarize(rows: List[dict], start: Optional[date] = None, end: Optional[date] = None,
              rejections: Optional[List[dict]] = None) -> dict:
    """Coverage, source mix, secondary fill share, and annual totals for a review summary."""
    from collections import defaultdict
    start = start or _parse_iso(PERIOD_START)
    end = end or _parse_iso(PERIOD_END)
    expected = {yr: 0 for yr in range(start.year, end.year + 1)}
    for d in _daterange(start, end):
        expected[d.year] += 1
    coverage = defaultdict(lambda: defaultdict(int))
    sources = defaultdict(lambda: defaultdict(int))
    sources_by_year = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    annual = defaultdict(lambda: {"n_tmax": 0, "sum_tmax": 0.0, "n_tmin": 0, "sum_tmin": 0.0, "rain": 0.0, "n_rain": 0})
    for r in rows:
        d = _parse_iso(r["d"])
        key = r["var"] + "/" + r["type"]
        coverage[key][d.year] += 1
        sources[key][r["source"]] += 1
        sources_by_year[key][d.year][r["source"]] += 1
        if r["var"] == "temp" and r["type"] == "max":
            annual[d.year]["n_tmax"] += 1
            annual[d.year]["sum_tmax"] += r["val"]
        elif r["var"] == "temp" and r["type"] == "min":
            annual[d.year]["n_tmin"] += 1
            annual[d.year]["sum_tmin"] += r["val"]
        elif r["var"] == "rain":
            annual[d.year]["n_rain"] += 1
            annual[d.year]["rain"] += r["val"]
    by_var = {}
    for key in ("temp/max", "temp/min", "rain/total"):
        years = coverage[key]
        by_var[key] = {
            str(yr): {"n": years.get(yr, 0), "of": expected[yr],
                      "pct": round(100.0 * years.get(yr, 0) / expected[yr], 1) if expected[yr] else 0,
                      "missing": expected[yr] - years.get(yr, 0)}
            for yr in expected
        }
    source_mix = {k: dict(v) for k, v in sources.items()}
    source_mix_by_year = {}
    fill_share = {}
    for key in ("temp/max", "temp/min", "rain/total"):
        source_mix_by_year[key] = {}
        fill_share[key] = {}
        for yr in expected:
            mix = dict(sources_by_year[key][yr])
            n = sum(mix.values())
            n_sec = mix.get("coop", 0) + mix.get("sfo", 0)
            source_mix_by_year[key][str(yr)] = mix
            fill_share[key][str(yr)] = {
                "n": n,
                "n_pugc1": mix.get("pugc1", 0),
                "n_coop": mix.get("coop", 0),
                "n_sfo": mix.get("sfo", 0),
                "n_secondary": n_sec,
                "pct_secondary": round(100.0 * n_sec / n, 1) if n else 0.0,
                "missing": expected[yr] - n,
            }
    annual_out = {}
    for yr in expected:
        a = annual[yr]
        days = expected[yr]
        tmax_mix = fill_share["temp/max"][str(yr)]
        tmin_mix = fill_share["temp/min"][str(yr)]
        rain_mix = fill_share["rain/total"][str(yr)]
        annual_out[str(yr)] = {
            "rain_in": round(a["rain"], 2),
            "rain_mm": round(a["rain"] * 25.4, 1),
            "n_rain": a["n_rain"],
            "mean_tmax_c": round(a["sum_tmax"] / a["n_tmax"], 2) if a["n_tmax"] else None,
            "mean_tmin_c": round(a["sum_tmin"] / a["n_tmin"], 2) if a["n_tmin"] else None,
            "n_tmax": a["n_tmax"],
            "n_tmin": a["n_tmin"],
            "days_in_year": days,
            "missing_tmax": days - a["n_tmax"],
            "missing_tmin": days - a["n_tmin"],
            "missing_rain": days - a["n_rain"],
            "tmax_secondary": tmax_mix["n_secondary"],
            "tmin_secondary": tmin_mix["n_secondary"],
            "rain_secondary": rain_mix["n_secondary"],
            "tmax_coop": tmax_mix["n_coop"],
            "tmax_sfo": tmax_mix["n_sfo"],
            "tmin_coop": tmin_mix["n_coop"],
            "tmin_sfo": tmin_mix["n_sfo"],
            "rain_coop": rain_mix["n_coop"],
            "rain_sfo": rain_mix["n_sfo"],
        }
    return {
        "version": VERSION,
        "period": [start.isoformat(), end.isoformat()],
        "n_rows": len(rows),
        "coverage": by_var,
        "source_mix": source_mix,
        "source_mix_by_year": source_mix_by_year,
        "fill_share": fill_share,
        "annual": annual_out,
        "sample": rows[:8] + rows[max(0, len(rows)//2 - 4):len(rows)//2 + 4] + rows[-8:],
        "cv_rmse": {
            "pugc1_tmax_linear_c": CV_RMSE[("pugc1", "tmax", "linear")],
            "pugc1_tmin_linear_c": CV_RMSE[("pugc1", "tmin", "linear")],
            "pugc1_rain_ratio_in": CV_RMSE[("pugc1", "rain", "ratio")],
            "coop_tmax_linear_c": CV_RMSE[("coop", "tmax", "linear")],
            "coop_tmin_linear_c": CV_RMSE[("coop", "tmin", "linear")],
            "coop_rain_ratio_in": CV_RMSE[("coop", "rain", "ratio")],
            "sfo_tmax_offset_c": CV_RMSE[("sfo", "tmax", "offset")],
            "sfo_tmin_linear_c": CV_RMSE[("sfo", "tmin", "linear")],
            "sfo_rain_ratio_in": CV_RMSE[("sfo", "rain", "ratio")],
        },
        "rejections": list(rejections or []),
        "n_rejections": len(rejections or []),
    }


def insert_mysql(sql_path: Path, mysql_url: str) -> None:
    """Apply a generated SQL file. Requires an explicit --insert and MYSQL_URL; not used in dry-run."""
    # Imported lazily so a dry run never touches DB drivers or credentials.
    from urllib.parse import urlparse
    import subprocess
    parsed = urlparse(mysql_url)
    # mysql client reads the URL pieces via arguments; never print the URL.
    cmd = ["mysql"]
    if parsed.hostname:
        cmd += ["-h", parsed.hostname]
    if parsed.port:
        cmd += ["-P", str(parsed.port)]
    if parsed.username:
        cmd += ["-u", parsed.username]
    if parsed.password:
        env = os.environ.copy()
        env["MYSQL_PWD"] = parsed.password
    else:
        env = os.environ.copy()
    dbname = (parsed.path or "/wx").lstrip("/") or "wx"
    cmd += [dbname]
    with open(sql_path, "rb") as fh:
        subprocess.run(cmd, stdin=fh, check=True, env=env)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate v5 estimated daily history (Tmax, Tmin, rain) from Pulgas Ridge, with COOP/SFO gap-fill and quality control.")
    p.add_argument("--cache-dir", type=Path, required=True, help="Directory of IEM/ACIS cache files (created if fetching).")
    p.add_argument("--fetch", action="store_true", help="Download missing source files from IEM and ACIS.")
    p.add_argument("--csv-out", type=Path, required=True, help="Destination CSV.")
    p.add_argument("--sql-out", type=Path, help="Optional batched INSERT SQL file.")
    p.add_argument("--summary-out", type=Path, help="Optional JSON summary (coverage, source mix, annual totals).")
    p.add_argument("--start", default=PERIOD_START, help="Inclusive start date (default v5 window).")
    p.add_argument("--end", default=PERIOD_END, help="Inclusive end date (default v5 window).")
    p.add_argument("--insert", action="store_true",
                   help="Apply --sql-out to MYSQL_URL. Refused unless this flag is set. Never used in a dry run.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = build_arg_parser().parse_args(argv)
    start, end = _parse_iso(args.start), _parse_iso(args.end)
    if start > end:
        raise SystemExit("start is after end")
    sources = ensure_sources(args.cache_dir, start, end, fetch=args.fetch)
    rejections: List[dict] = []
    rows = generate_rows(sources, start, end, rejections)
    write_csv(rows, args.csv_out)
    if args.sql_out:
        write_sql(rows, args.sql_out)
    if args.summary_out:
        summary = summarize(rows, start, end, rejections)
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(json.dumps(summary, indent=2))
        logger.info("wrote %s", args.summary_out)
    if args.insert:
        if not args.sql_out or not args.sql_out.is_file():
            raise SystemExit("--insert requires --sql-out")
        mysql_url = os.environ.get("MYSQL_URL")
        if not mysql_url:
            raise SystemExit("--insert set but MYSQL_URL is not in the environment")
        insert_mysql(args.sql_out, mysql_url)
    return 0


if __name__ == "__main__":
    sys.exit(main())

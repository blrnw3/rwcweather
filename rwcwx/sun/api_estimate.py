"""Daily sunshine estimated from free, keyless weather APIs, for days the webcam cannot cover.

Sources (chosen by cross-validated daily MAE against webcam totals, 2021-2026; see PR):
  * Open-Meteo historical-forecast archive (NCEP HRRR over the US), hourly direct normal irradiance (DNI).
    Feature: hrrr_f = sum over the local day of clip(DNI / 700 W/m2, 0, 1) hours, / daylight hours.
  * KSQL (San Carlos airport, ~6 km) ASOS cloud reports via Iowa Environmental Mesonet.
    Feature: asos_clear = 1 - mean over 08:00-17:59 local reports of the highest-coverage layer
    (CLR/SKC 0, FEW .19, SCT .44, BKN .75, OVC/VV 1).
Model: sunshine fraction = a + b*hrrr_f + c*asos_clear (least squares on full-coverage webcam days), clipped to
[0, 1] and multiplied by daylight hours. Days without ASOS reports use the HRRR-only fit.
"""
import csv
import io
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from dateutil.tz import UTC

from rwcwx.config import TZ

LAT, LON = 37.470, -122.265
ASOS_STATION = "SQL"
DNI_FULL = 700.0
ASOS_HOURS = range(8, 18)
SKY_COVER = {"CLR": 0.0, "SKC": 0.0, "NSC": 0.0, "FEW": 0.19, "SCT": 0.44, "BKN": 0.75, "OVC": 1.0, "VV": 1.0}
NAME_FULL = "api:hrrr+asos"
NAME_HRRR = "api:hrrr"
UA = {"User-Agent": "rwcweather sunshine backfill (rwcweather.com)"}


def _get(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def hrrr_url(start: date, end: date) -> str:
    q = dict(latitude=LAT, longitude=LON, start_date=start.isoformat(), end_date=end.isoformat(),
             hourly="direct_normal_irradiance", models="ncep_hrrr_conus", timezone="America/Los_Angeles")
    return "https://historical-forecast-api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)


def hrrr_dni_hours(payload: dict) -> Dict[date, float]:
    """Open-Meteo hourly response (local-time stamps) -> {local day: sum clip(DNI/700, 0, 1)}; days with gaps dropped."""
    out: Dict[date, float] = {}
    bad = set()
    for t, v in zip(payload["hourly"]["time"], payload["hourly"]["direct_normal_irradiance"]):
        d = datetime.fromisoformat(t).date()
        if v is None:
            bad.add(d)
            continue
        out[d] = out.get(d, 0.0) + min(max(v / DNI_FULL, 0.0), 1.0)
    return {d: round(v, 4) for d, v in out.items() if d not in bad}


def asos_url(start: date, end: date) -> str:
    e = end + timedelta(days=2)
    q = [("station", ASOS_STATION), ("data", "skyc1"), ("data", "skyc2"), ("data", "skyc3"),
         ("year1", start.year), ("month1", start.month), ("day1", start.day),
         ("year2", e.year), ("month2", e.month), ("day2", e.day),
         ("tz", "Etc/UTC"), ("format", "onlycomma"), ("missing", "M"), ("report_type", 3), ("report_type", 4)]
    return "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?" + urllib.parse.urlencode(q)


def _cover(row: dict) -> Optional[float]:
    vals = [SKY_COVER.get(str(row.get(k, "")).strip()) for k in ("skyc1", "skyc2", "skyc3")]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def asos_clear(text: str) -> Dict[date, float]:
    """IEM CSV (UTC 'valid') -> {local day: 1 - mean daytime cover}; needs >= 6 daytime reports."""
    acc: Dict[date, List[float]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        try:
            t = datetime.strptime(row["valid"], "%Y-%m-%d %H:%M").replace(tzinfo=UTC).astimezone(TZ)
        except (KeyError, ValueError):
            continue
        c = _cover(row)
        if c is None or t.hour not in ASOS_HOURS:
            continue
        acc.setdefault(t.date(), []).append(c)
    return {d: round(1 - sum(v) / len(v), 4) for d, v in acc.items() if len(v) >= 6}


@dataclass
class Fit:
    name: str
    coef: Tuple[float, ...]         # intercept, then one per feature
    feats: Tuple[str, ...]
    n: int
    cv_mae_h: Optional[float] = None
    cv_bias_h: Optional[float] = None

    def frac(self, x: Dict[str, float]) -> float:
        v = self.coef[0] + sum(c * x[f] for c, f in zip(self.coef[1:], self.feats))
        return min(max(v, 0.0), 1.0)


def _lstsq(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    A = np.column_stack([np.ones(len(X)), X])
    return np.linalg.lstsq(A, y, rcond=None)[0]


def fit(rows: Sequence[dict], feats: Tuple[str, ...], name: str) -> Fit:
    """rows: dicts with the features, 'hours' (webcam truth), 'N' (daylight h), 'd' (date). Leave-one-year-out CV."""
    rows = [r for r in rows if all(r.get(f) is not None for f in feats)]
    X = np.array([[r[f] for f in feats] for r in rows], dtype=float)
    y = np.array([r["hours"] / r["N"] for r in rows])
    N = np.array([r["N"] for r in rows])
    yrs = np.array([r["d"].year for r in rows])
    err = []
    for yr in sorted(set(yrs)):
        tr, te = yrs != yr, yrs == yr
        if tr.sum() < 30 or not te.any():
            continue
        c = _lstsq(X[tr], y[tr])
        p = np.clip(c[0] + X[te] @ c[1:], 0, 1) * N[te]
        err.extend(p - y[te] * N[te])
    c = _lstsq(X, y)
    err = np.array(err)
    return Fit(name=name, coef=tuple(round(float(v), 5) for v in c), feats=feats, n=len(rows),
               cv_mae_h=round(float(np.abs(err).mean()), 2) if len(err) else None,
               cv_bias_h=round(float(err.mean()), 2) if len(err) else None)


def estimate(d: date, N: float, feat: Dict[str, Optional[float]], full: Fit, hrrr: Fit) -> Optional[dict]:
    """-> dict(val hours, name, fit) or None if no HRRR data for the day."""
    if feat.get("hrrr_f") is None:
        return None
    m = full if feat.get("asos_clear") is not None else hrrr
    return dict(d=d, val=round(m.frac(feat) * N, 2), name=m.name, fit=m)


def comment_for(est: dict, coverage_pct: Optional[float]) -> str:
    f = est["fit"]
    s = f"API estimate ({est['name']}; calibrated vs webcam, CV MAE {f.cv_mae_h} h)"
    s += f"; webcam coverage {coverage_pct:.1f}%" if coverage_pct is not None else "; no webcam total"
    return s[:255]


def features(days: Iterable[date], N: Dict[date, float], dni: Dict[date, float],
             clear: Dict[date, float]) -> Dict[date, Dict[str, Optional[float]]]:
    return {d: dict(hrrr_f=(round(dni[d] / N[d], 4) if d in dni and N.get(d) else None), asos_clear=clear.get(d))
            for d in days}


def fetch(start: date, end: date) -> Tuple[Dict[date, float], Dict[date, float]]:
    """Fetch HRRR DNI hours and ASOS clear fractions for [start, end], yearly chunks."""
    dni: Dict[date, float] = {}
    clear: Dict[date, float] = {}
    s = start
    while s <= end:
        e = min(date(s.year, 12, 31), end)
        dni.update(hrrr_dni_hours(json.loads(_get(hrrr_url(s, e)))))
        clear.update({d: v for d, v in asos_clear(_get(asos_url(s, e)).decode()).items() if s <= d <= e})
        s = e + timedelta(days=1)
    return dni, clear

"""Heatwave / cold-snap spells: consecutive days where daily temp departs from the climate normal.

Departure = observed − normal (°C). Heatwave: departure ≥ +level. Cold snap: departure ≤ −level.
Levels are accepted in °F (3,5,8,10) or native °C (2,3,5,7,10); stored comparison is always °C.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from rwcwx.calc.climate_normal import daily_temp_normal
from rwcwx.calc.rolling import span_overlaps_months, target_months

DIRECTIONS = ("above", "below")
# Display thresholds (°F) and metric °C options (accepted as °F equivalents via conversion).
LEVELS_F = (3, 5, 8, 10)
LEVELS_C = (2, 3, 5, 7, 10)
# All accepted query levels in °F (exact), including C→F so the API stays in one unit.
LEVELS = tuple(sorted(set(LEVELS_F) | {round(c * 9 / 5, 4) for c in LEVELS_C}))
TYPES = ("max", "min", "avg")
ORDERS = ("length", "cum", "peak")
EPS = 1e-9


def level_c(level_f: float) -> float:
    """°F departure threshold → °C."""
    return level_f * 5 / 9


def departures(daily: Iterable[Tuple[date, Optional[float]]], typ: str
               ) -> List[Tuple[date, float, float]]:
    """(date, departure_C, observed_C) for days with data and a known normal."""
    out = []
    for d, v in daily:
        if v is None:
            continue
        n = daily_temp_normal(typ, d)
        if n is None:
            continue
        out.append((d, v - n, v))
    return out


def find_anom_spells(deps: Sequence[Tuple], level_celsius: float, direction: str,
                     month: Union[int, str, None] = 0, last_day: Optional[date] = None
                     ) -> List[dict]:
    """Spells where departure meets the threshold; month/season overlap keeps spells whole.

    Each deps entry is (date, departure_C) or (date, departure_C, observed_C). Observed
    temps are included in the spell when provided (mean_temp / peak_temp).
    """
    thresh = abs(level_celsius)
    # Normalise to (date, dep, obs|None)
    normed = []
    for row in deps:
        d, dep = row[0], row[1]
        obs = row[2] if len(row) > 2 else None
        if last_day is None or d <= last_day:
            normed.append((d, dep, obs))
    days = sorted(normed)
    spells, run = [], []

    def ok(dep: float) -> bool:
        return dep >= thresh - EPS if direction == "above" else dep <= -thresh + EPS

    for d, dep, obs in days:
        if run and (not ok(dep) or d != run[-1][0] + timedelta(days=1)):
            spells.append(_spell(run, direction))
            run = []
        if ok(dep):
            run.append((d, dep, obs))
    if run:
        spells.append(_spell(run, direction))
    months = target_months(month)
    if months:
        spells = [s for s in spells if span_overlaps_months(s["start"], s["end"], months)]
    return spells


def _spell(run: List[Tuple], direction: str) -> dict:
    deps = [row[1] for row in run]
    obs = [row[2] for row in run if len(row) > 2 and row[2] is not None]
    cum = sum(deps)
    peak = max(deps) if direction == "above" else min(deps)
    out = dict(
        start=run[0][0], end=run[-1][0], length=len(run),
        mean=round(sum(deps) / len(deps), 4),
        peak=round(peak, 4),
        cum=round(cum, 4),
        max=round(max(deps), 4),
        min=round(min(deps), 4),
    )
    if obs:
        out["mean_temp"] = round(sum(obs) / len(obs), 4)
        out["peak_temp"] = round(max(obs) if direction == "above" else min(obs), 4)
    return out


def _sort_key(order: str, direction: str):
    # Extreme first; further ties: most recent end date.
    # Length ties: larger |mean departure| first (cold snaps: more negative mean ranks higher).
    if order == "cum":
        return (lambda s: (s["cum"] if direction == "above" else -s["cum"], s["end"]))
    if order == "peak":
        return (lambda s: (s["peak"] if direction == "above" else -s["peak"], s["end"]))
    mean_key = (lambda s: s["mean"]) if direction == "above" else (lambda s: -s["mean"])
    return (lambda s: (s["length"], mean_key(s), s["end"]))


def rank_anom_spells(spells: List[dict], order: str, direction: str, limit: int) -> List[dict]:
    return sorted(spells, key=_sort_key(order, direction), reverse=True)[:limit]


def _fmt(s: dict) -> dict:
    t = lambda d: (d.year, d.month, d.day)
    out = dict(start=t(s["start"]), end=t(s["end"]), length=s["length"],
               mean=s["mean"], peak=s["peak"], cum=s["cum"], max=s["max"], min=s["min"])
    if "mean_temp" in s:
        out["mean_temp"] = s["mean_temp"]
    if "peak_temp" in s:
        out["peak_temp"] = s["peak_temp"]
    return out


def anom_spell_ranking(daily: Iterable[Tuple[date, Optional[float]]], typ: str, level_f: float,
                       direction: str = "above", month: Union[int, str, None] = 0,
                       order: str = "length", limit: int = 25,
                       today: Optional[date] = None) -> dict:
    """Top anomaly spells + current ongoing (ends yesterday — partial today ignored for temp)."""
    last_day = (today - timedelta(days=1)) if today is not None else None
    deps = departures(daily, typ)
    spells = find_anom_spells(deps, level_c(level_f), direction, month, last_day)
    ranked = rank_anom_spells(spells, order, direction, limit)

    current = None
    if today is not None and spells:
        latest = spells[-1]
        if latest["end"] == last_day:
            key = _sort_key(order, direction)
            better = sum(1 for s in spells if key(s) > key(latest))
            current = dict(_fmt(latest), rank=better + 1, of=len(spells), status="yesterday")

    return dict(result=[_fmt(s) for s in ranked], current=current, found=len(spells))

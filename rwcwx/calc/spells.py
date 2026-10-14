"""
Spell rankings: the longest runs of consecutive days on which a daily value is above (>=) or below (<) a
threshold, e.g. the longest dry spells (rain < 0.01 in), wet spells, heatwaves (max >= 90 °F) or cold runs.
Modelled on nw3weather's RankSpells.php.

Computed from the daily avg_extreme rows only (one indexed query, ~2,100 rows), in plain Python.

Rules:
- Thresholds are in inches (rain), °F (temperature) or hours (sunshine, wet hours). Temperatures are stored in
  °C, so °F thresholds are converted before comparing.
- A spell is a run of consecutive calendar days that all have data and all meet the condition. A missing day
  ends the spell (we can't tell whether it met the condition).
- Month filter: only days in that month count, so spells are cut at month boundaries ("longest dry spell in
  July"). Start year: only days from 1 January of that year count.
- Rain and wet-hour totals include today when today already meets the condition; temperatures and sunshine stop
  at yesterday, because a partial day isn't comparable.
- Ranked by length (longest first); ties: most recent first, as elsewhere in the rankings.
- The current spell is the one still running: it ends on the last eligible day, or (rain / wet hours) it ended
  yesterday and today can still extend it.
"""
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

DIRECTIONS = ("above", "below")

# (var, daily statistic) -> spell config. thresholds are in display units (in, °F, hours); "partial": today counts.
SPELL_VARS: Dict[Tuple[str, str], dict] = {
    ("rain", "total"): dict(thresholds=(0.01, 0.1, 0.25, 0.5, 1.0), sum=True, partial=True),
    ("wet", "total"): dict(thresholds=(1, 3, 6, 12), sum=True, partial=True),
    ("temp", "max"): dict(thresholds=(40, 50, 60, 70, 80, 90, 100), fahrenheit=True),
    ("temp", "min"): dict(thresholds=(32, 40, 45, 50, 55, 60), fahrenheit=True),
    ("temp", "avg"): dict(thresholds=(40, 50, 60, 70, 80), fahrenheit=True),
    ("sun", "total"): dict(thresholds=(0.1, 1, 4, 8, 10, 12), sum=True),
}

EPS = 1e-9


def supported() -> dict:
    return {v + "/" + t: list(c["thresholds"]) for (v, t), c in SPELL_VARS.items()}


def stored_threshold(var: str, typ: str, threshold: float) -> float:
    cfg = SPELL_VARS[(var, typ)]
    return (threshold - 32) * 5 / 9 if cfg.get("fahrenheit") else threshold


def meets(val: float, threshold: float, direction: str) -> bool:
    return val >= threshold - EPS if direction == "above" else val < threshold - EPS


def find_spells(daily: Iterable[Tuple[date, Optional[float]]], threshold: float, direction: str,
                month: int = 0, start_year: Optional[int] = None, last_day: Optional[date] = None) -> List[dict]:
    """Every maximal run of consecutive qualifying days (threshold already in stored units), oldest first."""
    days = sorted((d, v) for d, v in daily if v is not None
                  and (last_day is None or d <= last_day)
                  and (not month or d.month == month)
                  and (start_year is None or d.year >= start_year))
    spells, run = [], []
    for d, v in days:
        ok = meets(v, threshold, direction)
        if run and (not ok or d != run[-1][0] + timedelta(days=1)):
            spells.append(_spell(run))
            run = []
        if ok:
            run.append((d, v))
    if run:
        spells.append(_spell(run))
    return spells


def _spell(run: List[Tuple[date, float]]) -> dict:
    vals = [v for _, v in run]
    return dict(start=run[0][0], end=run[-1][0], length=len(run), total=round(sum(vals), 4),
                mean=round(sum(vals) / len(vals), 4), max=max(vals), min=min(vals))


def rank_spells(spells: List[dict], limit: int = 25) -> List[dict]:
    return sorted(spells, key=lambda s: (s["length"], s["end"]), reverse=True)[:limit]


def spell_ranking(daily: Iterable[Tuple[date, Optional[float]]], var: str, typ: str, threshold: float,
                  direction: str = "above", month: int = 0, start_year: Optional[int] = None, limit: int = 25,
                  today: Optional[date] = None) -> dict:
    """{result: top spells, current: the running spell with its rank (or None), found: number of spells}."""
    cfg = SPELL_VARS[(var, typ)]
    daily = list(daily)
    stored = stored_threshold(var, typ, threshold)
    last_day = None
    if today is not None:
        last_day = today if cfg.get("partial") else today - timedelta(days=1)
    spells = find_spells(daily, stored, direction, month, start_year, last_day)

    current = None
    if today is not None and spells:
        latest = spells[-1]
        running = latest["end"] == last_day
        if not running and cfg.get("partial") and latest["end"] == today - timedelta(days=1):
            # Today hasn't met the condition yet but still can (rain / wet hours only grow) - if today is in scope.
            in_scope = (not month or today.month == month) and (start_year is None or today.year >= start_year)
            running = in_scope and direction == "above"
        if running:
            better = sum(1 for s in spells if s["length"] > latest["length"])
            # status: "today" (runs to today, so far), "pending" (ended yesterday, today can still extend it) or
            # "yesterday" (runs to the last complete day; temperature and sunshine)
            status = "today" if latest["end"] == today else "pending" if cfg.get("partial") else "yesterday"
            current = dict(_fmt(latest), rank=better + 1, of=len(spells), status=status)

    return dict(result=[_fmt(s) for s in rank_spells(spells, limit)], current=current, found=len(spells),
                stat="total" if cfg.get("sum") else "mean")


def _fmt(s: dict) -> dict:
    t = lambda d: (d.year, d.month, d.day)
    return dict(start=t(s["start"]), end=t(s["end"]), length=s["length"], total=s["total"], mean=s["mean"],
                max=s["max"], min=s["min"])

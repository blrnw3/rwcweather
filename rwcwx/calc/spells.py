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
from typing import Dict, Iterable, List, Optional, Tuple, Union

from rwcwx.calc.rolling import SEASONS, span_overlaps_months, target_months

DIRECTIONS = ("above", "below")

# (var, daily statistic) -> spell config. thresholds are in display units (in, °F, hours); "partial": today counts.
SPELL_VARS: Dict[Tuple[str, str], dict] = {
    ("rain", "total"): dict(thresholds=(0.01, 0.1, 0.25, 0.5, 1.0), sum=True, partial=True),
    ("wet", "total"): dict(thresholds=(1, 3, 6, 12), sum=True, partial=True),
    ("wetrate", "avg"): dict(thresholds=(0.02, 0.05, 0.1, 0.2)),
    ("rain60", "max"): dict(thresholds=(0.05, 0.1, 0.25, 0.5), partial=True),
    ("rain10", "max"): dict(thresholds=(0.02, 0.05, 0.1, 0.2), partial=True),
    ("temp", "max"): dict(thresholds=(40, 50, 60, 70, 80, 90, 100), fahrenheit=True),
    ("temp", "min"): dict(thresholds=(32, 40, 45, 50, 55, 60), fahrenheit=True),
    ("temp", "avg"): dict(thresholds=(40, 50, 60, 70, 80), fahrenheit=True),
    ("sun", "total"): dict(thresholds=(0.1, 1, 4, 8, 10, 12), sum=True),
    ("sunpct", "avg"): dict(thresholds=(10, 25, 50, 75, 90)),
    ("fog", "total"): dict(thresholds=(0.5, 1, 2, 3, 4), sum=True),
    ("fogday", "total"): dict(thresholds=(1,), sum=True),
    ("humi", "max"): dict(thresholds=(50, 60, 70, 80, 90, 95)),
    ("humi", "min"): dict(thresholds=(20, 30, 40, 50, 60, 70)),
    ("humi", "avg"): dict(thresholds=(30, 40, 50, 60, 70, 80, 90)),
    ("dewpt", "max"): dict(thresholds=(32, 40, 50, 55, 60, 65), fahrenheit=True),
    ("dewpt", "min"): dict(thresholds=(25, 32, 40, 45, 50, 55), fahrenheit=True),
    ("dewpt", "avg"): dict(thresholds=(32, 40, 45, 50, 55, 60), fahrenheit=True),
    ("aqi", "max"): dict(thresholds=(25, 50, 100, 150, 200)),
    ("aqi", "min"): dict(thresholds=(10, 25, 50, 100)),
    ("aqi", "avg"): dict(thresholds=(25, 50, 100, 150)),
    ("wind", "max"): dict(thresholds=(5, 10, 15, 20, 25)),
    ("wind", "avg"): dict(thresholds=(2, 4, 6, 8, 10)),
    ("wind", "min"): dict(thresholds=(1, 2, 5)),
    ("gust", "max"): dict(thresholds=(10, 15, 20, 25, 30, 40)),
    ("gust", "avg"): dict(thresholds=(4, 6, 8, 10, 15)),
    ("gust", "min"): dict(thresholds=(1, 2, 5)),
    ("pres", "max"): dict(thresholds=(1005, 1010, 1015, 1020, 1025)),
    ("pres", "min"): dict(thresholds=(1005, 1010, 1015, 1020, 1025)),
    ("pres", "avg"): dict(thresholds=(1005, 1010, 1015, 1020, 1025)),
}

# Round Celsius thresholds offered to metric users, accepted as their exact °F equivalents (5 °C steps are whole °F).
CELSIUS_THRESHOLDS = {
    ("temp", "max"): (10, 15, 20, 25, 30, 35, 40),
    ("temp", "min"): (0, 5, 10, 15),
    ("temp", "avg"): (5, 10, 15, 20, 25),
    ("dewpt", "max"): (0, 5, 10, 15, 20),
    ("dewpt", "min"): (-5, 0, 5, 10, 15),
    ("dewpt", "avg"): (0, 5, 10, 15, 20),
}
for _key, _cs in CELSIUS_THRESHOLDS.items():
    SPELL_VARS[_key]["thresholds"] = tuple(sorted(set(SPELL_VARS[_key]["thresholds"]) | {c * 9 / 5 + 32 for c in _cs}))

# Round mm (and mm/h) thresholds offered to metric users, accepted as their inch equivalents (rounded to 4 dp).
MM_THRESHOLDS = {
    ("rain", "total"): (0.2, 2, 5, 10, 25),
    ("wetrate", "avg"): (0.5, 1, 2, 5),
    ("rain60", "max"): (1, 2, 5, 10),
    ("rain10", "max"): (0.5, 1, 2, 5),
}
for _key, _mms in MM_THRESHOLDS.items():
    SPELL_VARS[_key]["thresholds"] = tuple(sorted(set(SPELL_VARS[_key]["thresholds"]) | {round(mm / 25.4, 4) for mm in _mms}))

# Round kph thresholds offered to EU metric users, accepted as their mph equivalents (rounded to 4 dp).
KPH_THRESHOLDS = {
    ("wind", "max"): (10, 15, 20, 30, 40),
    ("wind", "avg"): (5, 10, 15, 20),
    ("wind", "min"): (2, 5, 10),
    ("gust", "max"): (15, 25, 30, 40, 50, 60),
    ("gust", "avg"): (5, 10, 15, 20, 25),
    ("gust", "min"): (2, 5, 10),
}
for _key, _kphs in KPH_THRESHOLDS.items():
    SPELL_VARS[_key]["thresholds"] = tuple(sorted(set(SPELL_VARS[_key]["thresholds"]) | {round(kph / 1.60934, 4) for kph in _kphs}))

# Round inHg thresholds offered to US users, accepted as their mb equivalents (rounded to 2 dp).
INHG_THRESHOLDS = {
    ("pres", "max"): (29.7, 29.8, 29.9, 30.0, 30.1, 30.2),
    ("pres", "min"): (29.7, 29.8, 29.9, 30.0, 30.1, 30.2),
    ("pres", "avg"): (29.7, 29.8, 29.9, 30.0, 30.1, 30.2),
}
for _key, _inhgs in INHG_THRESHOLDS.items():
    SPELL_VARS[_key]["thresholds"] = tuple(sorted(set(SPELL_VARS[_key]["thresholds"]) | {round(inhg / 0.02953, 2) for inhg in _inhgs}))

EPS = 1e-9


def supported() -> dict:
    return {v + "/" + t: list(c["thresholds"]) for (v, t), c in SPELL_VARS.items()}


def stored_threshold(var: str, typ: str, threshold: float) -> float:
    cfg = SPELL_VARS[(var, typ)]
    return (threshold - 32) * 5 / 9 if cfg.get("fahrenheit") else threshold


def meets(val: float, threshold: float, direction: str) -> bool:
    return val >= threshold - EPS if direction == "above" else val < threshold - EPS


def find_spells(daily: Iterable[Tuple[date, Optional[float]]], threshold: float, direction: str,
                month: Union[int, str, None] = 0, start_year: Optional[int] = None,
                last_day: Optional[date] = None, season: Optional[str] = None) -> List[dict]:
    """Every maximal run of consecutive qualifying days (threshold already in stored units), oldest first.
    When a month or season filter is given, any spell overlapping that month/season is included in full.
    """
    days = sorted((d, v) for d, v in daily if v is not None
                  and (last_day is None or d <= last_day)
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
    months = target_months(month, season)
    if months:
        spells = [s for s in spells if span_overlaps_months(s["start"], s["end"], months)]
    return spells


def _spell(run: List[Tuple[date, float]]) -> dict:
    vals = [v for _, v in run]
    return dict(start=run[0][0], end=run[-1][0], length=len(run), total=round(sum(vals), 4),
                mean=round(sum(vals) / len(vals), 4), max=max(vals), min=min(vals))


def rank_spells(spells: List[dict], limit: int = 25) -> List[dict]:
    return sorted(spells, key=lambda s: (s["length"], s["end"]), reverse=True)[:limit]


def spell_ranking(daily: Iterable[Tuple[date, Optional[float]]], var: str, typ: str, threshold: float,
                  direction: str = "above", month: Union[int, str, None] = 0, start_year: Optional[int] = None,
                  limit: int = 25, today: Optional[date] = None, season: Optional[str] = None) -> dict:
    """{result: top spells, current: the running spell with its rank (or None), found: number of spells}."""
    cfg = SPELL_VARS[(var, typ)]
    daily = list(daily)
    stored = stored_threshold(var, typ, threshold)
    last_day = None
    if today is not None:
        last_day = today if cfg.get("partial") else today - timedelta(days=1)
    spells = find_spells(daily, stored, direction, month, start_year, last_day, season=season)
    months = target_months(month, season)

    current = None
    if today is not None and spells:
        latest = spells[-1]
        running = latest["end"] == last_day
        if not running and cfg.get("partial") and latest["end"] == today - timedelta(days=1):
            # Today hasn't met the condition yet but still can (rain / wet hours only grow) - if spell is in scope.
            in_scope = span_overlaps_months(latest["start"], today, months) and (start_year is None or today.year >= start_year)
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

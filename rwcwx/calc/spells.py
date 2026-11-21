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
- Month filter (rankings): any spell that overlaps the month or season is returned in full. Start year: only
  days from 1 January of that year count.
- All-time grid: a cell is the longest qualifying spell (full length, in days) that either fully covers that
  month, calendar year or water year, or has its midpoint in that period. Midpoint is start + (length-1)//2,
  the earlier middle day when the length is even. A spell that crosses a boundary is counted at its full
  length (so a 22-day run from 20 December to 10 January, midpoint 30 December, is 22 in December and 0 in
  January). An ongoing spell (ending on the latest eligible day) is counted at its length so far; for the
  current in-progress period, "fully covers" means covering the period to date.
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


def _period_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _water_year_of(d: date) -> int:
    """California / USGS label: the calendar year in which the Oct-Sep water year ends."""
    return d.year + 1 if d.month >= 10 else d.year


def _midpoint(start: date, length: int) -> date:
    """Earlier middle day when the length is even: start + (length-1)//2."""
    return start + timedelta(days=(length - 1) // 2)


def _effective_hi(lo: date, hi: date, last_day: Optional[date]) -> date:
    """For the current in-progress period, treat the period as running only to the latest eligible day."""
    if last_day is not None and lo <= last_day < hi:
        return last_day
    return hi


def _qualifies(start: date, end: date, length: int, lo: date, hi: date) -> bool:
    """True if the spell fully covers [lo, hi] or its midpoint falls in that span."""
    if end < lo or start > hi:
        return False
    if start <= lo and end >= hi:
        return True
    mid = _midpoint(start, length)
    return lo <= mid <= hi


def _span_has_est(lo: date, hi: date, est_dates: Optional[set]) -> bool:
    if not est_dates:
        return False
    d = lo
    while d <= hi:
        if d in est_dates:
            return True
        d += timedelta(days=1)
    return False


def _consider(lengths: dict, est_flags: dict, key, start: date, end: date, length: int,
              lo: date, hi: date, last_day: Optional[date], est_dates: Optional[set]) -> None:
    hi = _effective_hi(lo, hi, last_day)
    if not _qualifies(start, end, length, lo, hi):
        return
    est = _span_has_est(start, end, est_dates)
    prev = lengths.get(key, 0)
    if length > prev:
        lengths[key] = length
        est_flags[key] = est
    elif length == prev and est:
        est_flags[key] = True


def _month_name(month: int) -> str:
    return ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[month - 1]


def _dmy(d: date) -> str:
    return "%s %s %s" % (d.day, _month_name(d.month), d.year)


def _water_year_status(wy: int, today: Optional[date], first_date: Optional[date]) -> str:
    end = date(wy, 9, 30)
    start = date(wy - 1, 10, 1)
    if today is not None and today <= end:
        return "current"
    if first_date is not None and first_date > start:
        return "partial"
    return "complete"


def _water_year_note(wy: int, status: str, today: Optional[date], first_date: Optional[date]) -> str:
    if status == "current" and today is not None:
        return "WY%s to date: 1 Oct %s – %s" % (wy, wy - 1, _dmy(today))
    if status == "partial" and first_date is not None:
        return "WY%s partial: records start %s" % (wy, _dmy(first_date))
    return "WY%s: 1 Oct %s – 30 Sep %s" % (wy, wy - 1, wy)


def _cell(period, length: int, est: bool) -> dict:
    out = dict(m=period, val=length)
    if est:
        out["est"] = True
    return out


def spell_grid(daily: Iterable[Tuple[date, Optional[float]]], var: str, typ: str, threshold: float,
               direction: str = "above", today: Optional[date] = None,
               est_dates: Optional[set] = None) -> dict:
    """Longest qualifying spell (full length, in days) for each month, calendar year and water year.

    Spells are the same runs as find_spells (consecutive calendar days meeting the
    threshold, broken by a missing day). A spell counts in a period at its full
    length if it fully covers that period, or if its midpoint (start + (length-1)//2)
    falls in the period. Months, years and water years that have at least one daily
    value are included (0 if no spell qualifies). Periods with no data are omitted.

    An ongoing spell ending on the latest eligible day is counted at its length so
    far; "fully covers" for the current in-progress period means covering it to date.

    last-day rules match spell_ranking: rain / wet hours / rates may include today;
    temperatures and sunshine stop at yesterday.
    """
    cfg = SPELL_VARS[(var, typ)]
    stored = stored_threshold(var, typ, threshold)
    last_day = None
    if today is not None:
        last_day = today if cfg.get("partial") else today - timedelta(days=1)
    days = [(d, v) for d, v in daily if v is not None and (last_day is None or d <= last_day)]
    spells = find_spells(days, stored, direction, last_day=last_day)

    months_with_data, years_with_data, wys_with_data = set(), set(), set()
    first_date = None
    for d, _v in days:
        months_with_data.add((d.year, d.month))
        years_with_data.add(d.year)
        wys_with_data.add(_water_year_of(d))
        if first_date is None or d < first_date:
            first_date = d

    monthly, monthly_est = {k: 0 for k in months_with_data}, {}
    yearly, yearly_est = {k: 0 for k in years_with_data}, {}
    wateryear, wateryear_est = {k: 0 for k in wys_with_data}, {}

    for s in spells:
        start, end, length = s["start"], s["end"], s["length"]
        y, m = start.year, start.month
        while date(y, m, 1) <= end:
            _consider(monthly, monthly_est, (y, m), start, end, length,
                      date(y, m, 1), _period_end(y, m), last_day, est_dates)
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
        for year in range(start.year, end.year + 1):
            _consider(yearly, yearly_est, year, start, end, length,
                      date(year, 1, 1), date(year, 12, 31), last_day, est_dates)
        start_wy, end_wy = _water_year_of(start), _water_year_of(end)
        for wy in range(start_wy, end_wy + 1):
            _consider(wateryear, wateryear_est, wy, start, end, length,
                      date(wy - 1, 10, 1), date(wy, 9, 30), last_day, est_dates)

    monthly_rows = [_cell([y, m], monthly[(y, m)], monthly_est.get((y, m), False))
                    for y, m in sorted(monthly)]
    yearly_rows = [_cell(y, yearly[y], yearly_est.get(y, False)) for y in sorted(yearly)]
    wateryear_rows = []
    for wy in sorted(wateryear):
        status = _water_year_status(wy, today, first_date)
        row = _cell(wy, wateryear[wy], wateryear_est.get(wy, False))
        row["status"] = status
        row["note"] = _water_year_note(wy, status, today, first_date)
        wateryear_rows.append(row)

    first = [first_date.year, first_date.month, first_date.day] if first_date else None
    return dict(monthly=monthly_rows, yearly=yearly_rows, wateryear=wateryear_rows, first_date=first)

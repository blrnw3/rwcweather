"""Daily profile: the average of a variable at each time of day (local Pacific time), in BIN_MIN-minute bins.

Periods: all time, one calendar year, one month of the year across all years (e.g. every July), or one year+month.

Local time of day without MySQL time zone tables: the period is split into runs of local days that share one UTC
offset (DST changes split it), and each run is aggregated in SQL relative to midnight at that offset, so
  bin = ((seconds since that midnight) mod 86400) div (BIN_MIN * 60).
Runs meet at true local midnights, so every minute is counted once. DST is taken from each day's local noon, so on
the two changeover days only the minutes before 02:00 land one hour out. Each run is one indexed range scan on obs.t (or obs_inferred.t) returning at most 288 rows; the per-run
sums and counts are added up here.

Values are in DB units (temperature, dew point °C; pressure hPa; wind, gust mph; rain in./h; aqi US AQI, the mean of
each PM2.5 reading's AQI); sun, wet and fog are % of observed/classified time.

Per-bin sums and counts are computed per calendar month and cached: in-process for every month, and on disk (shared
by uWSGI workers and across restarts and reboots, see CACHE_DIR) for finished months. Finished months are reused for
DISK_TTL (so backfills show up within a month), the current month for CURRENT_TTL. Any period is then a sum over its
months, so after the first request all-time, a year, every July, etc. cost no further queries. A cold all-time
request runs one query per month (~70); `python -m rwcwx.calc.day_profile` warms every variable. On prod that runs
daily from cron and after each backend deploy via scripts/run_day_profile_warm.sh.
"""
import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from dateutil.tz import UTC
from sqlalchemy import text

from rwcwx.config import TZ

BIN_MIN = 5
N_BINS = 24 * 60 // BIN_MIN
FIRST_DAY = date(2020, 12, 21)          # first day with obs

# var -> (source, SQL expression for the per-row value). "obs" rows are one minute each.
# Magnus dew point (as Obs.dewpt), via a derived table so LN is evaluated once per row
_DEWPT_FROM = ("(SELECT t, 237.7 * g / (17.271 - g) dp FROM (SELECT t, 17.271 * temp / (237.7 + temp) + LN(humi / 100) g "
               "FROM obs WHERE t >= :st AND t < :en AND humi > 0 AND temp IS NOT NULL) a) obs")
OBS_VARS: Dict[str, str] = {
    "temp": "temp",
    "humi": "humi",
    "dewpt": "dp",
    "pres": "pres",
    "wind": "wind",
    "gust": "gust",
    "aqi": "",          # filled in below: US AQI per reading
    "wet": "100 * wet",
}


def _aqi_sql(c: str) -> str:
    """US EPA AQI of a PM2.5 concentration already truncated to 0.1 µg/m³ (column `c`), as the site computes it
    (Obs.aqi, python-aqi): linear within the EPA breakpoints, rounded half-even to a whole number. Above the top
    breakpoint (500.4) it is 500, where python-aqi would raise. Built from python-aqi's own breakpoints so they stay in
    step. The slope is a DOUBLE literal so MySQL's ROUND is half-even like python-aqi's (DECIMAL ROUND is half-up)."""
    from aqi.algos.epa import AQI
    from aqi.constants import POLLUTANT_PM25
    pw = AQI.piecewise
    whens = " ".join(f"WHEN {c} <= {hi} THEN ROUND(({c} - {lo}) * {float((ahi - alo) / (hi - lo))!r}e0 + {alo})"
                     for (lo, hi), (alo, ahi) in zip(pw["bp"][POLLUTANT_PM25], pw["aqi"]))
    return f"(CASE WHEN {c} IS NULL THEN NULL {whens} ELSE {pw['aqi'][-1][1]} END)"


# obs.pm2 is FLOAT (12.9 is stored as 12.8999996), so it goes through DECIMAL before truncating; done once per row in
# a derived table rather than in each CASE branch
_AQI_C = "TRUNCATE(CAST(pm2 AS DECIMAL(10, 3)), 1)"
_AQI_FROM = f"(SELECT t, {_AQI_C} c FROM obs WHERE t >= :st AND t < :en AND pm2 >= 0) obs"
OBS_VARS["aqi"] = _aqi_sql("c")
_SOURCES: Dict[str, str] = {"dewpt": _DEWPT_FROM, "aqi": _AQI_FROM}
# old name for the AQI profile (it showed raw PM2.5 µg/m³ before)
ALIASES: Dict[str, str] = {"pm2": "aqi"}

# classifier kinds in obs_inferred (value 1/0, NULL = unclassified), each row covering `minutes` minutes
INFERRED_VARS: Dict[str, str] = {"sun": "sunny", "fog": "fog"}
RAIN_VAR = "rain"
VARS = tuple(OBS_VARS) + (RAIN_VAR,) + tuple(INFERRED_VARS)

# single steps above this are logger catch-up artefacts, not rain (see rwcwx.wet.intensity.SPIKE_IN)
SPIKE_IN = 0.10


@dataclass(frozen=True)
class Run:
    """Local days [d0, d1) sharing one UTC offset: UTC bounds (true local midnights) and the anchor (midnight at
    this offset), all naive UTC."""
    d0: date
    d1: date
    st: datetime
    en: datetime
    anchor: datetime


def _offset(d: date) -> timedelta:
    return datetime(d.year, d.month, d.day, 12, tzinfo=TZ).utcoffset()


def _utc_midnight(d: date, off: timedelta) -> datetime:
    return datetime(d.year, d.month, d.day) - off


def period_days(year: Optional[int], month: Optional[int], first: date, last: date) -> List[Tuple[date, date]]:
    """[start, end) local-date ranges for the period, clipped to [first, last]."""
    ranges: List[Tuple[date, date]] = []
    for y in range(first.year, last.year + 1):
        if year is not None and y != year:
            continue
        if month is None:
            s, e = date(y, 1, 1), date(y + 1, 1, 1)
        else:
            s = date(y, month, 1)
            e = date(y + 1, 1, 1) if month == 12 else date(y, month + 1, 1)
        s, e = max(s, first), min(e, last + timedelta(days=1))
        if s < e:
            ranges.append((s, e))
    return ranges


def _local_midnight_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=TZ).astimezone(UTC).replace(tzinfo=None)


def runs(ranges: Iterable[Tuple[date, date]]) -> List[Run]:
    """Split date ranges at DST changes.

    Each run's [st, en) runs between true local midnights, so no minute is counted twice or skipped. The anchor
    is midnight at the run's own offset (taken at local noon); on a change day the minutes before 02:00 land an
    hour off, which is unavoidable with a fixed-offset day grid."""
    out: List[Run] = []
    for s, e in ranges:
        d0, off = s, _offset(s)
        d = s + timedelta(days=1)
        while d <= e:
            o = _offset(d) if d < e else None
            if d == e or o != off:
                out.append(Run(d0, d, _local_midnight_utc(d0), _local_midnight_utc(d), _utc_midnight(d0, off)))
                d0, off = d, o
            d += timedelta(days=1)
    return out


def _bin_sql(t_expr: str) -> str:
    return f"FLOOR(MOD(TIMESTAMPDIFF(SECOND, :anchor, {t_expr}), 86400) / {BIN_MIN * 60})"


def _query(var: str) -> str:
    if var in OBS_VARS:
        x = OBS_VARS[var]
        src = _SOURCES.get(var, "obs")
        return (f"SELECT {_bin_sql('t')} b, SUM({x}) s, COUNT({x}) n FROM {src} "
                f"WHERE t >= :st AND t < :en GROUP BY b")
    if var == RAIN_VAR:
        # obs.rain is the day's running total: a positive step is rain (resets at midnight are negative)
        return (f"SELECT {_bin_sql('t')} b, SUM(CASE WHEN d > 0 AND d <= {SPIKE_IN} THEN d ELSE 0 END) * 60 s, COUNT(*) n "
                f"FROM (SELECT t, rain - LAG(rain) OVER (ORDER BY t) d FROM obs WHERE t >= :st AND t < :en) x "
                f"WHERE d IS NOT NULL GROUP BY b")
    if var in INFERRED_VARS:
        # A row covers [t, t + minutes): spread it over the bins it covers, weighted by minutes per bin.
        ks = " UNION ALL ".join(f"SELECT {k} k" for k in range(6))
        t_expr = f"DATE_ADD(i.t, INTERVAL k.k * {BIN_MIN} MINUTE)"
        return (f"SELECT {_bin_sql(t_expr)} b, SUM(100 * i.value * LEAST(i.minutes, {BIN_MIN})) s, "
                f"SUM(LEAST(i.minutes, {BIN_MIN})) n FROM obs_inferred i JOIN ({ks}) k ON k.k * {BIN_MIN} < i.minutes "
                f"WHERE i.kind = :kind AND i.value IS NOT NULL AND i.t >= :st AND i.t < :en GROUP BY b")
    raise ValueError(f"Unsupported variable {var}")


Sums = Tuple[List[float], List[float]]


def _add(acc: Sums, rows: Iterable[Tuple[Optional[int], Optional[float], Optional[float]]]) -> Sums:
    for b, sm, cnt in rows:
        if b is None or sm is None or not cnt:
            continue
        b = int(b) % N_BINS
        acc[0][b] += float(sm)
        acc[1][b] += float(cnt)
    return acc


def _empty() -> Sums:
    return [0.0] * N_BINS, [0.0] * N_BINS


def averages(acc: Sums) -> Tuple[List[Optional[float]], List[int]]:
    s, n = acc
    return [round(s[i] / n[i], 4) if n[i] else None for i in range(N_BINS)], [int(round(x)) for x in n]


def month_sums(conn, var: str, y: int, m: int, last: date) -> Sums:
    """Per-bin (sums, counts) for the local days of month y-m up to `last`."""
    acc = _empty()
    sql = text(_query(var))
    for r in runs(period_days(y, m, FIRST_DAY, last)):
        params = dict(st=r.st, en=r.en, anchor=r.anchor)
        if var in INFERRED_VARS:
            params["kind"] = INFERRED_VARS[var]
        _add(acc, conn.execute(sql, params).fetchall())
    return acc


PAST_TTL = 7 * 24 * 3600         # in-process, finished months
DISK_TTL = 30 * 24 * 3600        # on-disk, finished months (they only change if history is re-imported)
CURRENT_TTL = 600
# <repo>/cache/day_profile (prod: /home/ben/rwcweather/cache/day_profile) survives reboots, unlike /tmp; the deploy
# rsyncs only rwcwx/ and scripts, so it is never overwritten. Falls back to the temp dir if that is not writable.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_cache_dir() -> str:
    d = os.path.join(_REPO_ROOT, "cache", "day_profile")
    try:
        os.makedirs(d, exist_ok=True)
        if os.access(d, os.W_OK):
            return d
    except OSError:
        pass
    return os.path.join(tempfile.gettempdir(), "rwcwx_day_profile")


CACHE_DIR = os.getenv("RWCWX_PROFILE_CACHE_DIR") or _default_cache_dir()
_CACHE_VERSION = 1
_cache: Dict[Tuple[str, int, int], Tuple[float, Sums]] = {}
_lock = threading.Lock()


def _disk_path(var: str, y: int, m: int) -> str:
    return os.path.join(CACHE_DIR, f"v{_CACHE_VERSION}-b{BIN_MIN}-{var}-{y}-{m:02d}.json")


def _disk_get(var: str, y: int, m: int) -> Optional[Sums]:
    path = _disk_path(var, y, m)
    try:
        if time.time() - os.path.getmtime(path) >= DISK_TTL:
            return None
        with open(path) as f:
            d = json.load(f)
        return d["s"], d["n"]
    except (OSError, ValueError, KeyError):
        return None


def _disk_put(var: str, y: int, m: int, val: Sums) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        path = _disk_path(var, y, m)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump({"s": val[0], "n": val[1]}, f)
        os.replace(tmp, path)
    except OSError:
        pass


def _cached_month(conn, var: str, y: int, m: int, last: date, now=time.monotonic) -> Sums:
    current = (y, m) >= (last.year, last.month)
    key = (var, y, m)
    t = now()
    with _lock:
        hit = _cache.get(key)
    if hit and t - hit[0] < (CURRENT_TTL if current else PAST_TTL):
        return hit[1]
    val = None if current else _disk_get(var, y, m)
    if val is None:
        val = month_sums(conn, var, y, m, last)
        if not current:
            _disk_put(var, y, m, val)
    with _lock:
        _cache[key] = (t, val)
    return val


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def profile(conn, var: str, year: Optional[int] = None, month: Optional[int] = None,
            last: Optional[date] = None) -> dict:
    var = ALIASES.get(var, var)
    if var not in VARS:
        raise ValueError(f"Unsupported variable {var}")
    last = last or datetime.now(TZ).date()
    ranges = period_days(year, month, FIRST_DAY, last)
    acc = _empty()
    for s, e in ranges:
        d = date(s.year, s.month, 1)
        while d < e:
            ms = _cached_month(conn, var, d.year, d.month, last)
            for i in range(N_BINS):
                acc[0][i] += ms[0][i]
                acc[1][i] += ms[1][i]
            d = date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)
    avg, cnt = averages(acc)
    days = sum((e - s).days for s, e in ranges)
    return dict(var=var, year=year, month=month, bin_min=BIN_MIN, days=days,
                start=ranges[0][0].isoformat() if ranges else None,
                end=(ranges[-1][1] - timedelta(days=1)).isoformat() if ranges else None,
                avg=avg, n=cnt)


def warm(conn, last: Optional[date] = None, variables: Sequence[str] = VARS) -> int:
    """Fill the month caches for every variable (e.g. after a deploy) so no visitor waits on a cold all-time query."""
    last = last or datetime.now(TZ).date()
    n = 0
    for var in variables:
        profile(conn, var, None, None, last)
        n += 1
    return n


if __name__ == "__main__":  # python -m rwcwx.calc.day_profile  (read-only; writes only the cache files)
    from rwcwx.main import app
    from rwcwx.models import db
    t0 = time.time()
    with app.app_context(), db.engine.connect() as c:
        warm(c)
    print(f"day profile cache warmed in {time.time() - t0:.1f}s ({CACHE_DIR})")

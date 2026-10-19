from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional, Union

from dateutil.tz import UTC
from flask import request

from rwcwx import logger, ttl_cache

from rwcwx.astronomy import get_all_times_rwc, getTimes
from rwcwx.calc.avg_extreme import (
    AvgExtAggregator, MonthSummary, DaySummary, YearSummary, WaterYearRainSummary, DayOfYearSummary,
)
from rwcwx.calc.spells import DIRECTIONS, SPELL_VARS, spell_ranking, supported as spells_supported
from rwcwx.calc import anom_spells as anom_spells_mod
from rwcwx.calc.rolling import (
    ROLLING_DAYS, ROLLING_VARS, SEASONS, min_days_required, rolling_ranking_with_current,
)
from rwcwx.config import TZ
from rwcwx.model.avgext import AvgExtQ
from rwcwx.model.obs import ObsQ
from rwcwx.model import sun as sun_model
from rwcwx.models import AvgExt, Base, db, m, Obs
from rwcwx.util import DateStampConverter, DateUtil
from rwcwx.wet import rate as wet_rate
from rwcwx.wet import intensity_store
from rwcwx.wet import store as wet_store
from rwcwx.fog import derive as fog_derive
from rwcwx.calc import day_profile


def todo():
    return "API docs TODO. Try /web/dashboard/live"


def lol():
    return {"lol": 42}


def current():
    q = ObsQ.latest(1)[0]
    # t = q.t_obs.replace(tzinfo=UTC).astimezone(TZ)
    return _wrap_result(
        q.dict_,
        # t_obs_pretty_date=t.strftime("%A %d %B %Y"),
        # t_obs_pretty_time=t.strftime("%H:%M:%S %Z")
    )


def dashboard_live():
    """
    Amalgamates all useful data for a live dashboard to reduce number of http calls
    """
    now = DateUtil.now()
    trends = ObsQ.trend([10, 60, 180, 1440])
    last_rain = ObsQ.last_rain()
    return _wrap_result(
        dict(
            now=trends[0],
            trends=trends,
            today=_today_stats(now.date(), int(now.timestamp() // 60)),
            sun=_sun_today(now.date(), int(now.timestamp() // 60)),
            wet=_wet_today(now.date(), int(now.timestamp() // 60)),
            last_rain=last_rain,
            rain_trend=dict(
                last=last_rain,
                hr24=ObsQ.rain_24hrs(),
                m10=trends[0].rain - trends[10].rain,
                hr1=trends[0].rain - trends[60].rain,
                hr3=trends[0].rain - trends[180].rain,
            )
        )
    )


@lru_cache(maxsize=2)
def _today_stats(day: date, _minute: int) -> dict:
    """Compute today's dashboard summary at most once per minute per worker."""
    return DaySummary(day).stats_json()


@lru_cache(maxsize=2)
def _sun_today(day: date, _minute: int) -> Optional[dict]:
    """Sunshine block for the live dashboard, at most once per minute per worker. Never breaks the dashboard."""
    try:
        return sun_model.dashboard_block(day)
    except Exception as e:  # e.g. obs_inferred missing on a dev DB
        logger.warning(f"sun dashboard block failed: {e}")
        return None


@lru_cache(maxsize=2)
def _wet_today(day: date, _minute: int) -> Optional[dict]:
    """Today's derived wet hours, spells, longest spell and rate; read-only, at most once per minute per worker."""
    try:
        wd, _, _ = wet_store.compute_day(day)
        return wd.summary(datetime.utcnow())
    except Exception as e:
        logger.warning(f"wet dashboard block failed: {e}")
        return None


def wet_day(d: date = None):
    """Derived wet hours for one local day from the stored obs.wet minutes: total, spells, longest, rate."""
    d = d or DateUtil.now().date()
    if isinstance(d, datetime):
        d = d.date()
    return _wrap_result(wet_store.stored_day(d), date=d)


def sun_day(d: date = None):
    """Webcam sunshine for one local day: total, spells (sun / no sun / unknown) and daylight."""
    d = d or DateUtil.now().date()
    if isinstance(d, datetime):
        d = d.date()
    return _wrap_result(sun_model.day_report(d), date=d)


def dashboard_summary():
    """
    Amalgamates all useful data for a live dashboard to reduce number of http calls
    """
    # The page polls this every 5 minutes per visitor. Month/year tables include today, so they are
    # reused for at most a minute (same freshness as the live obs feed); yesterday's minute obs can
    # still be revised shortly after midnight, so it is recomputed every 10 minutes.
    today = DateUtil.now().date()
    yesterday = DateUtil.yesterday().date()
    return _wrap_result(
        dict(
            yesterday=ttl_cache.cached(("yesterday", yesterday), 600, lambda: DaySummary(yesterday).stats_json()),
            month=ttl_cache.cached(("month", today), 60, lambda: MonthSummary(today).stats()),
            year=ttl_cache.cached(("year", today), 60, lambda: YearSummary(today.year).stats()),
            water_year=ttl_cache.cached(("water_year", today), 60, lambda: WaterYearRainSummary.for_this_year().stats()),
            day_of_year=DayOfYearSummary.for_today().stats(),
            astronomy=get_all_times_rwc(),
        )
    )


def day_summary(d: date = None):
    summary = DaySummary(d)
    return _wrap_result(
        summary.stats_json(),
        date=summary.day
    )


def day_report(d: date):
    """Summary and minute observations for a single local calendar day."""
    observations = ObsQ.day(d)
    return _wrap_result(
        dict(
            summary=DaySummary(d).stats_json(observations),
            observations=observations,
            rain_intensity=_rain_intensity(d),
        ),
        date=d,
    )


def _rain_intensity(d: date) -> Optional[dict]:
    """Max rain in any 10 / 60 minutes for the day (stored values, else computed from obs for days not yet stored)."""
    try:
        res = {ae.var: dict(val=ae.val, at=ae.at) for ae in AvgExtQ.for_var_between_dates("rain10", "max", d, d)
               + AvgExtQ.for_var_between_dates("rain60", "max", d, d)}
        if len(res) < 2:
            computed, _ = intensity_store.compute_day(d)
            res = {v: dict(val=val, at=at.replace(tzinfo=UTC) if at else None) for v, (val, at) in computed.items()}
        return res
    except Exception as e:
        logger.warning(f"rain intensity failed for {d}: {e}")
        return None


def month_summary(mnth: date = None):
    summary = MonthSummary(mnth)
    return _wrap_result(
        summary.stats(),
        date=summary.month,
        month=summary.month.month,
        year=summary.month.year
    )


def year_summary(yr: int = None):
    summary = YearSummary(yr)
    return _wrap_result(
        summary.stats(),
        year=summary.year
    )


def var_daily(var: str, typ: str):
    return _wrap_result(AvgExtAggregator.daily(_var_avg_exts_from_request(var, typ), var))


def var_monthly(var: str, typ: str):
    return _wrap_result(AvgExtAggregator.monthly(_var_avg_exts_from_request(var, typ), var))


def var_yearly(var: str, typ: str):
    return _wrap_result(AvgExtAggregator.annual(_var_avg_exts_from_request(var, typ), var))


def var_all_periods(var: str, typ: str):
    return _wrap_result(AvgExtAggregator.all_summaries(_var_avg_exts_from_request(var, typ), var))


def _parse_month_or_season(raw: str):
    if raw is None or raw == "" or raw == "0" or raw.lower() == "all":
        return 0
    low = raw.lower()
    if low in SEASONS:
        return low
    try:
        m = int(raw)
        return m if 0 <= m <= 12 else None
    except ValueError:
        return None


def var_rolling(var: str, typ: str):
    """
    Non-overlapping N-day period rankings, e.g. /api/var/rolling/rain/total/?days=3
    Query params: days (3, 5, 7, 14 or 30), order (highest|lowest), month (0=all, 1-12 or season), limit (1-100).
    """
    try:
        days = int(request.args.get("days", "3"))
        limit = int(request.args.get("limit", "25"))
    except ValueError:
        return {"error": "days and limit must be integers"}, 400
    order = request.args.get("order", "highest")
    month = _parse_month_or_season(request.args.get("month", "0"))
    season = request.args.get("season")
    if season and season.lower() in SEASONS:
        month = season.lower()
    if typ not in ROLLING_VARS.get(var, {}) or days not in ROLLING_DAYS \
            or order not in ("highest", "lowest") or month is None or not 1 <= limit <= 100:
        return {
            "error": "Unsupported rolling ranking",
            "supported": dict(vars={v: list(t) for v, t in ROLLING_VARS.items()}, days=list(ROLLING_DAYS),
                              order=["highest", "lowest"], month="0-12 or season", limit="1-100"),
        }, 400
    now = DateUtil.now()
    ranking, current = _rolling_cached(var, typ, days, order, month, limit, now.date(), int(now.timestamp() // 300))
    return _wrap_result(
        ranking,
        var=var, type=typ, days=days, order=order, month=month, min_days=min_days_required(days), current=current,
    )


@lru_cache(maxsize=64)
def _rolling_cached(var: str, typ: str, days: int, order: str, month, limit: int, today: date, _bucket: int) -> tuple:
    """Each ranking is computed at most once per 5 minutes per worker (the reports refresh every 5 minutes)."""
    return rolling_ranking_with_current(_daily_values(var, typ), var, typ, days, order, limit, today, month=month)


def var_spells(var: str, typ: str):
    """
    Longest runs of consecutive days above/below a threshold, e.g. /api/var/spells/rain/total/?dir=below&threshold=0.01
    Query params: dir (above|below), threshold (in, °F or hours; one of the supported values),
    month (0 = all, 1-12 or season), start_year, limit (1-100).
    """
    cfg = SPELL_VARS.get((var, typ))
    try:
        threshold = float(request.args.get("threshold", "nan"))
        start_year = int(request.args["start_year"]) if request.args.get("start_year") else None
        limit = int(request.args.get("limit", "25"))
    except ValueError:
        threshold = None
        start_year = None
        limit = 0
    month = _parse_month_or_season(request.args.get("month", "0"))
    season = request.args.get("season")
    if season and season.lower() in SEASONS:
        month = season.lower()
    direction = request.args.get("dir", "above")
    if cfg is None or threshold is None or threshold not in cfg["thresholds"] or direction not in DIRECTIONS \
            or month is None or not 1 <= limit <= 100 or (start_year is not None and not 2000 <= start_year <= 2100):
        return {
            "error": "Unsupported spell ranking",
            "supported": dict(vars=spells_supported(), dir=list(DIRECTIONS), month="0-12 or season", limit="1-100"),
        }, 400
    now = DateUtil.now()
    res = _spells_cached(var, typ, threshold, direction, month, start_year, limit, now.date(), int(now.timestamp() // 300))
    return _wrap_result(res["result"], var=var, type=typ, dir=direction, threshold=threshold, month=month,
                        start_year=start_year, current=res["current"], found=res["found"], stat=res["stat"])


@lru_cache(maxsize=128)
def _spells_cached(var, typ, threshold, direction, month, start_year, limit, today: date, _bucket: int) -> dict:
    return spell_ranking(_daily_values(var, typ), var, typ, threshold, direction, month, start_year, limit, today)


def var_anom_spells(var: str, typ: str):
    """
    Heatwave / cold-snap spells vs climate normal.
    /api/var/anom_spells/temp/max/?dir=above&level=5&order=length
    level is a departure in °F (3,5,8,10 or metric °C equivalents); only temp is supported.
    """
    try:
        level = float(request.args.get("level", "nan"))
        limit = int(request.args.get("limit", "25"))
    except ValueError:
        level, limit = None, 0
    month = _parse_month_or_season(request.args.get("month", "0"))
    season = request.args.get("season")
    if season and season.lower() in SEASONS:
        month = season.lower()
    direction = request.args.get("dir", "above")
    order = request.args.get("order", "length")
    if (var != "temp" or typ not in anom_spells_mod.TYPES or level is None
            or not any(abs(level - x) < 1e-6 for x in anom_spells_mod.LEVELS) or direction not in anom_spells_mod.DIRECTIONS
            or order not in anom_spells_mod.ORDERS or month is None or not 1 <= limit <= 100):
        return {
            "error": "Unsupported anomaly spell ranking",
            "supported": dict(
                vars=["temp/" + t for t in anom_spells_mod.TYPES],
                level=list(anom_spells_mod.LEVELS),
                dir=list(anom_spells_mod.DIRECTIONS),
                order=list(anom_spells_mod.ORDERS),
                month="0-12 or season", limit="1-100",
            ),
        }, 400
    now = DateUtil.now()
    res = _anom_spells_cached(var, typ, level, direction, month, order, limit, now.date(), int(now.timestamp() // 300))
    return _wrap_result(res["result"], var=var, type=typ, dir=direction, level=level, order=order,
                        month=month, current=res["current"], found=res["found"])


@lru_cache(maxsize=128)
def _anom_spells_cached(var, typ, level, direction, month, order, limit, today: date, _bucket: int) -> dict:
    return anom_spells_mod.anom_spell_ranking(
        _daily_values(var, typ), typ, level, direction, month, order, limit, today)


def _daily_values(var: str, typ: str):
    if (var, typ) == (sun_model.PCT_VAR, sun_model.PCT_TYPE):
        return sun_model.pct_daily_values(AvgExtQ.daily_values("sun", "total"))
    if (var, typ) == (fog_derive.DAY_VAR, fog_derive.DAY_TYPE):
        return fog_derive.fog_day_values(AvgExtQ.daily_values("fog", "total"))
    if (var, typ) == (wet_rate.RATE_VAR, wet_rate.RATE_TYPE):
        rain = dict(AvgExtQ.daily_values("rain", "total"))
        return [(d, wet_rate.rate(rain.get(d), w)) for d, w in AvgExtQ.daily_values("wet", "total")
                if rain.get(d) and wet_rate.rate(rain.get(d), w) is not None]
    return AvgExtQ.daily_values(var, typ)


def obs_latest():
    mins = int(request.args.get("d", "60"))
    assert 1 < mins <= 150_000
    return _wrap_result(
        ObsQ.latest(mins, optimized=True),
        duration=mins
    )


def astronomy():
    times = get_all_times_rwc()
    return _wrap_result(times)


def trend_live():
    periods_raw = request.args.get("p", "60")
    try:
        periods = [int(p) for p in periods_raw.split(",")]
    except ValueError:
        return {
            "error": "Misformatted periods. Must be ints"
        }
    return _wrap_result(
        ObsQ.trend(periods),
        periods=periods
    )


def rain_stats():
    rn_trends = ObsQ.trend([10, 60, 180])
    return _wrap_result(dict(
        last_rain=ObsQ.last_rain(),
        rain_24hrs=ObsQ.rain_24hrs(),
        rain_10m=rn_trends[0].rain - rn_trends[10].rain,
        rain_hr=rn_trends[0].rain - rn_trends[60].rain,
        rain_3hr=rn_trends[0].rain - rn_trends[180].rain,
    ))


def var_profile(var: str):
    """
    Average value at each time of day (local Pacific time) in 5-minute bins, e.g. /api/var/profile/temp/?month=7
    Query params: year (optional), month (optional, 1-12). Neither = all time; month alone = that month in every year.
    sun, wet and fog are % of classified/observed time; see rwcwx.calc.day_profile.
    """
    try:
        year = int(request.args["year"]) if request.args.get("year") else None
        month = int(request.args["month"]) if request.args.get("month") else None
    except ValueError:
        year = month = -1
    var = day_profile.ALIASES.get(var, var)       # pm2 -> aqi
    if var not in day_profile.VARS or (year is not None and not 2000 <= year <= 2100) \
            or (month is not None and not 1 <= month <= 12):
        return {"error": "Unsupported profile", "supported": dict(vars=list(day_profile.VARS), year="YYYY", month="1-12")}, 400
    with db.engine.connect() as conn:
        res = day_profile.profile(conn, var, year, month, DateUtil.now().date())
    return _wrap_result(res)


def _wrap_result(res, **extras) -> dict:
    now = DateUtil.now()
    return {
        "result": _dictify_obs_result(res),
        "server": dict(
            datetime=now,
            epoch=now.timestamp(),
            localtime=DateUtil.now_local_string(),
            date=(now.year, now.month, now.day),
            offset=int(now.utcoffset().total_seconds() // 3600)
        ),
        **extras
    }


def _dictify_obs_result(res):
    if isinstance(res, dict):
        return {k: _dictify_obs_result(v) for k, v in res.items()}
    elif isinstance(res, list):
        return [_dictify_obs_result(o) for o in res]
    elif isinstance(res, Base):
        return res.dict_
    return res


def _var_avg_exts_from_request(var: str, typ: str) -> List[AvgExt]:
    if var == wet_rate.RATE_VAR:
        # Derived per day from the rain and wet-hours totals; blank (left out) on days without wet hours.
        if typ != wet_rate.RATE_TYPE:
            return []
        return wet_rate.rate_days(_var_avg_exts_from_request("rain", "total"), _var_avg_exts_from_request("wet", "total"))
    if var == fog_derive.DAY_VAR:
        # Derived per day from the stored fog hours: 1 if any fog that morning.
        return fog_derive.fog_days(_var_avg_exts_from_request("fog", "total")) if typ == fog_derive.DAY_TYPE else []
    if var == sun_model.PCT_VAR:
        # Derived from the daily sunshine totals; only one daily statistic exists.
        return sun_model.pct_days(_var_avg_exts_from_request("sun", "total")) if typ == sun_model.PCT_TYPE else []
    if "year" in request.args:
        year = int(request.args.get("year", DateUtil.now().year))
        avg_ext = AvgExtQ.for_var_and_year(var, typ, year)
    else:
        if "start" in request.args:
            start = DateStampConverter.from_str(request.args["start"])
        else:
            n = int(request.args.get("n", "31"))
            start = DateUtil.now() - timedelta(days=n)

        if "end" in request.args:
            end = DateStampConverter.from_str(request.args["end"])
        elif "include_today" in request.args or DateUtil.now().hour >= 21:
            end = None
        else:
            end = DateUtil.yesterday()

        avg_ext = AvgExtQ.for_var_between_dates(var, typ, start, end)

    return avg_ext

"""Forecast API: home-card NWS summary, plus the forecast-page meteogram / 72-hour / ensemble endpoints.

Each upstream is fetched and cached server-side (see nws.py and openmeteo.py). Parts are null when a
source is unavailable.
"""
from datetime import datetime, timedelta, timezone

from flask import jsonify

from rwcwx.forecast import ensemble as ens_mod
from rwcwx.forecast import meteogram as mg_mod
from rwcwx.forecast import nws, openmeteo, parse, runs as runs_mod
from rwcwx.forecast.cache import merge_status
from rwcwx.config import TZ
from rwcwx.recap.rules import local_today


def _now() -> datetime:
    return datetime.now(timezone.utc)      # patched in tests


def _nws_meta(*names: str) -> dict:
    return merge_status(*(nws.status(n) for n in names))


def _om_meta(*names: str) -> dict:
    return merge_status(*(openmeteo.status(n) for n in names))


def build(now_utc: datetime) -> dict:
    today = local_today(now_utc)
    fc = nws.forecast()
    periods = parse.periods(fc, today)
    qpf_total = parse.add_qpf(periods, nws.gridpoint()) if periods else None
    return dict(
        location=dict(lat=nws.LAT, lon=nws.LON,
                      url=f"https://forecast.weather.gov/MapClick.php?lat={nws.LAT}&lon={nws.LON}"),
        updated=(fc or {}).get("updateTime") or (fc or {}).get("generatedAt"),
        periods=periods,
        qpf_total_mm=qpf_total,
        discussion=parse.discussion(nws.afd()),
        alerts=parse.alerts(nws.alerts()),
        today=today.isoformat(),
        **_nws_meta("forecast", "gridpoint", "afd", "alerts"),
    )


def _json(result, max_age=300):
    resp = jsonify(result=result)
    resp.headers["Cache-Control"] = f"public, max-age={max_age}"
    return resp


def get_forecast():
    return _json(build(_now()))


def build_nws(now_utc: datetime) -> dict:
    """72-hour NWS forecast (periods + hourly), full AFD, highlights and alerts."""
    today = local_today(now_utc)
    fc = nws.forecast()
    hourly_fc = nws.forecast_hourly()
    grid = nws.gridpoint()
    periods = parse.periods_through(fc, today, days=3)
    qpf_total = parse.add_qpf(periods, grid) if periods else None
    hourly = parse.hourly(hourly_fc, now_utc, now_utc + timedelta(hours=72))
    if hourly:
        parse.add_qpf(hourly, grid)
    afd = nws.afd()
    return dict(
        location=dict(lat=nws.LAT, lon=nws.LON,
                      url=f"https://forecast.weather.gov/MapClick.php?lat={nws.LAT}&lon={nws.LON}"),
        updated=(fc or {}).get("updateTime") or (fc or {}).get("generatedAt"),
        periods=periods,
        qpf_total_mm=qpf_total,
        hourly=hourly,
        discussion=parse.discussion(afd),
        afd=parse.discussion_full(afd),
        alerts=parse.alerts(nws.alerts()),
        today=today.isoformat(),
        **_nws_meta("forecast", "forecast_hourly", "gridpoint", "afd", "alerts"),
    )


def get_forecast_nws():
    return _json(build_nws(_now()))


def build_meteogram(now_utc=None) -> dict:
    now_utc = now_utc or _now()
    raw = openmeteo.meteogram()
    series = mg_mod.series(raw)
    latest = openmeteo.latest_available_run("gfs_seamless", now_utc)
    model_run = None
    if latest:
        model_run = dict(
            run=runs_mod.run_iso(latest["run"]),
            run_label=runs_mod.run_label(latest["run"]),
            run_z=runs_mod.run_label(latest["run"], with_date=False),
        )
    return dict(
        location=dict(lat=openmeteo.LAT, lon=openmeteo.LON, elevation=openmeteo.ELEV),
        source="Open-Meteo",
        source_url="https://open-meteo.com/",
        model="gfs_seamless",
        model_note="GFS seamless (HRRR in the near term, GFS thereafter)",
        model_run=model_run,
        series=series,
        **_om_meta("meteogram"),
    )


def get_meteogram():
    return _json(build_meteogram(), max_age=300)


def build_ensemble(now_utc: datetime) -> dict:
    ensembles = {
        "gefs": openmeteo.ensemble(ens_mod.MODELS["gefs"]["id"]),
        "ecmwf": openmeteo.ensemble(ens_mod.MODELS["ecmwf"]["id"]),
    }
    # Previous Runs API is no longer used for the run-to-run chart (daily
    # lead offsets only). Per-cycle history comes from the Single Runs API.
    out = ens_mod.build(ensembles, {}, now_utc)
    local = now_utc.astimezone(TZ).replace(minute=0, second=0, microsecond=0)
    history = runs_mod.build_history(now_utc, local, ensembles)
    for key, model in (out.get("models") or {}).items():
        if key in history.get("current", {}):
            model["model_run"] = history["current"][key]
    out["run_history"] = dict(
        source=history["source"],
        source_url=history["source_url"],
        lookback_days=history["lookback_days"],
        operational=history["operational"],
        latest=history["latest"],
    )
    out["heatmap"] = history["heatmap"]
    out["source"] = "Open-Meteo Ensemble API and Single Runs API"
    meta = _om_meta(
        "ensemble:" + ens_mod.MODELS["gefs"]["id"],
        "ensemble:" + ens_mod.MODELS["ecmwf"]["id"],
    )
    out.update(meta)
    return out


def get_ensemble():
    return _json(build_ensemble(_now()), max_age=300)

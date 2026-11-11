"""GET /api/nearby: current temperature and today's rain at nearby stations, each fetched and cached on its own."""
from flask import jsonify

from rwcwx.nearby import fetch, parse, store
from rwcwx.recap.rules import local_today


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _obs_for(st: dict):
    if st["kind"] == "official":
        return parse.official(fetch.nws_latest(st["nws_id"]),
                              fetch.iem_current(st["iem_id"], st["iem_network"]))
    if st["kind"] == "weatherlink":
        obs = parse.weatherlink(fetch.weatherlink(st["wl_id"]))
        if obs and st.get("wl_embed"):
            parse.apply_hilo(obs, parse.weatherlink_hilo(fetch.weatherlink_embed(st["wl_embed"])))
        return obs
    return None


def _fill_hilo_from_log(stations, day):
    """Use a logged Lo-Hi only when the source did not publish one and the log covers the day since midnight."""
    missing = [s["id"] for s in stations if s.get("temp_min_c") is None and s.get("temp_max_c") is None]
    if not missing:
        return
    try:
        samples = store.samples_on_day(day)
    except Exception as e:      # table missing already returns {}; any other error must not break the card
        from rwcwx import logger
        logger.warning("nearby log hilo unavailable: %s", type(e).__name__)
        return
    for s in stations:
        if s["id"] not in missing:
            continue
        hilo = parse.hilo_from_log(samples.get(s["id"]) or [], day)
        if hilo:
            parse.apply_hilo(s, hilo)


def build(now_utc=None) -> dict:
    now_utc = now_utc or _now()
    stations = [parse.station_record(st, _obs_for(st)) for st in parse.STATIONS]
    _fill_hilo_from_log(stations, local_today(now_utc))
    return dict(origin=dict(lat=parse.RWC_LAT, lon=parse.RWC_LON, elev_m=parse.RWC_ELEV_M),
                stations=stations)


def get_nearby():
    resp = jsonify(result=build())
    resp.headers["Cache-Control"] = "public, max-age=120"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

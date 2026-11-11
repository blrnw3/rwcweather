"""GET /api/nearby: current temperature and today's rain at nearby stations, each fetched and cached on its own."""
from flask import jsonify

from rwcwx.nearby import fetch, parse


def _obs_for(st: dict):
    if st["kind"] == "official":
        return parse.official(fetch.nws_latest(st["nws_id"]),
                              fetch.iem_current(st["iem_id"], st["iem_network"]))
    if st["kind"] == "weatherlink":
        return parse.weatherlink(fetch.weatherlink(st["wl_id"]))
    return None


def build() -> dict:
    stations = [parse.station_record(st, _obs_for(st)) for st in parse.STATIONS]
    return dict(origin=dict(lat=parse.RWC_LAT, lon=parse.RWC_LON, elev_m=parse.RWC_ELEV_M),
                stations=stations)


def get_nearby():
    resp = jsonify(result=build())
    resp.headers["Cache-Control"] = "public, max-age=120"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

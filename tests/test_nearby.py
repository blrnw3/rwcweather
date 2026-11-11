"""Weather nearby card: official (NWS + IEM) and WeatherLink shaping, caching (#98-style),
and /api/nearby with the network mocked. No network, no DB."""
import json
import os
from datetime import datetime, timezone

import pytest
from flask import Flask

from rwcwx.nearby import api as nb_api
from rwcwx.nearby import fetch, parse

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "nearby")


def load(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


NWS_SFO = load("nws_ksfo_latest.json")["properties"]
NWS_PUG = load("nws_pugc1_latest.json")["properties"]
IEM_SFO = load("iem_sfo_current.json")["last_ob"]
IEM_PUG = load("iem_pugc1_current.json")["last_ob"]
WL_TUM = load("wl_tum_suden.json")
WL_WO = load("wl_white_oaks.json")
WL_JR = load("wl_jasper_ridge.json")


# ---------------------------------------------------------------- units / distance

def test_conversions_and_distance():
    assert parse.f_to_c(32) == 0 and parse.f_to_c(None) is None
    assert parse.in_to_mm(0.01) == pytest.approx(0.25, abs=0.01)
    assert parse.haversine_km(37.470, -122.265) == 0
    assert parse.haversine_km(37.47500, -122.29810) == pytest.approx(2.97, abs=0.05)
    assert parse.haversine_km(37.61961, -122.36558) == pytest.approx(18.85, abs=0.1)


# ---------------------------------------------------------------- official stations

def test_sfo_prefers_nws_temp_and_iem_today_rain():
    rec = parse.official(NWS_SFO, IEM_SFO)
    assert rec["temp_c"] == pytest.approx(13.0, abs=0.05)          # NWS 13 °C, not IEM 56 °F = 13.33
    assert rec["temp_source"] == "nws"
    assert rec["rain_today_mm"] == 0                               # IEM precip_today 0.00 in
    assert rec["rain_source"] == "iem"
    assert rec["observed_at"].startswith("2026-11-11T15:")


def test_pulgas_nws_temp_iem_rain():
    rec = parse.official(NWS_PUG, IEM_PUG)
    assert rec["temp_c"] == pytest.approx(11.11, abs=0.05)
    assert rec["rain_today_mm"] == 0
    assert rec["temp_source"] == "nws" and rec["rain_source"] == "iem"


def test_official_falls_back_to_iem_when_nws_missing():
    rec = parse.official(None, IEM_SFO)
    assert rec["temp_c"] == pytest.approx(13.33, abs=0.05)
    assert rec["temp_source"] == "iem" and rec["rain_today_mm"] == 0
    assert rec["observed_at"] == "2026-11-11T15:56:00Z"


def test_official_uses_nws_precip_only_when_iem_has_none():
    nws = dict(NWS_SFO)
    nws["precipitationLast24Hours"] = {"unitCode": "wmoUnit:mm", "value": 1.2}
    rec = parse.official(nws, {"airtemp[F]": 56, "utc_valid": "2026-11-11T15:56:00Z"})
    assert rec["rain_today_mm"] == pytest.approx(1.2, abs=0.01) and rec["rain_source"] == "nws"


def test_official_both_missing():
    assert parse.official(None, None) is None
    assert parse.official({}, {}) is None


def test_nws_qc_null_precip_is_ignored():
    assert parse.nws_rain_mm(NWS_SFO) is None
    assert parse.nws_rain_mm(NWS_PUG) is None


# ---------------------------------------------------------------- WeatherLink

def test_weatherlink_tum_suden():
    rec = parse.weatherlink(WL_TUM)
    assert rec["temp_c"] == pytest.approx(16.67, abs=0.05)         # 62 °F
    assert rec["rain_today_mm"] == 0
    assert rec["observed_at"] is not None


def test_weatherlink_jasper_has_trace_rain():
    rec = parse.weatherlink(WL_JR)
    assert rec["temp_c"] == pytest.approx(12.22, abs=0.05)         # 54 °F
    assert rec["rain_today_mm"] == pytest.approx(0.254, abs=0.001)  # 0.01 in


def test_weatherlink_white_oaks():
    rec = parse.weatherlink(WL_WO)
    assert rec["temp_c"] == pytest.approx(12.78, abs=0.05)         # 55 °F
    assert rec["rain_today_mm"] == 0


def test_weatherlink_missing_and_dashes():
    assert parse.weatherlink(None) is None
    rec = parse.weatherlink({"sStation": "x", "temperature": "--", "dailyRain": "", "lastTimestamp": 0})
    assert rec is None or (rec["temp_c"] is None and rec["rain_today_mm"] is None)


def test_weatherlink_celsius_unit_is_not_converted():
    rec = parse.weatherlink({"sStation": "x", "temperature": "12.3", "temperatureUnit": "&deg;C",
                             "dailyRain": "0", "lastTimestamp": 1794414267})
    assert rec["temp_c"] == pytest.approx(12.3, abs=0.01)


# ---------------------------------------------------------------- cache (#98: success is kept for the full TTL)

def test_cache_ttl_backoff_and_stale():
    fetch.clear()
    t = [1000.0]
    calls = []

    def ok():
        calls.append("ok")
        return {"v": len(calls)}

    def boom():
        calls.append("boom")
        raise IOError("nope")

    now = lambda: t[0]
    assert fetch._safe("x", 600, ok, now) == {"v": 1}
    t[0] += 599
    assert fetch._safe("x", 600, boom, now) == {"v": 1} and calls == ["ok"]
    t[0] += 2
    assert fetch._safe("x", 600, boom, now) == {"v": 1}                # failed: last good
    t[0] += 60
    assert fetch._safe("x", 600, boom, now) == {"v": 1} and calls == ["ok", "boom"]
    t[0] = 1000 + fetch.STALE_MAX + 1
    assert fetch._safe("x", 600, boom, now) is None
    fetch.clear()
    assert fetch._safe("y", 600, boom, now) is None


def test_success_is_not_dropped_after_stale_max():
    fetch.clear()
    t = [1000.0]
    now = lambda: t[0]
    calls = []

    def ok():
        calls.append(1)
        return {"grid": "MTR"}

    assert fetch._safe("p", 24 * 3600, ok, now) == {"grid": "MTR"}
    t[0] += fetch.STALE_MAX + 60
    assert fetch._safe("p", 24 * 3600, ok, now) == {"grid": "MTR"} and calls == [1]
    fetch.clear()


def test_fetch_failure_is_logged_without_response_text(monkeypatch, caplog):
    fetch.clear()

    def fail(url, accept="application/json"):
        raise RuntimeError("secret-ish body text")
    monkeypatch.setattr(fetch, "get_json", fail)
    assert fetch.nws_latest("KSFO") is None
    assert fetch.iem_current("SFO", "CA_ASOS") is None
    assert fetch.weatherlink("abc") is None
    assert "secret-ish" not in caplog.text
    fetch.clear()


# ---------------------------------------------------------------- endpoint

def _client(monkeypatch, nws_sfo=NWS_SFO, nws_pug=NWS_PUG, iem_sfo=IEM_SFO, iem_pug=IEM_PUG,
            wl=None):
    wl = wl or {"tum_suden": WL_TUM, "white_oaks": WL_WO, "jasper_ridge": WL_JR}

    def nws(sid):
        return {"KSFO": nws_sfo, "PUGC1": nws_pug}.get(sid)

    def iem(sid, net):
        return {"SFO": iem_sfo, "PUGC1": iem_pug}.get(sid)

    def wlink(sid):
        for st in parse.STATIONS:
            if st.get("wl_id") == sid:
                return wl.get(st["id"])
        return None

    monkeypatch.setattr(fetch, "nws_latest", nws)
    monkeypatch.setattr(fetch, "iem_current", iem)
    monkeypatch.setattr(fetch, "weatherlink", wlink)
    app = Flask(__name__)
    app.add_url_rule("/api/nearby", view_func=nb_api.get_nearby)
    return app.test_client()


def test_endpoint_ok(monkeypatch):
    r = _client(monkeypatch).get("/api/nearby")
    assert r.status_code == 200 and "max-age=120" in r.headers["Cache-Control"]
    res = r.get_json()["result"]
    ids = [s["id"] for s in res["stations"]]
    assert ids == ["pulgas", "sfo", "tum_suden", "white_oaks", "jasper_ridge"]
    by = {s["id"]: s for s in res["stations"]}
    assert by["sfo"]["available"] and by["sfo"]["temp_c"] == pytest.approx(13.0, abs=0.05)
    assert by["jasper_ridge"]["rain_today_mm"] == pytest.approx(0.254, abs=0.001)
    assert res["origin"]["lat"] == parse.RWC_LAT


def test_endpoint_degrades_per_station(monkeypatch):
    res = _client(monkeypatch, nws_sfo=None, iem_sfo=None,
                  wl={"tum_suden": None, "white_oaks": WL_WO, "jasper_ridge": WL_JR}).get(
        "/api/nearby").get_json()["result"]
    by = {s["id"]: s for s in res["stations"]}
    assert by["sfo"]["available"] is False and by["sfo"]["temp_c"] is None
    assert by["tum_suden"]["available"] is False
    assert by["white_oaks"]["available"] and by["pulgas"]["available"]

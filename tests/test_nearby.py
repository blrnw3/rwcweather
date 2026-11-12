"""Weather nearby card: official (NWS + IEM) and WeatherLink shaping, caching (#98-style),
and /api/nearby with the network mocked. No network, no DB."""
import json
import os
from datetime import date, datetime, timezone

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
WL_JR_HILO = load("wl_jasper_embed_hilo.json")


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
    assert rec["temp_min_c"] == pytest.approx(12.22, abs=0.05)     # IEM min_dayairtemp 54 °F
    assert rec["temp_max_c"] == pytest.approx(14.44, abs=0.05)     # IEM max_dayairtemp 58 °F
    assert rec["hilo_source"] == "iem"
    assert rec["observed_at"].startswith("2026-11-11T15:")


def test_pulgas_nws_temp_iem_rain():
    rec = parse.official(NWS_PUG, IEM_PUG)
    assert rec["temp_c"] == pytest.approx(11.11, abs=0.05)
    assert rec["rain_today_mm"] == 0
    assert rec["temp_source"] == "nws" and rec["rain_source"] == "iem"
    assert rec["temp_min_c"] == pytest.approx(10.56, abs=0.05)     # 51 °F
    assert rec["temp_max_c"] == pytest.approx(15.00, abs=0.05)     # 59 °F
    assert rec["hilo_source"] == "iem"


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



def test_official_hilo_absent_without_iem():
    rec = parse.official(NWS_SFO, None)
    assert rec["temp_c"] == pytest.approx(13.0, abs=0.05)
    assert rec["temp_min_c"] is None and rec["temp_max_c"] is None and rec["hilo_source"] is None
    # Rolling 24 h NWS extremes are present-but-null on the fixture and must not be treated as today's hi/lo.
    nws = dict(NWS_SFO)
    nws["maxTemperatureLast24Hours"] = {"unitCode": "wmoUnit:degC", "value": 20}
    nws["minTemperatureLast24Hours"] = {"unitCode": "wmoUnit:degC", "value": 8}
    rec = parse.official(nws, None)
    assert rec["temp_min_c"] is None and rec["temp_max_c"] is None


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



def test_weatherlink_map_json_has_no_hilo():
    rec = parse.weatherlink(WL_TUM)
    assert rec["temp_min_c"] is None and rec["temp_max_c"] is None and rec["hilo_source"] is None


def test_weatherlink_embed_hilo_jasper():
    h = parse.weatherlink_hilo(WL_JR_HILO)
    assert h["hilo_source"] == "weatherlink"
    assert h["temp_max_c"] == pytest.approx(24.44, abs=0.05)       # 76 °F
    assert h["temp_min_c"] == pytest.approx(6.67, abs=0.05)        # 44 °F
    rec = parse.apply_hilo(parse.weatherlink(WL_JR), h)
    assert rec["temp_c"] == pytest.approx(12.22, abs=0.05)
    assert rec["temp_min_c"] == h["temp_min_c"] and rec["temp_max_c"] == h["temp_max_c"]


def test_weatherlink_hilo_missing():
    assert parse.weatherlink_hilo(None) == dict(temp_min_c=None, temp_max_c=None, hilo_source=None)
    assert parse.weatherlink_hilo({"highLowValues": []})["hilo_source"] is None


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

    def wlembed(token):
        return WL_JR_HILO if token == "f1628dfa80d64cce8825eb59f4020acb" else None

    monkeypatch.setattr(fetch, "nws_latest", nws)
    monkeypatch.setattr(fetch, "iem_current", iem)
    monkeypatch.setattr(fetch, "weatherlink", wlink)
    monkeypatch.setattr(fetch, "weatherlink_embed", wlembed)
    monkeypatch.setattr("rwcwx.nearby.store.samples_on_day", lambda day: {})
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
    assert by["sfo"]["temp_min_c"] == pytest.approx(12.22, abs=0.05) and by["sfo"]["hilo_source"] == "iem"
    assert by["jasper_ridge"]["rain_today_mm"] == pytest.approx(0.254, abs=0.001)
    assert by["jasper_ridge"]["temp_min_c"] == pytest.approx(6.67, abs=0.05)
    assert by["jasper_ridge"]["temp_max_c"] == pytest.approx(24.44, abs=0.05)
    assert by["tum_suden"]["temp_min_c"] is None and by["white_oaks"]["temp_max_c"] is None
    assert res["origin"]["lat"] == parse.RWC_LAT


def test_endpoint_degrades_per_station(monkeypatch):
    res = _client(monkeypatch, nws_sfo=None, iem_sfo=None,
                  wl={"tum_suden": None, "white_oaks": WL_WO, "jasper_ridge": WL_JR}).get(
        "/api/nearby").get_json()["result"]
    by = {s["id"]: s for s in res["stations"]}
    assert by["sfo"]["available"] is False and by["sfo"]["temp_c"] is None
    assert by["tum_suden"]["available"] is False
    assert by["white_oaks"]["available"] and by["pulgas"]["available"]


# ---------------------------------------------------------------- logged daily Lo-Hi

from dateutil.tz import gettz

PT = gettz("America/Los_Angeles")
DAY = date(2026, 11, 11)


def _pt(h, m, day=DAY):
    return datetime(day.year, day.month, day.day, h, m, tzinfo=PT)


def _freeze_now(monkeypatch, day=DAY, hour=14, minute=0):
    """Pin /api/nearby's idea of 'now' so log-fill tests do not depend on the real calendar day."""
    frozen = datetime(day.year, day.month, day.day, hour, minute, tzinfo=PT)
    monkeypatch.setattr(nb_api, "_now", lambda: frozen)


def test_hilo_from_log_needs_early_coverage():
    late = [(_pt(14, 30), 20.0), (_pt(15, 0), 21.0)]
    assert parse.hilo_from_log(late, DAY) is None          # started mid-afternoon
    just_after = [(_pt(6, 1), 10.0), (_pt(14, 0), 20.0)]
    assert parse.hilo_from_log(just_after, DAY) is None    # first sample after 06:00 PT
    on_cutoff = [(_pt(6, 0), 10.0), (_pt(14, 0), 20.0)]
    rec = parse.hilo_from_log(on_cutoff, DAY)
    assert rec["temp_min_c"] == 10.0 and rec["temp_max_c"] == 20.0 and rec["hilo_source"] == "log"
    early = [(_pt(1, 10), 8.5), (_pt(5, 59), 7.2), (_pt(14, 30), 22.0)]
    rec = parse.hilo_from_log(early, DAY)
    assert rec["temp_min_c"] == 7.2 and rec["temp_max_c"] == 22.0


def test_hilo_from_log_ignores_other_days_and_nulls():
    samples = [(_pt(23, 0, date(2026, 11, 10)), 4.0), (_pt(5, 0), 9.0), (None, 99.0)]
    # None timestamp would throw; only valid pairs
    samples = [(_pt(23, 0, date(2026, 11, 10)), 4.0), (_pt(5, 0), 9.0), (_pt(15, 0), None)]
    rec = parse.hilo_from_log(samples, DAY)
    assert rec["temp_min_c"] == 9.0 and rec["temp_max_c"] == 9.0


def test_hilo_from_log_accepts_naive_utc():
    # 05:00 PT = 13:00 UTC on 11 Nov 2026 (PST)
    rec = parse.hilo_from_log([(datetime(2026, 11, 11, 13, 0), 11.0)], DAY)
    assert rec["temp_min_c"] == 11.0


def test_endpoint_fills_missing_hilo_from_log(monkeypatch):
    samples = {"tum_suden": [(_pt(5, 0), 8.0), (_pt(14, 0), 18.0)]}
    client = _client(monkeypatch)
    _freeze_now(monkeypatch)
    monkeypatch.setattr("rwcwx.nearby.store.samples_on_day", lambda day: samples)
    res = client.get("/api/nearby").get_json()["result"]
    by = {s["id"]: s for s in res["stations"]}
    assert by["tum_suden"]["temp_min_c"] == 8.0 and by["tum_suden"]["temp_max_c"] == 18.0
    assert by["tum_suden"]["hilo_source"] == "log"
    # source-provided range is kept (IEM), not replaced by a log value
    assert by["sfo"]["hilo_source"] == "iem"
    assert by["white_oaks"]["temp_min_c"] is None          # no log samples, still a dash


def test_endpoint_omits_log_hilo_when_coverage_is_thin(monkeypatch):
    samples = {"tum_suden": [(_pt(14, 30), 20.0)]}
    client = _client(monkeypatch)
    _freeze_now(monkeypatch)
    monkeypatch.setattr("rwcwx.nearby.store.samples_on_day", lambda day: samples)
    res = client.get("/api/nearby").get_json()["result"]
    by = {s["id"]: s for s in res["stations"]}
    assert by["tum_suden"]["temp_min_c"] is None and by["tum_suden"]["temp_max_c"] is None


def test_logger_collects_and_upserts(monkeypatch):
    from rwcwx.job import nearby_log
    rows_written = []

    def upsert(rows, now_utc=None):
        rows_written.extend(rows)
        return len(rows)

    monkeypatch.setattr(nearby_log.store, "upsert_many", upsert)
    monkeypatch.setattr(nearby_log.store, "prune", lambda now_utc=None: 2)
    c = _client(monkeypatch)  # patches fetch
    out = nearby_log.run(now_utc=datetime(2026, 11, 11, 20, 0))
    assert out["table"] is True and out["pruned"] == 2 and out["logged"] == 5
    ids = {r["station"] for r in rows_written}
    assert ids == {"pulgas", "sfo", "tum_suden", "white_oaks", "jasper_ridge"}
    assert all(r["t_obs"] and r["temp_c"] is not None for r in rows_written)


def test_logger_ok_when_table_missing(monkeypatch):
    from rwcwx.job import nearby_log
    monkeypatch.setattr(nearby_log.store, "upsert_many",
                        lambda *a, **k: (_ for _ in ()).throw(nearby_log.store.TableMissing("no table")))
    # need fetch patches too
    _client(monkeypatch)
    out = nearby_log.run()
    assert out["table"] is False and out["logged"] == 0

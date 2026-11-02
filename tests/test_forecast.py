"""Forecast card backend: NWS shaping (fixtures captured from api.weather.gov on 2026-11-02), caching/back-off,
and the /api/forecast endpoint with the network mocked. No network, no DB."""
import json
import os
from datetime import date, datetime, timezone

import pytest
from flask import Flask

from rwcwx.forecast import api as fc_api
from rwcwx.forecast import nws, parse

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "nws")


def load(name):
    with open(os.path.join(FIX, name)) as f:
        return json.load(f)


FORECAST = load("forecast_mtr_87_91.json")["properties"]
AFD = load("afd_mtr_20261102.json")
ALERTS = load("alerts_test_fixture.json")["features"]


# ---------------------------------------------------------------- forecast periods

def test_periods_today_and_tomorrow_only():
    ps = parse.periods(FORECAST, date(2026, 11, 2))
    assert [p["name"] for p in ps] == ["Today", "Tonight", "Tuesday", "Tuesday Night"]
    assert [p["day"] for p in ps] == [0, 0, 1, 1]
    assert [p["is_daytime"] for p in ps] == [True, False, True, False]
    assert ps[0]["temp_c"] == pytest.approx(19.44, abs=0.01)     # 67 °F
    assert ps[2]["pop"] == 82
    assert (ps[2]["wind_mph_lo"], ps[2]["wind_mph_hi"]) == (3, 12)


def test_periods_use_the_local_date_of_each_period_not_utc():
    # Tonight starts 18:00-08:00 = 02:00Z next day; it still belongs to today.
    ps = parse.periods(FORECAST, date(2026, 11, 3))
    assert [p["name"] for p in ps] == ["Tuesday", "Tuesday Night", "Wednesday", "Wednesday Night"]


def test_periods_missing_or_bad():
    assert parse.periods(None, date(2026, 11, 2)) is None
    assert parse.periods({}, date(2026, 11, 2)) is None
    assert parse.periods({"periods": [{"name": "x"}]}, date(2026, 11, 2)) == []


@pytest.mark.parametrize("text,expect", [("5 to 10 mph", (5, 10)), ("10 mph", (10, 10)), ("Calm", (0, 0)),
                                         ("", (None, None)), (None, (None, None)), ("gusty", (None, None))])
def test_wind_mph(text, expect):
    assert parse.wind_mph(text) == expect


def test_f_to_c():
    assert parse.f_to_c(32) == 0
    assert parse.f_to_c(None) is None


# ---------------------------------------------------------------- AFD

def test_afd_sections_and_key_messages():
    secs = parse.sections(AFD["productText"])
    assert {"KEY MESSAGES", "SHORT TERM", "LONG TERM", "AVIATION"} <= set(secs)
    assert parse.key_messages(secs["KEY MESSAGES"]) == [
        "Hazardous beach conditions through Tuesday evening and again Thursday through Saturday",
        "Seasonal to slightly below seasonal temperatures through Thursday",
        "Light rain for Tuesday except interior Central Coast"]


def test_afd_discussion_shape():
    d = parse.discussion(AFD)
    assert d["office"] == "MTR" and d["issued"] == "2026-11-02T11:25:00+00:00"
    assert d["url"].startswith("https://forecast.weather.gov/product.php?site=MTR")
    assert d["short_term"].startswith("The system that brought precip over the weekend")
    assert "Issued at" not in d["short_term"] and "(Today and tonight)" not in d["short_term"]
    assert len(d["short_term"]) <= parse.EXCERPT_CHARS + 2 and d["short_term"].endswith("…")
    assert any("Bay Area 0.01-0.25" in s for s in d["local"])
    assert len(d["local"]) <= parse.MAX_LOCAL_MENTIONS


def test_afd_missing_or_empty():
    assert parse.discussion(None) is None
    assert parse.discussion({"productText": ""}) is None
    d = parse.discussion({"productText": "no sections here"})
    assert d["key_messages"] == [] and d["short_term"] is None and d["local"] == []


def test_excerpt_keeps_whole_sentences():
    body = "Issued at 1 AM\n(Today)\n\nOne two. Three four five.\n\nSix."
    assert parse.excerpt(body, limit=10) == "One two. …"
    assert parse.excerpt(body) == "One two. Three four five. Six."


# ---------------------------------------------------------------- alerts

def test_alerts_filter_and_sort():
    a = parse.alerts(ALERTS)
    assert [x["event"] for x in a] == ["High Wind Warning", "Wind Advisory"]    # Test message dropped; Severe first
    assert a[0]["ends"] == "2026-11-03T16:00:00-08:00"                         # falls back to expires
    assert a[1]["ends"] == "2026-11-03T16:00:00-08:00" and "Santa Cruz Mountains" in a[1]["description"]
    assert parse.alerts([]) == []
    assert parse.alerts(None) is None


# ---------------------------------------------------------------- cache / back-off

def test_cache_ttl_backoff_and_stale(monkeypatch):
    nws.clear()
    t = [1000.0]
    calls = []

    def ok():
        calls.append("ok")
        return {"v": len(calls)}

    def boom():
        calls.append("boom")
        raise IOError("nope")

    now = lambda: t[0]
    assert nws._safe("x", 600, ok, now) == {"v": 1}
    t[0] += 599
    assert nws._safe("x", 600, boom, now) == {"v": 1} and calls == ["ok"]       # cached
    t[0] += 2
    assert nws._safe("x", 600, boom, now) == {"v": 1}                          # failed: serves last good
    t[0] += 60
    assert nws._safe("x", 600, boom, now) == {"v": 1} and calls == ["ok", "boom"]   # backing off
    t[0] = 1000 + nws.STALE_MAX + 1
    assert nws._safe("x", 600, boom, now) is None                              # too stale
    nws.clear()
    assert nws._safe("y", 600, boom, now) is None


def test_fetch_failure_is_logged_without_response_text(monkeypatch, caplog):
    nws.clear()

    def fail(url, accept="application/geo+json"):
        raise RuntimeError("secret-ish body text")
    monkeypatch.setattr(nws, "get_json", fail)
    assert nws.point() is None and nws.forecast() is None and nws.afd() is None and nws.alerts() is None
    assert "secret-ish" not in caplog.text
    nws.clear()


# ---------------------------------------------------------------- endpoint

def _client(monkeypatch, fc=FORECAST, afd=AFD, alerts=ALERTS):
    monkeypatch.setattr(nws, "forecast", lambda: fc)
    monkeypatch.setattr(nws, "afd", lambda: afd)
    monkeypatch.setattr(nws, "alerts", lambda: alerts)
    # 17:30 UTC = 09:30 PST on Mon Nov 2
    monkeypatch.setattr(fc_api, "_now", lambda: datetime(2026, 11, 2, 17, 30, tzinfo=timezone.utc))
    app = Flask(__name__)
    app.add_url_rule("/api/forecast", view_func=fc_api.get_forecast)
    return app.test_client()


def test_endpoint_ok(monkeypatch):
    r = _client(monkeypatch).get("/api/forecast")
    assert r.status_code == 200 and "max-age=300" in r.headers["Cache-Control"]
    res = r.get_json()["result"]
    assert res["today"] == "2026-11-02"
    assert len(res["periods"]) == 4 and len(res["alerts"]) == 2
    assert res["discussion"]["key_messages"]


def test_endpoint_local_date_late_evening(monkeypatch):
    c = _client(monkeypatch)
    # 07:30 UTC Nov 3 is still 23:30 PST Nov 2
    monkeypatch.setattr(fc_api, "_now", lambda: datetime(2026, 11, 3, 7, 30, tzinfo=timezone.utc))
    assert c.get("/api/forecast").get_json()["result"]["today"] == "2026-11-02"


def test_endpoint_degrades_when_nws_down(monkeypatch):
    res = _client(monkeypatch, fc=None, afd=None, alerts=None).get("/api/forecast").get_json()["result"]
    assert res["periods"] is None and res["discussion"] is None and res["alerts"] is None

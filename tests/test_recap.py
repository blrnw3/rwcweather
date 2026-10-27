"""Recap: markdown subset (incl. XSS), payload validation, staleness in PT, endpoints (store mocked), DB upsert."""
import os
import re
from datetime import date, datetime

import pytest
from flask import Flask

from rwcwx.recap import api as recap_api
from rwcwx.recap import markdown, rules, store

EXAMPLE = ("**Mild, dry and fairly sunny, a touch cool for late October.** High 20.4°C (about 2.6°C below normal), "
           "low 11.3°C, mean 14.9°C.\n- 2nd-warmest Oct 26 in the station's six years.\n"
           "- No rain; October is at 0.17 in vs a 1.02 in normal.\n- 7.9 h of webcam sunshine.")
NOW = datetime(2026, 10, 27, 15, 30)          # 08:30 PDT on Tue Oct 27


# ---------------------------------------------------------------- markdown

def test_example_renders_headline_and_bullets():
    blocks = markdown.parse(EXAMPLE)
    assert [b["t"] for b in blocks] == ["p", "ul"]
    assert blocks[0]["c"][0] == {"t": "b", "c": [{"t": "text", "v": "Mild, dry and fairly sunny, a touch cool for "
                                                                    "late October."}]}
    assert len(blocks[1]["items"]) == 3
    assert markdown.render(EXAMPLE).startswith("<p><strong>Mild, dry")


def test_paragraphs_lists_and_links():
    md = "Line one\nline two\n\n1. first\n2) second\n   continued\n\nSee [the report](https://rwcweather.com/x?a=1&b=2)."
    assert markdown.render(md) == (
        "<p>Line one line two</p>\n<ol><li>first</li><li>second continued</li></ol>\n"
        '<p>See <a href="https://rwcweather.com/x?a=1&amp;b=2" rel="noopener nofollow">the report</a>.</p>')


def test_bold_may_contain_a_link_but_not_nest():
    assert markdown.render("**a [b](http://x.org/) c**") == \
        '<p><strong>a <a href="http://x.org/" rel="noopener nofollow">b</a> c</strong></p>'
    assert markdown.render("** not bold **") == "<p>** not bold **</p>"


ALLOWED_TAG = re.compile(r'^</?(p|ul|ol|li|strong)>$|^<a href="https?://[^"<>]+" rel="noopener nofollow">$|^</a>$')

XSS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "<svg/onload=alert(1)>",
    "<a href=\"javascript:alert(1)\">x</a>",
    "[x](javascript:alert(1))",
    "[x](javascript:alert`1`)",
    "[x](JaVaScRiPt:alert)",
    "[x](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)",
    "[x](vbscript:msgbox)",
    "[x](//evil.example/)",
    "[x](https://user:pw@evil.example/)",
    "[x](https://a.example/\"onmouseover=\"alert(1))",
    "[x](https://a.example/'onmouseover='alert)",
    "[x](https://a.example/<script>)",
    "[<img src=x onerror=alert(1)>](https://a.example/)",
    "[x](https://a.example/)<script>alert(1)</script>",
    "**<b onclick=alert(1)>bold</b>**",
    "![img](https://a.example/p.png)",
    "&lt;script&gt;alert(1)&lt;/script&gt;",
    "<iframe src=https://a.example></iframe>",
    "```\n<script>x</script>\n```",
    "- <style>body{display:none}</style>",
    "\"><script>alert(1)</script>",
]


@pytest.mark.parametrize("md", XSS)
def test_xss_is_escaped(md):
    out = markdown.render(md)
    for tag in re.findall(r"<[^>]*>", out):
        assert ALLOWED_TAG.match(tag), (md, tag, out)
    assert "javascript:" not in out.lower() or "href=\"javascript" not in out.lower()
    for href in re.findall(r'href="([^"]*)"', out):
        assert href.startswith(("http://", "https://")) and "@" not in href
    # Nothing in the parsed blocks can carry anything but text, bold or a vetted link either.
    def walk(nodes):
        for n in nodes:
            assert n["t"] in ("text", "b", "a")
            if n["t"] == "a":
                assert markdown.safe_url(n["href"]) == n["href"]
            if n["t"] == "b":
                walk(n["c"])
    for b in markdown.parse(md):
        for nodes in ([b["c"]] if b["t"] == "p" else b["items"]):
            walk(nodes)


def test_entities_are_double_escaped_not_decoded():
    assert markdown.render("&lt;b&gt; & <b>") == "<p>&amp;lt;b&amp;gt; &amp; &lt;b&gt;</p>"


def test_unsafe_link_stays_literal_text():
    assert markdown.parse("[x](javascript:alert(1))")[0]["c"] == [{"t": "text", "v": "[x](javascript:alert(1))"}]
    assert markdown.parse("[x](ftp://a.example/f)")[0]["c"] == [{"t": "text", "v": "[x](ftp://a.example/f)"}]


@pytest.mark.parametrize("url,ok", [
    ("https://rwcweather.com/reports/day?date=2026-10-26", True), ("http://a.example", True),
    ("HTTPS://A.EXAMPLE/x", True), ("javascript:alert(1)", False), ("mailto:a@b.c", False), ("/relative", False),
    ("//a.example", False), ("https://", False), ("https://u@a.example", False), ("https://a.example/ x", False),
    ("https://a.example/\u0000", False), ("https://a.example/" + "x" * 600, False),
])
def test_safe_url(url, ok):
    assert (markdown.safe_url(url) is not None) == ok


# ---------------------------------------------------------------- validation

def body(**kw):
    return dict(dict(kind="day", period="2026-10-26", body_md=EXAMPLE, generated_at="2026-10-27T15:20:00Z"), **kw)


def test_validate_normalises():
    out = rules.validate(body(generated_at="2026-10-27T08:20:00.123-07:00", body_md="  a\r\nb\t c  \n\n\n\nd ",
                              extra=1), NOW)
    assert out["record"] == dict(kind="day", period="2026-10-26", body_md="a\nb  c\n\nd",
                                 generated_at=datetime(2026, 10, 27, 15, 20))
    assert out["ignored"] == ["extra"]
    assert rules.validate(body(kind="month_to_date", period="2026-10"), NOW)["record"]["period"] == "2026-10"
    assert rules.validate(body(kind="month", period="2026-09"), NOW)["record"]["period"] == "2026-09"


@pytest.mark.parametrize("bad", [
    None, [], "x",
    body(kind="week"), body(kind=None),
    body(period="2026-10"), body(period="2026-10-26T00:00"), body(period="2026-02-30"), body(period=20261026),
    body(period="2026-10-28"),                                   # after today (PT)
    body(period="2019-05-01"),                                   # before the station
    body(kind="month", period="2026-10-26"), body(kind="month", period="2026-13"),
    body(kind="month", period="2026-10"),                        # this month is not finished
    body(kind="month_to_date", period="2026-11"),
    body(body_md=""), body(body_md="   \n "), body(body_md=None), body(body_md="x" * 1501),
    body(body_md="\n".join("- l" for _ in range(31))),
    body(body_md="a\u0007b"), body(body_md="abc\u202edcba"),
    body(generated_at="2026-10-27T15:20:00"),                    # no zone
    body(generated_at="yesterday"), body(generated_at=None),
    body(generated_at="2026-10-27T16:00:00Z"),                   # 30 min in the future
])
def test_validate_rejects(bad):
    with pytest.raises(rules.BadRequest):
        rules.validate(bad, NOW)


def test_validate_uses_the_pt_date_not_utc():
    late_utc = datetime(2026, 11, 1, 5, 0)      # 22:00 PDT Oct 31
    rules.validate(body(period="2026-10-31", generated_at="2026-11-01T04:59:00Z"), late_utc)
    with pytest.raises(rules.BadRequest):
        rules.validate(body(period="2026-11-01", generated_at="2026-11-01T04:59:00Z"), late_utc)
    with pytest.raises(rules.BadRequest):      # October is not finished in PT yet
        rules.validate(body(kind="month", period="2026-10", generated_at="2026-11-01T04:59:00Z"), late_utc)


# ---------------------------------------------------------------- staleness

@pytest.mark.parametrize("kind,period,today,fresh", [
    ("day", "2026-10-26", date(2026, 10, 27), True),
    ("day", "2026-10-25", date(2026, 10, 27), True),           # ~2 days: still shown
    ("day", "2026-10-24", date(2026, 10, 27), False),
    ("day", "2026-10-28", date(2026, 10, 27), False),
    ("month_to_date", "2026-10", date(2026, 10, 27), True),
    ("month_to_date", "2026-10", date(2026, 11, 1), False),
    ("month_to_date", "2026-09", date(2026, 10, 27), False),
    ("month", "2026-09", date(2026, 10, 27), True),
    ("month", "2026-09", date(2026, 11, 1), False),
    ("month", "2025-12", date(2026, 1, 3), True),             # year wrap
    ("month", "2026-08", date(2026, 10, 27), False),
    ("day", "garbage", date(2026, 10, 27), False),
])
def test_is_fresh(kind, period, today, fresh):
    assert rules.is_fresh(kind, period, today) is fresh


def test_local_today_and_expected():
    assert rules.local_today(datetime(2026, 11, 1, 6, 59)) == date(2026, 10, 31)    # 23:59 PDT
    assert rules.local_today(datetime(2026, 11, 1, 7, 0)) == date(2026, 11, 1)
    assert rules.local_today(datetime(2026, 1, 1, 7, 59)) == date(2025, 12, 31)     # 23:59 PST
    assert {k: rules.expected_period(k, date(2026, 1, 1)) for k in rules.KINDS} == \
        dict(day="2025-12-31", month_to_date="2026-01", month="2025-12")


# ---------------------------------------------------------------- endpoints (no DB: store mocked)

@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.add_url_rule("/api/recap", view_func=recap_api.post_recap, methods=["POST"])
    app.add_url_rule("/api/recap/latest", view_func=recap_api.get_latest)
    app.config["TESTING"] = True
    c = app.test_client()
    c.writes, c.rows = [], {}

    def fake_upsert(rec, now_utc=None):
        c.writes.append(rec)
        return "inserted"
    monkeypatch.setattr(store, "upsert", fake_upsert)
    monkeypatch.setattr(store, "latest", lambda: c.rows)
    monkeypatch.setattr(recap_api, "_now", lambda: NOW)
    monkeypatch.setenv("RWC_INGEST_TOKEN", "s3cret")
    return c


AUTH = {"Authorization": "Bearer s3cret"}


def test_post_disabled_without_token(client, monkeypatch):
    monkeypatch.delenv("RWC_INGEST_TOKEN")
    assert client.post("/api/recap", json=body(), headers=AUTH).status_code == 503
    assert not client.writes


@pytest.mark.parametrize("hdr", [None, "Bearer wrong", "bearer s3cret", "s3cret", "Basic s3cret", "Bearer"])
def test_post_rejects_bad_auth(client, hdr):
    r = client.post("/api/recap", json=body(), headers={"Authorization": hdr} if hdr else {})
    assert r.status_code == 401 and not client.writes


def test_post_rejects_bad_auth_even_for_dry_run(client):
    assert client.post("/api/recap?dry_run=1", json=body(), headers={"Authorization": "Bearer x"}).status_code == 401


def test_post_too_large(client):
    r = client.post("/api/recap", data="{" + " " * 20000 + "}", headers=dict(AUTH, **{"Content-Type": "application/json"}))
    assert r.status_code == 413 and not client.writes


def test_post_validation_error(client):
    r = client.post("/api/recap", json=body(kind="month", period="2026-10"), headers=AUTH)
    assert r.status_code == 400 and "finished month" in r.get_json()["error"] and not client.writes
    assert client.post("/api/recap", data="not json", headers=AUTH).status_code == 400


def test_post_upserts(client):
    r = client.post("/api/recap", json=body(), headers=AUTH)
    assert r.status_code == 200, r.get_json()
    j = r.get_json()
    assert j["status"] == "inserted" and j["dry_run"] is False and j["record"]["fresh"] is True
    assert client.writes == [dict(kind="day", period="2026-10-26", body_md=EXAMPLE,
                                  generated_at=datetime(2026, 10, 27, 15, 20))]
    assert j["record"]["generated_at"] == "2026-10-27T15:20:00Z" and j["html"].startswith("<p><strong>Mild")


@pytest.mark.parametrize("q", ["?dry_run=1", "?dry_run=true"])
def test_dry_run_writes_nothing(client, monkeypatch, q):
    monkeypatch.setattr(store, "upsert", lambda *a, **k: pytest.fail("dry run must not write"))
    r = client.post("/api/recap" + q, json=body(body_md="Hi <b>there</b>\n- [x](javascript:1)", note="x"),
                    headers=AUTH)
    j = r.get_json()
    assert r.status_code == 200 and j["status"] == "dry_run" and j["dry_run"] is True
    assert j["record"]["body_md"] == "Hi <b>there</b>\n- [x](javascript:1)" and j["ignored"] == ["note"]
    assert j["html"] == "<p>Hi &lt;b&gt;there&lt;/b&gt;</p>\n<ul><li>[x](javascript:1)</li></ul>"


def test_post_without_table_is_503(client, monkeypatch):
    def missing(*a, **k):
        raise store.TableMissing("recap table does not exist")
    monkeypatch.setattr(store, "upsert", missing)
    assert client.post("/api/recap", json=body(), headers=AUTH).status_code == 503


def test_get_latest(client):
    client.rows = {
        "day": dict(kind="day", period="2026-10-24", body_md="**Old**", generated_at=datetime(2026, 10, 25, 15, 0),
                    t_mod=datetime(2026, 10, 25, 15, 1)),
        "month": dict(kind="month", period="2026-09", body_md="- [link](https://rwcweather.com/) <i>x</i>",
                      generated_at=datetime(2026, 10, 1, 15, 0), t_mod=datetime(2026, 10, 1, 15, 1)),
    }
    r = client.get("/api/recap/latest")
    j = r.get_json()
    assert r.status_code == 200 and "max-age" in r.headers["Cache-Control"]
    res = j["result"]
    assert res["available"] is True and res["month_to_date"] is None
    assert res["day"]["fresh"] is False and res["day"]["period"] == "2026-10-24"          # 3 days old
    assert res["month"]["fresh"] is True and res["month"]["updated_at"] == "2026-10-01T15:01:00Z"
    assert res["month"]["blocks"] == [{"t": "ul", "items": [[
        {"t": "a", "href": "https://rwcweather.com/", "v": "link"}, {"t": "text", "v": " <i>x</i>"}]]}]
    assert res["expected"] == dict(day="2026-10-26", month_to_date="2026-10", month="2026-09")
    assert j["server"]["date"] == [2026, 10, 27]


def test_get_latest_without_table(client, monkeypatch):
    monkeypatch.setattr(store, "latest", lambda: None)
    res = client.get("/api/recap/latest").get_json()["result"]
    assert res["available"] is False and res["day"] is None


# ---------------------------------------------------------------- DB (dev MySQL)

needs_db = pytest.mark.skipif(bool(os.environ.get("RWC_TEST_NO_DB")), reason="needs MySQL")


@needs_db
def test_store_upsert_and_latest():
    from sqlalchemy import text
    from rwcwx.models import db
    ddl = open(os.path.join(os.path.dirname(__file__), "..", "data", "migrations", "20261027_recap.sql")).read()
    db.execute(text(ddl[ddl.index("CREATE TABLE"):]))
    keys = dict(kind="day", period="2020-11-02")
    db.execute(text("DELETE FROM recap WHERE period IN ('2020-11-01', '2020-11-02')"))
    try:
        rec = dict(keys, body_md="**Warm** 20.4°C — “quotes”", generated_at=datetime(2020, 11, 3, 15, 20))
        assert store.upsert(rec, NOW) == "inserted"
        assert store.upsert(rec, NOW) == "unchanged"
        assert store.upsert(dict(rec, body_md="Edited"), NOW) == "updated"
        store.upsert(dict(rec, period="2020-11-01", body_md="older"), NOW)
        newer = db.execute(text("SELECT 1 FROM recap WHERE kind = 'day' AND period > '2020-11-02'")).fetchone()
        if newer is None:                        # dev DB has no later day rows: latest() must pick 2020-11-02
            got = store.latest()["day"]
            assert got["period"] == "2020-11-02" and got["body_md"] == "Edited"
        assert store.upsert(rec, NOW) == "updated"
        row = db.execute(text("SELECT body_md, generated_at FROM recap WHERE kind = 'day' AND period = '2020-11-02'"
                              )).fetchone()
        assert row[0] == "**Warm** 20.4°C — “quotes”" and row[1] == datetime(2020, 11, 3, 15, 20)
    finally:
        db.execute(text("DELETE FROM recap WHERE period IN ('2020-11-01', '2020-11-02')"))

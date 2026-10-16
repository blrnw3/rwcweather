"""Fog: decision + rain veto, rollup, frame window, and POST /api/inferred/fog auth/validation (store mocked)."""
from datetime import date, datetime, timedelta

import pytest

from rwcwx.fog import rules


T = datetime(2026, 1, 5, 17, 0)   # 09:00 PST


def tips_at(*mins, amount=0.01):
    return [(T + timedelta(minutes=m), amount) for m in mins]


def test_tips_near_counts_0_01_tips_in_window():
    assert rules.tips_near(T, tips_at(-30, 0, 30)) == 3
    assert rules.tips_near(T, tips_at(-31, 31)) == 0
    assert rules.tips_near(T, [(T, 0.03)]) == 3          # one reading carrying 3 tips


@pytest.mark.parametrize("fog,conf,flags,tips,value,out_flags", [
    (True, 0.85, None, 0, 1, None),                      # threshold is inclusive
    (True, 0.849, None, 0, 0, None),
    (False, 0.99, None, 0, 0, None),
    (True, 0.97, None, 1, 1, None),                      # a lone drizzle tip does not veto
    (True, 0.97, None, 2, 0, "rain_veto"),               # >= 2 tips within +/-30 min force no
    (False, 0.6, None, 5, 0, "rain_veto"),
    (True, 0.97, "ir", 0, None, "ir"),                   # gated frames are not judged
    (None, None, "glitch", 3, None, "glitch"),
    (None, None, None, 0, None, None),                   # judge error / no answer
    (True, 0.9, "rain_veto", 0, 1, None),                # a client-sent veto flag is recomputed, not trusted
])
def test_decide(fog, conf, flags, tips, value, out_flags):
    d = rules.decide(fog, conf, flags, tips)
    assert (d.value, d.flags) == (value, out_flags)


def test_e2_09_style_rainy_murk_is_vetoed():
    # eval2 e2_09: judge yes @0.55 with 0.62 in in the hour; would be vetoed even if the judge were confident.
    tips = [(T + timedelta(minutes=m), 0.01) for m in range(-30, 31)]
    assert rules.decide(True, 0.95, None, rules.tips_near(T, tips)).value == 0


def test_rollup_hours_and_coverage():
    fd = rules.rollup(date(2026, 1, 5), [1, 1, 1, 0, 0, None, 0, 0, 0, 0], expected=10)
    assert (fd.fog_h, fd.judged, fd.storable) == (1.5, 9, True)
    assert rules.rollup(date(2026, 1, 5), [1, 0, 0], expected=10).storable is False     # 30% coverage


def test_fog_days_derived_from_hours():
    from types import SimpleNamespace as NS
    from rwcwx.fog.derive import fog_day_values, fog_days
    rows = [NS(d=date(2026, 1, 5), val=0.5, cnt=10, comment=None), NS(d=date(2026, 1, 6), val=0.0, cnt=10, comment=None)]
    assert [x.val for x in fog_days(rows)] == [1, 0]
    assert fog_day_values([(date(2026, 1, 5), 2.0), (date(2026, 1, 6), 0)]) == [(date(2026, 1, 5), 1), (date(2026, 1, 6), 0)]


def test_window_frames_dawn_to_1pm_local_in_both_seasons():
    for d, first_local, n in [(date(2026, 1, 5), "08:00", 10), (date(2026, 6, 21), "06:30", 13)]:
        fr = rules.window_frames(d)
        assert len(fr) == n
        from dateutil import tz
        loc = [t.replace(tzinfo=tz.UTC).astimezone(tz.gettz("America/Los_Angeles")) for t in fr]
        assert loc[0].strftime("%H:%M") == first_local and loc[-1].strftime("%H:%M") == "12:30"
        assert all(t.minute in (0, 30) for t in fr)


def test_window_frames_dst_change_days():
    for d in (date(2026, 3, 8), date(2026, 11, 1)):
        fr = rules.window_frames(d)
        assert fr and all((b - a) == timedelta(minutes=30) for a, b in zip(fr, fr[1:]))


# ---- HTTP endpoint ----

@pytest.fixture
def client(monkeypatch):
    from rwcwx.main import app
    from rwcwx.fog import api, store
    calls = []

    def fake_ingest(rows, mv, source="live", now_utc=None):
        calls.append((rows, mv, source))
        return dict(rows=[dict(t=r["t"], status="inserted", value=1, flags=None, tips=0) for r in rows],
                    days=[dict(d="2026-01-05")])
    monkeypatch.setattr(store, "ingest", fake_ingest)
    app.config["TESTING"] = True
    c = app.test_client()
    c.calls = calls
    return c


BODY = dict(model_version="llmj2-test-abcd1234", rows=[dict(t="2026-01-05T17:00:00Z", fog=True, confidence=0.9,
                                                            reason="Dense fog")])


def test_endpoint_disabled_without_token(client, monkeypatch):
    monkeypatch.delenv("RWC_INGEST_TOKEN", raising=False)
    r = client.post("/api/inferred/fog", json=BODY, headers={"Authorization": "Bearer anything"})
    assert r.status_code == 503 and not client.calls
    monkeypatch.setenv("RWC_INGEST_TOKEN", "")
    assert client.post("/api/inferred/fog", json=BODY, headers={"Authorization": "Bearer "}).status_code == 503


@pytest.mark.parametrize("hdr", [None, "Bearer wrong", "bearer s3cret", "s3cret", "Basic s3cret"])
def test_endpoint_rejects_bad_auth(client, monkeypatch, hdr):
    monkeypatch.setenv("RWC_INGEST_TOKEN", "s3cret")
    r = client.post("/api/inferred/fog", json=BODY, headers={"Authorization": hdr} if hdr else {})
    assert r.status_code == 401 and not client.calls


def test_endpoint_accepts_and_normalises(client, monkeypatch):
    monkeypatch.setenv("RWC_INGEST_TOKEN", "s3cret")
    body = dict(BODY, rows=[dict(t="2026-01-05T09:30:00-08:00", fog=False, confidence=0.95), BODY["rows"][0]])
    r = client.post("/api/inferred/fog", json=body, headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 200, r.get_json()
    rows, mv, source = client.calls[0]
    assert [x["t"] for x in rows] == [datetime(2026, 1, 5, 17, 0), datetime(2026, 1, 5, 17, 30)]
    assert (mv, source) == ("llmj2-test-abcd1234", "live")
    assert r.get_json()["counts"] == {"inserted": 2}


@pytest.mark.parametrize("bad", [
    dict(BODY, model_version=""),
    dict(BODY, source="manual"),                                   # clients can never write manual rows
    dict(BODY, rows=[]),
    dict(BODY, rows=[dict(t="2026-01-05T17:00:00", fog=True)]),    # no zone
    dict(BODY, rows=[dict(t="2026-01-05T17:10:00Z", fog=True)]),   # off the 30-min grid
    dict(BODY, rows=[dict(t="2099-01-05T17:00:00Z", fog=True)]),   # future
    dict(BODY, rows=[dict(t="2026-01-05T17:00:00Z", fog="yes")]),
    dict(BODY, rows=[dict(t="2026-01-05T17:00:00Z", fog=True, confidence=1.5)]),
    dict(BODY, rows=[BODY["rows"][0], BODY["rows"][0]]),           # duplicate t
    dict(BODY, rows=[dict(t="2026-01-05T17:00:00Z")] * 501),
])
def test_endpoint_validation(client, monkeypatch, bad):
    monkeypatch.setenv("RWC_INGEST_TOKEN", "s3cret")
    r = client.post("/api/inferred/fog", json=bad, headers={"Authorization": "Bearer s3cret"})
    assert r.status_code == 400 and not client.calls

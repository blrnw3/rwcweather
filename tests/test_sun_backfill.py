"""Backfill from the 30-minute archive: no DB or frames needed (fake classifier and archive index)."""
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.job import sun_backfill as bf  # noqa: E402
from rwcwx.job.sun_classify import sun_times_utc  # noqa: E402


class FakeClf:
    version = "fake"

    def __init__(self, sunny_until=None, frozen_after=None):
        self.sunny_until, self.frozen_after = sunny_until, frozen_after

    def frame(self, path, t):
        sunny = self.sunny_until is None or t < self.sunny_until
        md5 = "same" if self.frozen_after and t >= self.frozen_after else path
        return dict(p=0.95 if sunny else 0.05, ps=0.9 if sunny else 0.1, smean=0.5, pink=0.0, el=30, md5=md5)


def _index(day, step=30):
    sr, ss = sun_times_utc(day)
    t = (sr - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    idx = {}
    while t <= ss + timedelta(hours=1):
        idx.setdefault(t.date(), {})[t] = f"/x/{t:%Y%m%d_%H%M}.jpg"
        t += timedelta(minutes=step)
    return idx


def test_clear_day_is_full_daylight():
    d = date(2022, 7, 1)
    res = bf.classify_backfill_day(d, FakeClf(), _index(d))
    sr, ss = sun_times_utc(d)
    assert abs(res["total"]["val"] - (ss - sr).total_seconds() / 3600) < 0.3
    assert res["total"]["comment"].startswith("estimated from 30-min snapshots")
    assert all(r["minutes"] == 30 and r["t"].minute in (15, 45) for r in res["rows"])   # period starts


def test_half_day_and_frozen_frames():
    d = date(2023, 1, 10)
    sr, ss = sun_times_utc(d)
    noon = sr + (ss - sr) / 2
    res = bf.classify_backfill_day(d, FakeClf(sunny_until=noon), _index(d))
    assert abs(res["total"]["val"] - (ss - sr).total_seconds() / 7200) < 0.6
    # frozen camera from noon: those snapshots are 'stale', coverage ~50% -> scaled or dropped
    res = bf.classify_backfill_day(d, FakeClf(frozen_after=noon), _index(d))
    assert any("stale" in (r["flags"] or "") for r in res["rows"])
    assert res["summary"]["coverage"] < 0.6


def test_per_minute_frames_are_thinned_to_the_archive_cadence():
    d = date(2022, 7, 1)
    res = bf.classify_backfill_day(d, FakeClf(), _index(d, step=1))
    assert all(r["t"].minute in (15, 45) for r in res["rows"])


# ---- live days (local dates in Python, no MySQL CONVERT_TZ) ----

def test_local_days_are_pacific_dates_with_dst():
    u = datetime
    assert bf.local_days([u(2026, 10, 11, 14, 14)]) == {date(2026, 10, 11)}            # first live row, 07:14 PDT
    assert bf.local_days([u(2026, 10, 11, 6, 59)]) == {date(2026, 10, 10)}             # 23:59 PDT
    assert bf.local_days([u(2026, 10, 11, 7, 0)]) == {date(2026, 10, 11)}              # 00:00 PDT
    assert bf.local_days([u(2026, 1, 10, 7, 59), u(2026, 1, 10, 8, 0)]) == {date(2026, 1, 9), date(2026, 1, 10)}
    assert bf.local_days([u(2026, 11, 1, 8, 30), u(2026, 11, 1, 9, 30)]) == {date(2026, 11, 1)}   # DST ends
    assert bf.local_days([None]) == set()


class _FakeConn:
    def __init__(self, rows, seen):
        self.rows, self.seen = rows, seen

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q, **kw):
        self.seen.append(str(q))
        return iter(self.rows)


class _FakeEngine:
    def __init__(self, rows):
        self.rows, self.seen = rows, []

    def connect(self):
        return _FakeConn(self.rows, self.seen)


def test_live_days_has_no_day_before_fallback():
    # (UTC date, UTC hour) buckets of the first live rows: 2026-10-11 14:00 UTC onwards, then into 10-12 UTC
    rows = [(date(2026, 10, 11), h) for h in range(14, 24)] + [(date(2026, 10, 12), h) for h in range(0, 24)]
    eng = _FakeEngine(rows)
    days = bf.live_days(eng)
    assert days == {date(2026, 10, 11), date(2026, 10, 12)}
    assert date(2026, 10, 10) not in days                    # was skipped by the old fallback
    assert "CONVERT_TZ" not in eng.seen[0]
    assert bf.live_days(_FakeEngine([])) == set()


# ---- which existing sun totals a backfill total may replace ----

def _keeps(overridden, comment):
    import sqlite3
    c = sqlite3.connect(":memory:")
    return bool(c.execute(f"SELECT {bf.KEEP_TOTAL} FROM (SELECT ? AS overridden, ? AS comment)",
                          (overridden, comment)).fetchone()[0])


def test_backfill_total_replaces_estimates_but_not_webcam_or_overridden():
    assert not _keeps(0, "estimated from 30-min snapshots; coverage 80.0%")
    assert not _keeps(0, "API estimate (api:hrrr+asos; calibrated vs webcam, CV MAE 1.2 h); no webcam total")
    assert not _keeps(0, "API estimate (api:hrrr+asos; calibrated vs webcam, CV MAE 1.2 h); webcam coverage 30.0%")
    assert _keeps(0, "webcam; coverage 100.0%")
    assert _keeps(1, "API estimate (api:hrrr); no webcam total")
    assert _keeps(1, "estimated from 30-min snapshots; coverage 80.0%")


def _mysql_engine():
    url = os.environ.get("MYSQL_URL")
    if not url or os.environ.get("RWC_TEST_NO_DB"):
        return None
    try:
        from sqlalchemy import create_engine
        eng = create_engine(f"mysql://{url}")
        eng.connect().close()
        return eng
    except Exception:
        return None


def test_upsert_total_on_mysql():
    """The real UPSERT_TOTAL against a temporary copy of avg_extreme (dev DB; skipped without one)."""
    import pytest
    from sqlalchemy import text
    eng = _mysql_engine()
    if eng is None:
        pytest.skip("needs MySQL (MYSQL_URL)")
    sql = bf.UPSERT_TOTAL.replace("INTO avg_extreme", "INTO ae_bf_test")
    api = "API estimate (api:hrrr+asos; calibrated vs webcam, CV MAE 1.2 h); no webcam total"
    seed = [("2000-01-01", 10.35, 0, api),
            ("2000-01-02", 7.0, 0, "estimated from 30-min snapshots; coverage 60.0%"),
            ("2000-01-03", 11.41, 0, "webcam; coverage 100.0%"),
            ("2000-01-04", 5.0, 1, "API estimate (api:hrrr); no webcam total")]
    with eng.connect() as c:
        c.execute(text("CREATE TEMPORARY TABLE ae_bf_test LIKE avg_extreme"))
        for d, v, o, cm in seed:
            c.execute(text("INSERT INTO ae_bf_test (d, var, type, period, val, cnt, t_mod, overridden, comment) "
                           "VALUES (:d, 'sun', 'total', 'day', :v, 1, '2026-10-13', :o, :c)"), d=d, v=v, o=o, c=cm)
        new = "estimated from 30-min snapshots; coverage 100.0%"
        for d, _, _, _ in seed + [("2000-01-05", None, None, None)]:
            c.execute(text(sql), d=d, val=11.45, cnt=25, comment=new, t_mod=datetime(2026, 10, 21))
        got = {str(r[0]): (r[1], r[2]) for r in c.execute(text("SELECT d, val, comment FROM ae_bf_test ORDER BY d"))}
        c.execute(text("DROP TEMPORARY TABLE ae_bf_test"))
    assert got["2000-01-01"] == (11.45, new)        # API estimate replaced
    assert got["2000-01-02"] == (11.45, new)        # earlier backfill replaced
    assert got["2000-01-03"][1].startswith("webcam") and got["2000-01-03"][0] == 11.41
    assert got["2000-01-04"][0] == 5.0              # overridden kept
    assert got["2000-01-05"] == (11.45, new)        # new row

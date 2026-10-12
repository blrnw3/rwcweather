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

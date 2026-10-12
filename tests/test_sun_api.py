"""Sunshine read side + API. Uses the dev DB in MYSQL_URL (needs obs_inferred); skipped if unreachable."""
import os
import sys
import unittest
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx.calc.rolling import rolling_ranking  # noqa: E402

try:
    from rwcwx.model import sun  # noqa: E402  (imports rwcwx.models, which reflects tables from the DB)
    from rwcwx.main import app  # noqa: E402
    DB_OK = True
except Exception:  # pragma: no cover
    DB_OK = False


class SunRollingTest(unittest.TestCase):
    def test_sun_excludes_partial_today(self):
        start = date(2026, 10, 1)
        daily = [(start + timedelta(days=i), v) for i, v in enumerate([11, 11, 11, 11, 0.5])]
        res = rolling_ranking(daily, "sun", "total", 3, order="lowest", limit=3, today=date(2026, 10, 5))
        self.assertTrue(all(r["end"] <= (2026, 10, 4) for r in res))


@unittest.skipUnless(DB_OK, "dev DB not reachable")
class SunModelTest(unittest.TestCase):
    T0 = datetime(2026, 10, 12, 15, 0)

    def rows(self, vals):
        return [dict(t=self.T0 + timedelta(minutes=i), value=v, minutes=1, flags=None if v is not None else "missing")
                for i, v in enumerate(vals)]

    def test_spells(self):
        sp = sun.spells(self.rows([1, 1, 0, None, None, 1]))
        self.assertEqual([(s["state"], s["minutes"]) for s in sp], [("sun", 2), ("nosun", 1), ("unknown", 2), ("sun", 1)])
        self.assertEqual(sp[0]["end"], sp[1]["start"])

    def test_now_state(self):
        now = self.T0 + timedelta(minutes=5)
        self.assertEqual(sun.now_state(dict(t=self.T0, value=1, flags="lowsun"), now)["state"], "sun")
        self.assertIsNone(sun.now_state(dict(t=self.T0, value=1, flags=None), now + timedelta(minutes=30)))
        self.assertIsNone(sun.now_state(dict(t=self.T0, value=None, flags="missing"), now))
        self.assertIsNone(sun.now_state(dict(t=self.T0, value=0, flags="stale"), now))

    def test_daylight_matches_classifier_convention(self):
        t = sun.sun_times(date(2026, 10, 9))
        sr = datetime.utcfromtimestamp(t["sunrise"] / 1000)
        self.assertEqual(sr.strftime("%H:%M"), "14:12")     # classifier log: sunrise 14:12:44 UTC
        self.assertAlmostEqual(t["daylight_h"], 11.49, places=1)

    def test_endpoints(self):
        c = app.test_client()
        r = c.get("/api/sun/day/20261009")
        self.assertEqual(r.status_code, 200)
        res = r.get_json()["result"]
        self.assertIn("spells", res)
        self.assertIn("sun", c.get("/api/web/dashboard/live").get_json()["result"])
        self.assertEqual(c.get("/api/var/monthly/sun/total/?n=60").status_code, 200)
        self.assertEqual(c.get("/api/var/rolling/sun/total/?days=3&order=lowest").status_code, 200)


if __name__ == "__main__":
    unittest.main()


def test_sun_times_passes_naive_datetime(monkeypatch):
    """astronomy uses time.mktime; an aware summer datetime (tm_isdst=1) overflows it on prod (TZ=UTC, older glibc)."""
    from datetime import date, datetime
    from rwcwx.model import sun
    seen = {}

    def fake(dt):
        seen["dt"] = dt
        return dict(sunrise=datetime(2026, 10, 12, 14, 10), sunset=datetime(2026, 10, 13, 1, 40), daylight_secs=41400)

    monkeypatch.setattr(sun, "get_all_times_rwc", fake)
    t = sun.sun_times(date(2026, 10, 12))
    assert seen["dt"].tzinfo is None and seen["dt"].timetuple().tm_isdst == -1
    assert t["daylight_h"] == 11.5


class SunPctTest(unittest.TestCase):
    """Derived % of possible: no DB needed (daylight comes from astronomy)."""

    def test_pct_of_possible(self):
        from rwcwx.model.sun import daylight_h, pct_of_possible
        d = date(2026, 10, 9)
        self.assertAlmostEqual(daylight_h(d), 11.5, delta=0.1)
        self.assertAlmostEqual(pct_of_possible(7.5, d), 65.0, delta=1.0)
        self.assertEqual(pct_of_possible(13.0, d), 100.0)   # capped
        self.assertIsNone(pct_of_possible(None, d))

    def test_today_uses_daylight_so_far(self):
        from rwcwx.model.sun import pct_of_possible, sun_times
        d = date(2026, 10, 12)
        sunrise = datetime.utcfromtimestamp(sun_times(d)["sunrise"] / 1000)
        now = sunrise + timedelta(hours=4)
        self.assertAlmostEqual(pct_of_possible(3.0, d, now), 75.0, delta=0.2)
        self.assertIsNone(pct_of_possible(0.0, d, sunrise - timedelta(hours=1)))   # before sunrise

    def test_pct_rolling_is_mean_and_skips_today(self):
        from rwcwx.model.sun import pct_daily_values
        start = date(2026, 6, 18)
        hours = [14.0, 7.0, 14.0, 0.0, 14.0]
        daily = pct_daily_values([(start + timedelta(days=i), h) for i, h in enumerate(hours)])
        res = rolling_ranking(daily, "sunpct", "avg", 3, order="highest", limit=1, today=date(2026, 6, 22))
        self.assertEqual(res[0]["end"], (2026, 6, 20))
        self.assertTrue(60 < res[0]["val"] < 90)


@unittest.skipUnless(DB_OK, "dev DB not reachable")
class SunPctApiTest(unittest.TestCase):
    def test_endpoints(self):
        c = app.test_client()
        daily = c.get("/api/var/daily/sunpct/avg/?year=2026").get_json()["result"]
        hours = {tuple(r["d"]): r["val"] for r in c.get("/api/var/daily/sun/total/?year=2026").get_json()["result"]}
        self.assertEqual(len(daily), len(hours))
        for r in daily:
            self.assertTrue(0 <= r["val"] <= 100)
        monthly = c.get("/api/var/monthly/sunpct/avg/?year=2026").get_json()["result"]
        self.assertTrue(all(0 <= m["summary"]["avg"] <= 100 for m in monthly))
        self.assertEqual(c.get("/api/var/rolling/sunpct/avg/?days=3").status_code, 200)
        self.assertEqual(c.get("/api/var/daily/sunpct/max/?year=2026").get_json()["result"], [])

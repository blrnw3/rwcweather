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

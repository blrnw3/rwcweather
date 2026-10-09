"""
Tests for N-day period rankings. Run with: python -m unittest tests.test_rolling
The endpoint tests use the database in MYSQL_URL (the dev DB) and are skipped if it can't be reached.
"""
import unittest
from datetime import date, timedelta

from rwcwx.calc.rolling import min_days_required, rolling_ranking, rolling_windows


def series(values, start=date(2024, 1, 1)):
    return [(start + timedelta(days=i), v) for i, v in enumerate(values) if v is not None]


class RollingTest(unittest.TestCase):

    def test_coverage_rule(self):
        self.assertEqual([min_days_required(n) for n in (3, 7, 14, 30)], [3, 7, 13, 27])

    def test_sum_and_non_overlap(self):
        res = rolling_ranking(series([0, 1, 5, 2, 0, 0, 3, 3, 3, 0]), "rain", "total", 3, limit=5)
        self.assertEqual([(r["start"], r["end"], r["val"]) for r in res],
                         [((2024, 1, 7), (2024, 1, 9), 9.0), ((2024, 1, 2), (2024, 1, 4), 8.0)])

    def test_gap_excludes_short_windows(self):
        # Day 3 missing: no complete 3-day window covers it.
        wins = rolling_windows(series([1, 1, None, 1, 1, 1]), 3, "sum")
        self.assertEqual([w["end"] for w in wins], [date(2024, 1, 6)])

    def test_gap_allowed_in_long_windows(self):
        values = [1.0] * 14
        values[5] = None
        wins = rolling_windows(series(values), 14, "sum")
        self.assertEqual(len(wins), 1)
        self.assertEqual((wins[0]["days"], wins[0]["val"]), (13, 13.0))

    def test_mean_lowest_and_today_excluded(self):
        data = series([10, 2, 3, 4, 20, 1])
        res = rolling_ranking(data, "temp", "min", 3, order="lowest", limit=3, today=date(2024, 1, 6))
        # Jan 6 is "today" and left out of means; the coldest spell is Jan 2-4.
        self.assertEqual(res[0]["start"], (2024, 1, 2))
        self.assertAlmostEqual(res[0]["val"], 3.0)
        self.assertTrue(all(r["end"] < (2024, 1, 6) for r in res))

    def test_ties_prefer_most_recent(self):
        res = rolling_ranking(series([1, 1, 1, 0, 1, 1, 1]), "rain", "total", 3, limit=1)
        self.assertEqual(res[0]["end"], (2024, 1, 7))


class RollingEndpointTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            from rwcwx.main import app
            from rwcwx.models import db
            db.s.execute("select 1")
        except Exception as e:  # pragma: no cover - only without a database
            raise unittest.SkipTest(f"database not available: {e}")
        cls.client = app.test_client()

    def test_rain_three_day(self):
        res = self.client.get("/api/var/rolling/rain/total/?days=3&limit=10")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual((body["days"], body["min_days"]), (3, 3))
        rows = body["result"]
        self.assertLessEqual(len(rows), 10)
        self.assertEqual([r["val"] for r in rows], sorted((r["val"] for r in rows), reverse=True))
        spans = [(date(*r["start"]), date(*r["end"])) for r in rows]
        for i, (s1, e1) in enumerate(spans):
            self.assertEqual((e1 - s1).days, 2)
            for s2, e2 in spans[i + 1:]:
                self.assertTrue(e1 < s2 or e2 < s1, "windows overlap")

    def test_rejects_unsupported(self):
        for url in ("/api/var/rolling/wind/avg/?days=3", "/api/var/rolling/rain/total/?days=5",
                    "/api/var/rolling/rain/total/?limit=1000", "/api/var/rolling/temp/max/?order=up"):
            self.assertEqual(self.client.get(url).status_code, 400, url)


if __name__ == "__main__":
    unittest.main()

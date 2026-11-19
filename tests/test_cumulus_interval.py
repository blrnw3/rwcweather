"""Cumulus interval-chart and monthly-log parsers (no database)."""
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rwcwx.config import TZ
from rwcwx.cumulus_interval import (
    as_obs_params, chart_ms_to_local, load_interval_dir, parse_monthly_log, rows_in_window,
)

FIX = Path(__file__).parent / "fixtures" / "cumulus_interval"
PT = timezone(timedelta(hours=-8))


def loc(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=TZ)


class ChartMsTest(unittest.TestCase):

    def test_known_boundary_instants(self):
        # 22:15 PT 18 Nov 2026 stored as UTC clock numbers
        ms = int(datetime(2026, 11, 18, 22, 15, tzinfo=timezone.utc).timestamp() * 1000)
        t = chart_ms_to_local(ms)
        self.assertEqual(t.hour, 22)
        self.assertEqual(t.minute, 15)
        self.assertEqual(t.date().isoformat(), "2026-11-18")
        # True UTC is 06:15 on the 19th
        self.assertEqual(t.astimezone(timezone.utc).hour, 6)
        self.assertEqual(t.astimezone(timezone.utc).day, 19)


class IntervalDirTest(unittest.TestCase):

    def setUp(self):
        self.by_t = load_interval_dir(FIX)

    def test_gap_window_excludes_boundaries(self):
        after, before = loc(2026, 11, 18, 22, 15), loc(2026, 11, 19, 7, 1)
        rows = rows_in_window(self.by_t, after, before)
        times = [r["t_local"] for r in rows]
        self.assertNotIn(after, times)
        self.assertNotIn(before, times)
        self.assertEqual(times[0], loc(2026, 11, 18, 22, 16))
        self.assertEqual(times[-1], loc(2026, 11, 19, 7, 0))
        # midnight reset is inside the gap
        rains = {r["t_local"]: r["rain"] for r in rows}
        self.assertEqual(rains[loc(2026, 11, 18, 23, 59)], 3.11)
        self.assertEqual(rains[loc(2026, 11, 19, 0, 0)], 0.0)
        self.assertEqual(rains[loc(2026, 11, 19, 7, 0)], 0.64)

    def test_obs_params_use_utc_minute_and_running_total(self):
        after, before = loc(2026, 11, 18, 22, 15), loc(2026, 11, 19, 7, 1)
        rows = rows_in_window(self.by_t, after, before)
        first = as_obs_params(rows[0])
        self.assertEqual(first["t"], datetime(2026, 11, 19, 6, 16))  # 22:16 PT
        self.assertEqual(first["rain"], 2.96)
        midn = as_obs_params(next(r for r in rows if r["t_local"] == loc(2026, 11, 19, 0, 0)))
        self.assertEqual(midn["t"], datetime(2026, 11, 19, 8, 0))
        self.assertEqual(midn["rain"], 0.0)
        last = as_obs_params(rows[-1])
        self.assertEqual(last["t"], datetime(2026, 11, 19, 15, 0))  # 07:00 PT
        self.assertEqual(last["rain"], 0.64)
        # 07:01 is not in the insert set
        self.assertTrue(all(p["t"] != datetime(2026, 11, 19, 15, 1) for p in map(as_obs_params, rows)))


class MonthlyLogTest(unittest.TestCase):

    def test_parses_local_times_and_daily_rain(self):
        rows = parse_monthly_log(FIX / "Nov26log_sample.txt")
        by_t = {r["t_local"]: r for r in rows}
        after, before = loc(2026, 11, 18, 22, 15), loc(2026, 11, 19, 7, 1)
        gap = rows_in_window(by_t, after, before)
        self.assertEqual(gap[0]["t_local"], loc(2026, 11, 18, 22, 16))
        self.assertEqual(gap[0]["rain"], 2.96)
        rains = {r["t_local"]: r["rain"] for r in gap}
        self.assertEqual(rains[loc(2026, 11, 18, 23, 59)], 3.11)
        self.assertEqual(rains[loc(2026, 11, 19, 0, 0)], 0.0)
        self.assertEqual(rains[loc(2026, 11, 19, 7, 0)], 0.64)


if __name__ == "__main__":
    unittest.main()

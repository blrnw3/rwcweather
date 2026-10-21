"""Civil and astronomical twilight in sun_times (used by /api/sun/day and the Daily Report webcam filter).

Reference times from the astral library (37.470, -122.265, sea level). suncalc is within ~2 min of astral,
so allow 3 min. Runs without a DB, in both process zones (scripts/test_backend.sh).
"""
import math
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwcwx import astronomy  # noqa: E402
from rwcwx.sun.daylight import sun_times  # noqa: E402

TOL_S = 180

# date: (astronomical dawn, astronomical dusk) as UTC epoch seconds, from astral (depression 18 deg)
ASTRAL_ASTRO = {
    date(2026, 10, 21): (1792587338, 1792637456),
    date(2026, 6, 21): (1782039242, 1782106071),   # summer solstice
    date(2025, 12, 21): (1766324764, 1766370527),  # winter solstice
    date(2026, 3, 8): (1772975002, 1773027408),    # DST starts
    date(2026, 11, 1): (1793538332, 1793587146),   # DST ends
    date(2025, 11, 2): (1762088799, 1762137477),   # DST ends
}


class TwilightTest(unittest.TestCase):
    def test_astronomical_twilight_matches_astral(self):
        for d, (dawn, dusk) in ASTRAL_ASTRO.items():
            t = sun_times(d)
            self.assertLess(abs(t["astro_dawn"] / 1000 - dawn), TOL_S, d)
            self.assertLess(abs(t["astro_dusk"] / 1000 - dusk), TOL_S, d)

    def test_order_is_symmetric(self):
        for d in ASTRAL_ASTRO:
            t = sun_times(d)
            self.assertLess(t["astro_dawn"], t["dawn"])
            self.assertLess(t["dawn"], t["sunrise"])
            self.assertLess(t["sunset"], t["dusk"])
            self.assertLess(t["dusk"], t["astro_dusk"])
            # Twilight before sunrise and after sunset last about as long (within a few minutes).
            self.assertLess(abs((t["sunrise"] - t["astro_dawn"]) - (t["astro_dusk"] - t["sunset"])), 5 * 60000, d)

    def test_unreachable_angle_is_left_out(self):
        # Far north in midsummer the sun never gets 18 deg below the horizon: no keys, no exception.
        from datetime import datetime
        times = astronomy.getTimes(datetime(2026, 6, 21, 12), 60.0, 10.0)
        self.assertIn("sunrise", times)
        self.assertNotIn("nightEnd", times)
        self.assertNotIn("night", times)
        self.assertFalse(any(isinstance(v, float) and math.isnan(v) for v in times.values()))


if __name__ == "__main__":
    unittest.main()

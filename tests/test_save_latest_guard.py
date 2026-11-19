"""save_latest memory guard: identity-map release, RSS/age restart policy (no database)."""
import os
import unittest
from datetime import datetime, timedelta

from rwcwx.job.save_latest_guard import (
    DEFAULT_MAX_AGE_DAYS, DEFAULT_MAX_RSS_MB, release_orm_session, rss_bytes, should_restart,
)


class FakeMap(dict):
    pass


class FakeSession:
    def __init__(self, n):
        self.identity_map = FakeMap({i: object() for i in range(n)})
        self.expunged = False

    def expunge_all(self):
        self.identity_map.clear()
        self.expunged = True


class ReleaseSessionTest(unittest.TestCase):

    def test_expunge_clears_identity_map_and_reports_prior_size(self):
        s = FakeSession(50400)  # ~35 days of 1-minute obs
        n = release_orm_session(s)
        self.assertEqual(n, 50400)
        self.assertTrue(s.expunged)
        self.assertEqual(len(s.identity_map), 0)

    def test_none_is_a_no_op(self):
        self.assertEqual(release_orm_session(None), 0)


class ShouldRestartTest(unittest.TestCase):

    def setUp(self):
        self.started = datetime(2026, 10, 15, 0, 26, 58)

    def test_healthy_new_process(self):
        self.assertIsNone(should_restart(
            44 * 1024 * 1024, self.started, now=self.started + timedelta(hours=1),
            max_rss_mb=DEFAULT_MAX_RSS_MB, max_age_days=DEFAULT_MAX_AGE_DAYS,
        ))

    def test_rss_threshold(self):
        reason = should_restart(
            200 * 1024 * 1024, self.started, now=self.started + timedelta(hours=1),
            max_rss_mb=200, max_age_days=7,
        )
        self.assertIsNotNone(reason)
        self.assertIn("200 MiB", reason)

    def test_age_threshold(self):
        reason = should_restart(
            50 * 1024 * 1024, self.started, now=self.started + timedelta(days=7),
            max_rss_mb=200, max_age_days=7,
        )
        self.assertIsNotNone(reason)
        self.assertIn("7d", reason)

    def test_zero_disables_a_limit(self):
        self.assertIsNone(should_restart(
            500 * 1024 * 1024, self.started, now=self.started + timedelta(days=40),
            max_rss_mb=0, max_age_days=0,
        ))

    def test_env_defaults(self):
        os.environ["SAVE_LATEST_MAX_RSS_MB"] = "100"
        os.environ["SAVE_LATEST_MAX_AGE_DAYS"] = "2"
        try:
            self.assertIsNotNone(should_restart(100 * 1024 * 1024, self.started, now=self.started))
        finally:
            os.environ.pop("SAVE_LATEST_MAX_RSS_MB", None)
            os.environ.pop("SAVE_LATEST_MAX_AGE_DAYS", None)


class RssBytesTest(unittest.TestCase):

    def test_self_rss_is_positive_on_linux(self):
        n = rss_bytes()
        self.assertIsNotNone(n)
        self.assertGreater(n, 0)


if __name__ == "__main__":
    unittest.main()

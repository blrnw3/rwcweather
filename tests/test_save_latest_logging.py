"""
save_latest.py logging: rotation, heartbeat, crash logging. Imports rwcwx.models (needs the dev MySQL for table
reflection); skipped otherwise. Run: . dev/box/env.sh; venv/bin/python -m unittest tests.test_save_latest_logging
"""
import logging
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

try:
    from click.testing import CliRunner
    from rwcwx.job import save_latest
    OK = True
except Exception:  # pragma: no cover
    OK = False


@unittest.skipUnless(OK, "dev MySQL not reachable")
class SaveLatestLoggingTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = logging.getLogger()
        self.saved_handlers, self.saved_level = list(self.root.handlers), self.root.level

    def tearDown(self):
        for h in list(self.root.handlers):
            self.root.removeHandler(h)
            if h not in self.saved_handlers:
                h.close()
        for h in self.saved_handlers:
            self.root.addHandler(h)
        self.root.setLevel(self.saved_level)
        self.tmp.cleanup()

    def _log(self):
        return os.path.join(self.tmp.name, "sub", "save_latest.log")

    def _read(self, path=None):
        with open(path or self._log()) as f:
            return f.read()

    def test_rotates_by_size_and_replaces_stderr_handler(self):
        save_latest.setup_logging(self._log(), max_bytes=1000, backups=2, verbose=False)
        self.assertEqual(len(self.root.handlers), 1)
        for i in range(100):
            save_latest.logger.info("line %03d %s", i, "x" * 40)
        files = sorted(os.listdir(os.path.dirname(self._log())))
        self.assertEqual(files, ["save_latest.log", "save_latest.log.1", "save_latest.log.2"])
        self.assertIn("line 099", self._read())
        for f in files:
            self.assertLessEqual(os.path.getsize(os.path.join(os.path.dirname(self._log()), f)), 1000)

    def test_routine_updates_are_debug_and_heartbeat_summarises(self):
        save_latest.setup_logging(self._log(), max_bytes=10**6, backups=1, verbose=False)
        imp = save_latest.CumulusObsImporter("/nonexistent/realtime.txt", self.tmp.name)
        imp.n_saved, imp.n_avg_ext, imp.last_obs_dt = 4, 2, datetime(2026, 10, 9, 14, 0)
        save_latest.logger.debug("routine per-update message")
        imp.maybe_heartbeat()  # interval not elapsed yet: nothing
        imp.last_heartbeat -= timedelta(minutes=16)
        imp.maybe_heartbeat()
        log = self._read()
        self.assertNotIn("routine per-update message", log)
        self.assertEqual(log.count("Heartbeat:"), 1)
        self.assertIn("saved 4 updates, 2 avg/ext refreshes, 0 errors", log)
        self.assertEqual(imp.n_saved, 0)

    def test_air_data_failures_logged_once_then_counted(self):
        save_latest.setup_logging(self._log(), max_bytes=10**6, backups=1, verbose=False)
        imp = save_latest.CumulusObsImporter("/nonexistent/realtime.txt", self.tmp.name)  # no aqi.json there
        for _ in range(5):
            self.assertIsNone(imp.get_pm2_5())
        self.assertEqual(self._read().count("Failed extracting air q data"), 1)
        self.assertEqual(imp.n_air_missing, 5)

    def test_crash_is_logged_before_exit(self):
        with mock.patch.object(save_latest.CumulusObsImporter, "run", side_effect=RuntimeError("boom")):
            result = CliRunner().invoke(save_latest.main, ["-o", "x", "-e", "y", "--log-file", self._log()])
        self.assertIsInstance(result.exception, RuntimeError)
        log = self._read()
        self.assertIn("Starting save_latest", log)
        self.assertIn("CRITICAL", log)
        self.assertIn("RuntimeError: boom", log)


if __name__ == "__main__":
    unittest.main()

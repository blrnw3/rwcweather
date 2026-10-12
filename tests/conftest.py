"""Run the backend tests in the same process time zone as prod (UTC) by default.

Prod (uwsgi, cron jobs) runs with TZ=UTC; dev boxes are often in America/Los_Angeles. rwcwx.astronomy
uses time.mktime / datetime.fromtimestamp, so results and failures depend on the process zone.

  RWC_TEST_TZ=UTC (default)          -> like prod
  RWC_TEST_TZ=America/Los_Angeles    -> catches code that only works when the box is in UTC
  RWC_TEST_NO_DB=1                   -> skip DB-backed tests (used by the deploy pre-check)

scripts/test_backend.sh runs the suite under both zones.
"""
import os
import time

import pytest

TEST_TZ = os.environ.get("RWC_TEST_TZ", "UTC")
os.environ["TZ"] = TEST_TZ
time.tzset()

if os.environ.get("RWC_TEST_NO_DB"):
    os.environ["MYSQL_URL"] = "nodb:nodb@127.0.0.1:1/wx"

_real_mktime = time.mktime


def _prod_like_mktime(t):
    # Prod's glibc rejects tm_isdst=1 in a zone with no DST (UTC): "mktime argument out of range".
    # Newer glibc on dev boxes accepts it, which hid the /api/sun/day bug. Emulate prod's behaviour.
    if TEST_TZ == "UTC" and getattr(t, "tm_isdst", -1) > 0:
        raise OverflowError("mktime argument out of range (tm_isdst=1 under TZ=UTC, as on prod)")
    return _real_mktime(t)


@pytest.fixture(autouse=True)
def prod_like_mktime(monkeypatch):
    monkeypatch.setattr(time, "mktime", _prod_like_mktime)
    yield


def pytest_report_header(config):
    return f"process TZ={TEST_TZ} (time.tzname={time.tzname})"

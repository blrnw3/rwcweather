"""Daily profile report (rwcwx.calc.day_profile): period ranges, DST runs, binning, caching, endpoint."""
import os
from datetime import date, datetime, timedelta

import pytest

from rwcwx.calc import day_profile as dp

LAST = date(2026, 10, 15)


# ---- period_days ----

def test_all_time_is_one_range_per_year_clipped():
    r = dp.period_days(None, None, dp.FIRST_DAY, LAST)
    assert r[0] == (date(2020, 12, 21), date(2021, 1, 1))
    assert r[-1] == (date(2026, 1, 1), date(2026, 10, 16))
    assert len(r) == 7


def test_month_every_year_skips_years_without_data():
    r = dp.period_days(None, 7, dp.FIRST_DAY, LAST)
    assert r[0] == (date(2021, 7, 1), date(2021, 8, 1))
    assert len(r) == 6  # 2021..2026


def test_specific_year_month_and_current_month_clipped():
    assert dp.period_days(2025, 12, dp.FIRST_DAY, LAST) == [(date(2025, 12, 1), date(2026, 1, 1))]
    assert dp.period_days(2026, 10, dp.FIRST_DAY, LAST) == [(date(2026, 10, 1), date(2026, 10, 16))]
    assert dp.period_days(2026, 11, dp.FIRST_DAY, LAST) == []
    assert dp.period_days(2019, None, dp.FIRST_DAY, LAST) == []


# ---- runs (DST splitting) ----

def _local_midnight(d):
    return datetime(d.year, d.month, d.day, tzinfo=dp.TZ).astimezone(dp.UTC).replace(tzinfo=None)


def test_runs_split_at_dst_and_tile_the_period():
    rs = dp.runs([(date(2025, 1, 1), date(2026, 1, 1))])
    assert [(r.d0, r.d1) for r in rs] == [(date(2025, 1, 1), date(2025, 3, 9)),
                                          (date(2025, 3, 9), date(2025, 11, 2)),
                                          (date(2025, 11, 2), date(2026, 1, 1))]
    # consecutive runs meet exactly: nothing counted twice or skipped on change days
    for a, b in zip(rs, rs[1:]):
        assert a.en == b.st
    assert rs[0].st == datetime(2025, 1, 1, 8) and rs[-1].en == datetime(2026, 1, 1, 8)
    for r in rs:
        assert r.st == _local_midnight(r.d0) and r.en == _local_midnight(r.d1)
    # anchors are midnight at the run's offset: PST +8h, PDT +7h
    assert [r.anchor.hour for r in rs] == [8, 7, 8]


def test_runs_without_dst_change_is_single():
    rs = dp.runs([(date(2025, 7, 1), date(2025, 8, 1))])
    assert len(rs) == 1 and rs[0].anchor == datetime(2025, 7, 1, 7) and rs[0].en == datetime(2025, 8, 1, 7)


# ---- sums / averages ----

def test_add_and_averages():
    acc = dp._empty()
    dp._add(acc, [(0, 10.0, 2), (0, 2.0, 1), (dp.N_BINS, 3.0, 1), (-1, 5.0, 1), (5, None, 0), (None, 1, 1)])
    avg, n = dp.averages(acc)
    assert avg[0] == pytest.approx(15 / 4) and n[0] == 4  # bin N_BINS wraps to 0
    assert avg[-1] == 5.0 and n[-1] == 1                   # negative bins wrap to the end of the day
    assert avg[5] is None and n[5] == 0
    assert len(avg) == dp.N_BINS == 288


def test_query_shapes():
    assert "FROM obs" in dp._query("temp") and "SUM(temp)" in dp._query("temp")
    assert "LN(humi / 100)" in dp._query("dewpt")
    assert "LAG(rain)" in dp._query("rain") and f"<= {dp.SPIKE_IN}" in dp._query("rain")
    q = dp._query("sun")
    assert "obs_inferred" in q and "k.k * 5 < i.minutes" in q and "LEAST(i.minutes, 5)" in q
    with pytest.raises(ValueError):
        dp._query("winddir")
    assert "pm2" not in dp.VARS and "aqi" in dp.VARS and "TRUNCATE(CAST(pm2" in dp._query("aqi")
    assert "pm2 >= 0" in dp._query("aqi")


# ---- profile + caching with a fake connection ----

class FakeConn:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append(params)
        res = [(0, 2.0 * 30, 30), (144, 20.0 * 30, 30)]  # 00:00 bin avg 2, 12:00 bin avg 20

        class R:
            def fetchall(self_inner):
                return res
        return R()


@pytest.fixture
def fresh_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "CACHE_DIR", str(tmp_path))
    dp.clear_cache()
    yield tmp_path
    dp.clear_cache()


def test_profile_combines_months_and_caches(fresh_cache):
    c = FakeConn()
    res = dp.profile(c, "temp", None, 7, LAST)
    assert res["days"] == 6 * 31 and res["start"] == "2021-07-01" and res["end"] == "2026-07-31"
    assert res["avg"][0] == 2.0 and res["avg"][144] == 20.0 and res["avg"][1] is None
    assert res["n"][0] == 6 * 30 and res["bin_min"] == 5
    first = len(c.calls)
    assert first == 6
    dp.profile(c, "temp", 2025, 7, LAST)          # month already cached in-process
    assert len(c.calls) == first
    dp.clear_cache()
    dp.profile(c, "temp", 2025, 7, LAST)          # past month comes back from the disk cache
    assert len(c.calls) == first
    assert any(p.name.endswith("temp-2025-07.json") for p in fresh_cache.iterdir())


def test_current_month_not_disk_cached_and_expires(fresh_cache):
    c = FakeConn()
    t = [1000.0]
    dp._cached_month(c, "sun", 2026, 10, LAST, now=lambda: t[0])
    assert c.calls[-1]["kind"] == "sunny"
    assert not list(fresh_cache.iterdir())
    n = len(c.calls)
    t[0] += dp.CURRENT_TTL - 1
    dp._cached_month(c, "sun", 2026, 10, LAST, now=lambda: t[0])
    assert len(c.calls) == n
    t[0] += 2
    dp._cached_month(c, "sun", 2026, 10, LAST, now=lambda: t[0])
    assert len(c.calls) > n


def test_pm2_is_an_alias_for_aqi(fresh_cache):
    res = dp.profile(FakeConn(), "pm2", 2025, 7, LAST)
    assert res["var"] == "aqi"
    assert any(p.name.endswith("aqi-2025-07.json") for p in fresh_cache.iterdir())


def test_warm_covers_aqi(fresh_cache):
    c = FakeConn()
    assert dp.warm(c, LAST, ["aqi"]) == 1
    assert any(p.name.endswith("aqi-2025-07.json") for p in fresh_cache.iterdir())
    assert "aqi" in dp.warm.__defaults__[1]


def test_profile_rejects_unknown_var():
    with pytest.raises(ValueError):
        dp.profile(FakeConn(), "solr", last=LAST)


# ---- against MySQL (read-only) ----

needs_db = pytest.mark.skipif(bool(os.environ.get("RWC_TEST_NO_DB")), reason="needs MySQL")


@pytest.fixture
def client():
    from rwcwx.main import app
    app.config["TESTING"] = True
    return app.test_client()


@needs_db
def test_endpoint_validation(client):
    assert client.get("/api/var/profile/solr/").status_code == 400
    assert client.get("/api/var/profile/temp/?month=13").status_code == 400
    assert client.get("/api/var/profile/temp/?year=abc").status_code == 400


def _epa_aqi(pm):
    """Exact US EPA PM2.5 AQI (truncate to 0.1, linear, round half-even), independent of python-aqi."""
    from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN
    c = Decimal(str(pm)).quantize(Decimal("0.1"), rounding=ROUND_DOWN)
    table = [("0.0", "12.0", 0, 50), ("12.1", "35.4", 51, 100), ("35.5", "55.4", 101, 150), ("55.5", "150.4", 151, 200),
             ("150.5", "250.4", 201, 300), ("250.5", "350.4", 301, 400), ("350.5", "500.4", 401, 500)]
    for lo, hi, alo, ahi in table:
        lo, hi = Decimal(lo), Decimal(hi)
        if c <= hi:
            return int(((ahi - alo) / (hi - lo) * (c - lo) + alo).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN))
    return 500


@needs_db
def test_aqi_sql_matches_epa():
    """The SQL AQI on FLOAT pm2 values equals the EPA formula, including breakpoints, halves and the cap."""
    from sqlalchemy import text
    from rwcwx.main import app
    from rwcwx.models import db
    vals = [0, 0.05, 0.6, 0.7, 4.885, 11.4, 12.0, 12.05, 12.1, 12.9, 35.4, 35.45, 35.5, 55.4, 55.5, 100, 150.4,
            150.5, 250.4, 250.5, 334.5, 350.5, 500.4, 600]
    union = " UNION ALL ".join(f"SELECT CAST({v} AS FLOAT) pm2" for v in vals)
    with app.app_context(), db.engine.connect() as conn:
        got = conn.execute(text(f"SELECT pm2, {dp.OBS_VARS['aqi']} FROM (SELECT pm2, {dp._AQI_C} c FROM ({union}) u) x")).fetchall()
    assert [int(a) for _, a in got] == [_epa_aqi(v) for v in vals]
    with app.app_context(), db.engine.connect() as conn:
        assert conn.execute(text(f"SELECT {dp._aqi_sql('NULL')}")).scalar() is None


@needs_db
def test_endpoint_accepts_pm2_alias(client):
    r = client.get("/api/var/profile/pm2/?year=2025&month=7")
    assert r.status_code == 200 and r.get_json()["result"]["var"] == "aqi"


@needs_db
def test_sql_matches_python_binning(fresh_cache):
    """July 2025 temperature: SQL bins equal binning the raw rows in Python by Pacific time of day."""
    from sqlalchemy import text
    from rwcwx.main import app
    from rwcwx.models import db
    st, en = datetime(2025, 7, 1, 7), datetime(2025, 8, 1, 7)
    with app.app_context(), db.engine.connect() as conn:
        rows = conn.execute(text("SELECT t, temp FROM obs WHERE t >= :st AND t < :en AND temp IS NOT NULL"),
                            dict(st=st, en=en)).fetchall()
        if not rows:
            pytest.skip("no obs for July 2025 in this DB")
        res = dp.profile(conn, "temp", 2025, 7, LAST)
    s, n = [0.0] * dp.N_BINS, [0] * dp.N_BINS
    for t, v in rows:
        loc = t.replace(tzinfo=dp.UTC).astimezone(dp.TZ)
        b = (loc.hour * 60 + loc.minute) // dp.BIN_MIN
        s[b] += float(v)
        n[b] += 1
    assert res["n"] == n
    for i in range(dp.N_BINS):
        if n[i]:
            assert res["avg"][i] == pytest.approx(s[i] / n[i], abs=1e-3)


@needs_db
def test_dst_month_counts_each_row_once(fresh_cache):
    from sqlalchemy import text
    from rwcwx.main import app
    from rwcwx.models import db
    st, en = _local_midnight(date(2025, 11, 1)), _local_midnight(date(2025, 12, 1))
    with app.app_context(), db.engine.connect() as conn:
        cnt = conn.execute(text("SELECT COUNT(temp) FROM obs WHERE t >= :st AND t < :en"), dict(st=st, en=en)).scalar()
        if not cnt:
            pytest.skip("no obs for November 2025 in this DB")
        res = dp.profile(conn, "temp", 2025, 11, LAST)
    assert sum(res["n"]) == cnt


# ---- cache dir + cron wrapper ----

def test_default_cache_dir_in_repo_and_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "_REPO_ROOT", str(tmp_path))
    assert dp._default_cache_dir() == str(tmp_path / "cache" / "day_profile")
    assert (tmp_path / "cache" / "day_profile").is_dir()
    blocker = tmp_path / "ro"
    blocker.write_text("not a dir")
    monkeypatch.setattr(dp, "_REPO_ROOT", str(blocker))     # cache/ cannot be created under a file
    assert dp._default_cache_dir().endswith("rwcwx_day_profile")


def _run_wrapper(tmp_path, *args, extra_env=None):
    import subprocess
    root = tmp_path / "root"
    (root / "venv" / "bin").mkdir(parents=True, exist_ok=True)
    py = root / "venv" / "bin" / "python"
    py.write_text('#!/bin/sh\necho "args=$* pp=$PYTHONPATH url=$MYSQL_URL pwd=$(pwd)"\n')
    py.chmod(0o755)
    env_file = tmp_path / "rwcwx.env"
    env_file.write_text("MYSQL_URL=u:p@h:1/wx\n")
    env = dict(os.environ, RWCWX_ROOT=str(root), RWCWX_ENV_FILE=str(env_file), RWCWX_VENV=str(root / "venv"),
               LOG_DIR=str(tmp_path / "log"), PROFILE_WARM_LOCK=str(tmp_path / "warm.lock"), **(extra_env or {}))
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_day_profile_warm.sh")
    r = subprocess.run(["bash", script, *args], env=env, capture_output=True, text=True, timeout=30)
    return r, tmp_path / "log" / "day_profile_warm.log"


def test_warm_wrapper_runs_module_with_app_env_and_logs(tmp_path):
    r, log = _run_wrapper(tmp_path)
    assert r.returncode == 0, r.stderr
    out = log.read_text()
    root = tmp_path / "root"
    assert f"args=-W ignore -m rwcwx.calc.day_profile pp={root} url=u:p@h:1/wx pwd={root}" in out
    assert out.splitlines()[0].endswith(" start") and out.splitlines()[-1].endswith(" exit 0")


def test_warm_wrapper_rotates_log_and_skips_when_locked(tmp_path):
    import fcntl
    (tmp_path / "log").mkdir()
    big = tmp_path / "log" / "day_profile_warm.log"
    big.write_text("x" * 1048577)
    r, log = _run_wrapper(tmp_path)
    assert r.returncode == 0 and (tmp_path / "log" / "day_profile_warm.log.1").stat().st_size == 1048577
    assert log.stat().st_size < 1000
    with open(tmp_path / "warm.lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r, log = _run_wrapper(tmp_path)
    assert r.returncode == 0 and log.read_text().splitlines()[-1].endswith("still running; skipping")

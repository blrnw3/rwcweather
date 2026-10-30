"""All-years per-calendar-day statistics for the Year Charts overlay (rwcwx.calc.day_of_year, /api/var/day_stats)."""
import os
from datetime import date, timedelta

import pytest

from rwcwx.calc import day_of_year as doy


def _by_md(rows):
    return {(r["m"], r["d"]): r for r in rows}


def test_daily_stats_avg_min_max_and_years():
    vals = [(date(2021, 7, 14), 30.0), (date(2022, 7, 14), 25.0), (date(2023, 7, 14), 35.0), (date(2023, 7, 15), 1.0)]
    rows = doy.daily_stats(vals, today=date(2026, 10, 19))
    assert len(rows) == 366 and (rows[0]["m"], rows[0]["d"]) == (1, 1) and (rows[-1]["m"], rows[-1]["d"]) == (12, 31)
    r = _by_md(rows)[(7, 14)]
    assert r == dict(m=7, d=14, n=3, avg=30.0, min=25.0, max=35.0, min_year=2022, max_year=2023)
    assert _by_md(rows)[(7, 15)]["n"] == 1
    assert _by_md(rows)[(1, 1)] == dict(m=1, d=1, n=0, avg=None, min=None, max=None, min_year=None, max_year=None)


def test_daily_stats_excludes_today_future_and_nulls():
    today = date(2026, 10, 19)
    vals = [(date(2025, 10, 19), 10.0), (today, 99.0), (today + timedelta(days=366), 99.0), (date(2024, 10, 19), None)]
    r = _by_md(doy.daily_stats(vals, today))[(10, 19)]
    assert (r["n"], r["max"]) == (1, 10.0)


def test_daily_stats_ties_earliest_year_holds_record():
    vals = [(date(2021, 1, 5), 2.0), (date(2022, 1, 5), 2.0), (date(2023, 1, 5), 2.0)]
    r = _by_md(doy.daily_stats(vals, date(2026, 1, 1)))[(1, 5)]
    assert (r["min_year"], r["max_year"]) == (2021, 2021)


def test_feb29_pools_feb28_to_mar1():
    vals = [(date(2023, 2, 28), 10.0), (date(2023, 3, 1), 20.0), (date(2024, 2, 29), 30.0), (date(2024, 2, 28), 0.0)]
    rows = _by_md(doy.daily_stats(vals, date(2026, 1, 1)))
    assert rows[(2, 29)]["n"] == 4 and rows[(2, 29)]["avg"] == 15.0
    assert (rows[(2, 29)]["min_year"], rows[(2, 29)]["max_year"]) == (2024, 2024)
    assert rows[(2, 28)]["n"] == 2 and rows[(3, 1)]["n"] == 1       # neighbours keep their own values only


def _daily(start, end, val=1.0):
    d, out = start, []
    while d <= end:
        out.append((d, val))
        d += timedelta(days=1)
    return out


def test_cumulative_calendar_running_totals_and_partial_year():
    # records from 1 Dec 2020: 2020 is not a whole year (starts before the record) so it is left out
    vals = _daily(date(2020, 12, 1), date(2022, 6, 30))
    rows = _by_md(doy.cumulative_stats(vals, today=date(2022, 7, 1)))
    assert rows[(1, 1)] == dict(m=1, d=1, n=2, avg=1.0, min=1.0, max=1.0, min_year=2021, max_year=2021)
    assert rows[(6, 30)]["avg"] == 181.0 and rows[(6, 30)]["n"] == 2
    assert rows[(7, 1)]["n"] == 1 and rows[(7, 1)]["max"] == 182.0    # 2022 stops at its last complete day
    assert rows[(12, 31)]["max"] == 365.0
    # Feb 29 in a non-leap year is that year's end-of-February total
    assert rows[(2, 29)]["n"] == 2 and rows[(2, 29)]["max"] == 59.0


def test_cumulative_excludes_today_and_counts_missing_days_as_zero():
    vals = [(date(2025, 1, 1), 5.0), (date(2025, 1, 3), 2.0), (date(2025, 1, 4), 100.0)]
    rows = _by_md(doy.cumulative_stats(vals, today=date(2025, 1, 4)))
    assert rows[(1, 2)]["avg"] == 5.0 and rows[(1, 3)]["avg"] == 7.0
    assert rows[(1, 4)]["n"] == 0


def test_cumulative_water_year():
    vals = _daily(date(2020, 12, 1), date(2022, 10, 5), val=2.0)
    rows = _by_md(doy.cumulative_stats(vals, today=date(2026, 1, 1), water=True))
    # WY2021 started 1 Oct 2020, before the record: excluded. WY2022 (Oct 2021-Sep 2022) and WY2023 (to 5 Oct 2022)
    assert rows[(10, 1)]["n"] == 2 and rows[(10, 1)]["avg"] == 2.0
    assert rows[(10, 6)]["n"] == 1
    assert rows[(9, 30)]["n"] == 1 and rows[(9, 30)]["max"] == 730.0
    assert doy.period_start(2023, True) == date(2022, 10, 1) and doy.period_start(2023, False) == date(2023, 1, 1)


def test_cumulative_no_data():
    rows = doy.cumulative_stats([], today=date(2026, 1, 1))
    assert len(rows) == 366 and all(r["n"] == 0 for r in rows)


needs_db = pytest.mark.skipif(bool(os.environ.get("RWC_TEST_NO_DB")), reason="needs MySQL")


@pytest.fixture
def client():
    from rwcwx.main import app
    app.config["TESTING"] = True
    return app.test_client()


@needs_db
def test_endpoint_validation(client):
    assert client.get("/api/var/day_stats/wdir/avg/").status_code == 400          # circular
    assert client.get("/api/var/day_stats/fogday/total/").status_code == 400      # 0/1 days
    assert client.get("/api/var/day_stats/temp/max/?mode=cumulative").status_code == 400
    assert client.get("/api/var/day_stats/rain/total/?mode=sum").status_code == 400
    assert client.get("/api/var/day_stats/rain/total/?mode=cumulative&period=month").status_code == 400


@needs_db
def test_endpoint_shape(client):
    r = client.get("/api/var/day_stats/temp/max/")
    assert r.status_code == 200
    j = r.get_json()["result"]
    assert len(j) == 366 and set(j[0]) == {"m", "d", "n", "avg", "min", "max", "min_year", "max_year"}
    r = client.get("/api/var/day_stats/rain/total/?mode=cumulative&period=water")
    assert r.status_code == 200 and len(r.get_json()["result"]) == 366

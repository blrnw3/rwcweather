"""Derived daily variables (ranges, ET0): FAO-56 worked examples and the derivation rules."""
import math
import os
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pytest

from rwcwx.calc import derived_daily as dd
from rwcwx.calc import et0


# ---- FAO-56 worked examples ----

def test_fao56_example8_extraterrestrial_radiation():
    # Example 8: 20 deg S on 3 September (day 246): Ra = 32.2 MJ m-2 day-1
    ra, _ = et0.solar_geometry(246, -20.0)
    assert ra == pytest.approx(32.2, abs=0.05)


def test_fao56_example9_daylight_hours():
    # Example 9: 20 deg S on 3 September: N = 11.7 h
    _, n = et0.solar_geometry(246, -20.0)
    assert n == pytest.approx(11.7, abs=0.05)


def test_fao56_example18_penman_monteith():
    # Example 18: Brussels (50 deg 48' N, 100 m), 6 July (day 187); Tmax 21.5, Tmin 12.3 degC, RHmax 84 %, RHmin 63 %,
    # wind 10 km/h at 10 m -> u2 = 2.078 m/s, n = 9.25 h. FAO: Ra 41.09, N 16.1, ea 1.409 kPa, ET0 = 3.9 mm/day.
    lat = 50 + 48 / 60
    ra, n_daylight = et0.solar_geometry(187, lat)
    assert ra == pytest.approx(41.09, abs=0.05)
    assert n_daylight == pytest.approx(16.1, abs=0.05)
    ea = (et0.sat_vp(12.3) * 0.84 + et0.sat_vp(21.5) * 0.63) / 2
    assert ea == pytest.approx(1.409, abs=0.002)
    assert et0.pressure_kpa(100) == pytest.approx(100.1, abs=0.05)
    v = et0.penman_monteith(21.5, 12.3, ea, 2.078, 9.25, ra, n_daylight, z=100)
    assert v == pytest.approx(3.9, abs=0.05)


def test_hargreaves_eq52():
    # Same day as Example 18: 0.0023 (16.9 + 17.8) sqrt(9.2) * 0.408 * 41.09
    ra, _ = et0.solar_geometry(187, 50 + 48 / 60)
    assert et0.hargreaves(21.5, 12.3, ra) == pytest.approx(0.0023 * 34.7 * math.sqrt(9.2) * 0.408 * ra, rel=1e-9)
    assert et0.hargreaves(21.5, 12.3, ra) == pytest.approx(4.06, abs=0.02)


def test_wind_floor_and_factor():
    assert et0.u2_from_mph(0.2) == et0.MIN_U2
    assert et0.u2_from_mph(5) == pytest.approx(5 * 0.44704)
    assert et0.u2_from_mph(5, factor=1.5) == pytest.approx(7.5 * 0.44704)


# ---- derivation from daily rows ----

@dataclass
class Row:
    d: date
    val: Optional[float]
    comment: Optional[str] = None


D = date(2025, 7, 14)


def _series(sun_comment="webcam; coverage 98.0%", sun=12.0, wind=3.0, dewpt=11.0):
    s = {("temp", "max"): [Row(D, 30.0)], ("temp", "min"): [Row(D, 13.0)], ("humi", "max"): [Row(D, 90.0)],
         ("humi", "min"): [Row(D, 30.0)], ("wind", "avg"): [Row(D, wind)] if wind is not None else [],
         ("dewpt", "avg"): [Row(D, dewpt)] if dewpt is not None else [],
         ("sun", "total"): [Row(D, sun, sun_comment)] if sun is not None else []}
    return s


def test_ranges():
    days = dd.range_days([Row(D, 30.0), Row(date(2025, 7, 15), 25.0)], [Row(D, 13.5)], "temprange")
    assert [(x.d, x.val) for x in days] == [(D, 16.5)]
    assert days[0].simple_dict_ == dict(d=(2025, 7, 14), val=16.5)


def test_et0_penman_monteith_when_sunshine_is_usable():
    [x] = dd.et0_days(_series())
    assert x.method == "pm" and 4 < x.val < 8 and x.simple_dict_["method"] == "pm"


@pytest.mark.parametrize("kw", [dict(sun=None), dict(sun_comment="API estimate (api:x); webcam coverage 20%"),
                                dict(sun_comment="webcam; coverage 60.0%; scaled"), dict(wind=None),
                                dict(dewpt=None, sun=None)])
def test_et0_falls_back_to_hargreaves(kw):
    [x] = dd.et0_days(_series(**kw))
    ra, _ = et0.solar_geometry(D.timetuple().tm_yday)
    assert x.method == "hs" and x.val == round(et0.hargreaves(30.0, 13.0, ra), 2)


def test_et0_rh_when_no_dewpoint():
    [x] = dd.et0_days(_series(dewpt=None))
    assert x.method == "pm"


def test_et0_excludes_today_and_needs_tmax_tmin():
    assert dd.et0_days(_series(), today=D) == []
    s = _series()
    s[("temp", "min")] = []
    assert dd.et0_days(s) == []


def _month_series(days, sun=12.0, start=date(2024, 7, 1)):
    """`days` consecutive July days, same weather; sun=None makes them Hargreaves days."""
    from datetime import timedelta
    ds = [start + timedelta(days=i) for i in range(days)]
    rows = lambda v, c=None: [Row(d, v, c) for d in ds]   # noqa: E731
    return {("temp", "max"): rows(30.0), ("temp", "min"): rows(13.0), ("humi", "max"): rows(90.0),
            ("humi", "min"): rows(30.0), ("wind", "avg"): rows(3.0), ("dewpt", "avg"): rows(11.0),
            ("sun", "total"): rows(sun, "webcam; coverage 98.0%") if sun is not None else []}


def test_hs_ratios_are_pm_over_hs_on_pm_days():
    s = _month_series(25)
    ratios = dd.hs_ratios(s)
    pm = dd.et0_days(s)
    ra = [et0.solar_geometry(x.d.timetuple().tm_yday)[0] for x in pm]
    expect = sum(x.val for x in pm) / sum(et0.hargreaves(30.0, 13.0, r) for r in ra)
    assert list(ratios) == [7] and ratios[7] == pytest.approx(expect, abs=1e-3)
    # too few PM days in a month -> no ratio for it
    assert dd.hs_ratios(_month_series(dd.MIN_RATIO_DAYS - 1)) == {}


def test_hs_days_are_calibrated_pm_days_are_not():
    hs = dd.et0_days(_month_series(3, sun=None), ratios={7: 0.8})
    raw = dd.et0_days(_month_series(3, sun=None))
    assert all(x.method == "hs" and x.cal == 0.8 for x in hs)
    assert [x.val for x in hs] == [round(r.val * 0.8, 2) for r in raw]
    assert hs[0].simple_dict_["cal"] == 0.8 and "cal" not in raw[0].simple_dict_
    pm = dd.et0_days(_month_series(3), ratios={7: 0.8})
    assert all(x.method == "pm" and x.cal is None for x in pm)
    assert dd.et0_days(_month_series(3, sun=None), ratios={1: 0.8})[0].cal is None   # other month: raw


def test_sun_usable():
    assert dd.sun_usable("webcam; coverage 75.0%; scaled")
    assert not dd.sun_usable("webcam; coverage 74.9%; scaled")
    assert dd.sun_usable("estimated from 30-min snapshots; coverage 91.2%")
    assert not dd.sun_usable("API estimate (api:hrrr); no webcam total")
    assert not dd.sun_usable(None)


def test_add_to_summary_averages_ranges_and_sums_et0():
    by_type = {("temp", "max"): [Row(D, 30.0), Row(date(2025, 7, 15), 28.0)],
               ("temp", "min"): [Row(D, 10.0), Row(date(2025, 7, 15), 14.0)]}
    stats = {}
    dd.add_to_summary(stats, by_type, lambda days: dict(n=len(days), total=sum(x.val for x in days)))
    assert stats["temprange_avg"] == dict(n=2, total=34.0)
    assert stats["et0_total"]["n"] == 2 and stats["et0_total"]["methods"] == {"hs": 2}
    assert "humirange_avg" not in stats


# ---- endpoints (dev MySQL, read-only) ----

needs_db = pytest.mark.skipif(bool(os.environ.get("RWC_TEST_NO_DB")), reason="needs MySQL")


@pytest.fixture
def client():
    from rwcwx.main import app
    app.config["TESTING"] = True
    return app.test_client()


@needs_db
@pytest.mark.parametrize("var,typ", [("temprange", "avg"), ("humirange", "avg"), ("presrange", "avg"),
                                     ("dewptrange", "avg"), ("et0", "total")])
def test_endpoints(client, var, typ):
    r = client.get(f"/api/var/daily/{var}/{typ}/?start=20250701&end=20250731")
    assert r.status_code == 200
    rows = r.get_json()["result"]
    assert len(rows) == 31 and all(x["val"] >= 0 for x in rows)
    r = client.get(f"/api/var/monthly/{var}/{typ}/?year=2025")
    assert r.status_code == 200 and len(r.get_json()["result"]) == 12
    assert client.get(f"/api/var/rolling/{var}/{typ}/?days=7").status_code == 200
    assert client.get(f"/api/var/day_stats/{var}/{typ}/").status_code == 200
    assert client.get(f"/api/var/daily/{var}/max/?year=2025").get_json()["result"] == []


@needs_db
def test_temprange_matches_max_minus_min(client):
    q = "?start=20250701&end=20250731"
    hi = {tuple(x["d"]): x["val"] for x in client.get("/api/var/daily/temp/max/" + q).get_json()["result"]}
    lo = {tuple(x["d"]): x["val"] for x in client.get("/api/var/daily/temp/min/" + q).get_json()["result"]}
    rng = {tuple(x["d"]): x["val"] for x in client.get("/api/var/daily/temprange/avg/" + q).get_json()["result"]}
    assert rng and all(v == pytest.approx(hi[d] - lo[d], abs=1e-6) for d, v in rng.items())


@needs_db
def test_summaries_include_derived(client):
    s = client.get("/api/obs/summary/month/20250701").get_json()["result"]
    assert {"temprange_avg", "humirange_avg", "presrange_avg", "dewptrange_avg", "et0_total"} <= set(s)
    assert s["et0_total"]["count"] == 31 and sum(s["et0_total"]["methods"].values()) == 31

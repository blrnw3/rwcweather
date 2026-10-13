"""web/app/data/climate.js sun.possible must match rwcwx.astronomy daylight (sunrise to sunset) at the station."""
import calendar
import datetime as dt
import os
import re

from rwcwx.astronomy import get_all_times_rwc

CLIMATE_JS = os.path.join(os.path.dirname(__file__), "..", "web", "app", "data", "climate.js")


def _possible_block():
    src = open(CLIMATE_JS, encoding="utf-8").read()
    m = re.search(r"possible:\s*\{.*?monthly:\s*\[([^\]]*)\].*?annual:\s*([\d.]+)", src, re.S)
    assert m, "sun.possible normals missing from climate.js"
    return [float(x) for x in m.group(1).split(",")], float(m.group(2))


def _daylight_h(d: dt.date) -> float:
    return get_all_times_rwc(dt.datetime(d.year, d.month, d.day, 12))["daylight_secs"] / 3600


def test_possible_matches_astronomy():
    monthly, annual = _possible_block()
    assert len(monthly) == 12
    calc = [sum(_daylight_h(dt.date(2025, mo, d)) for d in range(1, calendar.monthrange(2025, mo)[1] + 1))
            for mo in range(1, 13)]
    for got, want in zip(monthly, calc):
        assert abs(got - want) <= 0.6
    assert abs(annual - sum(calc)) <= 1
    assert abs(annual - sum(monthly)) <= 1


def test_no_solar_radiation_normals():
    src = open(CLIMATE_JS, encoding="utf-8").read()
    assert "solr:" not in src

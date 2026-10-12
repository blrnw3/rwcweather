"""NOAA solar position (good to ~0.1 deg) for the station. Input: naive UTC datetime."""
import math
from datetime import datetime
from typing import Tuple

LAT, LON = 37.470, -122.265


def solar_pos(t: datetime, lat: float = LAT, lon: float = LON) -> Tuple[float, float]:
    r = math.radians
    jd = (t - datetime(2000, 1, 1, 12)).total_seconds() / 86400.0 + 2451545.0
    jc = (jd - 2451545.0) / 36525.0
    gml = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    gma = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    ecc = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    ceq = (math.sin(r(gma)) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) + math.sin(r(2 * gma)) * (0.019993 - 0.000101 * jc)
           + math.sin(r(3 * gma)) * 0.000289)
    sal = gml + ceq - 0.00569 - 0.00478 * math.sin(r(125.04 - 1934.136 * jc))
    moe = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
    oc = moe + 0.00256 * math.cos(r(125.04 - 1934.136 * jc))
    dec = math.degrees(math.asin(math.sin(r(oc)) * math.sin(r(sal))))
    y = math.tan(r(oc / 2)) ** 2
    eot = 4 * math.degrees(y * math.sin(2 * r(gml)) - 2 * ecc * math.sin(r(gma)) + 4 * ecc * y * math.sin(r(gma)) * math.cos(2 * r(gml))
                           - 0.5 * y * y * math.sin(4 * r(gml)) - 1.25 * ecc * ecc * math.sin(2 * r(gma)))
    mins = t.hour * 60 + t.minute + t.second / 60
    tst = (mins + eot + 4 * lon) % 1440
    ha = tst / 4 + 180 if tst / 4 < 0 else tst / 4 - 180
    cz = math.sin(r(lat)) * math.sin(r(dec)) + math.cos(r(lat)) * math.cos(r(dec)) * math.cos(r(ha))
    zen = math.degrees(math.acos(max(-1., min(1., cz))))
    el = 90 - zen
    ca = ((math.sin(r(lat)) * math.cos(r(zen))) - math.sin(r(dec))) / (math.cos(r(lat)) * math.sin(r(zen)))
    az = math.degrees(math.acos(max(-1., min(1., ca))))
    az = (az + 180) % 360 if ha > 0 else (540 - az) % 360
    return el, az

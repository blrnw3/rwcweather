"""Daily reference evapotranspiration (ET0, grass reference, mm/day) after FAO-56 (Allen et al. 1998).

Penman-Monteith (FAO-56 eq. 6) with G = 0 for daily steps:

    ET0 = (0.408 D (Rn - G) + g 900 / (T + 273) u2 (es - ea)) / (D + g (1 + 0.34 u2))

  T      mean of the daily max and min temperature (eq. 9)
  es     mean saturation vapour pressure from Tmax and Tmin (eqs. 11, 12)
  ea     actual vapour pressure: from the day's mean dew point (eq. 14); the daily RH max/min (eq. 17) only when there
         is no dew point. The station's RH sensor sits in the sun-exposed T/H shield, so RHmin pairs with a Tmax that
         reads high; the mean dew point averages the whole day's minutes and is FAO's first choice.
  Rs     Angstrom (eq. 35): (0.25 + 0.50 n / N) Ra, n = webcam sunshine hours, N = daylight hours (eq. 34)
  Rso    (0.75 + 2e-5 z) Ra (eq. 37); Rns = 0.77 Rs (albedo 0.23, eq. 38); Rnl from eq. 39; Rn = Rns - Rnl
  P      from the station elevation (eq. 7): the stored pressure is reduced to sea level, so it is not station pressure
  u2     the daily mean wind speed, taken as the 2 m wind (see WIND_TO_U2), floored at 0.5 m/s as FAO-56 advises

Hargreaves-Samani (FAO-56 eq. 52), used when a day has no usable sunshine:

    ET0 = 0.0023 (T + 17.8) (Tmax - Tmin) ** 0.5 * 0.408 Ra
"""
import math
from datetime import date
from typing import Optional

LAT_DEG = 37.470          # station latitude (rwcwx/sun/solar.py)
ELEV_M = 125.0            # station elevation (about page: ~125 m / 420 ft)
GSC = 0.0820              # solar constant, MJ m-2 min-1
SIGMA = 4.903e-9          # Stefan-Boltzmann, MJ K-4 m-2 day-1
ALBEDO = 0.23
AS, BS = 0.25, 0.50       # Angstrom coefficients (FAO-56 defaults, no local calibration)
MPH_TO_MS = 0.44704
# The anemometer is above the roofline on a sheltered hillside and reads a little low, so the FAO height reduction
# (eq. 47), which would lower it further, is not applied: the measured daily mean is used as u2 directly. Change
# this factor if the wind is ever calibrated against an open-site 2 m measurement.
WIND_TO_U2 = 1.0
MIN_U2 = 0.5              # m/s; FAO-56 recommends u2 >= 0.5 m/s for the Penman-Monteith equation


def _rad(deg: float) -> float:
    return deg * math.pi / 180


def solar_geometry(doy: int, lat_deg: float = LAT_DEG):
    """-> (Ra in MJ m-2 day-1, N daylight hours) for day of year `doy` (FAO-56 eqs. 21-25, 34)."""
    phi = _rad(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    dec = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(dec))))
    ra = 24 * 60 / math.pi * GSC * dr * (ws * math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.sin(ws))
    return ra, 24 / math.pi * ws


def sat_vp(t: float) -> float:
    """Saturation vapour pressure (kPa) at t degC (eq. 11)."""
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def pressure_kpa(z: float = ELEV_M) -> float:
    return 101.3 * ((293 - 0.0065 * z) / 293) ** 5.26


def hargreaves(tmax: float, tmin: float, ra: float) -> float:
    """FAO-56 eq. 52 (mm/day); ra in MJ m-2 day-1."""
    t = (tmax + tmin) / 2
    return 0.0023 * (t + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * 0.408 * ra


def penman_monteith(tmax: float, tmin: float, ea: float, u2: float, sun_h: float, ra: float, n_daylight: float,
                    z: float = ELEV_M, pressure: Optional[float] = None) -> float:
    """FAO-56 eq. 6 with G = 0 (mm/day). ea in kPa, u2 in m/s at 2 m, sun_h = n (h), ra in MJ m-2 day-1."""
    t = (tmax + tmin) / 2
    es = (sat_vp(tmax) + sat_vp(tmin)) / 2
    delta = 4098 * sat_vp(t) / (t + 237.3) ** 2
    gamma = 0.665e-3 * (pressure if pressure is not None else pressure_kpa(z))
    rs = (AS + BS * min(sun_h / n_daylight, 1.0)) * ra
    rso = (0.75 + 2e-5 * z) * ra
    rns = (1 - ALBEDO) * rs
    rnl = SIGMA * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (0.34 - 0.14 * math.sqrt(max(ea, 0.0))) \
        * (1.35 * min(rs / rso, 1.0) - 0.35)
    rn = rns - rnl
    return (0.408 * delta * rn + gamma * 900 / (t + 273) * u2 * (es - ea)) / (delta + gamma * (1 + 0.34 * u2))


def u2_from_mph(wind_mph: float, factor: float = WIND_TO_U2) -> float:
    return max(wind_mph * MPH_TO_MS * factor, MIN_U2)


def daily_et0(d: date, tmax: Optional[float], tmin: Optional[float], dewpt: Optional[float] = None,
              rh_max: Optional[float] = None, rh_min: Optional[float] = None, wind_mph: Optional[float] = None,
              sun_h: Optional[float] = None, wind_factor: float = WIND_TO_U2):
    """-> (ET0 mm/day rounded to 0.01, "pm" | "hs") or None without a daily max and min temperature.
    Penman-Monteith when the day has sunshine hours, wind and humidity; otherwise Hargreaves-Samani."""
    if tmax is None or tmin is None:
        return None
    ra, n_daylight = solar_geometry(d.timetuple().tm_yday)
    if dewpt is not None:
        ea = sat_vp(dewpt)
    elif rh_max is not None and rh_min is not None:
        ea = (sat_vp(tmin) * rh_max / 100 + sat_vp(tmax) * rh_min / 100) / 2
    else:
        ea = None
    if sun_h is not None and wind_mph is not None and ea is not None:
        val = penman_monteith(tmax, tmin, ea, u2_from_mph(wind_mph, wind_factor), sun_h, ra, n_daylight)
        method = "pm"
    else:
        val = hargreaves(tmax, tmin, ra)
        method = "hs"
    return round(max(val, 0.0), 2), method

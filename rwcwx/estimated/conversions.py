"""Versioned conversions from nearby daily observations to this site.

Version v1 was fitted on the overlap of our measured daily series (from 27 Dec 2020)
with Pulgas Ridge RAWS (PUGC1, IEM daily), Redwood City COOP (USC00047339, ACIS/GHCND)
and San Francisco International (SFO, IEM daily), using leave-one-year-out cross-validation
on calendar years 2021-2026. Full comparison tables live with the research that produced
these coefficients.

Blend (v1), 1 Jan 2009 through 26 Dec 2020 only:
  Tmax  — COOP monthly linear, else SFO monthly offset (confidence B)
  Tmin  — PUGC1 monthly linear, else SFO monthly linear (confidence B)
  rain  — PUGC1 annual ratio, else SFO annual ratio (confidence B)

Inputs and outputs are in this site's native units: temperature in °C, rain in inches.
Source temperatures published in °F must be converted to °C before apply().

Pulgas IEM daily starts 6 Dec 2010, so Tmin and rain in 2009 through early December 2010
are almost entirely the SFO gap-fill (confidence B). Climate normals stay measured-only.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Tuple

# Bump this and add a new param set when the models are refitted.
VERSION = "v1"

# Inclusive generation window for this version.
PERIOD_START = "2009-01-01"
PERIOD_END = "2020-12-26"

# First day of our own measured daily series; estimates are not written on or after this date.
MEASURED_START = "2020-12-27"

# Leave-one-year-out CV RMSE on the 2021-2026 overlap (for documentation / confidence).
# Temperature in °C, rain in inches.
CV_RMSE = {
    ("coop", "tmax", "linear"): 1.41,
    ("pugc1", "tmin", "linear"): 1.06,
    ("pugc1", "rain", "ratio"): 0.047,
    ("sfo", "tmax", "offset"): 2.17,
    ("sfo", "tmin", "linear"): 1.55,
    ("sfo", "rain", "ratio"): 0.107,
}

# Monthly linear: estimate = slope * source + intercept  (source already in °C).
# Coefficients are ordinary-least-squares fits on all overlap days of that calendar month.
COOP_TMAX_LINEAR: Dict[int, Tuple[float, float]] = {
    1: (0.757430, 2.455326),
    2: (0.916823, 0.183036),
    3: (0.922531, 0.733343),
    4: (0.940136, 1.492271),
    5: (1.002003, 0.978211),
    6: (0.968646, 2.206900),
    7: (0.956781, 2.715966),
    8: (0.925875, 3.039665),
    9: (0.902111, 2.611729),
    10: (0.924731, 0.616024),
    11: (0.894590, 0.049326),
    12: (0.751482, 2.133567),
}

PUGC1_TMIN_LINEAR: Dict[int, Tuple[float, float]] = {
    1: (0.789233, 2.319256),
    2: (0.819524, 2.130180),
    3: (0.852394, 2.025295),
    4: (0.864952, 2.215736),
    5: (0.864799, 2.678604),
    6: (0.786584, 4.182354),
    7: (0.766463, 4.778775),
    8: (0.679264, 6.125869),
    9: (0.918385, 2.551842),
    10: (0.826848, 3.057732),
    11: (0.847874, 2.323188),
    12: (0.836896, 2.033703),
}

SFO_TMIN_LINEAR: Dict[int, Tuple[float, float]] = {
    1: (0.720822, 1.711012),
    2: (0.916889, -0.081948),
    3: (1.066348, -1.806082),
    4: (1.028805, -1.833980),
    5: (0.910255, -0.034257),
    6: (0.645665, 4.189851),
    7: (0.617074, 5.395665),
    8: (0.307983, 10.291001),
    9: (0.759878, 3.247537),
    10: (1.103262, -1.730934),
    11: (0.797759, 1.403820),
    12: (0.925300, -0.419990),
}

# Monthly offset: estimate = source + offset  (source already in °C).
SFO_TMAX_OFFSET: Dict[int, float] = {
    1: -0.042995,
    2: 0.038593,
    3: 1.154839,
    4: 3.012911,
    5: 4.731243,
    6: 5.987407,
    7: 6.760275,
    8: 6.073118,
    9: 3.971728,
    10: 1.262186,
    11: -0.515775,
    12: -0.465000,
}

# Annual rain ratio = our_total / source_total on the overlap days both series reported.
# Applied every month (monthly ratios were noisier, especially in the dry season).
PUGC1_RAIN_RATIO = 133.81 / 143.91          # 0.929817...
SFO_RAIN_RATIO = 133.81 / 111.7216          # 1.197709...

# Primary then gap-fill. Each entry is (source_id, method).
BLEND = {
    ("temp", "max"): (("coop", "linear"), ("sfo", "offset")),
    ("temp", "min"): (("pugc1", "linear"), ("sfo", "linear")),
    ("rain", "total"): (("pugc1", "ratio"), ("sfo", "ratio")),
}

PARAMS = {
    ("coop", "tmax", "linear"): COOP_TMAX_LINEAR,
    ("pugc1", "tmin", "linear"): PUGC1_TMIN_LINEAR,
    ("sfo", "tmin", "linear"): SFO_TMIN_LINEAR,
    ("sfo", "tmax", "offset"): SFO_TMAX_OFFSET,
    ("pugc1", "rain", "ratio"): PUGC1_RAIN_RATIO,
    ("sfo", "rain", "ratio"): SFO_RAIN_RATIO,
}

SOURCE_VAR = {
    ("coop", "temp", "max"): "tmax",
    ("pugc1", "temp", "min"): "tmin",
    ("sfo", "temp", "max"): "tmax",
    ("sfo", "temp", "min"): "tmin",
    ("pugc1", "rain", "total"): "rain",
    ("sfo", "rain", "total"): "rain",
}


def f_to_c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def apply_linear(source_c: float, month: int, params: Mapping[int, Tuple[float, float]]) -> float:
    slope, intercept = params[month]
    return slope * source_c + intercept


def apply_offset(source_c: float, month: int, params: Mapping[int, float]) -> float:
    return source_c + params[month]


def apply_ratio(source_in: float, ratio: float) -> float:
    if source_in <= 0:
        return 0.0
    return source_in * ratio


def apply(source_id: str, var: str, typ: str, method: str, source_native, month: int) -> Optional[float]:
    """Convert one source reading (temp in °C, rain in inches) for a calendar month 1-12.

    Returns None if the source value is missing. Temp is rounded to 2 decimals °C,
    rain to 3 decimals inches (never negative).
    """
    if source_native is None:
        return None
    try:
        x = float(source_native)
    except (TypeError, ValueError):
        return None
    key_var = SOURCE_VAR[(source_id, var, typ)]
    params = PARAMS[(source_id, key_var, method)]
    if method == "linear":
        out = apply_linear(x, month, params)
    elif method == "offset":
        out = apply_offset(x, month, params)
    elif method == "ratio":
        out = apply_ratio(x, params)
    else:
        raise ValueError("unknown method: " + method)
    if var == "rain":
        return round(max(0.0, out), 3)
    return round(out, 2)


def method_label(method: str) -> str:
    return "v1-" + method


def confidence_for(source_id: str) -> str:
    return "B" if source_id == "sfo" else "A"

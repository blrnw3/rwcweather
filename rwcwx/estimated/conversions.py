"""Versioned conversions from nearby daily observations to this site.

Version v4 uses the same conversions as v3, fitted on the overlap of our measured daily series (from 27 Dec 2020)
with Pulgas Ridge RAWS (PUGC1, IEM daily), Redwood City COOP (USC00047339, ACIS/GHCND)
and San Francisco International (SFO, IEM daily), using leave-one-year-out
cross-validation on calendar years 2021-2026. Full comparison tables live with the
research that produced these coefficients.

Blend (v4), 1 Jan 2011 through 26 Dec 2020 only — Pulgas Ridge PUGC1 first for every
variable; days or variables missing from Pulgas, or rejected by quality control, are
filled from a calibrated secondary:
  Tmax  — PUGC1 monthly linear, else COOP monthly linear (confidence B), else SFO monthly offset (C)
  Tmin  — PUGC1 monthly linear, else COOP monthly linear (confidence B), else SFO monthly linear (C)
  rain  — PUGC1 annual ratio, else COOP annual ratio (confidence B), else SFO annual ratio (C)

Quality control (see rwcwx.estimated.qc): a Pulgas rain total above 1 in is rejected
if it is more than 3× the larger of the same-day COOP and SFO raw totals, or if both
are dry. A Pulgas temperature is rejected if it differs by more than 8 °C from the
COOP (else SFO) converted estimate for that day.

Inputs and outputs are in this site's native units: temperature in °C, rain in inches.
Source temperatures published in °F must be converted to °C before apply().
Climate normals stay measured-only.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Tuple

# Bump this and add a new param set when the models are refitted.
VERSION = "v4"

# Inclusive generation window for this version.
PERIOD_START = "2011-01-01"
PERIOD_END = "2020-12-26"

# First day of our own measured daily series; estimates are not written on or after this date.
MEASURED_START = "2020-12-27"

# Leave-one-year-out CV RMSE on the 2021-2026 overlap (for documentation / confidence).
# Temperature in °C, rain in inches.
CV_RMSE = {
    ("pugc1", "tmax", "linear"): 2.04,
    ("pugc1", "tmin", "linear"): 1.06,
    ("pugc1", "rain", "ratio"): 0.047,
    ("coop", "tmax", "linear"): 1.41,
    ("coop", "tmin", "linear"): 1.34,
    ("coop", "rain", "ratio"): 0.066,
    ("sfo", "tmax", "offset"): 2.17,
    ("sfo", "tmin", "linear"): 1.55,
    ("sfo", "rain", "ratio"): 0.107,
}

# Monthly linear: estimate = slope * source + intercept  (source already in °C).
# Coefficients are ordinary-least-squares fits on all overlap days of that calendar month.
PUGC1_TMAX_LINEAR: Dict[int, Tuple[float, float]] = {
    1: (0.719714, 2.907010),
    2: (0.770688, 2.393647),
    3: (0.842248, 2.226221),
    4: (0.769956, 5.088214),
    5: (0.802842, 5.545266),
    6: (0.707752, 8.389222),
    7: (0.658842, 9.306664),
    8: (0.619869, 10.245507),
    9: (0.667303, 7.909140),
    10: (0.727677, 4.249686),
    11: (0.718347, 3.220469),
    12: (0.706563, 2.739508),
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

COOP_TMIN_LINEAR: Dict[int, Tuple[float, float]] = {
    1: (0.526067, 5.168116),
    2: (0.638241, 4.137993),
    3: (0.821794, 2.665558),
    4: (0.793802, 2.503395),
    5: (0.785156, 2.510849),
    6: (0.799136, 2.441663),
    7: (0.872114, 1.643018),
    8: (0.530499, 7.032902),
    9: (0.811939, 3.373938),
    10: (0.816081, 4.151903),
    11: (0.619834, 5.600918),
    12: (0.645043, 4.092883),
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
COOP_RAIN_RATIO = 133.28 / 106.26           # 1.254282...
SFO_RAIN_RATIO = 133.81 / 111.7216          # 1.197709...

# Primary then gap-fill. Each entry is (source_id, method).
BLEND = {
    ("temp", "max"): (("pugc1", "linear"), ("coop", "linear"), ("sfo", "offset")),
    ("temp", "min"): (("pugc1", "linear"), ("coop", "linear"), ("sfo", "linear")),
    ("rain", "total"): (("pugc1", "ratio"), ("coop", "ratio"), ("sfo", "ratio")),
}

PARAMS = {
    ("pugc1", "tmax", "linear"): PUGC1_TMAX_LINEAR,
    ("pugc1", "tmin", "linear"): PUGC1_TMIN_LINEAR,
    ("coop", "tmax", "linear"): COOP_TMAX_LINEAR,
    ("coop", "tmin", "linear"): COOP_TMIN_LINEAR,
    ("sfo", "tmin", "linear"): SFO_TMIN_LINEAR,
    ("sfo", "tmax", "offset"): SFO_TMAX_OFFSET,
    ("pugc1", "rain", "ratio"): PUGC1_RAIN_RATIO,
    ("coop", "rain", "ratio"): COOP_RAIN_RATIO,
    ("sfo", "rain", "ratio"): SFO_RAIN_RATIO,
}

SOURCE_VAR = {
    ("pugc1", "temp", "max"): "tmax",
    ("pugc1", "temp", "min"): "tmin",
    ("coop", "temp", "max"): "tmax",
    ("coop", "temp", "min"): "tmin",
    ("sfo", "temp", "max"): "tmax",
    ("sfo", "temp", "min"): "tmin",
    ("pugc1", "rain", "total"): "rain",
    ("coop", "rain", "total"): "rain",
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
    return VERSION + "-" + method


def confidence_for(source_id: str) -> str:
    """A = Pulgas primary, B = COOP gap-fill, C = SFO gap-fill."""
    return {"pugc1": "A", "coop": "B", "sfo": "C"}.get(source_id, "B")

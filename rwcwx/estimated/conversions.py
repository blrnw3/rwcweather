"""Versioned conversions from nearby daily observations to this site.

Version v2 was fitted on the overlap of our measured daily series (from 27 Dec 2020)
with Pulgas Ridge RAWS (PUGC1, IEM daily), using leave-one-year-out cross-validation
on calendar years 2021-2026. Full comparison tables live with the research that produced
these coefficients.

Blend (v2), 1 Jan 2011 through 26 Dec 2020 only — Pulgas Ridge PUGC1 for every variable:
  Tmax  — PUGC1 monthly linear
  Tmin  — PUGC1 monthly linear
  rain  — PUGC1 annual ratio

Days or variables missing from Pulgas are left unestimated (no gap-fill). Inputs and
outputs are in this site's native units: temperature in °C, rain in inches. Source
temperatures published in °F must be converted to °C before apply().

Climate normals stay measured-only.
"""
from __future__ import annotations

from typing import Dict, Mapping, Optional, Tuple

# Bump this and add a new param set when the models are refitted.
VERSION = "v2"

# Inclusive generation window for this version.
PERIOD_START = "2011-01-01"
PERIOD_END = "2020-12-26"

# First day of our own measured daily series; estimates are not written on or after this date.
MEASURED_START = "2020-12-27"

# Leave-one-year-out CV RMSE on the 2021-2026 overlap (for documentation / confidence).
# Temperature in °C, rain in inches. COOP Tmax is retained for comparison with v1.
CV_RMSE = {
    ("pugc1", "tmax", "linear"): 2.04,
    ("pugc1", "tmin", "linear"): 1.06,
    ("pugc1", "rain", "ratio"): 0.047,
    ("coop", "tmax", "linear"): 1.41,  # v1 Tmax source; not used in v2
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

# Annual rain ratio = our_total / source_total on the overlap days both series reported.
# Applied every month (monthly ratios were noisier, especially in the dry season).
PUGC1_RAIN_RATIO = 133.81 / 143.91          # 0.929817...

# Primary only. Each entry is a chain of (source_id, method); v2 has a single source.
BLEND = {
    ("temp", "max"): (("pugc1", "linear"),),
    ("temp", "min"): (("pugc1", "linear"),),
    ("rain", "total"): (("pugc1", "ratio"),),
}

PARAMS = {
    ("pugc1", "tmax", "linear"): PUGC1_TMAX_LINEAR,
    ("pugc1", "tmin", "linear"): PUGC1_TMIN_LINEAR,
    ("pugc1", "rain", "ratio"): PUGC1_RAIN_RATIO,
}

SOURCE_VAR = {
    ("pugc1", "temp", "max"): "tmax",
    ("pugc1", "temp", "min"): "tmin",
    ("pugc1", "rain", "total"): "rain",
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
    return "A"

"""Sunshine-from-webcam inference (numpy + Pillow only; see PLAN in the sunshine research notes).

features.py  per-frame features (192x108 downsample)
solar.py     NOAA solar position
model.py     JSON logistic-regression artifacts
rules.py     gates, median filter, low-sun rule R3, daylight weighting
"""

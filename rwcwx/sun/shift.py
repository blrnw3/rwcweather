"""Camera-pointing monitor: phase correlation of the foreground edge map (gable, trees) against a reference.

The models were trained on one fixed view. If the camera is knocked, the regional features move and the
classifier silently degrades, so the health JSON reports the shift and flags it above SHIFT_WARN_PX."""
import os
from typing import Tuple

import numpy as np
from PIL import Image

from rwcwx.sun.model import MODEL_DIR

W, H = 192, 108
REF_PATH = os.path.join(MODEL_DIR, "reference_edges.png")
SHIFT_WARN_PX = 2.0      # at 192 px width (~16 px at full 1560 px)
PEAK_WARN = 0.35         # clear days score 0.6-0.85; a moved/zoomed view drops below this


def edge_map(img: Image.Image) -> np.ndarray:
    g = np.asarray(img.convert("L").resize((W, H), Image.BILINEAR), np.float32) / 255.
    gx = np.zeros_like(g)
    gy = np.zeros_like(g)
    gx[:, 1:] = np.abs(np.diff(g, axis=1))
    gy[1:, :] = np.abs(np.diff(g, axis=0))
    e = gx + gy
    e[: int(H * 0.35)] = 0          # sky changes with clouds; use the foreground only
    return e


def save_reference(img: Image.Image, path: str = REF_PATH) -> None:
    e = edge_map(img)
    Image.fromarray(np.clip(e / max(e.max(), 1e-6) * 255, 0, 255).astype(np.uint8)).save(path, optimize=True)


def load_reference(path: str = REF_PATH) -> np.ndarray:
    return np.asarray(Image.open(path), np.float32) / 255.


def phase_shift(a: np.ndarray, b: np.ndarray) -> Tuple[float, float, float]:
    """(dx, dy, peak) such that b ~= a shifted by (dx, dy). peak ~1 for a clean match, small for no match."""
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    fa, fb = np.fft.fft2((a - a.mean()) * win), np.fft.fft2((b - b.mean()) * win)
    r = fb * np.conj(fa)
    r /= np.abs(r) + 1e-9
    c = np.real(np.fft.ifft2(r))
    dy, dx = np.unravel_index(np.argmax(c), c.shape)
    if dy > a.shape[0] // 2:
        dy -= a.shape[0]
    if dx > a.shape[1] // 2:
        dx -= a.shape[1]
    return float(dx), float(dy), float(c.max())


def camera_shift(img: Image.Image) -> dict:
    dx, dy, peak = phase_shift(load_reference(), edge_map(img))
    return dict(dx=dx, dy=dy, peak=round(peak, 3), moved=bool(max(abs(dx), abs(dy)) >= SHIFT_WARN_PX or peak < PEAK_WARN))

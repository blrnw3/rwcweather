"""scripts/fog_judge.py: answer parsing, pixel gates, frame selection and the no-default-secrets rule."""
import importlib.util
import io
import os
from datetime import date

import numpy as np
import pytest
from PIL import Image

_spec = importlib.util.spec_from_file_location(
    "fog_judge", os.path.join(os.path.dirname(__file__), "..", "scripts", "fog_judge.py"))
fj = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fj)


def jpeg(arr):
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.uint8)).save(buf, "JPEG", quality=95)
    return buf.getvalue()


def test_parse_answer():
    a = fj.parse_answer('Sure: {"fog": "Yes", "confidence": 0.9, "reason": "Dense fog"}')
    assert a == dict(answer="yes", confidence=0.9, reason="Dense fog")
    assert fj.parse_answer('{"fog":"unusable","confidence":1,"reason":"IR"}')["answer"] == "unusable"
    for bad in ("no json", '{"fog": "maybe", "confidence": 0.5}', '{"fog": "no", "confidence": 2}'):
        with pytest.raises(ValueError):
            fj.parse_answer(bad)


def test_pixel_gate_ir_vs_grey_fog():
    rng = np.random.default_rng(0)
    g = rng.integers(60, 200, (200, 360)).astype(np.float32)
    ir = np.stack([g, g, g], -1)
    assert fj.pixel_gate(jpeg(ir)) == "ir"
    fog = np.stack([g + 6, g + 8, g + 14], -1)     # dull, low-saturation but not exactly grey
    assert fj.pixel_gate(jpeg(fog)) is None
    pink = fog.copy()
    pink[100:, :, :] = (200, 120, 200)
    assert fj.pixel_gate(jpeg(pink)) == "glitch"


def test_unreadable_frame_is_corrupt_not_a_crash(monkeypatch):
    assert fj.pixel_gate(b"not a jpeg") == "corrupt"
    assert fj.pixel_gate(jpeg(np.full((200, 360, 3), 120))[:200]) in ("corrupt", "ir")   # truncated
    rng = np.random.default_rng(1)

    def good():                                                       # distinct frames that pass the gates
        g = rng.integers(60, 200, (200, 360)).astype(np.float32)
        return jpeg(np.stack([g + 6, g + 8, g + 14], -1))
    frames = iter([None, b"\x00garbage"])                           # pre-window frame, then the first in-window one
    monkeypatch.setattr(fj, "fetch", lambda s, url: next(frames, None) or good())
    calls = []
    rows = fj.day_rows(date(2025, 12, 15), None, "https://x", lambda b: calls.append(1) or
                       dict(answer="no", confidence=0.9, reason="ok"))
    assert rows[0]["flags"] == "corrupt" and rows[0]["fog"] is None
    assert rows[1]["fog"] is False and len(calls) == len(rows) - 1      # the run carried on, corrupt not judged


def test_corrupt_flag_is_a_gate():
    assert fj.rules.decide(True, 0.99, "corrupt", 0).value is None


def test_window_and_urls():
    fr = fj.rules.window_frames(date(2025, 12, 15))
    assert fj.frame_url("https://x/sky_lg/", fr[0]) == "https://x/sky_lg/20251215_1600.jpg"


def test_model_version_tracks_prompt():
    mv = fj.model_version("some-vision-model")
    assert mv.startswith("llmj2-some-vision-model-") and len(mv) <= 32


def test_no_default_secrets(monkeypatch):
    for k in ("FOG_LLM_API_KEY", "FOG_LLM_MODEL", "RWC_INGEST_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SystemExit):
        fj.Judge(None)
    with pytest.raises(SystemExit):
        fj.post(None, [], "mv", "live")
    src = open(os.path.join(os.path.dirname(__file__), "..", "scripts", "fog_judge.py")).read().lower()
    assert "roboflow" not in src.replace("never uses roboflow", "")


def test_frozen_gate_includes_frame_before_window(monkeypatch):
    """A frozen run that spans midnight: the day's first frame equals the pre-window frame, so it is gated."""
    rng = np.random.default_rng(1)
    g = rng.integers(60, 200, (120, 200)).astype(np.float32)
    frozen = jpeg(np.stack([g + 6, g + 8, g + 14], -1))
    d = date(2026, 7, 20)
    frames = fj.rules.window_frames(d)
    fresh = {frames[-1]: jpeg(np.stack([g + 30, g + 8, g], -1))}   # camera back for the last frame
    by_url = {fj.frame_url("B", t): fresh.get(t, frozen) for t in frames}
    by_url[fj.frame_url("B", frames[0] - fj.timedelta(minutes=fj.rules.FRAME_MIN))] = frozen
    calls = []
    monkeypatch.setattr(fj, "fetch", lambda s, url: by_url.get(url))

    def judge(data):
        calls.append(data)
        return dict(answer="no", confidence=0.9, reason="clear")
    rows = fj.day_rows(d, None, "B", judge)
    assert [r["flags"] for r in rows[:-1]] == ["frozen"] * (len(frames) - 1)
    assert rows[-1]["flags"] is None and rows[-1]["fog"] is False and len(calls) == 1


def test_first_frame_judged_when_no_frame_before(monkeypatch):
    d = date(2026, 7, 20)
    frames = fj.rules.window_frames(d)
    rng = np.random.default_rng(2)
    imgs = {}
    for t in frames:
        rg = rng.integers(60, 200, (60, 80))
        imgs[fj.frame_url("B", t)] = jpeg(np.stack([rg, rg, rng.integers(0, 60, (60, 80))], -1))
    monkeypatch.setattr(fj, "fetch", lambda s, url: imgs.get(url))
    rows = fj.day_rows(d, None, "B", lambda data: dict(answer="no", confidence=0.9, reason="clear"))
    assert all(r["flags"] is None for r in rows)

#!/usr/bin/env python3
"""Fog judge client for the Weather bot (research/fog/PIPELINE_PLAN.md).

For each local day it takes the 30-minute webcam archive frames from dawn (sun >= 5 deg) to 1 pm PT, gates out
missing / frozen / IR / glitched frames with pixel checks, asks a vision LLM (OpenAI-compatible chat API) the
scripts/fog_judge_prompt.txt question, and POSTs the answers to the rwcweather backend (POST /api/inferred/fog).
The backend applies the 0.85 threshold and the rain veto and rolls up the daily fog hours / fog day.

Never uses Roboflow. Needs: requests, numpy, Pillow, python-dateutil; run from the repo root (imports rwcwx.fog.rules).

Environment (nothing secret has a default):
  RWC_INGEST_TOKEN    bearer token for the backend endpoint (required unless --no-post / --dry-run)
  FOG_LLM_API_KEY     API key for the vision LLM (required unless --dry-run)
  FOG_LLM_MODEL       model name, e.g. a vision-capable chat model (required unless --dry-run)
  FOG_LLM_BASE_URL    OpenAI-compatible base URL (default https://api.openai.com/v1)
  RWC_API_BASE        backend base URL (default https://rwcweather.com)
  RWC_FRAME_BASE      archive base URL (default https://rwcweather.com/cumulus/camdump/sky_lg)

Usage:
  python3 scripts/fog_judge.py                       # today (local), after sunset
  python3 scripts/fog_judge.py --date 2025-12-15
  python3 scripts/fog_judge.py --from 2021-09-09 --to 2026-10-15 --source backfill --cache out/fog_cache
  python3 scripts/fog_judge.py --from 2021-09-09 --to 2026-10-15 --dry-run   # frames + gates only: no LLM, no post
Results per day are cached as JSON (with --cache) so a backfill can resume and re-post without re-paying the LLM.
"""
import argparse
import base64
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import requests
from PIL import Image, ImageFile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rwcwx.fog import rules  # noqa: E402

ImageFile.LOAD_TRUNCATED_IMAGES = True
PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fog_judge_prompt.txt")
SEND_WIDTH = 1024
IR_GREY = 0.01        # mean |R-B| + |R-G|: IR night frames are exactly grey (e2_20: 0.000; day frames >= 0.03)
GLITCH_PINK = 0.05    # pastel magenta encoder smear over the foreground (same cue as the sun job)
GLITCH_MAGENTA = 0.02
MAX_POST_ROWS = 400


def prompt_text() -> str:
    with open(PROMPT_PATH) as f:
        return f.read()


def model_version(model: str) -> str:
    sha = hashlib.sha256(prompt_text().encode()).hexdigest()[:8]
    return f"llmj2-{re.sub(r'[^A-Za-z0-9.-]', '', model)[:18]}-{sha}"[:32]


def frame_url(base: str, t: datetime) -> str:
    return f"{base.rstrip('/')}/{t:%Y%m%d_%H%M}.jpg"


def fetch(session: requests.Session, url: str) -> Optional[bytes]:
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return None


def pixel_gate(data: bytes) -> Optional[str]:
    """'corrupt' | 'ir' | 'glitch' | None. Fog itself is low-saturation, so IR is detected as *exactly* grey, not just
    dull. A frame Pillow can't decode (truncated / garbage bytes) is 'corrupt' so the run carries on."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            a = np.asarray(im.convert("RGB").resize((192, 108), Image.BILINEAR), np.float32) / 255.
    except (OSError, ValueError, Image.DecompressionBombError):
        return "corrupt"
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    if np.abs(R - B).mean() + np.abs(R - G).mean() < IR_GREY:
        return "ir"
    Rb, Gb, Bb = R[54:], G[54:], B[54:]
    pink = ((Rb - Gb > 0.08) & (Bb - Gb > 0.08) & (np.minimum(Rb, Bb) > 0.45)).mean()
    magenta = ((R > 0.6) & (B > 0.6) & (G < 0.45)).mean()
    if pink > GLITCH_PINK or magenta > GLITCH_MAGENTA:
        return "glitch"
    return None


def downscale_jpeg(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        if im.width > SEND_WIDTH:
            im = im.resize((SEND_WIDTH, round(im.height * SEND_WIDTH / im.width)), Image.BILINEAR)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
        return buf.getvalue()


def parse_answer(text: str) -> Dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in reply")
    j = json.loads(m.group(0))
    ans = str(j.get("fog", "")).strip().lower()
    if ans not in ("yes", "no", "unusable"):
        raise ValueError(f"bad fog value {ans!r}")
    conf = float(j.get("confidence"))
    if not 0 <= conf <= 1:
        raise ValueError("confidence out of range")
    return dict(answer=ans, confidence=round(conf, 3), reason=str(j.get("reason", "")).strip()[:255])


class Judge:
    def __init__(self, session: requests.Session):
        self.key = os.environ.get("FOG_LLM_API_KEY", "")
        self.model = os.environ.get("FOG_LLM_MODEL", "")
        if not self.key or not self.model:
            sys.exit("FOG_LLM_API_KEY and FOG_LLM_MODEL must be set (no defaults)")
        self.url = os.environ.get("FOG_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
        self.session = session
        self.prompt = prompt_text()
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

    def __call__(self, jpeg: bytes) -> Dict:
        img = "data:image/jpeg;base64," + base64.b64encode(downscale_jpeg(jpeg)).decode()
        body = dict(model=self.model, temperature=0, max_tokens=200, messages=[dict(role="user", content=[
            dict(type="text", text=self.prompt), dict(type="image_url", image_url=dict(url=img))])])
        last = None
        for attempt in range(2):     # one retry on a malformed answer or transient error
            try:
                r = self.session.post(self.url, json=body, timeout=90,
                                      headers={"Authorization": f"Bearer {self.key}"})
                if r.status_code == 429 or r.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {r.status_code}")
                r.raise_for_status()
                j = r.json()
                self.calls += 1
                u = j.get("usage") or {}
                self.tokens_in += u.get("prompt_tokens", 0)
                self.tokens_out += u.get("completion_tokens", 0)
                return parse_answer(j["choices"][0]["message"]["content"])
            except (requests.RequestException, ValueError, KeyError, TypeError) as e:
                last = e
                time.sleep(3 * (attempt + 1))
        return dict(answer=None, confidence=None, reason=f"judge error: {str(last)[:200]}")


def day_rows(d: date, session: requests.Session, frame_base: str, judge: Optional[Judge]) -> List[Dict]:
    rows, prev_md5 = [], None
    for t in rules.window_frames(d):
        row = dict(t=t.strftime("%Y-%m-%dT%H:%M:%SZ"), fog=None, confidence=None, reason=None, flags=None)
        data = fetch(session, frame_url(frame_base, t))
        if data is None:
            row["flags"] = "missing"
            rows.append(row)
            continue
        md5 = hashlib.md5(data).hexdigest()
        gate = "frozen" if md5 == prev_md5 else pixel_gate(data)
        prev_md5 = md5
        if gate:
            row["flags"] = gate
        elif judge is not None:
            a = judge(data)
            row.update(confidence=a["confidence"], reason=a["reason"])
            if a["answer"] is None:
                row["flags"] = "judge_err"
            elif a["answer"] == "unusable":
                row["flags"] = "unusable"
            else:
                row["fog"] = a["answer"] == "yes"
        rows.append(row)
    return rows


def post(session: requests.Session, rows: List[Dict], mv: str, source: str) -> Dict:
    token = os.environ.get("RWC_INGEST_TOKEN", "")
    if not token:
        sys.exit("RWC_INGEST_TOKEN must be set to post (or use --no-post)")
    url = os.environ.get("RWC_API_BASE", "https://rwcweather.com").rstrip("/") + "/api/inferred/fog"
    out = dict(counts={}, days=[])
    for i in range(0, len(rows), MAX_POST_ROWS):
        r = session.post(url, json=dict(model_version=mv, source=source, rows=rows[i:i + MAX_POST_ROWS]),
                         headers={"Authorization": f"Bearer {token}"}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"POST {url} -> {r.status_code}: {r.text[:300]}")
        j = r.json()
        for k, v in j.get("counts", {}).items():
            out["counts"][k] = out["counts"].get(k, 0) + v
        out["days"] += j.get("days", [])
    return out


def today_local() -> date:
    from dateutil import tz
    return datetime.now(tz.gettz("America/Los_Angeles")).date()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--date", type=date.fromisoformat)
    ap.add_argument("--from", dest="start", type=date.fromisoformat)
    ap.add_argument("--to", dest="end", type=date.fromisoformat)
    ap.add_argument("--source", choices=("live", "backfill"), default="live")
    ap.add_argument("--dry-run", action="store_true", help="fetch + gate only: no LLM calls, no POST")
    ap.add_argument("--no-post", action="store_true", help="judge but print instead of posting")
    ap.add_argument("--cache", help="directory for per-day JSON results (resume / re-post without re-judging)")
    a = ap.parse_args(argv)
    if a.start:
        days = [a.start + timedelta(days=i) for i in range(((a.end or today_local()) - a.start).days + 1)]
    else:
        days = [a.date or today_local()]
    session = requests.Session()
    session.headers["User-Agent"] = "rwcweather-fog-judge/1"
    frame_base = os.environ.get("RWC_FRAME_BASE", "https://rwcweather.com/cumulus/camdump/sky_lg")
    judge = None if a.dry_run else Judge(session)
    mv = model_version(judge.model) if judge else "dry-run"
    if a.cache:
        os.makedirs(a.cache, exist_ok=True)
    tot = dict(days=0, frames=0, gated=0, judged=0, fog_yes=0, errors=0)
    t0 = time.time()
    for d in days:
        cpath = os.path.join(a.cache, f"{d.isoformat()}.json") if a.cache else None
        if cpath and os.path.exists(cpath) and not a.dry_run:
            with open(cpath) as f:
                cached = json.load(f)
            rows = cached["rows"] if cached.get("model_version") == mv else None
        else:
            rows = None
        if rows is None:
            rows = day_rows(d, session, frame_base, judge)
            if cpath and not a.dry_run:
                with open(cpath, "w") as f:
                    json.dump(dict(model_version=mv, rows=rows), f)
        tot["days"] += 1
        tot["frames"] += len(rows)
        tot["gated"] += sum(1 for r in rows if r["flags"] in rules.GATE_FLAGS and r["flags"] != "judge_err")
        tot["judged"] += sum(1 for r in rows if r["fog"] is not None)
        tot["fog_yes"] += sum(1 for r in rows if r["fog"] and (r["confidence"] or 0) >= rules.THRESHOLD)
        tot["errors"] += sum(1 for r in rows if r["flags"] == "judge_err")
        if a.dry_run or a.no_post:
            for r in rows:
                print(json.dumps(dict(r, d=d.isoformat())))
        else:
            res = post(session, rows, mv, a.source)
            print(json.dumps(dict(d=d.isoformat(), counts=res["counts"], days=res["days"])))
    tot["elapsed_s"] = round(time.time() - t0, 1)
    if judge:
        tot.update(llm_calls=judge.calls, tokens_in=judge.tokens_in, tokens_out=judge.tokens_out, model_version=mv)
    print(json.dumps(dict(summary=tot)), file=sys.stderr)


if __name__ == "__main__":
    main()

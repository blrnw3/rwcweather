"""POST /api/inferred/fog: the Weather bot's fog-judge client posts judged frames here.

Auth: "Authorization: Bearer <token>", compared in constant time with the RWC_INGEST_TOKEN environment variable.
There is no default: if RWC_INGEST_TOKEN is unset or empty the endpoint answers 503 and writes nothing.

Body (JSON, <= MAX_BYTES, <= MAX_ROWS rows):
  {"model_version": "llmj2-<model>-<prompt sha8>", "source": "live" | "backfill",
   "rows": [{"t": "2026-01-05T16:00:00Z", "fog": true|false|null, "confidence": 0.92, "reason": "...", "flags": "ir"}]}
t is the frame time in UTC (archive filename time). fog=null (or a gate flag) means not judged.
"""
from datetime import datetime, timedelta

from dateutil import parser as dtparser
from dateutil.tz import UTC
from flask import jsonify, request

from rwcwx import logger
from rwcwx.fog import rules, store
from rwcwx.ingest_auth import TOKEN_ENV, authorized, check as check_auth, error as _err  # noqa: F401

MAX_ROWS = 500
MAX_BYTES = 1_000_000


class BadRequest(ValueError):
    pass


def parse_time(raw) -> datetime:
    if not isinstance(raw, str) or not raw:
        raise BadRequest("t must be an ISO 8601 UTC string")
    try:
        t = dtparser.isoparse(raw)
    except ValueError:
        raise BadRequest(f"bad t: {raw!r}")
    if t.tzinfo is None:
        raise BadRequest(f"t must carry a zone (use Z): {raw!r}")
    t = t.astimezone(UTC).replace(tzinfo=None)
    if t.second or t.microsecond or t.minute % rules.FRAME_MIN:
        raise BadRequest(f"t must be on a {rules.FRAME_MIN}-minute boundary: {raw!r}")
    return t


def parse_body(body, now_utc: datetime) -> dict:
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    mv = body.get("model_version")
    if not isinstance(mv, str) or not mv.strip() or len(mv) > 32:
        raise BadRequest("model_version required (<= 32 chars)")
    source = body.get("source", "live")
    if source not in store.SOURCES:
        raise BadRequest(f"source must be one of {store.SOURCES}")
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        raise BadRequest("rows must be a non-empty list")
    if len(rows) > MAX_ROWS:
        raise BadRequest(f"at most {MAX_ROWS} rows per request")
    out, seen = [], set()
    for r in rows:
        if not isinstance(r, dict):
            raise BadRequest("each row must be an object")
        t = parse_time(r.get("t"))
        if t > now_utc + timedelta(minutes=5):
            raise BadRequest(f"t is in the future: {r.get('t')}")
        if t in seen:
            raise BadRequest(f"duplicate t: {r.get('t')}")
        seen.add(t)
        fog = r.get("fog")
        if fog is not None and not isinstance(fog, bool):
            raise BadRequest("fog must be true, false or null")
        conf = r.get("confidence")
        if conf is not None:
            if isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
                raise BadRequest("confidence must be a number in [0, 1]")
            conf = float(conf)
        reason = r.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise BadRequest("reason must be a string")
        flags = r.get("flags")
        if flags is not None and not isinstance(flags, str):
            raise BadRequest("flags must be a comma-separated string")
        out.append(dict(t=t, fog=fog, confidence=conf, reason=(reason or "").strip()[:rules.NOTE_MAX] or None,
                        flags=flags))
    return dict(model_version=mv.strip(), source=source, rows=sorted(out, key=lambda x: x["t"]))


def post_fog():
    denied = check_auth(MAX_BYTES)
    if denied is not None:
        return denied
    try:
        parsed = parse_body(request.get_json(force=True, silent=True), datetime.utcnow())
    except BadRequest as e:
        return _err(400, str(e))
    res = store.ingest(parsed["rows"], parsed["model_version"], parsed["source"])
    counts = {}
    for r in res["rows"]:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    logger.info(f"fog ingest: {len(parsed['rows'])} rows {counts} source={parsed['source']} "
                f"model={parsed['model_version']} days={[d['d'] for d in res['days']]}")
    return jsonify(counts=counts, days=res["days"],
                   rows=[dict(r, t=r["t"].strftime("%Y-%m-%dT%H:%M:%SZ")) for r in res["rows"]])

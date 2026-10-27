"""Recap endpoints.

POST /api/recap             ingest one recap (bearer token, see rwcwx.ingest_auth); upserts on (kind, period).
POST /api/recap?dry_run=1   validate and normalise only: returns the record (and its rendering) and writes nothing;
                            needs no DB, so it works before the table exists.
GET  /api/recap/latest      public: the latest entry of each kind with its parsed blocks and a `fresh` flag.

Payload and validation rules: rwcwx.recap.rules. Markdown subset: rwcwx.recap.markdown.
"""
from datetime import datetime
from typing import Optional

from flask import jsonify, request

from rwcwx import logger
from rwcwx.ingest_auth import check as check_auth, error, flag
from rwcwx.recap import markdown, rules, store

MAX_BYTES = 16_384


def _iso(t: Optional[datetime]) -> Optional[str]:
    return None if t is None else t.replace(microsecond=0).isoformat() + "Z"


def public(rec: dict, today) -> dict:
    blocks = markdown.parse(rec["body_md"])
    out = dict(kind=rec["kind"], period=rec["period"], body_md=rec["body_md"], blocks=blocks,
               generated_at=_iso(rec.get("generated_at")), fresh=rules.is_fresh(rec["kind"], rec["period"], today))
    if rec.get("t_mod") is not None:
        out["updated_at"] = _iso(rec["t_mod"])
    return out


def _now() -> datetime:
    return datetime.utcnow()     # naive UTC; patched in tests


def _server(now_utc: datetime) -> dict:
    today = rules.local_today(now_utc)
    return dict(date=(today.year, today.month, today.day), now=_iso(now_utc.replace(tzinfo=None)))


def post_recap():
    denied = check_auth(MAX_BYTES)
    if denied is not None:
        return denied
    now_utc = _now()
    try:
        parsed = rules.validate(request.get_json(force=True, silent=True), now_utc)
    except rules.BadRequest as e:
        return error(400, str(e))
    rec, today = parsed["record"], rules.local_today(now_utc)
    out = dict(record=public(rec, today), html=markdown.to_html(markdown.parse(rec["body_md"])),
               ignored=parsed["ignored"])
    if flag("dry_run"):
        return jsonify(status="dry_run", dry_run=True, **out)
    try:
        status = store.upsert(rec, now_utc)
    except store.TableMissing as e:
        return error(503, str(e))
    logger.info(f"recap ingest: {rec['kind']} {rec['period']} {status} ({len(rec['body_md'])} chars, "
                f"generated {_iso(rec['generated_at'])})")
    return jsonify(status=status, dry_run=False, **out)


def get_latest():
    now_utc = _now()
    today = rules.local_today(now_utc)
    rows = store.latest()
    result = {k: (public(rows[k], today) if rows and k in rows else None) for k in rules.KINDS}
    result["available"] = rows is not None
    result["expected"] = {k: rules.expected_period(k, today) for k in rules.KINDS}
    resp = jsonify(result=result, server=_server(now_utc))
    resp.headers["Cache-Control"] = "public, max-age=60"
    return resp

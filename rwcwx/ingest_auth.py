"""Bearer-token auth shared by the ingest endpoints (POST /api/inferred/fog, POST /api/recap).

"Authorization: Bearer <token>", compared in constant time with the RWC_INGEST_TOKEN environment variable
(set in /etc/rwcwx.env on prod). There is no default: if it is unset or empty the endpoints answer 503.
Imports nothing from the DB layer, so it can be used (and tested) without MySQL.
"""
import hmac
import os
from typing import Optional

from flask import jsonify, request

TOKEN_ENV = "RWC_INGEST_TOKEN"


def error(code: int, msg: str, **extra):
    resp = jsonify(error=msg, **extra)
    resp.status_code = code
    return resp


def authorized(header: str, token: str) -> bool:
    if not token or not header or not header.startswith("Bearer "):
        return False
    return hmac.compare_digest(header[len("Bearer "):].strip().encode(), token.encode())


def check(max_bytes: int):
    """None if the current request is authorized and its body size is acceptable, else the error response."""
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        return error(503, "ingest disabled: server token not configured")
    if not authorized(request.headers.get("Authorization", ""), token):
        return error(401, "unauthorized")
    if request.content_length is None or request.content_length > max_bytes:
        return error(413, f"body required and must be <= {max_bytes} bytes")
    return None


def flag(name: str) -> Optional[bool]:
    """Query-string boolean (?dry_run=1 / true / yes)."""
    v = request.args.get(name)
    return None if v is None else v.strip().lower() in ("1", "true", "yes", "on")

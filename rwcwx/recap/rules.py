"""Recap records: payload validation and staleness. Pure (no DB, no Flask), so it is tested without MySQL.

Payload (JSON object):
  kind          "day" | "month_to_date" | "month"
  period        "YYYY-MM-DD" for day; "YYYY-MM" for month_to_date and month (station-local / PT calendar)
  body_md       markdown subset (see recap.markdown), <= MAX_BODY characters and <= MAX_LINES lines
  generated_at  ISO 8601 with a zone, e.g. "2026-10-27T15:20:00Z" or "2026-10-27T08:20:00-07:00"

Rules (today = the station's local date, America/Los_Angeles):
  day            period <= today
  month_to_date  period <= this month
  month          period <  this month (a finished month)
  all periods >= 2020-11 (the station's first month); generated_at at most 10 minutes in the future.
Unknown keys are ignored (and listed in the response).

Staleness for display: a day entry is fresh for periods >= today - 2 days; month_to_date only for this month;
month only for last month.
"""
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional

from dateutil import parser as dtparser
from dateutil.tz import UTC

from rwcwx.config import TZ

KINDS = ("day", "month_to_date", "month")
FIELDS = ("kind", "period", "body_md", "generated_at")
MAX_BODY = 1500
MAX_LINES = 30
MAX_FUTURE = timedelta(minutes=10)
FIRST_MONTH = (2020, 11)
DAY_FRESH_DAYS = 2
DAY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
# Bidi overrides / isolates can make text render differently from what was written.
BIDI = set("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


class BadRequest(ValueError):
    pass


def local_today(now_utc: datetime) -> date:
    """Station-local (PT) date of a naive-UTC or aware datetime."""
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    return now_utc.astimezone(TZ).date()


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def prev_month(d: date) -> date:
    return (d.replace(day=1) - timedelta(days=1)).replace(day=1)


def parse_period(kind: str, period) -> date:
    """date of the period (the 1st for the month kinds); raises BadRequest on a bad format."""
    if not isinstance(period, str):
        raise BadRequest("period must be a string")
    if kind == "day":
        m = DAY_RE.match(period)
        if not m:
            raise BadRequest(f"period for kind 'day' must be YYYY-MM-DD: {period!r}")
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            raise BadRequest(f"not a calendar date: {period!r}")
    m = MONTH_RE.match(period)
    if not m:
        raise BadRequest(f"period for kind '{kind}' must be YYYY-MM: {period!r}")
    if not 1 <= int(m.group(2)) <= 12:
        raise BadRequest(f"not a month: {period!r}")
    return date(int(m.group(1)), int(m.group(2)), 1)


def clean_body(raw) -> str:
    if not isinstance(raw, str):
        raise BadRequest("body_md must be a string")
    body = raw.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    body = "\n".join(line.rstrip() for line in body.split("\n")).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    if not body:
        raise BadRequest("body_md must not be empty")
    if len(body) > MAX_BODY:
        raise BadRequest(f"body_md is {len(body)} characters; at most {MAX_BODY}")
    if body.count("\n") + 1 > MAX_LINES:
        raise BadRequest(f"body_md has more than {MAX_LINES} lines")
    for ch in body:
        if ch != "\n" and (unicodedata.category(ch) in ("Cc", "Cs") or ch in BIDI):
            raise BadRequest(f"body_md contains a control character (U+{ord(ch):04X})")
    return unicodedata.normalize("NFC", body)


def parse_generated_at(raw, now_utc: datetime) -> datetime:
    if not isinstance(raw, str) or not raw:
        raise BadRequest("generated_at must be an ISO 8601 string with a zone")
    try:
        t = dtparser.isoparse(raw)
    except (ValueError, OverflowError):
        raise BadRequest(f"bad generated_at: {raw!r}")
    if t.tzinfo is None:
        raise BadRequest(f"generated_at must carry a zone (Z or an offset): {raw!r}")
    t = t.astimezone(UTC).replace(tzinfo=None, microsecond=0)
    if t > now_utc.replace(tzinfo=None) + MAX_FUTURE:
        raise BadRequest(f"generated_at is in the future: {raw!r}")
    return t


def validate(body, now_utc: datetime) -> dict:
    """Normalised record {kind, period, body_md, generated_at (naive UTC)} plus 'ignored' unknown keys."""
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    kind = body.get("kind")
    if kind not in KINDS:
        raise BadRequest(f"kind must be one of {list(KINDS)}")
    pdate = parse_period(kind, body.get("period"))
    today = local_today(now_utc)
    if (pdate.year, pdate.month) < FIRST_MONTH:
        raise BadRequest("period is before the station's records (2020-11)")
    if kind == "day" and pdate > today:
        raise BadRequest(f"period {body['period']} is after today ({today.isoformat()}, PT)")
    if kind == "month_to_date" and pdate > today.replace(day=1):
        raise BadRequest(f"period {body['period']} is after this month ({month_key(today)}, PT)")
    if kind == "month" and pdate >= today.replace(day=1):
        raise BadRequest(f"kind 'month' is for a finished month: period must be before {month_key(today)}")
    rec = dict(kind=kind, period=pdate.isoformat() if kind == "day" else month_key(pdate),
               body_md=clean_body(body.get("body_md")),
               generated_at=parse_generated_at(body.get("generated_at"), now_utc))
    ignored = sorted(k for k in body if k not in FIELDS)
    return dict(record=rec, ignored=ignored)


def is_fresh(kind: str, period: str, today: date) -> bool:
    """Whether an entry should still be shown on the home page on the station-local date `today`."""
    try:
        pdate = parse_period(kind, period)
    except BadRequest:
        return False
    if kind == "day":
        return today - timedelta(days=DAY_FRESH_DAYS) <= pdate <= today
    if kind == "month_to_date":
        return month_key(pdate) == month_key(today)
    if kind == "month":
        return month_key(pdate) == month_key(prev_month(today))
    return False


def expected_period(kind: str, today: date) -> Optional[str]:
    """The period a fresh entry would normally carry today (for placeholders and monitoring)."""
    if kind == "day":
        return (today - timedelta(days=1)).isoformat()
    if kind == "month_to_date":
        return month_key(today)
    if kind == "month":
        return month_key(prev_month(today))
    return None

"""Pure shaping of NWS responses for the home forecast card (no I/O; unit-tested with fixtures).

Units out: temperatures in °C and wind in mph (the site's base units; the frontend converts to the visitor's
unit choice). NWS sends °F and wind as text such as "5 to 10 mph".
"""
import re
from datetime import date, datetime, timedelta
from typing import List, Optional

# SF Peninsula relevance: the Peninsula itself, SF, San Mateo, the Santa Cruz Mountains, the (non-Central) coast and
# coastal hills, beaches, and Bay Area / SF Bay wording. Marine-only lines ("coastal waters") don't count.
PENINSULA_TERMS = re.compile(r"\b(Peninsula|San Francisco|SF|San Mateo|Redwood City|Half Moon Bay|Pacifica|"
                             r"Santa Cruz Mountains|coastal hills|coastal mountains|beach(?:es)?|"
                             r"(?<!Central )(?<!Big Sur )coast(?:al|line)?|Bay Area|SF Bay|Bay shoreline)\b")
NOT_PENINSULA = re.compile(r"coastal waters|\bwaters\b|\bTAF|\bVFR|\bIFR", re.I)
LOCAL_TERMS = PENINSULA_TERMS
MAX_HIGHLIGHTS = 3
MAX_KEY_MESSAGES = 5
MAX_LOCAL_MENTIONS = 3
EXCERPT_CHARS = 600


def f_to_c(f: Optional[float]) -> Optional[float]:
    return None if f is None else round((f - 32) * 5 / 9, 2)


def wind_mph(text: Optional[str]):
    """'5 to 10 mph' -> (5, 10); '10 mph' -> (10, 10); 'Calm'/'' -> (0, 0); unparseable -> (None, None)."""
    if not text:
        return None, None
    if re.match(r"\s*calm", text, re.I):
        return 0, 0
    nums = [int(n) for n in re.findall(r"\d+", text)]
    if not nums or "km" in text.lower():
        return None, None
    return min(nums), max(nums)


def _local_date(iso: str) -> date:
    # NWS times carry the office's own offset (-08:00/-07:00 here), so the date part is the local date.
    return datetime.fromisoformat(iso).date()


def periods(fc: Optional[dict], today: date) -> Optional[List[dict]]:
    """Forecast periods that start today or tomorrow (local), in order."""
    if not fc or not isinstance(fc.get("periods"), list):
        return None
    keep = (today, today + timedelta(days=1))
    out = []
    for p in fc["periods"]:
        try:
            d = _local_date(p["startTime"])
        except (KeyError, TypeError, ValueError):
            continue
        if d not in keep:
            continue
        lo, hi = wind_mph(p.get("windSpeed"))
        temp = p.get("temperature")
        if isinstance(temp, dict):      # quantitative-value form
            temp = temp.get("value")
        if temp is not None and (p.get("temperatureUnit") or "F") == "C":
            temp_c = float(temp)
        else:
            temp_c = f_to_c(temp)
        pop = (p.get("probabilityOfPrecipitation") or {}).get("value")
        out.append(dict(name=p.get("name"), day=0 if d == today else 1, is_daytime=bool(p.get("isDaytime")),
                        start=p.get("startTime"), end=p.get("endTime"), short=p.get("shortForecast"), detailed=p.get("detailedForecast"),
                        temp_c=temp_c, pop=int(pop) if pop is not None else 0,
                        wind_dir=p.get("windDirection") or None, wind_mph_lo=lo, wind_mph_hi=hi,
                        icon=p.get("icon")))
    return out


# ---------------------------------------------------------------- QPF (rain totals)

DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?$")


def _interval(valid_time: str):
    """'2026-11-03T12:00:00+00:00/PT6H' -> (start, end) aware datetimes; None if unparseable."""
    try:
        start_s, dur = valid_time.split("/")
        m = DURATION.match(dur)
        if not m or not any(m.groups()):
            return None
        d, h, mi = (int(g or 0) for g in m.groups())
        start = datetime.fromisoformat(start_s)
        return start, start + timedelta(days=d, hours=h, minutes=mi)
    except (AttributeError, ValueError):
        return None


def qpf_mm(grid: Optional[dict], start_iso: str, end_iso: str) -> Optional[float]:
    """Forecast precipitation (mm) between two times: each QPF interval contributes in proportion to its overlap
    (NWS spreads an interval's amount evenly; 6 h blocks rarely line up with the 6am/6pm periods).
    None when there is no QPF data or it doesn't cover the whole window."""
    q = (grid or {}).get("quantitativePrecipitation") or {}
    vals = q.get("values")
    if not isinstance(vals, list) or not start_iso or not end_iso:
        return None
    factor = 25.4 if "in" == (q.get("uom") or "wmoUnit:mm").split(":")[-1] else 1.0
    try:
        w0, w1 = datetime.fromisoformat(start_iso), datetime.fromisoformat(end_iso)
    except ValueError:
        return None
    total, covered = 0.0, 0.0
    for v in vals:
        iv = _interval((v or {}).get("validTime") or "")
        if iv is None or v.get("value") is None:
            continue
        a, b = max(iv[0], w0), min(iv[1], w1)
        if b <= a:
            continue
        frac = (b - a).total_seconds() / (iv[1] - iv[0]).total_seconds()
        total += float(v["value"]) * factor * frac
        covered += (b - a).total_seconds()
    if covered < (w1 - w0).total_seconds() - 60:
        return None
    return round(total, 2)


def add_qpf(periods_: Optional[List[dict]], grid: Optional[dict]) -> Optional[float]:
    """Set each period's qpf_mm; return the whole window's total (None if any period lacks coverage)."""
    if not periods_:
        return None
    for p in periods_:
        p["qpf_mm"] = qpf_mm(grid, p.get("start"), p.get("end"))
    amounts = [p["qpf_mm"] for p in periods_]
    return None if any(a is None for a in amounts) else round(sum(amounts), 2)


# ---------------------------------------------------------------- AFD

SECTION = re.compile(r"^\.([A-Z][A-Z /&]+?)\.\.\.[ \t]*(.*)$", re.M)


def sections(text: str) -> dict:
    """{'KEY MESSAGES': body, 'SHORT TERM': body, ...}: each '.NAME...' heading up to its '&&' terminator."""
    out = {}
    heads = list(SECTION.finditer(text or ""))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        body = text[m.end():end].split("&&")[0]
        out.setdefault(m.group(1).strip(), (m.group(2) + "\n" + body).strip())
    return out


def _strip_meta(body: str) -> str:
    """Drop 'Issued at …' / 'Updated at …' lines and '(Today and tonight)' sub-headings."""
    lines = [ln for ln in body.splitlines()
             if not re.match(r"\s*(Issued|Updated) at\b", ln) and not re.match(r"\s*\(.*\)\s*$", ln)]
    return "\n".join(lines).strip()


def _paragraphs(body: str) -> List[str]:
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def key_messages(body: Optional[str]) -> List[str]:
    if not body:
        return []
    items = re.split(r"(?m)^\s*[-*]\s+", _strip_meta(body))
    msgs = [re.sub(r"\s+", " ", it).strip() for it in items if it.strip()]
    return msgs[:MAX_KEY_MESSAGES]


SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])")


def sentences(text: str) -> List[str]:
    return [s.strip() for s in SENTENCE.split(text) if s.strip()]


def excerpt(body: Optional[str], limit: int = EXCERPT_CHARS) -> Optional[str]:
    """Whole sentences from the start of a section, up to about `limit` characters."""
    if not body:
        return None
    text = " ".join(_paragraphs(_strip_meta(body)))
    out = ""
    for s in sentences(text):
        if out and len(out) + 1 + len(s) > limit:
            return out + " …"
        out = (out + " " + s).strip()
    if len(out) > limit:
        out = out[:limit].rsplit(" ", 1)[0] + " …"
    return out or None


def is_peninsula(text: str) -> bool:
    return bool(PENINSULA_TERMS.search(text)) and not NOT_PENINSULA.search(text)


def highlights(key_msgs: List[str], local: List[str]) -> (List[str], str):
    """Headline lines for the collapsed card: Peninsula-relevant key messages, then Peninsula-relevant sentences
    from the synopsis / short / long term; general key messages only if nothing Peninsula-relevant exists."""
    pen = [m for m in key_msgs if is_peninsula(m)]
    for s in local:
        if len(pen) >= MAX_HIGHLIGHTS:
            break
        if s not in pen:
            pen.append(s)
    if pen:
        return pen[:MAX_HIGHLIGHTS], "peninsula"
    return key_msgs[:MAX_HIGHLIGHTS], "general"


def local_mentions(*bodies: Optional[str]) -> List[str]:
    """Sentences that name the Peninsula / Bay Area (in order, de-duplicated, capped)."""
    seen, out = set(), []
    for body in bodies:
        if not body:
            continue
        for s in sentences(" ".join(_paragraphs(_strip_meta(body)))):
            if is_peninsula(s) and s not in seen and len(s) <= 300:
                seen.add(s)
                out.append(s)
    return out[:MAX_LOCAL_MENTIONS]


def discussion(product: Optional[dict]) -> Optional[dict]:
    if not product or not product.get("productText"):
        return None
    secs = sections(product["productText"])
    short = secs.get("SHORT TERM")
    long_ = secs.get("LONG TERM")
    synopsis = secs.get("SYNOPSIS") or secs.get("DISCUSSION")
    office = (product.get("issuingOffice") or "KMTR")[-3:]
    kms = key_messages(secs.get("KEY MESSAGES"))
    local = local_mentions(synopsis, short, long_)
    hl, scope = highlights(kms, local)
    return dict(issued=product.get("issuanceTime"), office=office, key_messages=kms,
                highlights=hl, highlights_scope=scope,
                synopsis=excerpt(synopsis), short_term=excerpt(short), long_term=excerpt(long_),
                local=local,
                url=f"https://forecast.weather.gov/product.php?site={office}&issuedby={office}&product=AFD")


# ---------------------------------------------------------------- alerts

SEVERITY_ORDER = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}


def alerts(features: Optional[list]) -> Optional[List[dict]]:
    if features is None:
        return None
    out = []
    for f in features:
        p = (f or {}).get("properties") or {}
        if p.get("status", "Actual") != "Actual" or p.get("messageType") == "Cancel":
            continue
        desc = re.sub(r"\s+", " ", p.get("description") or "").strip()
        out.append(dict(event=p.get("event"), headline=p.get("headline") or p.get("event"),
                        severity=p.get("severity") or "Unknown", onset=p.get("onset"),
                        ends=p.get("ends") or p.get("expires"), sender=p.get("senderName"),
                        description=(desc[:500].rsplit(" ", 1)[0] + " …") if len(desc) > 500 else desc))
    out.sort(key=lambda a: SEVERITY_ORDER.get(a["severity"], 9))
    return out

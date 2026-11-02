"""Pure shaping of NWS responses for the home forecast card (no I/O; unit-tested with fixtures).

Units out: temperatures in °C and wind in mph (the site's base units; the frontend converts to the visitor's
unit choice). NWS sends °F and wind as text such as "5 to 10 mph".
"""
import re
from datetime import date, datetime, timedelta
from typing import List, Optional

LOCAL_TERMS = re.compile(r"\b(Peninsula|San Mateo|Redwood City|Bay Area|SF Bay|San Francisco Bay|"
                         r"Santa Cruz Mountains|Bay shoreline|urban areas?)\b", re.I)
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
                        start=p.get("startTime"), short=p.get("shortForecast"), detailed=p.get("detailedForecast"),
                        temp_c=temp_c, pop=int(pop) if pop is not None else 0,
                        wind_dir=p.get("windDirection") or None, wind_mph_lo=lo, wind_mph_hi=hi,
                        icon=p.get("icon")))
    return out


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


def local_mentions(*bodies: Optional[str]) -> List[str]:
    """Sentences that name the Peninsula / Bay Area (in order, de-duplicated, capped)."""
    seen, out = set(), []
    for body in bodies:
        if not body:
            continue
        for s in sentences(" ".join(_paragraphs(_strip_meta(body)))):
            if LOCAL_TERMS.search(s) and s not in seen and len(s) <= 300:
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
    return dict(issued=product.get("issuanceTime"), office=office,
                key_messages=key_messages(secs.get("KEY MESSAGES")),
                synopsis=excerpt(synopsis), short_term=excerpt(short), long_term=excerpt(long_),
                local=local_mentions(short, long_, synopsis),
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

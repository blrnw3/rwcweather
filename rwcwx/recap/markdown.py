"""A deliberately tiny markdown subset for the recap text, parsed into a safe structure.

Supported, and nothing else:
  * paragraphs (separated by a blank line; consecutive lines join with a space)
  * lists: lines starting "- ", "* " or "+ " (bullets) or "1. " / "1) " (numbered)
  * **bold** (not nested; may contain links)
  * [text](http(s)://...) links, rendered with rel="noopener nofollow"
Everything else (HTML, headings, code, images, _emphasis_, autolinks...) stays literal text. Links whose
target is not a plain http(s) URL are shown as their literal markdown text.

parse() returns JSON-able blocks that the frontend maps to React elements (so text is escaped by React and no
HTML string is ever injected); to_html() renders the same blocks with every text node and attribute escaped.

  blocks  = [{"t": "p", "c": inlines} | {"t": "ul" | "ol", "items": [inlines, ...]}]
  inlines = [{"t": "text", "v": str} | {"t": "b", "c": inlines} | {"t": "a", "href": str, "v": str}]
"""
import html
import re
from typing import List, Optional
from urllib.parse import urlsplit

MAX_URL = 500
LINK_RE = re.compile(r"\[([^\[\]\n]{1,200})\]\(([^()\s]{1,%d})\)" % MAX_URL)
BOLD_RE = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
LIST_RE = re.compile(r"^ {0,3}(?:([-*+])|(\d{1,2})[.)])[ \t]+(\S.*)$")
# Characters never allowed in a link target (quotes, angle brackets, backslash, backtick, whitespace/control).
URL_BAD = re.compile(r"[\x00-\x20\x7f<>\"'`\\]")


def safe_url(url: str) -> Optional[str]:
    """The URL if it is a plain absolute http(s) URL with a host and no credentials, else None."""
    if not url or len(url) > MAX_URL or URL_BAD.search(url):
        return None
    try:
        p = urlsplit(url)
        host = p.hostname
    except ValueError:
        return None
    if p.scheme.lower() not in ("http", "https") or not host or "@" in p.netloc:
        return None
    return url


def _text(out: list, v: str):
    if not v:
        return
    if out and out[-1]["t"] == "text":
        out[-1]["v"] += v
    else:
        out.append({"t": "text", "v": v})


def parse_inline(s: str, bold_ok: bool = True) -> List[dict]:
    out, pos = [], 0
    while pos < len(s):
        lm = LINK_RE.search(s, pos)
        bm = BOLD_RE.search(s, pos) if bold_ok else None
        m = min((x for x in (lm, bm) if x), key=lambda x: x.start(), default=None)
        if m is None:
            _text(out, s[pos:])
            break
        _text(out, s[pos:m.start()])
        if m is bm:
            out.append({"t": "b", "c": parse_inline(m.group(1), bold_ok=False)})
        else:
            href = safe_url(m.group(2))
            if href:
                out.append({"t": "a", "href": href, "v": m.group(1)})
            else:
                _text(out, m.group(0))
        pos = m.end()
    return out


def parse(md: str) -> List[dict]:
    blocks, cur = [], None       # cur: ("p", [lines]) or (list type, [item lines])

    def close():
        nonlocal cur
        if cur:
            kind, parts = cur
            if kind == "p":
                blocks.append({"t": "p", "c": parse_inline(" ".join(parts))})
            else:
                blocks.append({"t": kind, "items": [parse_inline(x) for x in parts]})
        cur = None

    for raw in md.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            close()
            continue
        m = LIST_RE.match(line)
        if m:
            kind = "ul" if m.group(1) else "ol"
            if not cur or cur[0] != kind:
                close()
                cur = (kind, [])
            cur[1].append(m.group(3).strip())
        elif cur and cur[0] != "p" and raw[:1] in (" ", "\t"):
            cur[1][-1] += " " + line.strip()          # indented continuation of a list item
        else:
            if not cur or cur[0] != "p":
                close()
                cur = ("p", [])
            cur[1].append(line.strip())
    close()
    return blocks


def _inline_html(nodes: List[dict]) -> str:
    out = []
    for n in nodes:
        if n["t"] == "text":
            out.append(html.escape(n["v"], quote=True))
        elif n["t"] == "b":
            out.append("<strong>" + _inline_html(n["c"]) + "</strong>")
        elif n["t"] == "a":
            out.append('<a href="%s" rel="noopener nofollow">%s</a>'
                       % (html.escape(n["href"], quote=True), html.escape(n["v"], quote=True)))
    return "".join(out)


def to_html(blocks: List[dict]) -> str:
    out = []
    for b in blocks:
        if b["t"] == "p":
            out.append("<p>" + _inline_html(b["c"]) + "</p>")
        else:
            out.append("<%s>%s</%s>" % (b["t"], "".join("<li>" + _inline_html(i) + "</li>" for i in b["items"]),
                                        b["t"]))
    return "\n".join(out)


def render(md: str) -> str:
    return to_html(parse(md))

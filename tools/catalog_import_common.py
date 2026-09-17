"""Shared, source-agnostic helpers for the bundled rules importers.

The runtime never imports this module.  It keeps network/cache concerns out of
the application while giving every catalog importer the same stable text,
slug, fragment, and retry behavior.
"""
from __future__ import annotations

import html
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


USER_AGENT = "Character Sheet App rules catalog importer/2.0"


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def clean_text(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


class _TextParser(HTMLParser):
    BREAK_TAGS = {
        "br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6",
        "table", "thead", "tbody", "tfoot",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript"}:
            self.ignored += 1
        elif not self.ignored and tag in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.ignored:
            self.ignored -= 1
        elif not self.ignored and tag in self.BREAK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored:
            self.parts.append(data)

    def text(self) -> str:
        return clean_text("".join(self.parts))


def html_text(fragment: str) -> str:
    parser = _TextParser()
    parser.feed(fragment)
    return parser.text()


def element_fragment(source: str, element_id: str) -> str:
    """Return the inner HTML of an element, respecting nested same-name tags."""

    opening = re.search(
        rf'<([a-z][a-z0-9]*)\b[^>]*\bid=["\']{re.escape(element_id)}["\'][^>]*>',
        source,
        re.I,
    )
    if not opening:
        return ""
    tag = opening.group(1)
    token = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.I)
    depth = 1
    for match in token.finditer(source, opening.end()):
        if match.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return source[opening.end() : match.start()]
        elif not match.group(0).rstrip().endswith("/>"):
            depth += 1
    return source[opening.end() :]


def fetch_cached(
    url: str,
    cache_path: Path,
    *,
    refresh: bool = False,
    retries: int = 3,
    pause: float = 0.0,
) -> str:
    if cache_path.exists() and not refresh:
        return cache_path.read_text(encoding="utf-8")
    safe_url = urllib.parse.quote(url, safe=":/?=&%#")
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            request = urllib.request.Request(safe_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", "ignore")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(body, encoding="utf-8")
            if pause:
                time.sleep(pause)
            return body
        except Exception as error:  # pragma: no cover - depends on remote service
            last_error = error
            if attempt + 1 < retries:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


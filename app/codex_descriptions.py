"""Conservative cleanup for imported Spheres Codex prose.

The Spheres wiki places its table of contents, store cards, and large site-wide
navigation tables inside the same ``page-content`` element as the rules.  The
importers intentionally keep a broad capture so rules are not lost when the
site changes, but that broad capture is unpleasant to read in the Codex.

This module is the single boundary between source-shaped text and
Codex-shaped text.  It removes only mechanically identifiable wiki chrome and
normalizes whitespace; it does not paraphrase or otherwise rewrite rules.
Both the runtime catalog and the offline importers use the same functions so a
fresh import and an older bundled catalog have identical presentation.
"""

from __future__ import annotations

import html
import re
from collections.abc import Mapping

from app.text_cleanup import repair_mojibake


_WIKI_NAVIGATION_HEADING = re.compile(
    r"^(?:(?:Spheres of (?:Power|Might|Guile)|Champions of the Spheres) "
    r"by Drop Dead Studios|City of 7 Seraphs by Lost Spheres Publishing)$",
    re.IGNORECASE,
)
_PRICE_LINE = re.compile(r"^\$\d+(?:\.\d{2})?$|^Pay What You Want$", re.IGNORECASE)
_CLASS_STRUCTURE_LINE = re.compile(
    r"^(?:Role|Alignment|Hit Die|Hit Dice|Starting Wealth|Class Skills|"
    r"Skill Ranks(?: Per Level| at Each Level)?|Skill Points(?: at each Level)?|"
    r"Requirements)(?::|$)",
    re.IGNORECASE,
)
_META_PREFIX = re.compile(
    r"^(?:Source|Note|Author(?:'|’)s Note|Wiki Note|Special):",
    re.IGNORECASE,
)
_MECHANICAL_SUMMARY_PREFIX = re.compile(
    r"^(?:This (?:archetype )?(?:requires|may|replaces|alters|modifies)|"
    r"Proficienc(?:y|ies)|Casting|Spell Pool|Spell Points|Combat Training|"
    r"Blended Training)(?::|\b)",
    re.IGNORECASE,
)
_INLINE_SPACE = re.compile(r"[ \t\f\v]+")
_TITLE_TOKEN = re.compile(r"[^a-z0-9]+")


def normalize_codex_text(value: object) -> str:
    """Return stable plain text without changing its words or punctuation."""

    text = repair_mojibake(html.unescape(str(value or "")))
    text = (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
    )
    # The source parser emits a blank line around virtually every HTML block.
    # One newline still preserves every heading/paragraph boundary without the
    # double-spaced, spreadsheet-like wall of text in the Codex.
    lines = (_INLINE_SPACE.sub(" ", line).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line).strip()


def normalize_spheres_class_codex_entry(entry: Mapping[str, object]) -> dict:
    """Copy a Spheres class record with clean Codex description fields.

    Selection statistics, feature data, identifiers, URLs, capabilities, and
    every other imported field pass through unchanged.
    """

    result = dict(entry)
    rules = normalize_codex_text(entry.get("rules_text") or entry.get("description"))
    lines = _without_navigation_footer(_lines(rules))
    body_start = _class_body_start(lines, str(entry.get("name") or ""))
    body = lines[body_start:] if body_start < len(lines) else lines
    if not body:
        body = lines
    body = _without_store_prices(body)

    clean_rules = "\n".join(body).strip()
    description = _class_introduction(body)
    if not description:
        description = _first_readable_excerpt(body)
    if not description:
        description = normalize_codex_text(entry.get("description"))

    result["description"] = description
    result["summary"] = _excerpt(description or clean_rules)
    result["rules_text"] = clean_rules or rules
    return result


def normalize_spheres_archetype_codex_entry(entry: Mapping[str, object]) -> dict:
    """Copy a Spheres archetype record with wiki chrome removed from its prose."""

    result = dict(entry)
    original = normalize_codex_text(entry.get("description") or entry.get("summary"))
    source_lines = _without_foldout_table_of_contents(
        _without_navigation_footer(_lines(original))
    )
    lines = source_lines[
        _archetype_body_start(source_lines, str(entry.get("name") or "")) :
    ]
    if not lines:
        lines = source_lines
    lines = _without_store_prices(lines)

    description = "\n".join(lines).strip() or original
    supplied_summary = normalize_codex_text(entry.get("summary"))
    if _is_readable_summary(supplied_summary):
        summary = _excerpt(supplied_summary)
    else:
        summary = _first_readable_excerpt(lines, prefer_flavor=True)

    result["description"] = description
    result["summary"] = summary or _excerpt(description)
    return result


def _lines(value: str) -> list[str]:
    return [line for line in value.split("\n") if line]


def _without_navigation_footer(lines: list[str]) -> list[str]:
    boundary = next(
        (index for index, line in enumerate(lines) if _WIKI_NAVIGATION_HEADING.fullmatch(line)),
        len(lines),
    )
    return lines[:boundary]


def _without_store_prices(lines: list[str]) -> list[str]:
    """Remove only standalone storefront prices, never surrounding rules.

    Some wiki pages embed a second complete edition after a product card.  The
    edition is useful Codex material, so the normalizer deliberately retains
    its product heading and rules while dropping the mechanically impossible
    ``$19.99``/``Pay What You Want`` line between them.
    """

    return [line for line in lines if not _PRICE_LINE.fullmatch(line)]


def _without_foldout_table_of_contents(lines: list[str]) -> list[str]:
    """Remove Wikidot's inline foldout TOC while retaining leading notes.

    Most pages put the foldout first, but alternate-class-style archetypes can
    place a useful Wiki Note before it.  The first prose paragraph after the
    foldout is the stable boundary between repeated heading labels and rules.
    """

    try:
        start = lines.index("FoldUnfold")
    except ValueError:
        return lines
    if start + 1 >= len(lines) or lines[start + 1] != "Table of Contents":
        return lines
    body = next(
        (
            index
            for index in range(start + 2, len(lines))
            if _looks_like_prose(lines[index]) or _looks_like_short_summary(lines[index])
        ),
        None,
    )
    if body is None:
        return lines[:start]
    return lines[:start] + lines[body:]


def _class_body_start(lines: list[str], name: str) -> int:
    if not lines:
        return 0
    structure_indexes = [
        index for index, line in enumerate(lines) if _CLASS_STRUCTURE_LINE.match(line)
    ]
    structure = structure_indexes[0] if structure_indexes else None
    has_toc = lines[:2] == ["FoldUnfold", "Table of Contents"]
    search_end = (
        min(len(lines), 320)
        if has_toc
        else structure if structure is not None else min(len(lines), 120)
    )
    prices = [index for index in range(search_end) if _PRICE_LINE.fullmatch(lines[index])]
    if prices:
        return _skip_repeated_title(lines, prices[-1] + 1, name)

    # A TOC repeats headings such as "Requirements" before the real prose, so
    # its first apparent structure marker is not a safe body boundary.  Find
    # the first marker immediately preceded by the actual introductory prose.
    if has_toc:
        for candidate in structure_indexes:
            if candidate <= 2 or not _is_intro_line(lines[candidate - 1]):
                continue
            start = candidate
            while start > 2 and _is_intro_line(lines[start - 1]):
                start -= 1
            return start
        source = next(
            (index for index, line in enumerate(lines[2:search_end], 2) if line.startswith("Source:")),
            None,
        )
        if source is not None:
            return source
        prose = next(
            (index for index, line in enumerate(lines[2:search_end], 2) if _looks_like_prose(line)),
            None,
        )
        if prose is not None:
            return prose
        return min(2, len(lines))

    if structure is not None:
        start = structure
        while start > 0 and _is_intro_line(lines[start - 1]):
            start -= 1
        if start < structure:
            return start

    return 0


def _archetype_body_start(lines: list[str], name: str) -> int:
    if not lines:
        return 0
    search_end = min(len(lines), 100)
    prices = [index for index in range(search_end) if _PRICE_LINE.fullmatch(lines[index])]
    first_prose = next(
        (
            index
            for index, line in enumerate(lines[:search_end])
            if _looks_like_prose(line) or _looks_like_short_summary(line)
        ),
        None,
    )
    # A cleaned page can legitimately contain a second edition/store card
    # between two complete versions of its rules.  A price is leading chrome
    # only when no rules prose precedes it; this also makes normalization
    # idempotent when freshly imported catalogs pass through the runtime.
    if prices and first_prose is not None and first_prose < prices[0]:
        prices = []
    if prices:
        # A few pages advertise two source books before the actual archetype.
        # Continue across another short title/price pair, but never across prose.
        start = prices[0] + 1
        while start < search_end:
            if _PRICE_LINE.fullmatch(lines[start]):
                start += 1
                continue
            if start + 1 < search_end and _PRICE_LINE.fullmatch(lines[start + 1]):
                start += 2
                continue
            break
        return _skip_repeated_title(lines, start, name)

    start = 0
    while start < len(lines) and lines[start] in {"FoldUnfold", "Table of Contents", "Ultimate", "Original"}:
        start += 1
    if start and lines[:2] == ["FoldUnfold", "Table of Contents"]:
        source = next(
            (index for index, line in enumerate(lines[start:search_end], start) if line.startswith("Source:")),
            None,
        )
        if source is not None:
            return source
        prose = next(
            (index for index, line in enumerate(lines[start:search_end], start) if _looks_like_prose(line)),
            None,
        )
        if prose is not None:
            return prose
    if start + 1 < len(lines) and lines[start + 1].startswith("Source:"):
        start += 1
    return _skip_repeated_title(lines, start, name)


def _skip_repeated_title(lines: list[str], start: int, name: str) -> int:
    if start >= len(lines) or not name:
        return start
    if _META_PREFIX.match(lines[start]):
        return start
    title = _TITLE_TOKEN.sub(" ", lines[start].casefold()).strip()
    expected = _TITLE_TOKEN.sub(" ", name.casefold()).strip()
    if (
        expected
        and expected in title
        and len(lines[start]) < 180
        and not _looks_like_prose(lines[start])
        and not _looks_like_short_summary(lines[start])
    ):
        return start + 1
    return start


def _class_introduction(lines: list[str]) -> str:
    structure = next(
        (index for index, line in enumerate(lines) if _CLASS_STRUCTURE_LINE.match(line)),
        len(lines),
    )
    candidates = [
        line
        for line in lines[:structure]
        if _looks_like_prose(line) and not _META_PREFIX.match(line)
    ]
    if not candidates:
        candidates = [line for line in lines[:structure] if _looks_like_prose(line)]
    return "\n".join(candidates).strip()


def _looks_like_prose(line: str) -> bool:
    return len(line) >= 45 and len(line.split()) >= 8


def _is_intro_line(line: str) -> bool:
    return (
        _looks_like_prose(line)
        or _looks_like_short_summary(line)
        or bool(_META_PREFIX.match(line))
        or (line.startswith(("“", '"')) and line.endswith(("”", '"')))
    )


def _is_readable_summary(value: str) -> bool:
    if (
        not value
        or value in {"FoldUnfold", "Table of Contents"}
        or bool(_PRICE_LINE.fullmatch(value))
    ):
        return False
    return not _WIKI_NAVIGATION_HEADING.fullmatch(value)


def _first_readable_excerpt(lines: list[str], *, prefer_flavor: bool = False) -> str:
    candidates = [
        line for line in lines
        if _looks_like_prose(line) or _looks_like_short_summary(line)
    ]
    if prefer_flavor:
        flavored = [
            line
            for line in candidates[:3]
            if not _META_PREFIX.match(line) and not _MECHANICAL_SUMMARY_PREFIX.match(line)
        ]
        if flavored:
            candidates = flavored
    return _excerpt(candidates[0]) if candidates else ""


def _looks_like_short_summary(line: str) -> bool:
    return (
        len(line) >= 18
        and len(line.split()) >= 3
        and line.rstrip().endswith((".", "?", "!"))
    )


def _excerpt(value: str, limit: int = 500) -> str:
    text = normalize_codex_text(value).replace("\n", " ")
    if len(text) <= limit:
        return text
    sentence = max(text.rfind(mark, 0, limit + 1) for mark in (". ", "? ", "! "))
    if sentence >= limit // 2:
        return text[: sentence + 1]
    word = text.rfind(" ", 0, limit - 1)
    return text[: word if word > 0 else limit - 1].rstrip(" ,;:") + "…"

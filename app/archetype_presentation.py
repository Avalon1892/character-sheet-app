"""Readable, theme-safe presentation of imported archetype rules.

Catalog prose remains untouched.  This module projects it into a structured
overview for the picker and Codex so future imports automatically gain the same
replacement summary and feature-by-feature layout.
"""
from __future__ import annotations

from dataclasses import dataclass
import html
import re
from typing import Mapping
import urllib.parse

from app.text_cleanup import repair_mojibake


_FEATURE_HEADING = re.compile(
    r"^(?P<title>[A-Z][^:]{1,100}?)(?:\s+\((?P<tag>Ex|Su|Sp)\))?\s*:\s*(?P<body>.*)$"
)
_CHANGE_SENTENCE = re.compile(
    r"\b(?:This|These)\s+(?:ability|abilities|class feature|class features)?\s*"
    r"(?:replaces?|alters?|modifies?)\s+[^.]+\.?",
    re.IGNORECASE,
)
_STANDALONE_HEADING = re.compile(
    r"^(?P<title>[A-Z][A-Za-z0-9’'\- /&]{1,90}?)(?:\s+\((?P<tag>Ex|Su|Sp)\))?$"
)


@dataclass(frozen=True, slots=True)
class ArchetypeRuleSection:
    title: str
    tag: str = ""
    body: str = ""
    changes: tuple[str, ...] = ()


def archetype_change_labels(entry: Mapping[str, object]) -> tuple[str, ...]:
    """Return concise, human-readable replacement labels in published order."""

    raw = repair_mojibake(str(entry.get("replaces") or "")).strip()
    values = [value.strip(" .") for value in re.split(r";|\n", raw) if value.strip(" .")]
    if not values:
        values = [
            re.sub(r"[-_]+", " ", str(value)).strip().title()
            for value in (entry.get("replaces_features") or ())
            if str(value).strip()
        ]
    return tuple(dict.fromkeys(values))


def archetype_rule_sections(entry: Mapping[str, object]) -> tuple[ArchetypeRuleSection, ...]:
    """Split broad imported prose into named feature blocks without rewriting it."""

    name = repair_mojibake(str(entry.get("name") or "")).strip()
    summary = repair_mojibake(str(entry.get("summary") or "")).strip()
    rules = repair_mojibake(
        str(entry.get("description") or summary or "No rules text available.")
    )
    # Spheres pages commonly preserve meaningful line breaks but contain no
    # blank paragraphs.  Parse that source shape explicitly instead of
    # collapsing the complete archetype into one enormous paragraph.
    if rules.count("\n") >= 3 and not re.search(r"\n\s*\n", rules):
        return _line_based_rule_sections(rules, name, summary)
    paragraphs = [
        re.sub(r"\s+", " ", paragraph).strip()
        for paragraph in re.split(r"\n\s*\n", rules.replace("\r", ""))
        if paragraph.strip()
    ]
    sections: list[ArchetypeRuleSection] = []
    overview: list[str] = []
    for paragraph in paragraphs:
        if paragraph.casefold() == name.casefold():
            continue
        if paragraph.casefold().startswith(f"{name.casefold()} source "):
            continue
        if paragraph.casefold().startswith("source ") and len(paragraph) < 180:
            continue
        if summary and paragraph.casefold() == summary.casefold():
            continue
        standalone_change = _CHANGE_SENTENCE.fullmatch(paragraph)
        if standalone_change is not None and sections:
            previous = sections[-1]
            sections[-1] = ArchetypeRuleSection(
                previous.title,
                previous.tag,
                previous.body,
                (*previous.changes, standalone_change.group(0).strip()),
            )
            continue
        match = _FEATURE_HEADING.match(paragraph)
        if match is None:
            overview.append(paragraph)
            continue
        body = match.group("body").strip()
        changes = tuple(
            dict.fromkeys(
                repair_mojibake(change.group(0)).strip()
                for change in _CHANGE_SENTENCE.finditer(body)
            )
        )
        if changes:
            body = _CHANGE_SENTENCE.sub("", body).strip()
        sections.append(
            ArchetypeRuleSection(
                match.group("title").strip(),
                match.group("tag") or "",
                body,
                changes,
            )
        )
    if overview:
        sections.insert(0, ArchetypeRuleSection("Additional rules", body="\n\n".join(overview)))
    return tuple(sections)


def _line_based_rule_sections(
    rules: str, name: str, summary: str,
) -> tuple[ArchetypeRuleSection, ...]:
    """Parse heading-per-line Spheres prose without inventing rules structure."""

    sections: list[ArchetypeRuleSection] = []
    overview: list[str] = []
    current_title = ""
    current_tag = ""
    current_body: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_tag, current_body
        if current_title:
            sections.append(
                ArchetypeRuleSection(
                    current_title,
                    current_tag,
                    "\n\n".join(current_body).strip(),
                )
            )
        elif current_body:
            overview.extend(current_body)
        current_title = ""
        current_tag = ""
        current_body = []

    for raw_line in rules.replace("\r", "").splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line.casefold() == name.casefold() or line.casefold() == summary.casefold():
            continue
        if line.casefold().startswith("source ") and len(line) < 180:
            continue
        change = _CHANGE_SENTENCE.fullmatch(line)
        if change is not None:
            flush()
            sections.append(
                ArchetypeRuleSection(
                    "Class-feature interaction",
                    changes=(change.group(0).strip(),),
                )
            )
            continue

        inline_heading = _FEATURE_HEADING.match(line)
        standalone_heading = _STANDALONE_HEADING.match(line)
        if inline_heading is not None:
            flush()
            current_title = inline_heading.group("title").strip()
            current_tag = inline_heading.group("tag") or ""
            body = inline_heading.group("body").strip()
            if body:
                current_body.append(body)
            continue
        if standalone_heading is not None:
            flush()
            current_title = standalone_heading.group("title").strip()
            current_tag = standalone_heading.group("tag") or ""
            continue

        embedded_changes = tuple(
            dict.fromkeys(match.group(0).strip() for match in _CHANGE_SENTENCE.finditer(line))
        )
        body = _CHANGE_SENTENCE.sub("", line).strip() if embedded_changes else line
        if body:
            current_body.append(body)
        if embedded_changes:
            flush()
            sections.append(
                ArchetypeRuleSection(
                    "Class-feature interaction", changes=embedded_changes
                )
            )
    flush()
    if overview:
        sections.insert(0, ArchetypeRuleSection("Overview", body="\n\n".join(overview)))
    return tuple(section for section in sections if section.body or section.changes)


def archetype_rules_html(entry: Mapping[str, object]) -> str:
    """Build the shared readable archetype page used by picker and Codex."""

    name = html.escape(repair_mojibake(str(entry.get("name") or "Archetype")))
    parent = html.escape(str(entry.get("class_name") or ""))
    source_group = html.escape(str(entry.get("source_group") or "Pathfinder"))
    summary = html.escape(repair_mojibake(str(entry.get("summary") or "")))
    changes = archetype_change_labels(entry)
    change_rows = "".join(
        f"<tr><td width='22'>&bull;</td><td><b>{html.escape(value)}</b></td></tr>"
        for value in changes
    ) or "<tr><td>—</td><td>No replaced feature is declared in the catalog. Review the feature notes below.</td></tr>"

    capabilities = entry.get("sphere_capabilities") or {}
    grants = ", ".join(str(value).replace("_", " ").title() for value in capabilities.get("grants", ()))
    removes = ", ".join(str(value).replace("_", " ").title() for value in capabilities.get("removes", ()))
    capability_parts = []
    if grants:
        capability_parts.append(f"Adds: {grants}")
    if removes:
        capability_parts.append(f"Removes: {removes}")
    capability_html = (
        f"<p><b>Sheet-system changes:</b> {html.escape(' · '.join(capability_parts))}</p>"
        if capability_parts else ""
    )

    section_html: list[str] = []
    for section in archetype_rule_sections(entry):
        tag = f" <small>({html.escape(section.tag)})</small>" if section.tag else ""
        body = "".join(
            f"<p>{html.escape(paragraph)}</p>"
            for paragraph in section.body.split("\n\n") if paragraph.strip()
        )
        claims = "".join(
            f"<li><b>{html.escape(claim)}</b></li>" for claim in section.changes
        )
        section_html.append(
            f"<h3>{html.escape(section.title)}{tag}</h3>{body}"
            + (f"<p><b>Class-feature interaction</b></p><ul>{claims}</ul>" if claims else "")
            + "<hr>"
        )

    source_url = html.escape(str(entry.get("source_url") or ""), quote=True)
    source_link = f"<p><a href='{source_url}'>Open rules source</a></p>" if source_url else ""
    return (
        f"<h1>{name}</h1>"
        f"<p><b>{parent}</b> &middot; {source_group}</p>"
        + (f"<blockquote>{summary}</blockquote>" if summary else "")
        + "<h2>Class feature changes</h2>"
        + f"<table cellspacing='4' cellpadding='2'>{change_rows}</table>"
        + capability_html
        + "<h2>Archetype features</h2>"
        + "".join(section_html)
        + source_link
    )


def archetype_collection_row_html(entry: Mapping[str, object]) -> str:
    target = urllib.parse.quote(str(entry.get("key") or ""), safe="")
    summary = repair_mojibake(str(entry.get("summary") or "No summary available."))
    changes = ", ".join(archetype_change_labels(entry)) or "No declared replacement summary"
    return (
        f"<h3><a href='codex:archetype:{target}'>{html.escape(str(entry.get('name') or 'Archetype'))}</a></h3>"
        f"<p>{html.escape(summary)}</p>"
        f"<p><b>Changes:</b> {html.escape(changes)}</p><hr>"
    )

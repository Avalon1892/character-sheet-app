"""Import selectable Spheres classes and their class-specific archetypes.

The wiki homepage is the source of truth for class families.  Each class page
is then parsed independently so future additions only require refreshing the
catalog rather than changing UI code.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from catalog_import_common import clean_text, element_fragment, fetch_cached, html_text, slug


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.codex_descriptions import (  # noqa: E402 - ROOT must be importable first
    normalize_spheres_archetype_codex_entry,
    normalize_spheres_class_codex_entry,
)

CACHE_ROOT = ROOT / ".archetype-source" / "spheres" / "classes"
ARCHETYPE_CACHE_ROOT = ROOT / ".archetype-source" / "spheres" / "class-archetypes"
HOME_CACHE = ROOT / ".archetype-source" / "spheres" / "archetype-index.html"
CLASS_OUTPUT = ROOT / "data" / "pf1e" / "spheres_classes.json"
ARCHETYPE_OUTPUT = ROOT / "data" / "pf1e" / "spheres_class_archetypes.json"
BASE_URL = "https://spheresofpower.wikidot.com/"
CLASS_FAMILIES = (
    "Spherecasters",
    "Operatives",
    "Practitioners",
    "Champions",
    "Prestige Classes",
)
SKILL_NAMES = (
    "Acrobatics", "Appraise", "Bluff", "Climb", "Craft", "Diplomacy",
    "Disable Device", "Disguise", "Escape Artist", "Fly", "Handle Animal",
    "Heal", "Intimidate", "Knowledge (Arcana)", "Knowledge (Dungeoneering)",
    "Knowledge (Engineering)", "Knowledge (Geography)", "Knowledge (History)",
    "Knowledge (Local)", "Knowledge (Nature)", "Knowledge (Nobility)",
    "Knowledge (Planes)", "Knowledge (Religion)", "Linguistics", "Perception",
    "Perform", "Profession", "Ride", "Sense Motive", "Sleight of Hand",
    "Spellcraft", "Stealth", "Survival", "Swim", "Use Magic Device",
)


def _content_after_heading(source: str, heading: str) -> str:
    """Capture every paragraph in a class family, including labeled 3PP rows."""

    match = re.search(
        rf"<p><strong>{re.escape(heading)}</strong></p>", source, re.I | re.S
    )
    if not match:
        return ""
    candidates = [
        position
        for position in (
            source.find("<p><strong>", match.end()),
            source.find("</div>", match.end()),
        )
        if position >= 0
    ]
    end = min(candidates) if candidates else len(source)
    return source[match.end() : end]


def class_index(source: str) -> list[dict]:
    result: list[dict] = []
    for family in CLASS_FAMILIES:
        fragment = _content_after_heading(source, family)
        for link in re.finditer(r'<a href="(/[^"]+)">(.*?)</a>', fragment, re.I | re.S):
            name = html_text(link.group(2))
            if not name or "alternate class feature" in name.casefold():
                continue
            class_key = "prodigy" if name == "Prodigy" else f"spheres-class:{slug(name)}"
            result.append(
                {
                    "key": class_key,
                    "name": name,
                    "category": family,
                    "source_group": "Spheres",
                    "source_url": urllib.parse.urljoin(BASE_URL, link.group(1)),
                }
            )
    return list({entry["key"]: entry for entry in result}.values())


def _table_rows(fragment: str) -> list[list[str]]:
    result: list[list[str]] = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", fragment, re.I | re.S):
        cells = re.findall(r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>", row, re.I | re.S)
        if cells:
            result.append([html_text(cell) for cell in cells])
    return result


def _class_table(page: str) -> tuple[list[str], list[list[str]]]:
    # Some Wikidot themes nest the page table of contents around the real class
    # table.  Anchor on the actual header row instead of trusting table nesting.
    for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", page, re.I | re.S):
        header_cells = re.findall(
            r"<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>", row_match.group(1), re.I | re.S
        )
        headers = [html_text(cell) for cell in header_cells]
        folded = " | ".join(headers).casefold()
        has_bab = "base attack bonus" in folded or bool(re.search(r"\bbab\b", folded))
        if not has_bab or "special" not in folded or "level" not in folded:
            continue
        end = page.find("</table>", row_match.end())
        body = page[row_match.end() : end if end >= 0 else len(page)]
        rows = _table_rows(body)
        if rows:
            return headers, rows
    return [], []


def _column(headers: list[str], *needles: str) -> int | None:
    for index, header in enumerate(headers):
        folded = header.casefold()
        if all(needle in folded for needle in needles):
            return index
    return None


def _progression(value: str, *, save: bool = False) -> str:
    number = re.search(r"[-+]?\d+", value)
    first = int(number.group()) if number else 0
    if save:
        return "Good" if first >= 2 else "Poor"
    if first >= 1:
        return "Full"
    # First-level 3/4 and 1/2 progressions are both +0; use later rows elsewhere.
    return ""


def _bab_progression(rows: list[list[str]], index: int | None) -> str:
    if index is None or not rows:
        return "3/4"
    last = rows[min(19, len(rows) - 1)]
    value = last[index] if index < len(last) else ""
    first = re.search(r"[-+]?\d+", value)
    maximum = int(first.group()) if first else 0
    if maximum >= 19:
        return "Full"
    if maximum >= 14:
        return "3/4"
    return "1/2"


def _split_features(value: str) -> list[str]:
    result: list[str] = []
    start = depth = 0
    for index, character in enumerate(value):
        if character in "([":
            depth += 1
        elif character in ")]" and depth:
            depth -= 1
        elif character == "," and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    result.append(value[start:].strip())
    return [item for item in result if item and item not in {"—", "-"}]


def _heading_sections(page: str) -> list[tuple[int, str, str]]:
    headings = list(re.finditer(r"<h([1-6])\b[^>]*>(.*?)</h\1>", page, re.I | re.S))
    result: list[tuple[int, str, str]] = []
    for index, heading in enumerate(headings):
        level = int(heading.group(1))
        end = len(page)
        for following in headings[index + 1 :]:
            if int(following.group(1)) <= level:
                end = following.start()
                break
        result.append((level, html_text(heading.group(2)), html_text(page[heading.end() : end])))
    return result


def _feature_description(name: str, sections: list[tuple[int, str, str]]) -> str:
    canonical = re.sub(r"\([^)]*\)|\[[^]]*\]", "", name).strip().casefold()
    canonical = re.sub(r"\s+[+]?\d+(?:st|nd|rd|th)?$", "", canonical).strip()
    for _level, heading, body in sections:
        candidate = re.sub(r"\([^)]*\)|\[[^]]*\]", "", heading).strip().casefold()
        if canonical and (candidate == canonical or candidate.startswith(canonical) or canonical.startswith(candidate)):
            return body
    return ""


def _class_skills(text: str) -> list[str]:
    match = re.search(r"class skills(?: are|:)?\s*(.*?)(?:\n\s*skill ranks|\n\s*skills? per level|\n\n)", text, re.I | re.S)
    source = match.group(1) if match else ""
    return [name for name in SKILL_NAMES if name.casefold() in source.casefold()]


def _capabilities(category: str, text: str, name: str) -> tuple[list[str], dict]:
    folded = text.casefold()
    active: set[str] = set()
    if category == "Spherecasters":
        active.add("magic")
    elif category == "Practitioners":
        active.add("martial")
    elif category == "Operatives":
        active.add("skill")
    if any(term in folded for term in ("magic talent", "casting tradition", "spherecasting")):
        active.add("magic")
    if any(term in folded for term in ("combat talent", "martial tradition", "practitioner modifier", "martial focus")):
        active.add("martial")
    if any(term in folded for term in ("skill talent", "trade tradition", "operative modifier")):
        active.add("skill")
    if name == "Prodigy":
        active.add("sequence")
    progression_match = re.search(r"considered (?:an? )?(high|mid|low)[ -]?caster", text, re.I)
    progression = progression_match.group(1).title() if progression_match else ""
    ability_match = re.search(
        r"(?:uses|use)\s+(Strength|Dexterity|Constitution|Intelligence|Wisdom|Charisma)\s+as\s+(?:his|her|their|its)\s+casting ability modifier",
        text,
        re.I,
    )
    ability = ability_match.group(1).casefold() if ability_match else ""
    return sorted(active), {
        "sphere_progression": progression,
        "ability": ability,
        "traditional": False,
    }


def _replacement_metadata(
    description: str, class_name: str = ""
) -> tuple[list[str], list[str], list[str]]:
    claims: list[str] = []
    features: set[str] = set()
    removed_features: set[str] = set()

    def record(claim: str, *, removes: bool) -> None:
        claim = clean_text(claim).strip(" ;,")
        if claim and claim.casefold() not in {value.casefold() for value in claims}:
            claims.append(claim)
        normalized = re.sub(
            r"\b(?:class feature|ability|at \d+(?:st|nd|rd|th) level|gained at .*?)\b",
            " ",
            claim,
            flags=re.I,
        )
        if class_name:
            normalized = re.sub(
                rf"\s+of\s+(?:the\s+)?{re.escape(class_name)}(?:\s+class)?\s*$",
                "",
                normalized,
                flags=re.I,
            )
        for part in re.split(r",|\band\b|\bor\b", normalized, flags=re.I):
            value = re.sub(r"\([^)]*\)|\[[^]]*\]|\bthe\b", " ", part, flags=re.I)
            value = slug(value)
            if value and len(value) > 2:
                features.add(value)
                if removes:
                    removed_features.add(value)

    statements = re.findall(
        r"\b(?:This|These)\s+(?:ability|abilities|class feature|class features|archetype)?\s*"
        r"(?:replaces?|alters?|modifies?)\b[^\n.]*",
        description,
        re.I,
    )
    for statement in statements:
        lead = re.sub(
            r"^.*?\b(?=(?:replaces?|alters?|modifies?)\b)", "", statement, flags=re.I
        )
        for match in re.finditer(
            r"(?:^|\band\b|\bbut\b)\s*(replaces?|alters?|modifies?)\s+"
            r"(?:the\s+)?(.+?)(?=(?:\s+(?:and|but)\s+)?"
            r"(?:replaces?|alters?|modifies?)\b|$)",
            lead,
            re.I,
        ):
            record(match.group(2), removes=match.group(1).casefold().startswith("replace"))
    # Standalone, sentence-leading "In place of" is replacement language. Do
    # not mistake ordinary prose such as "uses Wisdom in place of Charisma" for
    # removal of a class feature.
    for match in re.finditer(r"(?:^|\n)In place of (?:the )?([^\n,.]+)", description):
        record(match.group(1), removes=True)
    return claims, sorted(features), sorted(removed_features)


def _class_modifications(description: str) -> dict:
    """Extract conservative profile changes into the universal runtime schema."""

    statistics: dict[str, object] = {}
    casting: dict[str, object] = {}
    hit_die = re.search(
        r"(?:use|uses|using|has|gains?|becomes?)\s+(?:an?\s+)?d(\d+)\s+"
        r"(?:to determine (?:their|his|her) hit points|hit die)",
        description,
        re.I,
    ) or re.search(r"hit die\s+(?:is|becomes?|changes? to)\s+d(\d+)", description, re.I)
    if hit_die:
        statistics["hit_die"] = int(hit_die.group(1))

    if re.search(
        r"use(?:s)?\s+(?:their|his|her)\s+(?:class\s+)?level\s+to determine\s+"
        r"(?:their|his|her)\s+base attack bonus",
        description,
        re.I,
    ) or re.search(r"base attack bonus (?:progression )?(?:is|becomes) full", description, re.I):
        statistics["bab_progression"] = "Full"
    elif re.search(r"base attack bonus .{0,30}(?:3/4|three[- ]quarters?)", description, re.I):
        statistics["bab_progression"] = "3/4"
    elif re.search(r"base attack bonus .{0,30}(?:1/2|one[- ]half|half)", description, re.I):
        statistics["bab_progression"] = "1/2"

    skill_points = re.search(
        r"(?:skill ranks|skill points) per level\s*:?\s*(\d+)", description, re.I
    )
    if skill_points:
        statistics["skill_points"] = int(skill_points.group(1))

    sphere_progression = re.search(
        r"considered\s+(?:an?\s+)?(high|mid|low)[ -]?caster", description, re.I
    )
    if sphere_progression:
        casting["sphere_progression"] = sphere_progression.group(1).title()

    result: dict[str, object] = {}
    if statistics:
        result["statistics"] = statistics
    if casting:
        result["casting"] = casting
    return result


def _option_advancement(description: str) -> dict:
    match = re.search(
        r"gains?\s+(?:a|one)\s+(?:magic,?\s+combat,?\s+or\s+skill|"
        r"combat,?\s+magic,?\s+or\s+skill|magic\s+or\s+combat|combat\s+or\s+magic)?\s*"
        r"talent\s+at\s+(\d+)(?:st|nd|rd|th)\s+level\s+and\s+every\s+"
        r"(\d+)\s+levels?\s+thereafter",
        description,
        re.I,
    )
    if not match:
        return {}
    return {
        "talent_bonus_schedule": {
            "first_level": int(match.group(1)),
            "every_levels": int(match.group(2)),
            "count": 1,
        }
    }


def _archetype_choices(page: str, description: str) -> list[dict]:
    """Discover common heading-backed one-or-many archetype decisions."""

    sections = _heading_sections(page) if page else []
    by_name = {
        re.sub(r"\([^)]*\)|\[[^]]*\]", "", heading).strip().casefold(): (heading, body)
        for _level, heading, body in sections
        if heading.strip()
    }
    result: list[dict] = []
    for _heading_level, heading, body in sections:
        match = re.search(
            r"At\s+(\d+)(?:st|nd|rd|th)\s+level,?\s+[^.\n]+?\s+"
            r"chooses?\s+(?:one\s+of\s+|between\s+)([^.\n]+)",
            body,
            re.I,
        )
        if not match:
            continue
        option_names = [
            clean_text(value).strip(" ,")
            for value in re.split(r",|\band\b|\bor\b", match.group(2), flags=re.I)
            if clean_text(value).strip(" ,")
        ]
        options = []
        for option_name in option_names:
            canonical = re.sub(
                r"\([^)]*\)|\[[^]]*\]", "", option_name
            ).strip().casefold()
            section = by_name.get(canonical)
            if section is None:
                continue
            published_name, option_description = section
            option = {
                "key": slug(option_name),
                "name": re.sub(r"\s*\([^)]*\)\s*$", "", published_name).strip(),
                "description": option_description,
            }
            advancement = _option_advancement(option_description)
            if advancement:
                option["class_modifications"] = {"advancement": advancement}
            options.append(option)
        if len(options) < 2:
            continue
        clean_heading = re.sub(r"\s*\([^)]*\)\s*$", "", heading).strip()
        result.append(
            {
                "key": slug(clean_heading),
                "name": clean_heading,
                "description": clean_text(match.group(0)),
                "level": int(match.group(1)),
                "minimum": 1,
                "maximum": 1,
                "options": options,
            }
        )
    return result


def _archetype_feature_rows(page: str, choices: list[dict]) -> list[dict]:
    """Project top-level archetype headings into Special Ability records."""

    if not page:
        return []
    headings = list(re.finditer(r"<h([1-6])\b[^>]*>(.*?)</h\1>", page, re.I | re.S))
    if not headings:
        return []
    named = [(int(match.group(1)), html_text(match.group(2)), match) for match in headings]
    class_features = next(
        (level for level, name, _match in named if name.strip().casefold() == "class features"),
        None,
    )
    feature_level = (
        class_features + 1
        if class_features is not None
        else min(level for level, name, _match in named if name.strip())
    )
    option_names = {
        str(option.get("name") or "").casefold()
        for choice in choices
        for option in choice.get("options", ())
    }
    ignored = {
        "class features", "table of contents", "archetypes", "favored class bonuses",
        "related talents", "class equipment",
    }
    rows: list[dict] = []
    for index, (level, heading, match) in enumerate(named):
        clean_name = re.sub(r"\s*\[[^]]+\]\s*$", "", heading).strip()
        display_name = re.sub(r"\s*\((?:Ex|Su|Sp|Ps|Sla)\)\s*$", "", clean_name, flags=re.I).strip()
        if (
            level != feature_level
            or not display_name
            or display_name.casefold() in ignored
            or display_name.casefold() in option_names
        ):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(page)
        body = html_text(page[match.end() : end])
        if not body:
            continue
        gained = re.search(
            r"\b(?:at|starting at|beginning at|upon reaching)\s+(?:class\s+)?"
            r"(\d+)(?:st|nd|rd|th)\s+level\b",
            body,
            re.I,
        )
        rows.append(
            {
                "level": int(gained.group(1)) if gained else 1,
                "name": display_name,
                "description": body,
            }
        )
    return rows


def _archetypes(entry: dict, page: str) -> list[dict]:
    headings = list(re.finditer(r"<h([1-6])\b[^>]*>(.*?)</h\1>", page, re.I | re.S))
    start_index = next(
        (
            index
            for index, match in enumerate(headings)
            if html_text(match.group(2)).casefold() == "archetypes"
        ),
        None,
    )
    if start_index is None:
        return []
    section_level = int(headings[start_index].group(1))
    result: list[dict] = []
    for index in range(start_index + 1, len(headings)):
        heading = headings[index]
        level = int(heading.group(1))
        if level <= section_level:
            break
        if level != section_level + 1:
            continue
        name = re.sub(r"^\s*-\s*", "", html_text(heading.group(2)).strip())
        if (
            not name
            or name.casefold().startswith("old ")
            or "class features" in name.casefold()
        ):
            continue
        end = len(page)
        for following in headings[index + 1 :]:
            if int(following.group(1)) <= level:
                end = following.start()
                break
        description = html_text(page[heading.end() : end])
        clean_name = re.sub(r"\s*\[[^]]+\]\s*$", "", name).strip()
        link = re.search(r'href="([^"]+)"', heading.group(2), re.I)
        source_url = (
            urllib.parse.urljoin(BASE_URL, link.group(1))
            if link
            else entry["source_url"]
        )
        claims, features, removed = _replacement_metadata(description, str(entry["name"]))
        result.append(
            {
                "key": f"spheres-archetype:{entry['key']}:{slug(clean_name)}",
                "class_key": entry["key"],
                "class_name": entry["name"],
                "name": clean_name,
                "source_group": "Spheres",
                "source": "Spheres of Power Wiki",
                "source_url": source_url,
                "summary": description.split("\n", 1)[0][:500],
                "description": description,
                "replaces": "; ".join(claims),
                "replaces_features": features,
                "removed_features": removed,
                "compatibility": {
                    "explicitly_compatible": [],
                    "explicitly_incompatible": [],
                    "requires": [],
                },
                "sphere_capabilities": {"grants": [], "removes": []},
                "_inline": link is None,
            }
        )
    return result


def _load_archetype_detail(entry: dict, refresh: bool) -> dict:
    """Hydrate a class-page archetype link with its complete rules page.

    Official class pages often include an inline synopsis, while several 3PP
    families (including Necros, Dragoon, Mountebank, and Reaper) expose only a
    linked heading.  Treating both shapes as the same catalog contract prevents
    linked-only archetypes from silently disappearing.
    """

    inline = bool(entry.pop("_inline", False))
    detail_page = ""
    if not inline:
        try:
            source = fetch_cached(
                str(entry["source_url"]),
                ARCHETYPE_CACHE_ROOT
                / f"{slug(str(entry['class_name']))}--{slug(str(entry['name']))}.html",
                refresh=refresh,
            )
            detail_page = element_fragment(source, "page-content") or source
            rules = html_text(detail_page)
            if rules:
                entry["description"] = rules
        except Exception as error:  # retain the discoverable index entry offline
            entry["import_warning"] = str(error)

    description = str(entry.get("description") or entry.get("summary") or "")
    claims, features, removed = _replacement_metadata(
        description, str(entry["class_name"])
    )
    entry["replaces"] = "; ".join(claims)
    entry["replaces_features"] = features
    entry["removed_features"] = removed
    entry["class_modifications"] = _class_modifications(description)
    entry["choices"] = _archetype_choices(detail_page, description)
    entry["features"] = _archetype_feature_rows(detail_page, entry["choices"])
    return normalize_spheres_archetype_codex_entry(entry)


def _cross_reference_compatibility(archetypes: list[dict]) -> None:
    by_class: dict[str, list[dict]] = {}
    for entry in archetypes:
        by_class.setdefault(str(entry["class_key"]), []).append(entry)
    for siblings in by_class.values():
        for entry in siblings:
            folded = str(entry["description"]).casefold()
            compatible: set[str] = set()
            incompatible: set[str] = set()
            requires: set[str] = set()
            for other in siblings:
                if other["key"] == entry["key"]:
                    continue
                name = str(other["name"]).casefold()
                if any(phrase in folded for phrase in (
                    f"not compatible with the {name}", f"not compatible with {name}",
                    f"cannot be combined with the {name}", f"cannot be combined with {name}",
                )):
                    incompatible.add(str(other["key"]))
                elif any(phrase in folded for phrase in (
                    f"compatible with the {name}", f"compatible with {name}",
                    f"may be combined with the {name}", f"may be combined with {name}",
                )):
                    compatible.add(str(other["key"]))
                if any(phrase in folded for phrase in (
                    f"requires the {name}", f"requires {name}",
                    f"must have the {name}", f"must possess the {name}",
                )):
                    requires.add(str(other["key"]))
            entry["compatibility"] = {
                "explicitly_compatible": sorted(compatible),
                "explicitly_incompatible": sorted(incompatible),
                "requires": sorted(requires),
            }


def _load_class(entry: dict, refresh: bool) -> tuple[dict, list[dict]]:
    page_source = fetch_cached(
        str(entry["source_url"]), CACHE_ROOT / f"{slug(str(entry['name']))}.html", refresh=refresh
    )
    page = element_fragment(page_source, "page-content") or page_source
    text = html_text(page)
    archetype_heading = re.search(r"<h1\b[^>]*>\s*Archetypes\s*</h1>", page, re.I)
    base_page = page[: archetype_heading.start()] if archetype_heading else page
    base_text = html_text(base_page)
    headers, rows = _class_table(page)
    bab_index = _column(headers, "base attack")
    if bab_index is None:
        bab_index = _column(headers, "bab")
    fort_index = _column(headers, "fort")
    reflex_index = _column(headers, "ref")
    will_index = _column(headers, "will")
    special_index = _column(headers, "special")
    level_index = _column(headers, "level") or 0
    first = rows[0] if rows else []
    hit_die_match = re.search(r"Hit Die\s*:?\s*d\s*(\d+)", text, re.I)
    skills_match = re.search(r"Skill Ranks per Level\s*:?\s*(\d+)", text, re.I)
    sections = _heading_sections(page)
    features: list[dict] = []
    if special_index is not None:
        for row in rows[:20]:
            if special_index >= len(row):
                continue
            level_match = re.search(r"\d+", row[level_index] if level_index < len(row) else "")
            if not level_match:
                continue
            level = int(level_match.group())
            for name in _split_features(row[special_index]):
                features.append(
                    {
                        "level": level,
                        "name": name,
                        "description": _feature_description(name, sections),
                    }
                )
    capabilities, casting = _capabilities(
        str(entry["category"]), base_text, str(entry["name"])
    )
    description_end = re.search(r"<h1\b[^>]*>\s*Class Features\s*</h1>", page, re.I)
    description = html_text(page[: description_end.start()]) if description_end else text[:4000]
    entry.update(
        {
            "description": description or text[:4000],
            "rules_text": text,
            "summary": (description or text).split("\n", 1)[0][:500],
            "hit_die": int(hit_die_match.group(1)) if hit_die_match else 8,
            "bab": _bab_progression(rows, bab_index),
            "fort": _progression(first[fort_index], save=True) if first and fort_index is not None and fort_index < len(first) else "Poor",
            "reflex": _progression(first[reflex_index], save=True) if first and reflex_index is not None and reflex_index < len(first) else "Poor",
            "will": _progression(first[will_index], save=True) if first and will_index is not None and will_index < len(first) else "Poor",
            "skill_points": int(skills_match.group(1)) if skills_match else 4,
            "class_skills": _class_skills(text),
            "class_skill_keys": [slug(value).replace("-", "_") for value in _class_skills(text)],
            "features": features,
            "source": "Spheres of Power Wiki",
            "capabilities": capabilities,
            "casting": casting,
        }
    )
    return entry, _archetypes(entry, page)


def build_catalog(refresh: bool = False, workers: int = 10) -> tuple[dict, dict]:
    home = fetch_cached(BASE_URL, HOME_CACHE, refresh=refresh)
    indexed = class_index(home)
    classes: list[dict] = []
    archetypes: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(_load_class, dict(entry), refresh): entry for entry in indexed}
        for future in as_completed(futures):
            class_entry, class_archetypes = future.result()
            classes.append(class_entry)
            archetypes.extend(class_archetypes)
    classes.sort(key=lambda item: (CLASS_FAMILIES.index(str(item["category"])), str(item["name"]).casefold()))
    archetypes = list({entry["key"]: entry for entry in archetypes}.values())
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(_load_archetype_detail, dict(entry), refresh): entry["key"]
            for entry in archetypes
        }
        archetypes = [future.result() for future in as_completed(futures)]
    _cross_reference_compatibility(archetypes)
    classes = [normalize_spheres_class_codex_entry(entry) for entry in classes]
    archetypes.sort(key=lambda item: (str(item["class_name"]).casefold(), str(item["name"]).casefold()))
    source = {"name": "Spheres of Power Wiki", "url": BASE_URL}
    return (
        {"version": 1, "sources": [source], "entries": classes},
        {"version": 1, "sources": [source], "entries": archetypes},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Spheres class and archetype catalogs.")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=10)
    arguments = parser.parse_args()
    classes, archetypes = build_catalog(arguments.refresh, arguments.workers)
    CLASS_OUTPUT.write_text(json.dumps(classes, ensure_ascii=False, indent=2), encoding="utf-8")
    ARCHETYPE_OUTPUT.write_text(json.dumps(archetypes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(classes['entries'])} Spheres classes to {CLASS_OUTPUT}")
    print(f"Wrote {len(archetypes['entries'])} class-specific Spheres archetypes to {ARCHETYPE_OUTPUT}")


if __name__ == "__main__":
    main()

"""Resolve displayed class features after applying selected archetypes."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Mapping

from app.archetype_rules import archetype_choices


@dataclass(frozen=True, slots=True)
class ResolvedClassFeature:
    level: int
    name: str
    description: str
    source: str
    archetype: bool = False


@dataclass(frozen=True, slots=True)
class OptionalArchetypeFeature:
    """An archetype exchange that only applies after an explicit selection."""

    key: str
    level: int
    name: str
    description: str
    source: str
    replaces: tuple[str, ...] = ()


def _token(value: object) -> str:
    return _text_token(str(value))


@lru_cache(maxsize=8192)
def _text_token(value: str) -> str:
    """Bounded cache of pure text normalization, never character/rules state."""
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    text = re.sub(r"\([^)]*\)", " ", text)
    # Replacement clauses often qualify the first acquisition with its daily
    # use count (for example “judgment 1/day”).  Uses are not part of the
    # feature identity and must not prevent the base feature from matching.
    text = re.sub(r"\b\d+\s*/\s*day\b", " ", text, flags=re.I)
    text = re.sub(r"\b\d+(?:st|nd|rd|th)(?:-level)?\b", " ", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    text = re.sub(r"(^|-)judgements?(?=-|$)", r"\1judgment", text)
    aliases = {
        "bonus-feats": "bonus-feat",
        "bombs": "bomb",
        "judgement": "judgment",
        "judgements": "judgment",
        "domains": "domain",
        "teamwork-feats": "teamwork-feat",
        "bonus-teamwork-feats": "teamwork-feat",
    }
    return aliases.get(text, text)


def feature_token(value: object) -> str:
    """Public stable token used by modular class-system registries."""

    return _token(value)


def _replacement_clauses(entry: Mapping[str, object]) -> tuple[str, ...]:
    raw = str(entry.get("replaces") or "")
    if raw:
        return tuple(part.strip() for part in raw.split(";") if part.strip())
    description = str(entry.get("description") or "")
    return tuple(
        match.group(1).strip()
        for match in re.finditer(
            r"(?:This|These) (?:ability|abilities|class feature|class features)?\s*"
            r"(?:replaces?|alters?|modifies?)\s+(?:the )?([^\n.]+)",
            description,
            re.I,
        )
    )


def _removal_clauses(entry: Mapping[str, object]) -> tuple[str, ...]:
    """Return only features the archetype actually removes from the base list.

    New Spheres imports distinguish replacement from alteration.  Older saved
    catalogs and Pathfinder imports retain the legacy fallback so this remains
    backwards compatible.
    """

    precise = tuple(
        str(value)
        for value in (entry.get("removed_feature_clauses") or ())
        if str(value).strip()
    )
    if precise:
        return precise
    if "removed_features" in entry:
        return tuple(
            str(value)
            for value in (entry.get("removed_features") or ())
            if str(value).strip()
        )
    return _replacement_clauses(entry)


def _feature_matches_clause(feature_name: str, clause: str) -> bool:
    feature = _token(feature_name)
    candidate = _token(clause)
    if not feature or not candidate:
        return False
    if feature == candidate:
        return True
    # Printed progression values do not make a different class feature:
    # replacing Prey Casting Bonus also replaces its +1 through +5 rows.
    if re.sub(r"-\d+(?:d\d+)?$", "", feature) == candidate:
        return True
    # Qualifiers used only as prose scaffolding may be ignored, but meaningful
    # qualifiers must remain distinct: replacing "fleshcraft" must not also
    # erase "advanced fleshcraft", and altering a puppet's evolution must not
    # erase the entire "corpse puppet" feature.
    noise = {
        "class", "feature", "features", "the", "inquisitor",
        "gain", "gained", "at", "level", "levels",
    }
    feature_words = {word.rstrip("s") for word in feature.split("-") if word not in noise}
    candidate_words = {word.rstrip("s") for word in candidate.split("-") if word not in noise}
    return bool(feature_words and feature_words == candidate_words)


def base_feature_is_replaced(
    feature: Mapping[str, object], archetypes: Iterable[Mapping[str, object]]
) -> bool:
    """Return whether a base feature row is fully replaced at its gained level.

    Level-scoped replacements such as "2nd and 12th-level bonus feats" do not
    erase an overarching Bonus Feats row gained at 1st level. They are instead
    represented by the archetype ability gained at the scoped level.
    """

    name = str(feature.get("name") or "")
    level = int(feature.get("level") or 1)
    for archetype in archetypes:
        for clause in _removal_clauses(archetype):
            if "spells" in _token(clause).split("-") and (
                _token(name) == "orisons" or "spell" in _token(name).split("-")
            ):
                return True
            if not _feature_matches_clause(name, clause):
                continue
            scoped_levels = {
                int(value)
                for value in re.findall(r"\b(\d+)(?:st|nd|rd|th)(?:-level)?\b", clause, re.I)
            }
            if not scoped_levels or level in scoped_levels:
                return True
    return False


_FEATURE_HEADING = re.compile(
    r"^(?P<name>[A-Z][^:\n]{1,100}?)(?:\s+\((?:Ex|Su|Sp|Ps|Sla)\))?:\s*(?P<body>.+)$",
    re.I | re.S,
)
_LEVEL = re.compile(
    r"\b(?:at|starting at|beginning at|upon reaching)\s+(?:class\s+)?"
    r"(?P<level>\d+)(?:st|nd|rd|th)\s+level\b",
    re.I,
)


def _archetype_paragraphs(entry: Mapping[str, object]) -> tuple[str, ...]:
    description = str(entry.get("description") or "")
    for marker in (
        "\n\nChampions of the Spheres by Drop Dead Studios",
        "\n\nSpheres of Power by Drop Dead Studios",
        "\n\nSpheres of Might by Drop Dead Studios",
    ):
        description = description.split(marker, 1)[0]
    # Wikidot/Spheres pages commonly encode a feature heading as a short
    # title-only line instead of ``Feature Name: body``.  Normalize that
    # markup contract before the shared paragraph splitter.  Requiring a
    # punctuation-free, short line prevents ordinary wrapped prose from being
    # mistaken for a feature heading.
    description = re.sub(
        r"(?m)^(?P<heading>[A-Z][^\n:.!?]{1,80}?(?:\s+\((?:Ex|Su|Sp|Ps|Sla)\))?)\s*\n(?=[A-Z])",
        r"\g<heading>: ",
        description,
    )
    # Current catalogs store one normalized paragraph per line, while older
    # imports preserve blank lines and may wrap prose across several lines.
    # Split only when a new rules heading (``Name:``) or replacement sentence
    # begins, then safely rejoin any remaining wrapped lines.
    parts = re.split(
        r"\n\s*\n|"
        r"\n(?=[A-Z][^:\n]{1,100}?(?:\s+\((?:Ex|Su|Sp|Ps|Sla)\))?:\s)|"
        r"\n(?=This\s+(?:\(optionally\)\s+|optionally\s+)?"
        r"(?:replaces?|alters?|modifies?)\b)",
        description,
        flags=re.I,
    )
    return tuple(
        " ".join(part.strip().splitlines()).strip()
        for part in parts
        if part.strip()
    )


def optional_archetype_feature_key(
    entry: Mapping[str, object], feature_name: str
) -> str:
    """Return a catalog-stable persistence key for an optional exchange."""

    owner = str(entry.get("key") or entry.get("name") or "archetype")
    return f"archetype-option:{owner}:{_token(feature_name)}"


def _optional_replacements(body: str, continuation: str = "") -> tuple[str, ...]:
    """Extract the base features surrendered by an optional exchange."""

    clauses: list[str] = []
    match = re.search(
        r"\bmay choose to (?:lose|trade(?: away)?|replace)\s+(?P<features>.+?)\s+"
        r"to\s+(?:instead\s+)?(?:gain|receive|become|treat)",
        body,
        re.I,
    )
    if match is not None:
        clauses.append(match.group("features"))
    for text in (body, continuation):
        clauses.extend(
            match.group(1)
            for match in re.finditer(
                r"This\s+(?:\(optionally\)\s+|optionally\s+)?replaces?\s+"
                r"(?:the\s+)?([^\n.]+)",
                text,
                re.I,
            )
        )

    result: list[str] = []
    for clause in clauses:
        clause = re.sub(
            r"\b(?:the\s+)?(?:[a-z]+(?:'s|’s)\s+)?class features?\b",
            " ",
            clause,
            flags=re.I,
        )
        for part in re.split(r",|\band\b", clause, flags=re.I):
            clean = re.sub(
                r"^\s*(?:the\s+)?(?:[a-z]+(?:'s|’s)\s+)?",
                "",
                part,
                flags=re.I,
            ).strip(" .;:")
            if clean and _token(clean):
                result.append(clean)
    return tuple(dict.fromkeys(result))


def archetype_optional_features(
    entry: Mapping[str, object], maximum_level: int = 20
) -> tuple[OptionalArchetypeFeature, ...]:
    """Discover opt-in archetype exchanges without class-specific UI code.

    Spheres' Champion archetypes phrase Greater Training consistently as a
    choice to lose one or more class features.  Parsing that common contract
    also supports future archetypes that use the same published wording.
    """

    source = str(entry.get("name") or "Archetype")
    paragraphs = _archetype_paragraphs(entry)
    result: list[OptionalArchetypeFeature] = []
    seen: set[str] = set()
    for index, paragraph in enumerate(paragraphs):
        match = _FEATURE_HEADING.match(paragraph)
        if match is None:
            continue
        body = match.group("body").strip()
        if re.search(r"\bmay choose to (?:lose|trade(?: away)?|replace)\b", body, re.I) is None:
            continue
        name = match.group("name").strip()
        level_match = _LEVEL.search(body)
        level = int(level_match.group("level")) if level_match else 1
        if level > maximum_level:
            continue
        continuation = ""
        if index + 1 < len(paragraphs) and re.match(
            r"^This\s+(?:\(optionally\)\s+|optionally\s+)?"
            r"(?:replaces?|alters?|modifies?)\b",
            paragraphs[index + 1],
            re.I,
        ):
            continuation = paragraphs[index + 1]
        description = body + (f"\n\n{continuation}" if continuation else "")
        key = optional_archetype_feature_key(entry, name)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            OptionalArchetypeFeature(
                key,
                level,
                name,
                description,
                source,
                _optional_replacements(body, continuation),
            )
        )
    return tuple(result)


def optional_feature_conflicts(
    feature: OptionalArchetypeFeature,
    other_archetypes: Iterable[Mapping[str, object]],
) -> tuple[str, ...]:
    """Return selected archetypes that block an optional exchange."""

    conflicts = []
    for entry in other_archetypes:
        if any(
            _feature_matches_clause(replaced, clause)
            for replaced in feature.replaces
            for clause in _replacement_clauses(entry)
        ):
            conflicts.append(str(entry.get("name") or "Archetype"))
    return tuple(dict.fromkeys(conflicts))


def archetype_granted_features(
    entry: Mapping[str, object], maximum_level: int
) -> tuple[ResolvedClassFeature, ...]:
    """Extract named archetype abilities from imported, paragraph-based rules."""

    source = str(entry.get("name") or "Archetype")
    structured = tuple(
        ResolvedClassFeature(
            int(feature.get("level") or 1),
            str(feature.get("name") or "Archetype Feature"),
            str(feature.get("description") or ""),
            source,
            True,
        )
        for feature in (entry.get("features") or ())
        if isinstance(feature, Mapping)
        and int(feature.get("level") or 1) <= maximum_level
    )
    if structured:
        return tuple(
            sorted(structured, key=lambda item: (item.level, item.name.casefold()))
        )
    paragraphs = _archetype_paragraphs(entry)
    result: list[ResolvedClassFeature] = []
    seen: set[tuple[int, str]] = set()
    for index, paragraph in enumerate(paragraphs):
        match = _FEATURE_HEADING.match(paragraph)
        if match is None:
            continue
        name = match.group("name").strip()
        if name.casefold() in {
            "source", "table", "table of contents", "wiki note", "classes", "rules",
        }:
            continue
        body = match.group("body").strip()
        if re.search(r"\bmay choose to (?:lose|trade|replace)\b", body, re.I):
            # Optional archetype exchanges are not gained until the character
            # explicitly opts in; the manual feature editor remains available.
            continue
        level_match = _LEVEL.search(body)
        level = int(level_match.group("level")) if level_match else 1
        if level > maximum_level:
            continue
        description = body
        if index + 1 < len(paragraphs) and re.match(
            r"^This (?:replaces?|alters?|modifies?)\b", paragraphs[index + 1], re.I
        ):
            description += "\n\n" + paragraphs[index + 1]
        key = (level, name.casefold())
        if key in seen:
            continue
        seen.add(key)
        result.append(ResolvedClassFeature(level, name, description, source, True))
    return tuple(result)


def resolve_class_features(
    base_features: Iterable[Mapping[str, object]],
    archetypes: Iterable[Mapping[str, object]],
    maximum_level: int,
    class_name: str,
    selected_optional_feature_keys: Iterable[str] = (),
    selected_archetype_choices: Mapping[str, Iterable[str]] | None = None,
) -> tuple[ResolvedClassFeature, ...]:
    selected = tuple(archetypes)
    selected_keys = frozenset(str(key) for key in selected_optional_feature_keys)
    optional = tuple(
        feature
        for archetype in selected
        for feature in archetype_optional_features(archetype, maximum_level)
        if feature.key in selected_keys
    )
    replacement_entries = selected + tuple(
        {"replaces": "; ".join(feature.replaces)}
        for feature in optional
        if feature.replaces
    )
    features = [
        ResolvedClassFeature(
            int(feature.get("level") or 1),
            str(feature.get("name") or "Class Feature"),
            str(feature.get("description") or ""),
            class_name,
            False,
        )
        for feature in base_features
        if int(feature.get("level") or 1) <= maximum_level
        and not base_feature_is_replaced(feature, replacement_entries)
    ]
    for archetype in selected:
        features.extend(archetype_granted_features(archetype, maximum_level))
    selected_archetype_choices = selected_archetype_choices or {}
    for archetype in selected:
        for choice in archetype_choices(archetype, maximum_level):
            selected_keys = {
                str(value)
                for value in selected_archetype_choices.get(choice.key, ())
            }
            features.extend(
                ResolvedClassFeature(
                    choice.level,
                    option.name,
                    option.description,
                    str(archetype.get("name") or "Archetype"),
                    True,
                )
                for option in choice.options
                if option.key in selected_keys
            )
    features.extend(
        ResolvedClassFeature(
            feature.level,
            feature.name,
            feature.description,
            feature.source,
            True,
        )
        for feature in optional
    )
    return tuple(
        sorted(features, key=lambda item: (item.level, item.archetype, item.name.casefold()))
    )


def resolved_feature_key(class_level_id: int, feature: ResolvedClassFeature) -> str:
    """Stable persistence key for a displayed derived feature."""

    return f"class:{class_level_id}:{_token(feature.source)}:{feature.level}:{_token(feature.name)}"

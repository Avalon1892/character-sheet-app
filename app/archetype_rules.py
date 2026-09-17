"""Pure PF1e archetype stacking rules shared by UI and persistence boundaries."""
from __future__ import annotations

import re
import json
import unicodedata
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Mapping


@dataclass(frozen=True, slots=True)
class ArchetypeCompatibility:
    compatible: bool
    conflicts: tuple[tuple[str, str], ...] = ()
    missing_requirements: tuple[tuple[str, str], ...] = ()
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ArchetypeChoiceOption:
    """One catalog-declared answer to an archetype choice."""

    key: str
    name: str
    description: str = ""
    class_modifications: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ArchetypeChoice:
    """A reusable one-or-many selection required by an archetype."""

    key: str
    archetype_key: str
    level: int
    name: str
    description: str
    minimum: int
    maximum: int
    options: tuple[ArchetypeChoiceOption, ...]


def archetype_choice_key(entry: Mapping[str, object], choice_key: object) -> str:
    owner = str(entry.get("key") or entry.get("name") or "archetype")
    return f"archetype-choice:{owner}:{_token(str(choice_key))}"


def archetype_choices(
    entry: Mapping[str, object], maximum_level: int = 20
) -> tuple[ArchetypeChoice, ...]:
    """Return validated structured choices without interpreting prose at runtime.

    Importers and future hand-authored catalogs share this small schema. Invalid
    or incomplete declarations are ignored so a data typo cannot break class
    selection for existing characters.
    """

    result: list[ArchetypeChoice] = []
    owner = str(entry.get("key") or entry.get("name") or "archetype")
    for raw in entry.get("choices", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        level = max(1, int(raw.get("level") or 1))
        if level > maximum_level:
            continue
        options: list[ArchetypeChoiceOption] = []
        for raw_option in raw.get("options", ()) or ():
            if not isinstance(raw_option, Mapping):
                continue
            name = str(raw_option.get("name") or "").strip()
            key = _token(str(raw_option.get("key") or name))
            if not name or not key:
                continue
            modifications = raw_option.get("class_modifications")
            options.append(
                ArchetypeChoiceOption(
                    key,
                    name,
                    str(raw_option.get("description") or "").strip(),
                    modifications if isinstance(modifications, Mapping) else None,
                )
            )
        if not options:
            continue
        minimum = max(0, int(raw.get("minimum") or 0))
        maximum = max(minimum, int(raw.get("maximum") or 1))
        maximum = min(maximum, len(options))
        minimum = min(minimum, maximum)
        raw_key = str(raw.get("key") or raw.get("name") or "choice")
        result.append(
            ArchetypeChoice(
                archetype_choice_key(entry, raw_key),
                owner,
                level,
                str(raw.get("name") or "Archetype choice").strip(),
                str(raw.get("description") or "").strip(),
                minimum,
                maximum,
                tuple(options),
            )
        )
    return tuple(result)


def selected_archetype_choice_options(
    choices: Iterable[ArchetypeChoice],
    selections: Mapping[str, Iterable[str]],
) -> tuple[ArchetypeChoiceOption, ...]:
    """Resolve saved option keys against the current catalog declarations."""

    selected: list[ArchetypeChoiceOption] = []
    for choice in choices:
        keys = {
            str(value).strip()
            for value in selections.get(choice.key, ())
            if str(value).strip()
        }
        selected.extend(option for option in choice.options if option.key in keys)
    return tuple(selected)


def encode_archetype_choice_option_keys(values: Iterable[str]) -> str:
    """Store one-or-many choices in the existing selection option field."""

    return json.dumps(
        list(dict.fromkeys(str(value).strip() for value in values if str(value).strip())),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def decode_archetype_choice_option_keys(value: object) -> tuple[str, ...]:
    """Read current JSON values and tolerate legacy single-option records."""

    text = str(value or "").strip()
    if not text:
        return ()
    try:
        decoded = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        decoded = text
    if isinstance(decoded, list):
        return tuple(
            dict.fromkeys(str(item).strip() for item in decoded if str(item).strip())
        )
    return (str(decoded).strip(),) if str(decoded).strip() else ()


def archetype_choice_selections_from_records(
    records: Iterable[object], class_level_id: int | None = None
) -> dict[str, tuple[str, ...]]:
    """Project persisted selection records without coupling rules to the database."""

    result: dict[str, tuple[str, ...]] = {}
    for record in records:
        if class_level_id is not None and int(getattr(record, "class_level_id", -1)) != class_level_id:
            continue
        key = str(getattr(record, "feature_key", "") or "")
        kind = str(getattr(record, "option_type", "") or "").strip().casefold()
        if not key.startswith("archetype-choice:") and kind != "archetype choice":
            continue
        result[key] = decode_archetype_choice_option_keys(
            getattr(record, "option_key", "")
        )
    return result


def _token(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"\b\d+(?:st|nd|rd|th)(?:-level)?\b|\+\d+", " ", value, flags=re.I)
    value = re.sub(r"\([^)]*\)|\[[^]]*\]", " ", value)
    value = re.sub(r"\b(?:the|a|an|class feature|class features|ability|abilities|at level|gained)\b", " ", value, flags=re.I)
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    aliases = {
        "bombs": "bomb", "discoveries": "discovery", "spells": "spellcasting",
        "spell-casting": "spellcasting", "rage-powers": "rage-power",
        "rogue-talents": "rogue-talent", "ki-powers": "ki-power",
        "fleshcrafter": "fleshcraft", "fleshcrafting": "fleshcraft",
        "advanced-fleshcrafting": "advanced-fleshcraft",
    }
    return aliases.get(value, value)


def replaced_features(entry: Mapping[str, object]) -> frozenset[str]:
    declared = {
        _token(str(value)) for value in (entry.get("replaces_features") or ()) if str(value).strip()
    }
    raw = str(entry.get("replaces") or "")
    if not raw:
        description = str(entry.get("description") or "")
        claims = re.findall(
            r"(?:This|These) (?:ability|abilities|class feature|class features)?\s*(?:replaces?|alters?|modifies?)\s+(?:the )?([^\n.]+)",
            description,
            re.I,
        )
        raw = "; ".join(claims)
    raw = re.sub(r"\b\d+(?:st|nd|rd|th)(?:-level)?\b", "", raw, flags=re.I)
    for part in re.split(r";|,(?![^()]*\))|\band\b", raw, flags=re.I):
        normalized = _token(part)
        if normalized and len(normalized) > 2:
            declared.add(normalized)
    return frozenset(declared)


def _comparison_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _mentioned_archetypes(
    value: object, definitions: Mapping[str, Mapping[str, object]]
) -> tuple[str, ...]:
    haystack = f" {_comparison_text(value)} "
    matches = []
    for key, definition in definitions.items():
        name = _comparison_text(definition.get("name") or "")
        if name and f" {name} " in haystack:
            matches.append(str(key))
    return tuple(matches)


def archetype_compatibility_metadata(
    entry: Mapping[str, object],
    definitions: Mapping[str, Mapping[str, object]],
) -> dict[str, tuple]:
    """Merge imported compatibility fields with rules stated in page prose.

    Archives of Nethys exposes replaced features as structured columns, while
    many Spheres pages only say that an archetype requires, permits, or blocks
    another archetype in their rules text.  Normalizing both forms here keeps
    the picker and any future validation surface on one rules boundary.
    """

    declared = entry.get("compatibility") or {}
    requires = {str(value) for value in declared.get("requires", ()) if str(value)}
    compatible = {
        str(value) for value in declared.get("explicitly_compatible", ()) if str(value)
    }
    incompatible = {
        str(value) for value in declared.get("explicitly_incompatible", ()) if str(value)
    }
    requires_any: list[frozenset[str]] = []
    for group in declared.get("requires_any", ()):
        values = (group,) if isinstance(group, str) else group
        normalized = frozenset(str(value) for value in values if str(value))
        if normalized:
            requires_any.append(normalized)

    description = str(entry.get("description") or "")
    for match in re.finditer(
        r"\bthis archetype\s+(?:requires?|must\s+(?:have|possess))\s+([^\n.;]+)",
        description,
        re.I,
    ):
        clause = match.group(1)
        mentioned = set(_mentioned_archetypes(clause, definitions))
        mentioned.discard(str(entry.get("key") or ""))
        if not mentioned:
            continue
        if re.search(r"\bor\b", clause, re.I) and len(mentioned) > 1:
            requires_any.append(frozenset(mentioned))
        else:
            requires.update(mentioned)

    folded = _comparison_text(description)
    for other_key, other in definitions.items():
        other_key = str(other_key)
        if other_key == str(entry.get("key") or ""):
            continue
        name = _comparison_text(other.get("name") or "")
        if not name:
            continue
        blocked_phrases = (
            f"not compatible with {name}",
            f"incompatible with {name}",
            f"cannot be combined with {name}",
            f"cannot combine with {name}",
        )
        allowed_phrases = (
            f"compatible with {name}",
            f"may be combined with {name}",
            f"can be combined with {name}",
        )
        if any(phrase in folded for phrase in blocked_phrases):
            incompatible.add(other_key)
        elif any(phrase in folded for phrase in allowed_phrases):
            compatible.add(other_key)

    unique_groups = tuple(
        dict.fromkeys(tuple(sorted(group)) for group in requires_any)
    )
    return {
        "requires": tuple(sorted(requires)),
        "requires_any": unique_groups,
        "explicitly_compatible": tuple(sorted(compatible)),
        "explicitly_incompatible": tuple(sorted(incompatible)),
    }


def validate_archetype_selection(
    selected_keys: Iterable[str], definitions: Mapping[str, Mapping[str, object]]
) -> ArchetypeCompatibility:
    """Validate requirements, explicit exceptions, and replaced-feature overlap.

    PF1e's normal stacking rule is declarative: archetypes can stack unless they
    replace or alter the same class feature.  Explicit compatibility text wins
    over that general rule, while explicit incompatibility always blocks it.
    """

    metadata_by_key = {
        key: archetype_compatibility_metadata(entry, definitions)
        for key, entry in definitions.items()
    }
    return _validate_archetype_selection(selected_keys, definitions, metadata_by_key)


class ArchetypeCompatibilityIndex:
    """Reusable compatibility view for an immutable archetype catalog.

    Picker UIs evaluate every remaining candidate whenever the selection changes.
    Precomputing prose-derived metadata once keeps that interaction immediate while
    preserving the exact same rules boundary used by persistence validation.
    """

    def __init__(self, definitions: Mapping[str, Mapping[str, object]]) -> None:
        self._definitions = definitions
        self._metadata_by_key = {
            key: archetype_compatibility_metadata(entry, definitions)
            for key, entry in definitions.items()
        }

    def validate(self, selected_keys: Iterable[str]) -> ArchetypeCompatibility:
        return _validate_archetype_selection(
            selected_keys, self._definitions, self._metadata_by_key
        )


def _validate_archetype_selection(
    selected_keys: Iterable[str],
    definitions: Mapping[str, Mapping[str, object]],
    metadata_by_key: Mapping[str, Mapping[str, tuple]],
) -> ArchetypeCompatibility:
    keys = tuple(dict.fromkeys(str(key) for key in selected_keys if str(key)))
    selected = set(keys)
    conflicts: list[tuple[str, str]] = []
    missing: list[tuple[str, str]] = []
    reasons: list[str] = []
    for key in keys:
        entry = definitions.get(key)
        if not entry:
            continue
        metadata = metadata_by_key.get(key, {})
        for required in metadata.get("requires", ()):
            required = str(required)
            if required not in selected:
                missing.append((key, required))
                required_name = str((definitions.get(required) or {}).get("name") or required)
                reasons.append(f"{entry.get('name', key)} requires {required_name}.")
        for group in metadata.get("requires_any", ()):
            alternatives = tuple(str(value) for value in group)
            if selected.intersection(alternatives):
                continue
            missing.append((key, "|".join(alternatives)))
            names = [
                str((definitions.get(required) or {}).get("name") or required)
                for required in alternatives
            ]
            reasons.append(
                f"{entry.get('name', key)} requires one of {', '.join(names)}."
            )
    for left_key, right_key in combinations(keys, 2):
        left = definitions.get(left_key)
        right = definitions.get(right_key)
        if not left or not right:
            continue
        left_meta = metadata_by_key.get(left_key, {})
        right_meta = metadata_by_key.get(right_key, {})
        explicit_incompatible = (
            right_key in {str(value) for value in left_meta.get("explicitly_incompatible", ())}
            or left_key in {str(value) for value in right_meta.get("explicitly_incompatible", ())}
        )
        left_requirements = set(left_meta.get("requires", ())) | {
            value for group in left_meta.get("requires_any", ()) for value in group
        }
        right_requirements = set(right_meta.get("requires", ())) | {
            value for group in right_meta.get("requires_any", ()) for value in group
        }
        explicit_compatible = (
            right_key in {str(value) for value in left_meta.get("explicitly_compatible", ())}
            or left_key in {str(value) for value in right_meta.get("explicitly_compatible", ())}
            or right_key in left_requirements
            or left_key in right_requirements
        )
        overlap = replaced_features(left) & replaced_features(right)
        if explicit_incompatible or (overlap and not explicit_compatible):
            conflicts.append((left_key, right_key))
            left_name = str(left.get("name") or left_key)
            right_name = str(right.get("name") or right_key)
            if explicit_incompatible:
                reasons.append(f"{left_name} and {right_name} are explicitly incompatible.")
            else:
                features = ", ".join(value.replace("-", " ").title() for value in sorted(overlap))
                reasons.append(f"{left_name} and {right_name} both replace or alter {features}.")
    return ArchetypeCompatibility(
        compatible=not conflicts and not missing,
        conflicts=tuple(conflicts),
        missing_requirements=tuple(missing),
        reasons=tuple(dict.fromkeys(reasons)),
    )

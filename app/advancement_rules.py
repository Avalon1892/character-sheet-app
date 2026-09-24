"""Automatic, override-friendly PF1e advancement budgets.

The calculator is deliberately pure: persistence stores only a manual layer,
while catalog/class data and the current character state produce the default.
That keeps new classes and house rules additive instead of hard-coding them in
the widgets that display the result.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from app.class_feature_rules import (
    archetype_granted_features,
    archetype_optional_features,
)
from app.archetype_rules import (
    archetype_choice_selections_from_records, archetype_choices,
    selected_archetype_choice_options,
)
from app.class_modifications import resolve_class_profile, sphere_bonus_spell_conversions
from app.class_packages import class_package
from app.drawback_rules import drawback_bonus_feat_names, sphere_drawback_talent_value
from app.models import AdvancementAdjustment, ClassLevel


@dataclass(frozen=True, slots=True)
class AdvancementBudget:
    key: str
    name: str
    automatic: int | None
    adjustment: int
    override_total: int | None
    used: int
    explanation: str

    @property
    def total(self) -> int:
        if self.override_total is not None:
            return self.override_total
        return max(0, (self.automatic if self.automatic is not None else self.used) + self.adjustment)

    @property
    def remaining(self) -> int:
        return self.total - self.used


def _table_talent_value(rules_text: str, level: int) -> int | None:
    """Read the class table already bundled in the Codex.

    Imported Spheres tables preserve cells as lines and rows as blank-line
    groups. This accepts every talent-column spelling currently in the catalog
    without coupling the calculator to individual class names.
    """

    lines = str(rules_text).splitlines()
    for index, line in enumerate(lines):
        if line.strip().casefold() != "level":
            continue
        headers = ["Level"]
        cursor = index + 1
        first_row = re.compile(r"(\d+)(?:st|nd|rd|th)?$", re.I)
        while (
            cursor < len(lines)
            and lines[cursor].strip()
            and first_row.fullmatch(lines[cursor].strip()) is None
        ):
            headers.append(lines[cursor].strip())
            cursor += 1
        candidates = [
            column for column, header in enumerate(headers)
            if "talent" in header.casefold()
            and "granted per" not in header.casefold()
            and "utility" not in header.casefold()
        ]
        if not candidates:
            continue

        # Newer catalog cleanup stores table cells as one normalized line each
        # without blank row separators.  Once the first ordinal level appears,
        # the declared header count gives us an unambiguous fixed row width.
        if cursor < len(lines) and first_row.fullmatch(lines[cursor].strip()):
            width = len(headers)
            while cursor < len(lines):
                if first_row.fullmatch(lines[cursor].strip()) is None:
                    break
                row = [lines[cursor].strip()]
                cursor += 1
                while cursor < len(lines) and len(row) < width:
                    if lines[cursor].strip():
                        row.append(lines[cursor].strip())
                    cursor += 1
                row_level = int(re.match(r"\d+", row[0]).group())
                if row_level != level:
                    continue
                values = []
                for column in candidates:
                    if column >= len(row):
                        continue
                    match = re.search(r"-?\d+", row[column])
                    if match is not None:
                        values.append(int(match.group()))
                return sum(values) if values else None
            continue

        cursor += 1
        while cursor < len(lines):
            while cursor < len(lines) and not lines[cursor].strip():
                cursor += 1
            row: list[str] = []
            while cursor < len(lines) and lines[cursor].strip():
                row.append(lines[cursor].strip())
                cursor += 1
            if not row or re.fullmatch(r"(\d+)(?:st|nd|rd|th)?", row[0], re.I) is None:
                break
            row_level = int(re.match(r"\d+", row[0]).group())
            if row_level != level:
                continue
            values = []
            for column in candidates:
                if column >= len(row):
                    continue
                match = re.search(r"-?\d+", row[column])
                if match is not None:
                    values.append(int(match.group()))
            return sum(values) if values else None
    return None


def _progression_value(level: int, progression: str) -> int:
    value = str(progression).strip().casefold()
    if value in {"one-and-a-half", "one_and_a_half", "150%"}:
        return level + (level + 1) // 2
    if value in {"five-fourths", "five_fourths", "125%"}:
        return level + level // 4
    if value in {"high", "expert", "full", "master", "virtuoso"}:
        return level
    if value in {"mid", "medium", "adept", "3/4", "journeyman"}:
        return (level * 3) // 4
    if value in {"quarter", "1/4"}:
        return level // 4
    return level // 2


def _class_talents(class_level: ClassLevel, entry: Mapping[str, object]) -> tuple[int, str]:
    level = class_level.level
    table_value = _table_talent_value(str(entry.get("rules_text", "")), level)
    if table_value is not None:
        return table_value, f"{class_level.class_name} table {table_value}"

    features = tuple(entry.get("features", ()))
    training_text = " ".join(
        str(feature.get("description", ""))
        for feature in features
        if any(word in str(feature.get("name", "")).casefold() for word in ("training", "talent"))
    )
    match = re.search(r"considered\s+(expert|adept|proficient)\s+(?:combatants?|practitioners?)", training_text, re.I)
    if match is not None:
        progression = match.group(1)
        value = _progression_value(level, progression)
        return value, f"{class_level.class_name} {progression.title()} progression {value}"

    casting = entry.get("casting", {})
    if isinstance(casting, Mapping):
        progression = str(casting.get("sphere_progression", ""))
        if progression:
            value = _progression_value(level, progression)
            return value, f"{class_level.class_name} {progression.title()} magic progression {value}"
    return 0, ""


def _talent_progression_from_text(
    text: str, level: int, source_name: str
) -> tuple[int, str]:
    """Resolve the common Spheres talent-progression prose contracts."""

    every_level = re.search(
        r"\bgain(?:s)?\s+(?:either\s+)?(?:a|one)\s+"
        r"(?:combat\s+or\s+magic\s+|magic\s+or\s+combat\s+)?talent\s+"
        r"at\s+every\s+class\s+level\b",
        text,
        re.I,
    )
    if every_level is not None:
        return level, f"{source_name} one talent per level {level}"

    ratio = re.search(
        r"\bgain(?:s)?\s+(?P<count>\d+)\s+talents?\s+every\s+"
        r"(?P<levels>\d+)\s+(?:class\s+)?levels?\b",
        text,
        re.I,
    )
    if ratio is not None:
        count = int(ratio.group("count"))
        levels = max(1, int(ratio.group("levels")))
        value = (level * count) // levels
        return value, f"{source_name} {count}/{levels} progression {value}"

    combatant = re.search(
        r"considered\s+(?:an?\s+)?(expert|adept|proficient)\s+"
        r"(?:combatants?|practitioners?)",
        text,
        re.I,
    )
    if combatant is not None:
        progression = combatant.group(1)
        value = _progression_value(level, progression)
        return value, f"{source_name} {progression.title()} progression {value}"
    return 0, ""


def _selected_feature_keys_by_class(
    selections: Iterable[object],
) -> dict[int, frozenset[str]]:
    values: dict[int, set[str]] = {}
    for selection in selections:
        class_level_id = getattr(selection, "class_level_id", None)
        feature_key = str(getattr(selection, "feature_key", "") or "")
        if class_level_id is None or not feature_key:
            continue
        values.setdefault(int(class_level_id), set()).add(feature_key)
    return {class_level_id: frozenset(keys) for class_level_id, keys in values.items()}


def _archetype_talents(
    class_level: ClassLevel,
    archetype: Mapping[str, object],
    selected_feature_keys: frozenset[str],
) -> tuple[int, str]:
    """Resolve one archetype's effective progression, including opt-in trades."""

    for option in archetype_optional_features(archetype, class_level.level):
        if option.key not in selected_feature_keys:
            continue
        value, source = _talent_progression_from_text(
            option.description, class_level.level, f"{archetype.get('name', 'Archetype')}: {option.name}"
        )
        if source:
            return value, source

    features = archetype_granted_features(archetype, class_level.level)
    training_text = " ".join(
        feature.description
        for feature in features
        if any(word in feature.name.casefold() for word in ("training", "talent"))
    )
    return _talent_progression_from_text(
        training_text, class_level.level, str(archetype.get("name") or "Archetype")
    )


def _archetype_has_sphere_casting(
    archetype: Mapping[str, object],
    level: int,
    selected_feature_keys: frozenset[str],
) -> bool:
    features = archetype_granted_features(archetype, level)
    if any(
        feature.name.casefold() == "casting"
        or re.search(r"considered\s+(?:an?\s+)?(?:high|mid|low)[ -]?caster", feature.description, re.I)
        for feature in features
    ):
        return True
    if any(
        option.key in selected_feature_keys
        and re.search(r"(?:high|mid|low)[ -]?caster|casting tradition", option.description, re.I)
        for option in archetype_optional_features(archetype, level)
    ):
        return True
    declaration = archetype.get("sphere_capabilities") or {}
    # Declarations inferred from an optional paragraph (notably Adventurer's
    # Greater Training) are not active until that paragraph is selected.
    return bool(
        "magic" in declaration.get("grants", ())
        and not archetype_optional_features(archetype, level)
    )


def _archetype_removes_traditional_spells(
    archetype: Mapping[str, object],
    level: int,
    selected_feature_keys: frozenset[str],
) -> bool:
    declaration = archetype.get("sphere_capabilities") or {}
    if "traditional_spells" in declaration.get("removes", ()):
        return True
    nonoptional_text = " ".join(
        feature.description for feature in archetype_granted_features(archetype, level)
    )
    if re.search(
        r"not able to learn or create extracts|replaces?\s+(?:the\s+)?(?:spells?|extracts?)\s+class feature",
        nonoptional_text,
        re.I,
    ):
        return True
    return any(
        option.key in selected_feature_keys
        and any("spell" in replacement.casefold() or "extract" in replacement.casefold()
                for replacement in option.replaces)
        for option in archetype_optional_features(archetype, level)
    )


def _allocation_total(allocations: Mapping[str, object] | Iterable[object]) -> int:
    values = allocations.values() if isinstance(allocations, Mapping) else allocations
    total = 0
    for allocation in values:
        if isinstance(allocation, (int, float)):
            total += int(allocation)
        else:
            total += int(getattr(allocation, "points", 0) or 0)
    return total


_HIGH_SPELLS_KNOWN = (
    6, 7, 8, 10, 12, 14, 17, 19, 22, 24,
    28, 29, 32, 33, 36, 37, 40, 41, 43, 44,
)
_MED_SPELLS_KNOWN = (
    6, 8, 10, 12, 13, 14, 17, 18, 19, 20,
    22, 24, 25, 26, 28, 29, 30, 31, 34, 35,
)


def _spells_known_capacity(
    classes: Iterable[ClassLevel],
    class_lookup: Callable[[str], Mapping[str, object] | None],
    archetypes_by_class: Mapping[int, tuple[Mapping[str, object], ...]] | None = None,
    selected_features_by_class: Mapping[int, frozenset[str]] | None = None,
    choice_selections_by_class: Mapping[int, Mapping[str, Iterable[str]]] | None = None,
) -> tuple[int | None, str, bool]:
    total = 0
    sources: list[str] = []
    open_ended = False
    has_traditional = False
    archetypes_by_class = archetypes_by_class or {}
    selected_features_by_class = selected_features_by_class or {}
    choice_selections_by_class = choice_selections_by_class or {}
    for class_level in classes:
        entry = class_lookup(class_level.preset_key) or {}
        selected_features = selected_features_by_class.get(class_level.id, frozenset())
        if any(
            _archetype_removes_traditional_spells(archetype, class_level.level, selected_features)
            for archetype in archetypes_by_class.get(class_level.id, ())
        ):
            continue
        profile = resolve_class_profile(
            entry,
            archetypes_by_class.get(class_level.id, ()),
            choice_selections_by_class.get(class_level.id, {}),
        )
        casting = profile.casting
        if casting.get("traditional") is False:
            continue
        casting_type = str(casting.get("type", "")).casefold() if isinstance(casting, Mapping) else ""
        if casting_type == "prepared":
            has_traditional = True
            open_ended = True
            sources.append(f"{class_level.class_name}: prepared/open spell list")
        elif casting_type == "spontaneous":
            has_traditional = True
            progression = str(casting.get("progression", "")).casefold()
            if progression in {"high", "full"}:
                value = _HIGH_SPELLS_KNOWN[class_level.level - 1]
            elif progression in {"med", "mid", "medium", "3/4"}:
                value = _MED_SPELLS_KNOWN[class_level.level - 1]
            else:
                # Four-level spontaneous classes differ substantially. Keep
                # them editable until a class-specific table provider is added.
                open_ended = True
                sources.append(f"{class_level.class_name}: class-specific known progression")
                continue
            per_level_adjustment = int(
                casting.get("spells_known_per_spell_level_adjustment") or 0
            )
            if per_level_adjustment:
                if progression in {"high", "full"}:
                    # Sorcerers unlock 1st-level spells at class level 1,
                    # 2nd-level spells at 4, and one further level every two
                    # class levels thereafter.  This differs from the full
                    # prepared-caster schedule at odd class levels.
                    highest_spell_level = min(9, max(1, class_level.level // 2))
                else:
                    highest_spell_level = min(6, max(1, (class_level.level + 2) // 3))
                rows = highest_spell_level + 1  # cantrips plus every unlocked level
                value = max(0, value + per_level_adjustment * rows)
            total += value
            sources.append(f"{class_level.class_name}: {value}")
    return (
        None if open_ended and total == 0 else total,
        "; ".join(sources) or "No traditional spellcasting class",
        has_traditional,
    )


_ORDINAL_LEVEL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", re.I)


def _removed_bonus_feat_levels(
    archetypes: Iterable[Mapping[str, object]],
    available_levels: Iterable[int],
) -> frozenset[int]:
    """Read only explicit feature-exchange sentences from structured data.

    The importer already splits archetype rules into named feature records.
    This narrow resolver recognizes the standard Pathfinder wording for a
    bonus-feat exchange; it never searches unrelated descriptive paragraphs.
    """

    available = frozenset(int(value) for value in available_levels)
    removed: set[int] = set()
    for archetype in archetypes:
        for feature in archetype.get("features", ()):
            if not isinstance(feature, Mapping):
                continue
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(feature.get("description") or "")):
                folded = sentence.casefold()
                if "replac" not in folded or "bonus feat" not in folded:
                    continue
                levels = {
                    int(match.group(1))
                    for match in _ORDINAL_LEVEL.finditer(sentence)
                    if int(match.group(1)) in available
                }
                if levels:
                    removed.update(levels)
                elif re.search(
                    r"replaces?\s+(?:all\s+)?(?:of\s+)?(?:the\s+)?"
                    r"(?:fighter(?:'s|\u2019s)?\s+|sorcerer(?:'s|\u2019s)?\s+)?bonus feats?",
                    sentence,
                    re.I,
                ):
                    removed.update(available)
    return frozenset(removed)


def calculate_advancement_budgets(
    *,
    classes: Iterable[ClassLevel],
    class_lookup: Callable[[str], Mapping[str, object] | None],
    intelligence_modifier: int,
    race: str,
    skill_ranks: int,
    favored_skill_points: int,
    feats: Iterable,
    martial_talents: Iterable,
    spells: Iterable,
    traditions: Iterable,
    adjustments: Mapping[str, AdvancementAdjustment],
    ability_score_increases: Mapping[str, object] | Iterable[object] = (),
    archetype_keys_by_class_level: Mapping[int, Iterable[str]] | None = None,
    archetype_lookup: Callable[[str], Mapping[str, object] | None] | None = None,
    feature_selections: Iterable[object] = (),
    granted_skill_ranks: int = 0,
    racial_advancement: Mapping[str, int] | None = None,
) -> tuple[AdvancementBudget, ...]:
    classes = tuple(classes)
    feats = tuple(feats)
    martial_talents = tuple(martial_talents)
    spells = tuple(spells)
    traditions = tuple(traditions)
    feature_selections = tuple(feature_selections)
    level = sum(item.level for item in classes)
    selected_features_by_class = _selected_feature_keys_by_class(feature_selections)
    choice_selections_by_class = {
        item.id: archetype_choice_selections_from_records(feature_selections, item.id)
        for item in classes
    }
    archetype_keys_by_class_level = archetype_keys_by_class_level or {}
    archetypes_by_class: dict[int, tuple[Mapping[str, object], ...]] = {}
    if archetype_lookup is not None:
        for item in classes:
            archetypes_by_class[item.id] = tuple(
                entry
                for key in archetype_keys_by_class_level.get(item.id, ())
                if (entry := archetype_lookup(str(key))) is not None
            )

    skill_total = 0
    skill_sources: list[str] = []
    for item in classes:
        entry = class_lookup(item.preset_key) or {}
        profile = resolve_class_profile(
            entry,
            archetypes_by_class.get(item.id, ()),
            choice_selections_by_class.get(item.id, {}),
        )
        per_level = max(1, profile.skill_points + intelligence_modifier)
        gained = per_level * item.level
        skill_total += gained
        skill_sources.append(f"{item.class_name} {item.level}×{per_level}")
    legacy_human = race.strip().casefold() == "human" and racial_advancement is None
    racial_skill_per_level = (
        int(racial_advancement.get("skill_points_per_level", 0))
        if racial_advancement is not None else (1 if legacy_human else 0)
    )
    if racial_skill_per_level:
        racial_skill_total = level * racial_skill_per_level
        skill_total += racial_skill_total
        skill_sources.append(f"racial traits +{racial_skill_total}")
    skill_total += favored_skill_points
    if favored_skill_points:
        skill_sources.append(f"favored class +{favored_skill_points}")
    granted_skill_ranks = max(0, int(granted_skill_ranks))
    skill_total += granted_skill_ranks
    if granted_skill_ranks:
        skill_sources.append(f"rule-granted ranks +{granted_skill_ranks}")

    class_granted_feats = tuple(
        item for item in feats
        if str(getattr(item, "catalog_category", "")).casefold().startswith(
            "class granted"
        )
    )
    counted_feats = tuple(item for item in feats if item not in class_granted_feats)

    feat_total = (level + 1) // 2
    feat_sources = [f"odd character levels {(level + 1) // 2}"]
    racial_feat_slots = (
        int(racial_advancement.get("feat_slots", 0))
        if racial_advancement is not None else (1 if legacy_human else 0)
    )
    if racial_feat_slots:
        feat_total += racial_feat_slots
        feat_sources.append(f"racial traits +{racial_feat_slots}")
    for item in classes:
        package = class_package(item.preset_key)
        if package is None or not package.bonus_feat_levels:
            continue
        profile = resolve_class_profile(
            class_lookup(item.preset_key) or {},
            archetypes_by_class.get(item.id, ()),
            choice_selections_by_class.get(item.id, {}),
        )
        override_levels = tuple(
            max(1, int(value))
            for value in profile.advancement.get("bonus_feat_levels", ())
        )
        available = tuple(
            value
            for value in (override_levels or package.bonus_feat_levels)
            if value <= item.level
        )
        removed = set(
            frozenset()
            if override_levels
            else _removed_bonus_feat_levels(
                archetypes_by_class.get(item.id, ()), available
            )
        )
        provider_key = package.bonus_feat_replacement_choice_provider
        schedules = package.bonus_feat_replacement_levels_by_points or {}
        if provider_key and schedules:
            selection = next(
                (
                    record for record in feature_selections
                    if int(getattr(record, "class_level_id", -1)) == item.id
                    and str(getattr(record, "feature_key", ""))
                    == f"class-choice:{provider_key}"
                ),
                None,
            )
            try:
                selected_keys = tuple(json.loads(str(getattr(selection, "option_key", "") or "[]")))
            except (TypeError, ValueError, json.JSONDecodeError):
                selected_keys = ()
            provider = next(
                (choice for choice in package.choice_providers if choice.key == provider_key),
                None,
            )
            costs = {
                option.key: option.cost
                for option in (provider.fixed_options if provider is not None else ())
            }
            spent = min(5, sum(costs.get(key.rsplit(":", 1)[-1], 0) for key in selected_keys))
            removed.update(schedules.get(spent, ()))
        retained = sum(value not in removed for value in available)
        if retained:
            feat_total += retained
            label = str(
                profile.advancement.get("bonus_feat_label")
                or package.bonus_feat_label
            )
            feat_sources.append(f"{label} +{retained}")

    talent_total = 0
    talent_sources: list[str] = []
    has_sphere_casting = False
    for item in classes:
        entry = class_lookup(item.preset_key) or {}
        profile = resolve_class_profile(
            entry,
            archetypes_by_class.get(item.id, ()),
            choice_selections_by_class.get(item.id, {}),
        )
        declared_progression = str(
            profile.advancement.get("talent_progression") or ""
        )
        candidates = [] if declared_progression else [_class_talents(item, entry)]
        if declared_progression:
            declared_value = _progression_value(item.level, declared_progression)
            candidates.append((
                declared_value,
                f"{item.class_name} {declared_progression.title()} progression {declared_value}",
            ))
        selected_features = selected_features_by_class.get(item.id, frozenset())
        candidates.extend(
            _archetype_talents(item, archetype, selected_features)
            for archetype in archetypes_by_class.get(item.id, ())
        )
        replacement_levels = tuple(
            max(1, int(value))
            for value in profile.advancement.get("talent_bonus_levels", ())
        )
        if profile.advancement.get("talent_replaces_base"):
            gained = sum(item.level >= level for level in replacement_levels)
            source = (
                f"{item.class_name} replacement talent schedule {gained}"
                if gained else ""
            )
        else:
            gained, source = max(candidates, key=lambda candidate: candidate[0])
            bonus = sum(item.level >= level for level in replacement_levels)
            if bonus:
                gained += bonus
                source = f"{source}; class-granted talents +{bonus}" if source else f"Class-granted talents +{bonus}"
        for group in sphere_bonus_spell_conversions(
            entry, archetypes_by_class.get(item.id, ()), item.level,
            choice_selections_by_class.get(item.id, {}),
        ):
            if group.get("adds_known", True):
                gained += 1
                talent_sources.append(f"{group['source']}: spells-known group → 1 magic talent")
        talent_total += gained
        if source:
            talent_sources.append(source)
        declared_choices = tuple(
            choice
            for archetype in archetypes_by_class.get(item.id, ())
            for choice in archetype_choices(archetype, item.level)
        )
        for option in selected_archetype_choice_options(
            declared_choices, choice_selections_by_class.get(item.id, {})
        ):
            advancement = (
                option.class_modifications.get("advancement", {})
                if isinstance(option.class_modifications, Mapping) else {}
            )
            schedule = (
                advancement.get("talent_bonus_schedule", {})
                if isinstance(advancement, Mapping) else {}
            )
            if not isinstance(schedule, Mapping):
                continue
            first = max(1, int(schedule.get("first_level") or 1))
            every = max(1, int(schedule.get("every_levels") or 1))
            count = max(0, int(schedule.get("count") or 0))
            bonus = 0 if item.level < first else (1 + (item.level - first) // every) * count
            if bonus:
                talent_total += bonus
                talent_sources.append(f"{option.name} +{bonus}")
        casting = profile.casting
        has_sphere_casting = has_sphere_casting or (
            isinstance(casting, Mapping) and bool(casting.get("sphere_progression"))
        ) or any(
            _archetype_has_sphere_casting(archetype, item.level, selected_features)
            for archetype in archetypes_by_class.get(item.id, ())
        )
    if has_sphere_casting:
        talent_total += 2
        talent_sources.append("first Casting feature +2")
    martial_traditions = sum(1 for item in traditions if str(getattr(item, "kind", "")).casefold() == "martial")
    if martial_traditions:
        talent_total += 4 * martial_traditions
        talent_sources.append(f"martial tradition +{4 * martial_traditions}")
    martial_drawback_count = sum(
        1 for item in martial_talents
        if str(getattr(item, "catalog_category", "")) == "Drawback"
    )
    magic_drawbacks = tuple(
        item for item in spells
        if str(getattr(item, "catalog_category", "")) == "Drawback"
    )
    drawback_count = martial_drawback_count + sum(
        sphere_drawback_talent_value(item) for item in magic_drawbacks
    )
    talent_total += drawback_count
    if drawback_count:
        talent_sources.append(f"sphere drawbacks +{drawback_count}")
    drawback_bonus_feats = sum(
        len(drawback_bonus_feat_names({
            "sphere": str(getattr(item, "school_or_sphere", "")),
            "name": str(getattr(item, "name", "")),
        }))
        for item in magic_drawbacks
    )
    if drawback_bonus_feats:
        feat_total += drawback_bonus_feats
        feat_sources.append(f"sphere-drawback bonus feats +{drawback_bonus_feats}")
    free_base_choices = sum(
        1 for item in martial_talents
        if str(getattr(item, "catalog_category", "")) == "Base Sphere"
        and (
            (
                str(getattr(item, "sphere", "")) in {"Equipment", "Tech"}
                and bool(str(getattr(item, "choice", "")).strip())
            )
            or (
                str(getattr(item, "sphere", "")) == "Alchemy"
                and str(getattr(item, "choice", "")).startswith("Formulae —")
            )
        )
    )
    talent_total += free_base_choices
    if free_base_choices:
        talent_sources.append(f"base-sphere granted talents +{free_base_choices}")
    extra_talent_feats = sum(
        1 for item in feats
        if re.search(r"extra\s+(?:combat|magic|martial|sphere)\s+talent", str(getattr(item, "name", "")), re.I)
    )
    talent_total += extra_talent_feats
    if extra_talent_feats:
        talent_sources.append(f"extra-talent feats +{extra_talent_feats}")

    talent_used = sum(
        1 for item in martial_talents
        if str(getattr(item, "catalog_category", "")) not in {"Drawback", "Tradition"}
    ) + sum(
        1 for item in spells
        if str(getattr(item, "system", "")) == "Sphere"
        and str(getattr(item, "catalog_category", "")) != "Drawback"
    )
    traditional_spells = tuple(
        item for item in spells
        if str(getattr(item, "system", "")) != "Sphere"
        and str(getattr(item, "catalog_category", "")) != "Base Sphere"
    )
    spell_capacity, spell_source, has_traditional_spells = _spells_known_capacity(
        classes, class_lookup, archetypes_by_class, selected_features_by_class,
        choice_selections_by_class,
    )

    raw = [
        (
            "ability_score_increases",
            "Ability score increases",
            level // 4,
            _allocation_total(ability_score_increases),
            f"character levels 4, 8, 12, 16, and 20: {level // 4}",
        ),
        ("skill_points", "Skill points", skill_total, skill_ranks, "; ".join(skill_sources) or "No class levels"),
        ("feats", "Feats", feat_total, len(counted_feats), "; ".join(feat_sources)),
        ("talents", "Sphere talents", talent_total, talent_used, "; ".join(talent_sources) or "No sphere talent progression"),
    ]
    if has_traditional_spells:
        raw.append(
            ("spells", "Spells known / recorded", spell_capacity, len(traditional_spells), spell_source)
        )
    result = []
    for key, name, automatic, used, explanation in raw:
        saved = adjustments.get(key, AdvancementAdjustment(0, key))
        result.append(AdvancementBudget(
            key, name, automatic, saved.adjustment, saved.override_total, used,
            f"{explanation}" + (f" · {saved.note}" if saved.note else ""),
        ))
    return tuple(result)

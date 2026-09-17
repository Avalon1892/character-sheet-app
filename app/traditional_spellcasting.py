"""Shared traditional-spellcasting projections.

This module is deliberately independent of Qt.  The normal sheet, alternate
sheet types, and the Spell Book all consume the same archetype-aware caster
profiles and slot calculations.
"""
from __future__ import annotations

from app.archetype_rules import archetype_choice_selections_from_records
from app.class_capabilities import resolve_sphere_capabilities
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, entries
from app.database import CharacterRepository
from app.prepared_spell_rules import PreparedCasterCapacity, prepared_spell_slots
from app.services.character_calculations import CharacterCalculationService
from app.spontaneous_spell_rules import (
    SpontaneousCasterCapacity,
    spontaneous_spell_slots,
)


_ABILITY_KEYS = {
    "int": "intelligence",
    "intelligence": "intelligence",
    "wis": "wisdom",
    "wisdom": "wisdom",
    "cha": "charisma",
    "charisma": "charisma",
}


def _class_definitions() -> dict[str, dict]:
    definitions = {str(entry["key"]): entry for entry in entries("classes")}
    for key, entry in tuple(definitions.items()):
        if not key.startswith(("pathfinder-class:", "spheres-class:")):
            definitions.setdefault(f"pathfinder-class:{key}", entry)
    return definitions


def traditional_casting_classes(
    repository: CharacterRepository, character_id: int
) -> tuple[tuple[object, dict], ...]:
    """Return class rows and effective traditional-casting declarations.

    Capability checks and casting modifications use the same selected
    archetypes and declarative choice records as the rest of the rules engine.
    """

    classes = repository.list_class_levels(character_id)
    archetypes_by_level = repository.list_class_archetype_keys(character_id)
    selected_keys = {key for values in archetypes_by_level.values() for key in values}
    archetype_definitions = {
        key: value
        for key in selected_keys
        if (value := archetype_entry(key)) is not None
    }
    definitions = _class_definitions()
    selections = repository.list_class_feature_selections(character_id)
    result: list[tuple[object, dict]] = []
    for class_level in classes:
        selected_archetypes = tuple(
            archetype_definitions[key]
            for key in archetypes_by_level.get(class_level.id, ())
            if key in archetype_definitions
        )
        local = resolve_sphere_capabilities(
            (class_level,),
            {class_level.id: archetypes_by_level.get(class_level.id, ())},
            archetype_definitions,
            definitions,
        )
        if not local.traditional_spells:
            continue
        definition = definitions.get(class_level.preset_key) or definitions.get(
            f"pathfinder-class:{class_level.preset_key}", {}
        )
        profile = resolve_class_profile(
            definition,
            selected_archetypes,
            archetype_choice_selections_from_records(selections, class_level.id),
        )
        casting = dict(profile.casting)
        if casting.get("traditional") is False:
            continue
        result.append((class_level, casting))
    return tuple(result)


def traditional_spellbook_blocked_by_archetype(
    repository: CharacterRepository, character_id: int
) -> bool:
    """Whether selected archetypes removed every class-backed spellbook.

    A saved spell record is deliberately independent from class selection so
    changing an archetype never destroys character data.  Presentation code,
    however, must not expose those dormant records when the character had a
    traditional casting class and selected archetypes removed all effective
    traditional casting.  Standalone limited-use/custom spell records on a
    character that never had a casting class remain supported.
    """

    effective_ids = {
        class_level.id
        for class_level, _casting in traditional_casting_classes(
            repository, character_id
        )
    }
    if effective_ids:
        # A multiclass character keeps the book for any retained caster.  Spell
        # ownership is intentionally not inferred from names or descriptions.
        return False
    definitions = _class_definitions()
    archetypes_by_level = repository.list_class_archetype_keys(character_id)
    for class_level in repository.list_class_levels(character_id):
        if not archetypes_by_level.get(class_level.id):
            continue
        definition = definitions.get(class_level.preset_key) or definitions.get(
            f"pathfinder-class:{class_level.preset_key}", {}
        )
        casting = definition.get("casting") or {}
        base_traditional = casting.get("traditional") is not False and any(
            casting.get(key) for key in ("ability", "progression", "spells", "type")
        )
        if base_traditional and class_level.id not in effective_ids:
            return True
    return False


def prepared_caster_capacities(
    repository: CharacterRepository, character_id: int
) -> tuple[PreparedCasterCapacity, ...]:
    calculator = CharacterCalculationService(repository, character_id)
    result = []
    from app.class_choice_rules import resolve_class_choice_slots

    selected_providers = {
        (slot.class_level_id, slot.key)
        for slot in resolve_class_choice_slots(repository, character_id)
        if slot.selected_options
    }
    for class_level, casting in traditional_casting_classes(repository, character_id):
        if str(casting.get("type") or "").casefold() != "prepared":
            continue
        ability = _ABILITY_KEYS.get(
            str(casting.get("ability") or "").casefold(), "intelligence"
        )
        modifier = calculator.ability_result(ability).ability_modifier
        package = class_package(class_level.preset_key)
        bonus_provider = (
            package.prepared_bonus_slot_choice_provider if package else ""
        )
        result.append(
            PreparedCasterCapacity(
                class_level.id,
                class_level.class_name,
                class_level.preset_key,
                class_level.level,
                ability,
                prepared_spell_slots(
                    class_level.preset_key,
                    class_level.class_name,
                    class_level.level,
                    str(casting.get("progression") or "high"),
                    modifier,
                    daily_slot_adjustment=int(
                        casting.get("daily_slot_adjustment") or 0
                    ),
                    bonus_slot_per_spell_level=(
                        1
                        if bonus_provider
                        and (class_level.id, bonus_provider) in selected_providers
                        else 0
                    ),
                ),
            )
        )
    return tuple(result)


def spontaneous_caster_capacities(
    repository: CharacterRepository, character_id: int
) -> tuple[SpontaneousCasterCapacity, ...]:
    calculator = CharacterCalculationService(repository, character_id)
    result = []
    for class_level, casting in traditional_casting_classes(repository, character_id):
        if str(casting.get("type") or "").casefold() != "spontaneous":
            continue
        ability = _ABILITY_KEYS.get(
            str(casting.get("ability") or "").casefold(), "charisma"
        )
        modifier = calculator.ability_result(ability).ability_modifier
        base, bonus, total = spontaneous_spell_slots(
            class_level.level,
            str(casting.get("progression") or "high"),
            modifier,
        )
        result.append(
            SpontaneousCasterCapacity(
                class_level.id,
                class_level.class_name,
                class_level.preset_key,
                class_level.level,
                ability,
                base,
                bonus,
                total,
            )
        )
    return tuple(result)

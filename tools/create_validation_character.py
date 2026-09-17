"""Create a catalogue-backed character used for end-to-end release validation.

This is intentionally built from the same repository, catalog, automation, and
calculation extension points as the desktop UI.  It doubles as a repeatable
smoke fixture when those extension points change in the future.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content import feat_entries, item_entries, magic_entries, trait_entries
from app.database import CharacterRepository
from app.item_effects import automation_for_entry, automation_json
from app.models import (
    CharacterDetails,
    CurrencyPurse,
    HitPoints,
    SkillState,
    WORN_SLOTS,
)
from app.rules import calculate_casting_statistics
from app.services.character_calculations import CharacterCalculationService


CHARACTER_NAME = "Aster, Codex Cartographer"


def _by_name(records: tuple[dict, ...], name: str) -> dict:
    matches = [record for record in records if str(record["name"]) == name]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one catalog entry named {name!r}; found {len(matches)}.")
    return matches[0]


def _substituted_effects(entry: dict, choice_key: str = "") -> list[dict]:
    result = []
    for source in dict(entry.get("automation") or {}).get("effects", ()):
        effect = dict(source)
        effect["target"] = str(effect.get("target", "")).replace(
            "{choice_key}", choice_key
        )
        effect["scope"] = str(effect.get("scope", "")).replace(
            "{choice_key}", choice_key
        )
        result.append(effect)
    return result


def _add_feat(
    repository: CharacterRepository,
    character_id: int,
    name: str,
    *,
    choice: str = "",
    choice_key: str = "",
) -> None:
    entry = _by_name(feat_entries(), name)
    automation = dict(entry.get("automation") or {})
    categories = ", ".join(str(value) for value in entry.get("categories", ())) or "General"
    feat_id = repository.add_feat(
        character_id,
        name=str(entry["name"]),
        notes=str(entry.get("description") or ""),
        catalog_key=str(entry["key"]),
        catalog_category=f"{entry['source_group']} · {categories}",
        prerequisites=str(entry.get("prerequisites") or ""),
        source_url=str(entry.get("source_url") or ""),
        choice=choice,
        effects=_substituted_effects(entry, choice_key),
        repeatable=bool(entry.get("repeatable", False)),
        activation=str(automation.get("activation") or "always"),
        activation_note=str(automation.get("activation_note") or ""),
    )
    if automation and not bool(automation.get("default_enabled", True)):
        repository.set_feat_enabled(character_id, feat_id, False)


def _add_trait(repository: CharacterRepository, character_id: int, name: str) -> None:
    entry = _by_name(trait_entries(), name)
    automation = dict(entry.get("automation") or {})
    categories = ", ".join(str(value) for value in entry.get("categories", ())) or "General"
    trait_id = repository.add_trait(
        character_id,
        name=str(entry["name"]),
        notes=str(entry.get("description") or ""),
        catalog_key=str(entry["key"]),
        catalog_category=f"{entry['source_group']} · {categories}",
        prerequisites=str(entry.get("prerequisites") or ""),
        source_url=str(entry.get("source_url") or ""),
        effects=_substituted_effects(entry),
        repeatable=bool(entry.get("repeatable", False)),
        activation=str(automation.get("activation") or "always"),
        activation_note=str(automation.get("activation_note") or ""),
    )
    if automation and not bool(automation.get("default_enabled", True)):
        repository.set_trait_enabled(character_id, trait_id, False)


def _add_magic(repository: CharacterRepository, character_id: int, name: str) -> None:
    entry = _by_name(magic_entries(), name)
    automation = dict(entry.get("automation") or {})
    spell_id = repository.add_spell(
        character_id,
        name=str(entry["name"]),
        system="Sphere",
        school_or_sphere=str(entry["sphere"]),
        notes=str(entry.get("description") or ""),
        catalog_key=str(entry["key"]),
        catalog_category=str(entry["category"]),
        prerequisites=str(entry.get("prerequisites") or ""),
        source_url=str(entry.get("source_url") or ""),
        effects=_substituted_effects(entry),
        activation=str(automation.get("activation") or "always"),
        activation_note=str(automation.get("activation_note") or ""),
    )
    if automation and not bool(automation.get("default_enabled", True)):
        repository.set_spell_enabled(character_id, spell_id, False)


def _add_item(
    repository: CharacterRepository,
    character_id: int,
    name: str,
    *,
    choices: dict[str, str] | None = None,
) -> int:
    entry = _by_name(item_entries(), name)
    item_automation = automation_for_entry(entry)
    legacy = dict(entry.get("automation") or {})
    raw_slot = str(entry.get("slot") or "")
    slot_lookup = {slot.casefold(): slot for slot in WORN_SLOTS}
    slot = slot_lookup.get(raw_slot.casefold(), "")
    item_type = str(entry.get("item_type") or "").casefold()
    bonus_type = str(legacy.get("bonus_type") or "untyped")
    if bonus_type == "armor":
        category = "Armor"
    elif bonus_type == "shield":
        category = "Shield"
    elif item_type in {"weapon", "ammo"} or "weapon" in str(entry.get("family", "")).casefold():
        category = "Weapon"
    elif any(word in item_type for word in ("consumable", "potion", "scroll")):
        category = "Consumable"
    else:
        category = "Gear"
    state = (
        "armor" if category == "Armor"
        else "shield" if category == "Shield"
        else "wielded" if category == "Weapon"
        else "worn" if slot
        else "carried"
    )
    weapon = dict(entry.get("weapon") or {})
    return repository.add_equipment(
        character_id,
        name=str(entry["name"]),
        category=category,
        quantity=1,
        weight=float(entry.get("weight_lb") or 0),
        equipped=True,
        ac_bonus=int(legacy.get("ac_bonus") or 0),
        bonus_type=bonus_type,
        max_dex_bonus=legacy.get("max_dex_bonus"),
        armor_check_penalty=int(legacy.get("armor_check_penalty") or 0),
        notes=str(entry.get("description") or ""),
        slot=slot,
        value_gp=float(entry.get("price_gp") or 0),
        catalog_key=str(entry["key"]),
        catalog_source=str(entry.get("source_group") or ""),
        state=state,
        choices_json=json.dumps(choices or {}, separators=(",", ":")),
        automation_json=automation_json(item_automation),
        weapon_damage_dice=str(weapon.get("damage_dice") or ""),
        weapon_damage_type=str(weapon.get("damage_type") or ""),
        weapon_critical=str(weapon.get("critical") or ""),
        weapon_range=str(weapon.get("range") or ""),
    )


def build_character(repository: CharacterRepository, name: str = CHARACTER_NAME) -> int:
    """Build and verify a legal level-six Spheres utility caster."""
    character_id = repository.create_character(name, "Spheres")
    repository.update_character_details(
        CharacterDetails(
            character_id,
            player_name="Codex",
            race="Elf",
            alignment="N",
            deity="Nethys",
            size="Medium",
            race_key="elf",
        )
    )
    for ability, score in {
        "strength": 8,
        "dexterity": 14,
        "constitution": 14,
        "intelligence": 18,
        "wisdom": 12,
        "charisma": 10,
    }.items():
        repository.update_ability_score(character_id, ability, score)

    repository.add_class_level(
        character_id,
        "Incanter",
        6,
        "1/2",
        "Poor",
        "Poor",
        "Good",
        preset_key="spheres-class:incanter",
        hit_die=6,
        hp_gained=26,
    )

    for name in (
        "Warp Sphere",
        "Distant Teleport",
        "Emergency Teleport",
        "Quick Teleport",
        "Ranged Warp [range]",
        "Divination Sphere",
        "Expanded Divinations",
        "Fast Divinations",
        "Greater Divine [range]",
        "Protection Sphere",
        "Community",
        "Enduring Protection",
        "Greater Barrier",
    ):
        _add_magic(repository, character_id, name)

    for name in (
        "Improved Initiative",
        "Great Fortitude",
        "Spell Penetration",
    ):
        _add_feat(repository, character_id, name)
    _add_feat(repository, character_id, "Sphere Focus", choice="Warp", choice_key="warp")
    _add_feat(repository, character_id, "Extra Magic Talent")
    _add_feat(repository, character_id, "Extra Magic Talent")
    _add_feat(repository, character_id, "Extra Spell Points")
    _add_trait(repository, character_id, "Reactionary")
    _add_trait(repository, character_id, "Focused Mind")

    crossbow_id = _add_item(repository, character_id, "Light Crossbow")
    _add_item(
        repository,
        character_id,
        "Headband of Vast Intelligence +2",
        choices={"trained_skill": "spellcraft"},
    )
    _add_item(repository, character_id, "Cloak of Resistance +1")
    _add_item(repository, character_id, "Ring of Protection +1")
    _add_item(repository, character_id, "Handy Haversack")
    repository.add_attack(
        character_id,
        "Light Crossbow",
        "Ranged",
        "dexterity",
        0,
        "1d8",
        None,
        0.0,
        0,
        "19-20/x2",
        "80 ft; move action to reload",
        equipment_id=crossbow_id,
    )

    for key in (
        "spellcraft",
        "knowledge_arcana",
        "knowledge_planes",
        "perception",
        "linguistics",
        "use_magic_device",
    ):
        repository.update_skill_state(character_id, SkillState(key, ranks=6))
    repository.update_currency_purse(
        CurrencyPurse(character_id, gold=6965, notes="16,000 gp level-six budget; 9,035 gp equipped.")
    )

    calculator = CharacterCalculationService(repository, character_id)
    profile = repository.get_casting_profile(character_id)
    profile = replace(
        profile,
        casting_ability="intelligence",
        casting_class_levels=6,
        caster_level=6,
        spell_points_current=14,
        auto_spell_points=True,
        tradition_name="Focused Warp Adept",
        tradition_notes="Intelligence-based high-caster tradition; no casting drawbacks selected.",
    )
    repository.update_casting_profile(profile)
    repository.update_hit_points(HitPoints(character_id, 32, 32, auto_calculate=True))

    # Reload calculation state after the persistent casting and HP updates.
    calculator = CharacterCalculationService(repository, character_id)
    statistics = calculate_casting_statistics(
        profile,
        calculator.ability_result("intelligence").ability_modifier,
        concentration_bonus=calculator.automatic_total("concentration"),
        spell_point_sources=calculator.spell_point_contributions(),
    )
    expected = {
        "intelligence": 22,
        "initiative": 9,
        "spell_points": 14,
        "concentration": 14,
        "warp_dc": 20,
        "magic_entries": 13,
        "feats": 7,
        "traits": 2,
    }
    actual = {
        "intelligence": calculator.ability_result("intelligence").total,
        "initiative": calculator.combat_results()["initiative"].total,
        "spell_points": statistics.spell_points_maximum,
        "concentration": statistics.concentration_bonus,
        "warp_dc": statistics.save_dc + calculator.sphere_dc_bonus("Warp"),
        "magic_entries": len(repository.list_spells(character_id)),
        "feats": len(repository.list_feats(character_id)),
        "traits": len(repository.list_traits(character_id)),
    }
    if actual != expected:
        raise RuntimeError(f"Validation character did not calculate as expected: {actual!r}")
    return character_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("--name", default=CHARACTER_NAME)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    repository = CharacterRepository(args.database)
    try:
        existing = next(
            (item for item in repository.list_characters() if item.name == args.name),
            None,
        )
        if existing is not None:
            if not args.replace:
                raise RuntimeError(
                    f"Character {args.name!r} already exists; pass --replace to rebuild it."
                )
            repository.delete_character(existing.id)
        character_id = build_character(repository, args.name)
        print(f"Created {args.name} as character {character_id} in {args.database}")
    finally:
        repository.close()


if __name__ == "__main__":
    main()

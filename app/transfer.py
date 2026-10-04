from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from app.database import CharacterRepository
from app.engineering_rules import RESISTANCE_ROUTINE_KEY
from app.models import (
    AbilityScoreIncreaseAllocation,
    AdvancementAdjustment,
    CastingProfile,
    CharacterDetails,
    RaceTraitChoice,
    CurrencyPurse,
    FavoredClassBonus,
    HitPoints,
    InventoryCustomGroup,
    InventoryPlacement,
    MartialFocus,
    MovementProfile,
    ProdigySequence,
    SkillState,
    SphereStatistic,
    SpecialAbilityAdjustment,
    ProficiencyAdjustment,
    ClassFeatureSelection,
    ClassFeatureState,
    AnimalCompanion,
    BondedCompanion,
)
from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.registry import register_builtin_blocks
from app.presentation_storage import SheetStyleStore, StyleBlockRepository


FORMAT_NAME = "character-sheet-app"
FORMAT_VERSION = 1


def export_character(repository: CharacterRepository, character_id: int, path: Path) -> None:
    summary = next(item for item in repository.list_characters() if item.id == character_id)
    # Export presentation state through the character repository's existing
    # transaction boundary.  Opening a second writer while the live sheet is
    # active can make SQLite report ``database is locked`` on Windows.
    presentation = BuildingBlockRepository(
        repository.database_path,
        connection=repository.sqlite_connection,
    )
    try:
        presentation.ensure_character(character_id, register_builtin_blocks())
        building_blocks = presentation.export_character_state(character_id)
    finally:
        presentation.close()
    payload = {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "character": {
            "name": summary.name,
            "character_type": summary.character_type,
            "details": asdict(repository.get_character_details(character_id)),
            "abilities": repository.get_ability_scores(character_id),
            "modifiers": [asdict(item) for item in repository.list_modifiers(character_id)],
            "classes": [
                {
                    **asdict(item),
                    "archetype_keys": list(
                        repository.list_class_archetype_keys(character_id, item.id).get(item.id, ())
                    ),
                }
                for item in repository.list_class_levels(character_id)
            ],
            "special_ability_adjustments": [
                asdict(item) for item in repository.list_special_ability_adjustments(character_id)
            ],
            "proficiency_adjustments": [
                asdict(item) for item in repository.list_proficiency_adjustments(character_id)
            ],
            "class_feature_selections": [
                asdict(item) for item in repository.list_class_feature_selections(character_id)
            ],
            "class_feature_states": [
                asdict(item) for item in repository.list_class_feature_states(character_id)
            ],
            "animal_companion": asdict(repository.get_animal_companion(character_id)),
            "bonded_companions": [
                asdict(item) for item in repository.list_bonded_companions(character_id)
            ],
            "favored_class_bonuses": [
                asdict(item)
                for item in repository.list_favored_class_bonuses(character_id).values()
            ],
            "advancement_adjustments": [
                asdict(item)
                for item in repository.list_advancement_adjustments(character_id).values()
            ],
            "ability_score_increases": [
                asdict(item)
                for item in repository.list_ability_score_increases(character_id).values()
            ],
            "movement": asdict(repository.get_movement_profile(character_id)),
            "hit_points": asdict(repository.get_hit_points(character_id)),
            "worn_slots": list(repository.list_worn_slots(character_id)),
            "equipment": [asdict(item) for item in repository.list_equipment(character_id)],
            "inventory_placements": [
                asdict(item)
                for item in repository.list_inventory_placements(character_id)
            ],
            "inventory_custom_groups": [
                asdict(item)
                for item in repository.list_inventory_custom_groups(character_id)
            ],
            "item_enchantments": [
                asdict(item)
                for item in repository.list_item_enchantments(character_id)
            ],
            "currency": asdict(repository.get_currency_purse(character_id)),
            "attacks": [asdict(item) for item in repository.list_attacks(character_id)],
            "numeric_formulas": [
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "field_key": field_key,
                    "expression": expression,
                }
                for (entity_type, entity_id, field_key), expression
                in repository.numeric_formulas(character_id).items()
            ],
            "skills": [asdict(item) for item in repository.list_skill_states(character_id).values()],
            "skill_specializations": [
                asdict(item)
                for item in repository.list_skill_specializations(character_id)
            ],
            "sheet_notes": [
                asdict(item) for item in repository.list_sheet_notes(character_id)
            ],
            "conditions": [asdict(item) for item in repository.list_conditions(character_id)],
            "ongoing_effects": [
                asdict(item) for item in repository.list_ongoing_effects(character_id)
            ],
            "feats": [asdict(item) for item in repository.list_feats(character_id)],
            "traits": [asdict(item) for item in repository.list_traits(character_id)],
            "martial_focus": asdict(repository.get_martial_focus(character_id)),
            "martial_talents": [
                asdict(item) for item in repository.list_martial_talents(character_id)
            ],
            "flexible_talent_selections": [
                asdict(item)
                for item in repository.list_flexible_talent_selections(character_id)
            ],
            "flexible_talent_change_available": {
                source: repository.flexible_talent_change_available(character_id, source)
                for source in {
                    item.source_key
                    for item in repository.list_flexible_talent_selections(character_id)
                }
            },
            "spells": [asdict(item) for item in repository.list_spells(character_id)],
            "prepared_spells": [
                asdict(item) for item in repository.list_prepared_spells(character_id)
            ],
            "spontaneous_spell_slots": [
                asdict(item)
                for item in repository.list_spontaneous_slot_uses(character_id)
            ],
            "casting_profile": asdict(repository.get_casting_profile(character_id)),
            "traditions": [
                asdict(item) for item in repository.list_character_traditions(character_id)
            ],
            "sphere_statistics": [
                asdict(item) for item in repository.list_sphere_statistics(character_id)
            ],
            "prodigy_sequence": asdict(repository.get_prodigy_sequence(character_id)),
            "sequence_options": [
                asdict(item)
                for item in repository.list_sequence_options(character_id)
                if not item.built_in
            ],
            "custom_trackers": [
                asdict(item) for item in repository.list_custom_trackers(character_id)
            ],
            "engineering_devices": repository.list_engineering_devices(character_id),
            "engineering_polymorphed": repository.engineering_polymorphed(character_id),
            "rest_preferences": repository.get_rest_preferences(character_id),
            "audit_ignores": repository.list_audit_ignores(character_id),
            "sheet_layout": repository.get_character_sheet_layout(character_id),
            "building_blocks": building_blocks,
            "sheet_styles": SheetStyleStore(repository).export(character_id),
            "refined_blocks": StyleBlockRepository(repository, "refined", ()).export_character_state(character_id),
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _import_engineering_devices(repository,character_id,character):
    device_ids={}
    device_hosts=[]
    device_effects=[]
    for device in character.get("engineering_devices", []):
        device=dict(device)
        old_id=device.pop("id",None)
        if old_id is not None and old_id in device_ids:
            raise ValueError("Duplicate engineering device identity in character file.")
        device.pop("character_id",None)
        old_host=device.pop("host_id",None)
        old_effect_battery=device.pop("effect_battery_id",None)
        if device.get("catalog_key")==RESISTANCE_ROUTINE_KEY and device.get("state")=="active" and old_host is None:
            raise ValueError("An active routine requires an attachment host.")
        staged={**device,"state":"inactive"} if device.get("catalog_key")==RESISTANCE_ROUTINE_KEY and device.get("state")=="active" else device
        new_id=repository.save_engineering_device(character_id,staged)
        device_ids[old_id]=new_id
        if old_host is not None:device_hosts.append((new_id,old_host,device))
        if old_effect_battery is not None:device_effects.append((new_id,old_effect_battery))
    for device_id,host_id,device in device_hosts:
        if host_id not in device_ids:
            raise ValueError("Engineering device has a missing attachment host.")
        repository.save_engineering_device(character_id,{**device,"host_id":device_ids[host_id]},device_id)
    for device_id,battery_id in device_effects:
        if battery_id not in device_ids:
            raise ValueError("Engineering effect has a missing supporting battery.")
        device=next(d for d in repository.list_engineering_devices(character_id) if d["id"]==device_id)
        repository.save_engineering_device(character_id,{**device,"effect_battery_id":device_ids[battery_id]},device_id)
    return device_ids


def _remap_device_references(value,device_ids):
    if isinstance(value,dict):
        return {key:_remap_device_references(item,device_ids) for key,item in value.items()}
    if isinstance(value,list):
        return [_remap_device_references(item,device_ids) for item in value]
    if isinstance(value,str):
        def replace(match):
            old_id=int(match.group(1))
            if old_id not in device_ids:
                raise ValueError("Formula references a device missing from the character export.")
            return f"devices.device_{device_ids[old_id]}"
        return re.sub(r"\bdevices\.device_(\d+)(?=\.)",replace,value,flags=re.IGNORECASE)
    return value


def import_character(repository: CharacterRepository, path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("format") != FORMAT_NAME or payload.get("version") != FORMAT_VERSION:
        raise ValueError("This is not a supported Character Sheet App export.")
    character = payload["character"]
    character_id = repository.create_character(
        str(character["name"]), str(character["character_type"])
    )
    try:
        device_ids=_import_engineering_devices(repository,character_id,character)
        if "engineering_polymorphed" in character:
            repository.set_engineering_polymorphed(character_id,character["engineering_polymorphed"])
        character=_remap_device_references(character,device_ids)
        _populate_character(repository, character_id, character)
        styles = character.get("sheet_styles", {})
        if isinstance(styles, dict):
            store = SheetStyleStore(repository)
            for key, state in styles.items():
                if isinstance(state, dict):
                    store.save(character_id, key, state)
        refined = character.get("refined_blocks", {})
        if isinstance(refined, dict) and refined.get("tabs"):
            StyleBlockRepository(repository, "refined", ()).import_character_state(character_id, refined)
        layout = character.get("sheet_layout", {})
        if isinstance(layout, dict) and layout:
            repository.save_character_sheet_layout(character_id, layout)
        presentation = BuildingBlockRepository(repository.database_path)
        try:
            state = character.get("building_blocks")
            if isinstance(state, dict) and state:
                presentation.import_character_state(character_id, state)
            else:
                presentation.ensure_character(character_id, register_builtin_blocks())
        finally:
            presentation.close()
    except Exception:
        repository.delete_character(character_id)
        raise
    return character_id


def _populate_character(
    repository: CharacterRepository, character_id: int, character: dict
) -> None:
    details = dict(character.get("details", {}))
    details.pop("character_id", None)
    details["race_trait_choices"] = tuple(
        RaceTraitChoice(
            trait_key=str(choice.get("trait_key") or ""),
            choice_key=str(choice.get("choice_key") or ""),
            values=tuple(str(value) for value in choice.get("values", ())),
        )
        for choice in details.get("race_trait_choices", ())
        if isinstance(choice, dict)
    )
    repository.update_character_details(CharacterDetails(character_id=character_id, **details))
    for ability, value in character.get("abilities", {}).items():
        repository.update_ability_score(character_id, ability, int(value))
    modifier_id_map: dict[int, int] = {}
    for modifier in character.get("modifiers", []):
        modifier = dict(modifier)
        old_modifier_id = modifier.pop("id", None)
        enabled = bool(modifier.pop("enabled", True))
        # ``disabled_reason`` is calculation-time presentation metadata.  The
        # modifiers table stores the user's source/value and enabled state, so
        # older and newer exports can both be imported through the same API.
        modifier.pop("disabled_reason", None)
        modifier_id = repository.add_modifier(character_id, **modifier)
        if old_modifier_id is not None:
            modifier_id_map[int(old_modifier_id)] = modifier_id
        if not enabled:
            repository.set_modifier_enabled(character_id, modifier_id, False)
    class_level_id_map: dict[int, int] = {}
    for class_level in character.get("classes", []):
        class_level = dict(class_level)
        old_class_level_id = class_level.pop("id", None)
        archetype_keys = class_level.pop("archetype_keys", ())
        new_class_level_id = repository.add_class_level(character_id, **class_level)
        if old_class_level_id is not None:
            class_level_id_map[int(old_class_level_id)] = new_class_level_id
        if archetype_keys:
            repository.set_class_archetype_keys(
                character_id, new_class_level_id, tuple(str(key) for key in archetype_keys)
            )
    for allocation in character.get("favored_class_bonuses", []):
        allocation = dict(allocation)
        allocation.pop("character_id", None)
        old_class_level_id = allocation.pop("class_level_id", None)
        new_class_level_id = (
            class_level_id_map.get(int(old_class_level_id))
            if old_class_level_id is not None else None
        )
        if new_class_level_id is None:
            continue
        repository.update_favored_class_bonus(
            FavoredClassBonus(
                character_id=character_id,
                class_level_id=new_class_level_id,
                **allocation,
            )
        )
    for item in character.get("special_ability_adjustments", []):
        item = dict(item); item.pop("id", None); item.pop("character_id", None)
        feature_key = str(item.get("feature_key") or "")
        parts = feature_key.split(":", 2)
        if len(parts) == 3 and parts[0] == "class" and parts[1].isdigit():
            mapped = class_level_id_map.get(int(parts[1]))
            if mapped is not None:
                item["feature_key"] = f"class:{mapped}:{parts[2]}"
        repository.save_special_ability_adjustment(
            SpecialAbilityAdjustment(0, character_id, **item)
        )
    for item in character.get("proficiency_adjustments", []):
        item = dict(item); item.pop("character_id", None)
        old_id = int(item.pop("class_level_id"))
        if old_id not in class_level_id_map:
            continue
        repository.save_proficiency_adjustment(
            ProficiencyAdjustment(character_id, class_level_id_map[old_id], **item)
        )
    for item in character.get("class_feature_selections", []):
        item = dict(item); item.pop("character_id", None)
        old_id = int(item.pop("class_level_id"))
        if old_id not in class_level_id_map: continue
        repository.save_class_feature_selection(
            ClassFeatureSelection(character_id, class_level_id_map[old_id], **item)
        )
    for item in character.get("class_feature_states", []):
        item = dict(item); item.pop("character_id", None)
        old_id = int(item.pop("class_level_id"))
        if old_id not in class_level_id_map:
            continue
        repository.save_class_feature_state(
            ClassFeatureState(character_id, class_level_id_map[old_id], **item)
        )
    companion = dict(character.get("animal_companion", {}))
    if companion:
        companion.pop("character_id", None)
        repository.update_animal_companion(AnimalCompanion(character_id, **companion))
    for companion in character.get("bonded_companions", []):
        companion = dict(companion)
        companion.pop("character_id", None)
        repository.update_bonded_companion(
            BondedCompanion(character_id=character_id, **companion)
        )
    for adjustment in character.get("advancement_adjustments", []):
        adjustment = dict(adjustment)
        adjustment.pop("character_id", None)
        repository.update_advancement_adjustment(
            AdvancementAdjustment(character_id=character_id, **adjustment)
        )
    for allocation in character.get("ability_score_increases", []):
        allocation = dict(allocation)
        allocation.pop("character_id", None)
        repository.update_ability_score_increase(
            AbilityScoreIncreaseAllocation(character_id=character_id, **allocation)
        )
    movement = dict(character.get("movement", {}))
    if movement:
        movement.pop("character_id", None)
        repository.update_movement_profile(
            MovementProfile(character_id=character_id, **movement)
        )
    hit_points = dict(character.get("hit_points", {}))
    hit_points.pop("character_id", None)
    repository.update_hit_points(HitPoints(character_id=character_id, **hit_points))
    if "worn_slots" in character:
        repository.update_worn_slots(
            character_id,
            tuple(str(value) for value in character.get("worn_slots", ())),
        )
    equipment_id_map: dict[int, int] = {}
    for item in character.get("equipment", []):
        item = dict(item)
        old_item_id = item.pop("id", None)
        new_item_id = repository.add_equipment(character_id, **item)
        if old_item_id is not None:
            equipment_id_map[int(old_item_id)] = new_item_id
    for enchantment in character.get("item_enchantments", []):
        enchantment = dict(enchantment)
        enchantment.pop("id", None)
        old_equipment_id = enchantment.pop("equipment_id", None)
        new_equipment_id = (
            equipment_id_map.get(int(old_equipment_id))
            if old_equipment_id is not None
            else None
        )
        if new_equipment_id is None:
            continue
        repository.add_item_enchantment(
            character_id,
            new_equipment_id,
            **enchantment,
        )
    inventory_placements = []
    for placement in character.get("inventory_placements", []):
        placement = dict(placement)
        old_equipment_id = placement.pop("equipment_id", None)
        old_container_id = placement.pop("container_equipment_id", None)
        new_equipment_id = (
            equipment_id_map.get(int(old_equipment_id))
            if old_equipment_id is not None
            else None
        )
        if new_equipment_id is not None:
            placement["container_equipment_id"] = (
                equipment_id_map.get(int(old_container_id))
                if old_container_id is not None else None
            )
            inventory_placements.append(
                InventoryPlacement(new_equipment_id, **placement)
            )
    inventory_custom_groups = [
        InventoryCustomGroup(**dict(group))
        for group in character.get("inventory_custom_groups", [])
    ]
    if inventory_placements or inventory_custom_groups:
        repository.replace_inventory_organization(
            character_id, inventory_placements, inventory_custom_groups
        )
    currency = dict(character.get("currency", {}))
    if currency:
        currency.pop("character_id", None)
        repository.update_currency_purse(
            CurrencyPurse(character_id=character_id, **currency)
        )
    attack_id_map: dict[int, int] = {}
    for attack in character.get("attacks", []):
        attack = dict(attack)
        old_attack_id = attack.pop("id", None)
        old_equipment_id = attack.get("equipment_id")
        attack["equipment_id"] = (
            equipment_id_map.get(int(old_equipment_id))
            if old_equipment_id is not None
            else None
        )
        new_attack_id = repository.add_attack(character_id, **attack)
        if old_attack_id is not None:
            attack_id_map[int(old_attack_id)] = new_attack_id
    for specialization in character.get("skill_specializations", []):
        values = dict(specialization)
        repository.update_skill_specialization(
            character_id,
            str(values.get("skill_key", "")),
            str(values.get("base_skill_key", "")),
            str(values.get("specialty", "")),
        )
    for skill in character.get("skills", []):
        repository.update_skill_state(character_id, SkillState(**skill))
    for note in character.get("sheet_notes", []):
        values = dict(note)
        values.pop("id", None)
        values.pop("character_id", None)
        repository.add_sheet_note(character_id, **values)
    for condition in character.get("conditions", []):
        condition = dict(condition)
        condition.pop("id", None)
        enabled = bool(condition.pop("enabled", True))
        condition_id = repository.add_condition(character_id, **condition)
        if not enabled:
            repository.set_condition_enabled(character_id, condition_id, False)
    ongoing_effect_id_map: dict[int, int] = {}
    for effect in character.get("ongoing_effects", []):
        effect = dict(effect)
        old_effect_id = effect.pop("id", None)
        enabled = bool(effect.pop("enabled", True))
        effect_id = repository.add_ongoing_effect(character_id, **effect)
        if old_effect_id is not None:
            ongoing_effect_id_map[int(old_effect_id)] = effect_id
        if not enabled:
            repository.set_ongoing_effect_enabled(character_id, effect_id, False)
    feat_id_map: dict[int, int] = {}
    for feat in character.get("feats", []):
        feat = dict(feat)
        old_feat_id = feat.pop("id", None)
        enabled = bool(feat.pop("enabled", True))
        feat_id = repository.add_feat(character_id, **feat)
        if old_feat_id is not None:
            feat_id_map[int(old_feat_id)] = feat_id
        if not enabled:
            repository.set_feat_enabled(character_id, feat_id, False)
    trait_id_map: dict[int, int] = {}
    for trait in character.get("traits", []):
        trait = dict(trait)
        old_trait_id = trait.pop("id", None)
        enabled = bool(trait.pop("enabled", True))
        trait_id = repository.add_trait(character_id, **trait)
        if old_trait_id is not None:
            trait_id_map[int(old_trait_id)] = trait_id
        if not enabled:
            repository.set_trait_enabled(character_id, trait_id, False)
    martial_focus = dict(character.get("martial_focus", {}))
    if martial_focus:
        martial_focus.pop("character_id", None)
        repository.update_martial_focus(
            MartialFocus(character_id=character_id, **martial_focus)
        )
    for talent in character.get("martial_talents", []):
        talent = dict(talent)
        talent.pop("id", None)
        enabled = bool(talent.pop("enabled", True))
        # Exports may legitimately contain repeatable catalog talents.  The
        # exported records themselves remain authoritative during import.
        talent_id = repository.add_martial_talent(
            character_id, **talent, allow_duplicate_catalog=True
        )
        if not enabled:
            repository.set_martial_talent_enabled(character_id, talent_id, False)
    flexible_by_source: dict[str, list[dict]] = {}
    for selection in character.get("flexible_talent_selections", []):
        selection = dict(selection)
        selection.pop("id", None)
        selection.pop("character_id", None)
        source_key = str(selection.pop("source_key", "")).strip()
        selection.pop("slot_index", None)
        if source_key:
            flexible_by_source.setdefault(source_key, []).append(selection)
    for source_key, selections in flexible_by_source.items():
        repository.replace_flexible_talent_selections(
            character_id, source_key, selections
        )
    for source_key, available in dict(
        character.get("flexible_talent_change_available", {})
    ).items():
        repository.set_flexible_talent_change_available(
            character_id, str(source_key), bool(available)
        )
    spell_id_map: dict[int, int] = {}
    for spell in character.get("spells", []):
        spell = dict(spell)
        old_spell_id = spell.pop("id", None)
        enabled = bool(spell.pop("enabled", True))
        spell_id = repository.add_spell(character_id, **spell)
        if old_spell_id is not None:
            spell_id_map[int(old_spell_id)] = spell_id
        if not enabled:
            repository.set_spell_enabled(character_id, spell_id, False)
    for prepared in character.get("prepared_spells", []):
        prepared = dict(prepared)
        prepared.pop("id", None)
        prepared.pop("character_id", None)
        old_class_level_id = int(prepared.pop("class_level_id"))
        old_known_spell_id = prepared.pop("known_spell_id", None)
        prepared["class_level_id"] = class_level_id_map[old_class_level_id]
        prepared["known_spell_id"] = (
            spell_id_map[int(old_known_spell_id)]
            if old_known_spell_id is not None
            else None
        )
        repository.add_prepared_spell(character_id, **prepared)
    for slot in character.get("spontaneous_spell_slots", []):
        slot = dict(slot)
        slot.pop("character_id", None)
        old_class_level_id = int(slot.pop("class_level_id"))
        repository.set_spontaneous_slot_uses(
            character_id,
            class_level_id_map[old_class_level_id],
            int(slot["spell_level"]),
            int(slot.get("used_count", 0)),
        )
    casting_profile = dict(character.get("casting_profile", {}))
    if casting_profile:
        casting_profile.pop("character_id", None)
        repository.update_casting_profile(
            CastingProfile(character_id=character_id, **casting_profile)
        )
    for tradition in character.get("traditions", []):
        tradition = dict(tradition)
        tradition.pop("id", None)
        tradition.pop("character_id", None)
        repository.add_character_tradition(character_id, **tradition)
    for statistic in character.get("sphere_statistics", []):
        statistic = dict(statistic)
        statistic.pop("character_id", None)
        repository.update_sphere_statistic(
            SphereStatistic(character_id=character_id, **statistic)
        )
    prodigy_sequence = dict(character.get("prodigy_sequence", {}))
    if prodigy_sequence:
        prodigy_sequence.pop("character_id", None)
        repository.update_prodigy_sequence(
            ProdigySequence(character_id=character_id, **prodigy_sequence)
        )
    for option in character.get("sequence_options", []):
        option = dict(option)
        option.pop("id", None)
        if option.pop("built_in", False):
            continue
        repository.add_sequence_option(character_id, **option)
    for tracker in character.get("custom_trackers", []):
        tracker = dict(tracker)
        tracker.pop("id", None)
        repository.add_custom_tracker(character_id, **tracker)
    formula_id_maps = {
        "attack": attack_id_map,
        "equipment": equipment_id_map,
        "modifier": modifier_id_map,
        "feat": feat_id_map,
        "trait": trait_id_map,
        "spell": spell_id_map,
        "ongoing_effect": ongoing_effect_id_map,
    }
    for formula in character.get("numeric_formulas", []):
        formula = dict(formula)
        entity_type = str(formula.get("entity_type") or "")
        old_entity_id = int(formula.get("entity_id") or 0)
        entity_id = formula_id_maps.get(entity_type, {}).get(old_entity_id)
        if entity_type not in formula_id_maps:
            entity_id = old_entity_id
        if entity_id is None:
            continue
        repository.set_numeric_formula(
            character_id,
            entity_type,
            entity_id,
            str(formula.get("field_key") or ""),
            str(formula.get("expression") or ""),
        )
    rest_preferences = character.get("rest_preferences", {})
    if isinstance(rest_preferences, dict) and rest_preferences:
        repository.save_rest_preferences(character_id, rest_preferences)
    audit_ignores = character.get("audit_ignores", {})
    if isinstance(audit_ignores, dict):
        for finding_key, reason in audit_ignores.items():
            repository.set_audit_finding_ignored(
                character_id,
                str(finding_key),
                True,
                str(reason or ""),
            )

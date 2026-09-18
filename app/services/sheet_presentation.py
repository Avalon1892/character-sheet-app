"""Shared, read-only character projection for alternate sheet presentations."""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.content import archetype_entry, class_entry
from app.class_feature_rules import (
    archetype_granted_features,
    archetype_optional_features,
    resolve_class_features,
    resolved_feature_key,
)
from app.archetype_rules import archetype_choice_selections_from_records
from app.class_choice_rules import (
    projected_class_choice_features,
    resolve_class_choice_slots,
)
from app.class_power_rules import projected_class_power_features, resolve_class_power_sets
from app.database import CharacterRepository
from app.item_enchantments import item_display_name
from app.item_containers import carried_inventory_weight
from app.models import (
    SKILLS,
    Attack,
    CastingProfile,
    CharacterDetails,
    CharacterSummary,
    ClassLevel,
    Condition,
    CurrencyPurse,
    EquipmentItem,
    Feat,
    HitPoints,
    MartialFocus,
    MartialTalent,
    SkillDefinition,
    SkillState,
    Spell,
    Trait,
)
from app.rules import (
    AttackResult,
    CalculationResult,
    CarryingCapacity,
    CastingStatistics,
    SkillResult,
    calculate_attack,
    calculate_casting_statistics,
    carrying_capacity,
    class_bab,
    prodigy_inspired_sequence_bonus,
    prodigy_level,
    total_bab,
)
from app.services.character_calculations import CharacterCalculationService
from app.skill_specializations import character_skill_definitions


@dataclass(frozen=True, slots=True)
class PresentedSkill:
    definition: SkillDefinition
    state: SkillState
    result: SkillResult
    ability: str


@dataclass(frozen=True, slots=True)
class PresentedAttack:
    record: Attack
    result: AttackResult


@dataclass(frozen=True, slots=True)
class PresentedClassFeature:
    level: int
    name: str
    description: str
    class_name: str


@dataclass(frozen=True, slots=True)
class CharacterSheetSnapshot:
    summary: CharacterSummary
    details: CharacterDetails
    classes: tuple[ClassLevel, ...]
    abilities: dict[str, CalculationResult]
    base_abilities: dict[str, int]
    combat: dict[str, CalculationResult]
    skills: tuple[PresentedSkill, ...]
    hit_points: HitPoints
    displayed_hit_point_maximum: int
    casting_profile: CastingProfile
    casting: CastingStatistics
    sphere_statistics: dict[str, CastingStatistics]
    equipment: tuple[EquipmentItem, ...]
    attacks: tuple[PresentedAttack, ...]
    conditions: tuple[Condition, ...]
    feats: tuple[Feat, ...]
    traits: tuple[Trait, ...]
    martial_talents: tuple[MartialTalent, ...]
    spells: tuple[Spell, ...]
    class_features: tuple[PresentedClassFeature, ...]
    currency: CurrencyPurse
    martial_focus: MartialFocus
    carrying_capacity: CarryingCapacity
    total_weight: float
    base_speed: int


def build_character_sheet_snapshot(
    repository: CharacterRepository, character_id: int
) -> CharacterSheetSnapshot:
    summary = next(
        item for item in repository.list_characters() if item.id == character_id
    )
    sequence = repository.get_prodigy_sequence(character_id)
    calculator = CharacterCalculationService(
        repository,
        character_id,
        sequence_active=sequence.active,
        sequence_links=sequence.current,
    )
    state = calculator.state
    abilities = calculator.ability_results()
    combat = calculator.combat_results()
    skill_definitions = character_skill_definitions(repository, character_id)
    skills = tuple(
        PresentedSkill(
            definition,
            state.skills[definition.key],
            calculator.skill_result(definition.key),
            state.skills[definition.key].ability_override or definition.ability,
        )
        for definition in skill_definitions
    )

    hp = calculator.resolved_hit_points()
    displayed_hp = calculator.hit_point_maximum()

    profile = calculator.resolved_casting_profile()
    casting_ability = abilities[profile.casting_ability].ability_modifier
    sequence_bonus = prodigy_inspired_sequence_bonus(
        prodigy_level(state.classes), sequence.current, sequence.active
    )
    casting = calculator.casting_statistics()
    saved_spheres = {
        item.sphere: item for item in repository.list_sphere_statistics(character_id)
    }
    sphere_names = sorted(
        {
            spell.school_or_sphere.strip()
            for spell in state.magic_talents
            if spell.system == "Sphere" and spell.school_or_sphere.strip()
        }
        | set(saved_spheres),
        key=str.casefold,
    )
    sphere_statistics = {}
    for sphere in sphere_names:
        saved = saved_spheres.get(sphere)
        if saved is not None:
            saved = calculator.resolved_sphere_statistic(saved)
        sphere_statistics[sphere] = calculate_casting_statistics(
            profile,
            casting_ability,
            caster_level_bonus=(
                sequence_bonus
                + calculator.automatic_total("caster_level")
                + (0 if saved is None else saved.caster_level_bonus)
            ),
            dc_bonus=(
                calculator.automatic_total("save_dc")
                + calculator.sphere_dc_bonus(sphere)
                + (0 if saved is None else saved.dc_bonus)
            ),
        )

    bab = total_bab(calculator.resolved_classes())
    automatic_modifiers = calculator.automatic_modifier_map()
    attacks = []
    for attack in calculator.attacks():
        resolved = calculator.resolve_attack_profile(attack)
        attack_modifiers, damage_modifiers = calculator.attack_effects(attack, bab)
        attack_modifiers += automatic_modifiers.get("attack", [])
        damage_modifiers += automatic_modifiers.get("damage", [])
        attacks.append(
            PresentedAttack(
                resolved.attack,
                calculate_attack(
                    resolved.attack,
                    bab,
                    abilities,
                    state.details.size,
                    attack_modifiers,
                    damage_modifiers,
                    extra_damage=resolved.extra_damage,
                ),
            )
        )

    derived_class_features: list[tuple[str, PresentedClassFeature]] = []
    archetypes_by_level = repository.list_class_archetype_keys(character_id)
    selections = repository.list_class_feature_selections(character_id)
    class_choice_slots = resolve_class_choice_slots(repository, character_id)
    class_power_sets = resolve_class_power_sets(repository, character_id)
    selections_by_level = {
        class_level.id: tuple(
            selection for selection in selections
            if selection.class_level_id == class_level.id
        )
        for class_level in state.classes
    }
    optional_keys_by_level: dict[int, set[str]] = {}
    for class_level in state.classes:
        entry = class_entry(class_level.preset_key)
        if entry is None:
            continue
        selected_archetypes = tuple(
            definition
            for key in archetypes_by_level.get(class_level.id, ())
            if (definition := archetype_entry(key)) is not None
        )
        optional_keys = {
            option.key
            for archetype in selected_archetypes
            for option in archetype_optional_features(archetype, class_level.level)
        }
        optional_keys_by_level[class_level.id] = optional_keys
        selected_option_keys = {
            selection.feature_key
            for selection in selections_by_level[class_level.id]
            if selection.feature_key in optional_keys
        }
        resolved = resolve_class_features(
            entry.get("features", ()),
            selected_archetypes,
            class_level.level,
            class_level.class_name,
            selected_option_keys,
            archetype_choice_selections_from_records(
                selections_by_level[class_level.id], class_level.id
            ),
        )
        derived_class_features.extend(
            (
                resolved_feature_key(class_level.id, feature),
                PresentedClassFeature(
                    feature.level,
                    feature.name,
                    feature.description,
                    feature.source,
                ),
            )
            for feature in resolved
        )

    derived_class_features.extend(
        (
            stable_key,
            PresentedClassFeature(level, name, description, source),
        )
        for stable_key, level, name, description, source
        in projected_class_choice_features(class_choice_slots)
    )
    derived_class_features.extend(
        (
            f"class-power:{class_level_id}:{name.casefold()}:{level}",
            PresentedClassFeature(level, name, description, source),
        )
        for class_level_id, level, name, description, source
        in projected_class_power_features(class_power_sets)
    )
    class_choice_record_keys = {
        (slot.class_level_id, key)
        for slot in class_choice_slots
        for key in (slot.feature_key, *slot.legacy_feature_keys)
    }
    class_power_record_keys = {
        (power_set.class_level_id, power_set.feature_key)
        for power_set in class_power_sets
    }

    class_levels = {item.id: item for item in state.classes}
    for selection in selections:
        owner = class_levels.get(selection.class_level_id)
        if (
            owner is None
            or selection.feature_key in optional_keys_by_level.get(owner.id, set())
            or selection.feature_key.startswith("archetype-choice:")
            or selection.option_type.casefold() == "archetype choice"
            or (selection.class_level_id, selection.feature_key)
            in class_choice_record_keys
            or (selection.class_level_id, selection.feature_key)
            in class_power_record_keys
        ):
            continue
        prefix = f"selection:{selection.class_level_id}:{selection.feature_key}"
        derived_class_features.append(
            (
                prefix,
                PresentedClassFeature(
                    1,
                    f"{selection.option_type} — {selection.name}",
                    selection.description,
                    owner.class_name,
                ),
            )
        )
        if selection.option_type == "Inquisition" and selection.description:
            for granted in archetype_granted_features(
                {
                    "name": f"{selection.name} Inquisition",
                    "description": selection.description,
                },
                owner.level,
            ):
                derived_class_features.append(
                    (
                        f"{prefix}:{granted.level}:{granted.name.casefold()}",
                        PresentedClassFeature(
                            granted.level,
                            granted.name,
                            granted.description,
                            f"{selection.name} Inquisition",
                        ),
                    )
                )

    adjustments = {
        item.feature_key: item
        for item in repository.list_special_ability_adjustments(character_id)
    }
    class_features: list[PresentedClassFeature] = []
    for feature_key, feature in derived_class_features:
        overlay = adjustments.get(feature_key)
        if overlay is not None:
            if overlay.hidden:
                continue
            feature = PresentedClassFeature(
                overlay.level,
                overlay.name,
                overlay.description,
                feature.class_name,
            )
        class_features.append(feature)
    class_features.extend(
        PresentedClassFeature(
            item.level,
            item.name,
            item.description,
            "Custom",
        )
        for item in adjustments.values()
        if item.custom and not item.hidden
    )
    class_features.sort(
        key=lambda item: (item.level, item.class_name.casefold(), item.name.casefold())
    )

    resolved_equipment = calculator.resolved_equipment()
    total_weight = carried_inventory_weight(
        resolved_equipment,
        repository.list_inventory_placements(character_id),
    )
    capacity = carrying_capacity(abilities["strength"].total, state.details.size)
    speed = int(calculator.movement_results()["land_speed"])
    return CharacterSheetSnapshot(
        summary=summary,
        details=state.details,
        classes=tuple(calculator.resolved_classes()),
        abilities=abilities,
        base_abilities=dict(state.ability_scores),
        combat=combat,
        skills=skills,
        hit_points=hp,
        displayed_hit_point_maximum=displayed_hp,
        casting_profile=profile,
        casting=casting,
        sphere_statistics=sphere_statistics,
        equipment=tuple(
            replace(
                item,
                name=item_display_name(item, state.item_enchantments),
            )
            for item in resolved_equipment
        ),
        attacks=tuple(attacks),
        conditions=tuple(state.conditions),
        feats=calculator.resolved_feats(),
        traits=calculator.resolved_traits(),
        martial_talents=tuple(state.martial_talents),
        spells=tuple(state.magic_talents),
        class_features=tuple(class_features),
        currency=repository.get_currency_purse(character_id),
        martial_focus=calculator.resolved_martial_focus(),
        carrying_capacity=capacity,
        total_weight=total_weight,
        base_speed=max(0, speed),
    )


def class_bab_value(class_level: ClassLevel) -> int:
    """Stable presentation helper retained outside any concrete sheet UI."""

    return class_bab(class_level)

"""Rule-driven attack templates and dynamic attack-profile resolution."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.item_enchantments import (
    attack_matches_scope,
    enchantment_spec,
    item_is_active_for_attack,
)
from app.models import (
    Attack,
    EquipmentItem,
    Feat,
    ItemEnchantment,
    MartialTalent,
    Trait,
)


UNARMED_PROFILE_KEY = "unarmed"
UNARMED_SPHERES = frozenset({"boxing", "brute", "open hand", "wrestling"})
UNARMED_SPHERE_EXCLUSIONS = {
    "boxing": frozenset({"retaliator"}),
    "brute": frozenset({"armed combatant"}),
    "wrestling": frozenset({"constrictor"}),
}


@dataclass(frozen=True, slots=True)
class AttackTemplate:
    key: str
    label: str
    values: dict


UNARMED_ATTACK_TEMPLATE = AttackTemplate(
    key="builtin:unarmed",
    label="Unarmed strike (automatic)",
    values={
        "name": "Unarmed Strike",
        "attack_type": "Melee",
        "ability": "strength",
        "attack_bonus": 0,
        "damage_dice": "1d3",
        "damage_ability": "strength",
        "damage_multiplier": 1.0,
        "damage_bonus": 0,
        "critical": "20/x2",
        "notes": "May deal lethal or nonlethal damage as allowed by the character's rules.",
        "equipment_id": None,
        "profile_key": UNARMED_PROFILE_KEY,
        "damage_ability_mode": "automatic",
    },
)

ATTACK_TEMPLATES: tuple[AttackTemplate, ...] = (UNARMED_ATTACK_TEMPLATE,)
_ATTACK_TEMPLATES_BY_KEY = {template.key: template for template in ATTACK_TEMPLATES}


@dataclass(frozen=True, slots=True)
class UnarmedProgression:
    qualifying_talents: int
    base_talents: int
    virtual_talents: int
    excluded_spheres: tuple[str, ...]
    damage_dice: str
    source: str


@dataclass(frozen=True, slots=True)
class ExtraDamageComponent:
    dice: str
    damage_type: str
    source: str


@dataclass(frozen=True, slots=True)
class AttackProfileResolution:
    attack: Attack
    sources: tuple[str, ...] = ()
    unarmed: UnarmedProgression | None = None
    extra_damage: tuple[ExtraDamageComponent, ...] = ()
    conditional_effects: tuple[str, ...] = ()


def attack_template(key: str) -> AttackTemplate | None:
    return _ATTACK_TEMPLATES_BY_KEY.get(key)


def double_threat_range(critical: str) -> str:
    """Double only the threat range while preserving the critical multiplier."""
    match = re.fullmatch(r"\s*(?:(\d+)-)?20\s*/\s*x(\d+)\s*", critical, re.I)
    if match is None:
        return critical
    start = int(match.group(1) or 20)
    multiplier = int(match.group(2))
    doubled_start = max(2, 21 - (21 - start) * 2)
    threat = "20" if doubled_start == 20 else f"{doubled_start}-20"
    return f"{threat}/x{multiplier}"


def has_weapon_finesse(
    feats: list[Feat] | tuple[Feat, ...],
    martial_talents: list[MartialTalent] | tuple[MartialTalent, ...],
) -> bool:
    return any(
        feat.enabled and feat.name.casefold() == "weapon finesse" for feat in feats
    ) or any(
        talent.enabled and talent.name.casefold() == "finesse fighting"
        for talent in martial_talents
    )


def _selected_spheres_from_unorthodox_training(feats) -> set[str]:
    result: set[str] = set()
    for feat in feats:
        if not feat.enabled or feat.name.casefold() != "unorthodox unarmed training":
            continue
        result.update(
            value.strip().casefold()
            for value in re.split(r"[,;/|]", feat.choice)
            if value.strip()
        )
    return result


def _counts_as_talent(talent: MartialTalent) -> bool:
    category = talent.catalog_category.casefold()
    talent_type = talent.talent_type.casefold()
    return category != "drawback" and talent_type != "drawback"


_SIZE_ORDER = (
    "Fine", "Diminutive", "Tiny", "Small", "Medium", "Large", "Huge",
    "Gargantuan", "Colossal",
)
_SIZE_UP = {
    "1": "1d2", "1d2": "1d3", "1d3": "1d4", "1d4": "1d6",
    "1d6": "1d8", "1d8": "2d6", "1d10": "2d8", "2d4": "2d6",
    "2d6": "3d6", "2d8": "3d8", "2d10": "4d8", "3d6": "4d6",
    "3d8": "4d8", "4d6": "6d6", "4d8": "6d8", "6d6": "8d6",
    "6d8": "8d8", "1d12": "3d6",
}
_SIZE_DOWN = {
    "1d2": "1", "1d3": "1d2", "1d4": "1d3", "1d6": "1d4",
    "1d8": "1d6", "1d10": "1d8", "2d4": "1d6", "2d6": "1d8",
    "2d8": "2d6", "2d10": "2d8", "3d6": "2d6", "3d8": "2d8",
    "4d6": "3d6", "4d8": "3d8", "6d6": "4d6", "6d8": "4d8",
    "8d6": "6d6", "8d8": "6d8",
}


def scale_damage_dice(medium_dice: str, size: str) -> str:
    """Scale a Medium damage expression using PF1e weapon-size steps."""
    try:
        steps = _SIZE_ORDER.index(size) - _SIZE_ORDER.index("Medium")
    except ValueError:
        steps = 0
    result = medium_dice
    table = _SIZE_UP if steps > 0 else _SIZE_DOWN
    for _ in range(abs(steps)):
        result = table.get(result, result)
    return result


def _som_medium_unarmed_dice(count: int) -> str:
    if count <= 0:
        return "1d3"
    if count <= 3:
        return "1d4"
    if count <= 7:
        return "1d6"
    if count <= 11:
        return "1d8"
    if count <= 15:
        return "2d6"
    if count <= 19:
        return "2d8"
    return "2d10"


def _native_medium_unarmed_dice(level: int) -> str:
    if level <= 3:
        return "1d6"
    if level <= 7:
        return "1d8"
    if level <= 11:
        return "1d10"
    if level <= 15:
        return "2d6"
    if level <= 19:
        return "2d8"
    return "2d10"


def unarmed_progression(
    martial_talents: list[MartialTalent] | tuple[MartialTalent, ...],
    traits: list[Trait] | tuple[Trait, ...],
    feats: list[Feat] | tuple[Feat, ...],
    equipment: list[EquipmentItem] | tuple[EquipmentItem, ...],
    size: str,
    *,
    native_unarmed_level: int = 0,
    additional_counting_spheres: set[str] | frozenset[str] = frozenset(),
) -> UnarmedProgression:
    active = [talent for talent in martial_talents if talent.enabled]
    excluded: set[str] = set()
    for sphere, names in UNARMED_SPHERE_EXCLUSIONS.items():
        if any(
            talent.sphere.casefold() == sphere
            and talent.name.casefold() in names
            and talent.catalog_category.casefold() == "drawback"
            for talent in active
        ):
            excluded.add(sphere)

    counting_spheres = set(UNARMED_SPHERES)
    counting_spheres.update(value.casefold() for value in additional_counting_spheres)
    if any(feat.enabled and feat.name.casefold() == "iron palm" for feat in feats):
        counting_spheres.add("shield")
    counting_spheres.update(_selected_spheres_from_unorthodox_training(feats))

    base_count = sum(
        1
        for talent in active
        if talent.sphere.casefold() in counting_spheres
        and talent.sphere.casefold() not in excluded
        and _counts_as_talent(talent)
    )
    virtual_count = 0
    if base_count:
        virtual_count += sum(
            2
            for trait in traits
            if trait.enabled and trait.name.casefold() == "talented knuckle"
        )
        if any(
            item.name.casefold().startswith("brawler's vest")
            and item.quantity > 0
            and (item.state == "worn" or (not item.state and item.equipped))
            for item in equipment
        ):
            virtual_count += 4
    count = base_count + virtual_count

    if native_unarmed_level > 0:
        effective_size = size
        if count >= 3 and size in _SIZE_ORDER and size != _SIZE_ORDER[-1]:
            effective_size = _SIZE_ORDER[_SIZE_ORDER.index(size) + 1]
        dice = scale_damage_dice(
            _native_medium_unarmed_dice(native_unarmed_level), effective_size
        )
        source = (
            f"Native unarmed progression level {native_unarmed_level}"
            + ("; Spheres training increases effective size by one step" if count >= 3 else "")
        )
    else:
        dice = scale_damage_dice(_som_medium_unarmed_dice(count), size)
        source = (
            f"Spheres of Might unarmed progression: {count} qualifying talent"
            f"{'s' if count != 1 else ''}"
        )
    return UnarmedProgression(
        count,
        base_count,
        virtual_count,
        tuple(sorted(excluded)),
        dice,
        source,
    )


def resolve_attack_profile(
    attack: Attack,
    *,
    size: str,
    martial_talents: list[MartialTalent] | tuple[MartialTalent, ...] = (),
    feats: list[Feat] | tuple[Feat, ...] = (),
    traits: list[Trait] | tuple[Trait, ...] = (),
    equipment: list[EquipmentItem] | tuple[EquipmentItem, ...] = (),
    enchantments: list[ItemEnchantment] | tuple[ItemEnchantment, ...] = (),
    native_unarmed_level: int = 0,
    additional_counting_spheres: set[str] | frozenset[str] = frozenset(),
) -> AttackProfileResolution:
    resolved = attack
    sources: list[str] = []
    extra_damage: list[ExtraDamageComponent] = []
    conditional_effects: list[str] = []
    progression = None
    linked_weapon = next(
        (
            item for item in equipment
            if item.id == attack.equipment_id and item_is_active_for_attack(item)
        ),
        None,
    )
    if linked_weapon is not None:
        resolved = replace(
            resolved,
            damage_dice=linked_weapon.weapon_damage_dice or resolved.damage_dice,
            critical=linked_weapon.weapon_critical or resolved.critical,
        )
    if attack.profile_key == UNARMED_PROFILE_KEY:
        progression = unarmed_progression(
            martial_talents,
            traits,
            feats,
            equipment,
            size,
            native_unarmed_level=native_unarmed_level,
            additional_counting_spheres=additional_counting_spheres,
        )
        resolved = replace(resolved, damage_dice=progression.damage_dice)
        sources.append(f"{progression.source} -> {progression.damage_dice}")

    for item in equipment:
        if not item_is_active_for_attack(item):
            continue
        for saved in enchantments:
            if saved.equipment_id != item.id:
                continue
            spec = enchantment_spec(saved.key)
            if spec is None:
                continue
            matched_effect = False
            for effect in spec.effects:
                if not attack_matches_scope(resolved, effect.scope, item):
                    continue
                if effect.target == "critical_profile" and effect.operation == "double_threat_range":
                    previous = resolved.critical
                    resolved = replace(resolved, critical=double_threat_range(previous))
                    sources.append(f"{item.name} — {spec.name}: critical {previous} → {resolved.critical}")
                    matched_effect = True
                elif effect.target == "extra_damage" and effect.operation == "add_dice":
                    extra_damage.append(
                        ExtraDamageComponent(str(effect.value), effect.bonus_type, f"{item.name} — {spec.name}")
                    )
                    sources.append(
                        f"{item.name} — {spec.name}: +{effect.value} {effect.bonus_type} damage"
                    )
                    matched_effect = True
                elif effect.target == "damage_dice" and effect.operation == "scale_size_steps":
                    previous = resolved.damage_dice
                    for _step in range(max(0, int(effect.value))):
                        resolved = replace(
                            resolved,
                            damage_dice=scale_damage_dice(resolved.damage_dice, "Large"),
                        )
                    sources.append(
                        f"{item.name} — {spec.name}: damage {previous} → {resolved.damage_dice}"
                    )
                    matched_effect = True
            if not matched_effect and attack_matches_scope(resolved, "host_weapon_or_unarmed", item):
                conditional_effects.append(f"{spec.name}: {spec.description}")
            elif matched_effect and any(
                phrase in spec.description.casefold()
                for phrase in ("critical hit", "damage to the wielder", "all damage it deals is nonlethal", "doesn’t stack", "does not stack")
            ):
                conditional_effects.append(f"{spec.name}: {spec.description}")

    if resolved.damage_ability_mode == "automatic":
        damage_ability: str | None = "strength" if attack.attack_type == "Melee" else None
        damage_multiplier = resolved.damage_multiplier
        finesse = has_weapon_finesse(feats, martial_talents)
        for item in equipment:
            if not item_is_active_for_attack(item):
                continue
            for saved in enchantments:
                if saved.equipment_id != item.id:
                    continue
                spec = enchantment_spec(saved.key)
                if spec is None:
                    continue
                for effect in spec.effects:
                    if (
                        effect.target != "damage_ability"
                        or effect.operation != "default"
                        or not attack_matches_scope(attack, effect.scope, item)
                    ):
                        continue
                    if "weapon_finesse" in effect.requires and not finesse:
                        sources.append(
                            f"{item.name} — {spec.name} inactive: requires Weapon Finesse"
                        )
                        continue
                    damage_ability = str(effect.value)
                    sources.append(
                        f"{item.name} — {spec.name}: {damage_ability.title()} to damage"
                    )
                for effect in spec.effects:
                    if (
                        effect.target != "damage_multiplier"
                        or effect.operation != "cap_max"
                        or not attack_matches_scope(attack, effect.scope, item)
                    ):
                        continue
                    if "weapon_finesse" in effect.requires and not finesse:
                        continue
                    damage_multiplier = min(damage_multiplier, float(effect.value))
        resolved = replace(
            resolved,
            damage_ability=damage_ability,
            damage_multiplier=damage_multiplier,
        )
        if not any(" to damage" in source for source in sources):
            sources.append(
                "Automatic damage ability: "
                + (damage_ability.title() if damage_ability else "None")
            )
    else:
        sources.append(
            "Manual damage ability: "
            + (attack.damage_ability.title() if attack.damage_ability else "None")
        )

    return AttackProfileResolution(
        resolved, tuple(sources), progression, tuple(extra_damage), tuple(conditional_effects)
    )

"""Reusable, presentation-independent class combat profiles.

Class features own mutable state, class powers own player selections, and this
module combines those two inputs into generated attacks and contextual rules.
Nothing here knows about Qt, table layouts, or a particular sheet type.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.class_feature_systems import resolve_class_feature_modules
from app.class_power_rules import resolve_class_power_sets
from app.models import Attack


@dataclass(frozen=True, slots=True)
class BombVariant:
    damage_die: str = "d6"
    damage_type: str = "fire"


# Only discoveries which directly replace the bomb's damage expression need a
# separate attack row. Other selected bomb discoveries remain readable rules
# overlays on the base Bomb profile, avoiding dozens of misleading attacks.
ALCHEMIST_BOMB_VARIANTS: Mapping[str, BombVariant] = {
    "acid bomb": BombVariant("d6", "acid"),
    "anarchic bomb": BombVariant("d6", "chaotic divine"),
    "axiomatic bombs": BombVariant("d6", "lawful divine"),
    "concussive bomb": BombVariant("d4", "sonic"),
    "cytillesh bomb": BombVariant("d4", "untyped"),
    "force bomb": BombVariant("d4", "force"),
    "frost bomb": BombVariant("d6", "cold"),
    "holy bombs": BombVariant("d6", "good divine"),
    "profane bomb": BombVariant("d6", "evil divine"),
    "scrap bomb": BombVariant("d6", "piercing"),
    "shock bomb": BombVariant("d6", "electricity"),
    "thorny bomb": BombVariant("d6", "piercing"),
}


def _virtual_attack_id(class_level_id: int, index: int) -> int:
    """Stable negative IDs distinguish derived rows from persisted attacks."""

    return -(1_000_000 + int(class_level_id) * 100 + int(index))


def _selected_powers(repository, character_id: int, provider_key: str):
    for power_set in resolve_class_power_sets(repository, character_id):
        if power_set.key == provider_key:
            return power_set.selected_options
    return ()


def _bomb_attack(
    *,
    attack_id: int,
    name: str,
    level: int,
    intelligence_modifier: int,
    variant: BombVariant,
    current: int,
    maximum: int,
    extra_notes: tuple[str, ...] = (),
) -> Attack:
    dice_count = max(1, (level + 1) // 2)
    dice = f"{dice_count}{variant.damage_die}"
    splash = max(0, dice_count + intelligence_modifier)
    dc = 10 + level // 2 + intelligence_modifier
    notes = [
        "Standard action; creates and throws one bomb (spend one Bomb use).",
        "20-ft. range; ranged touch attack; thrown splash weapon.",
        f"Direct hit: {dice} {variant.damage_type} + Intelligence modifier.",
        f"Splash: {splash} {variant.damage_type}; Reflex DC {dc} halves splash damage.",
        "Bomb damage is not precision damage and cannot itself receive precision damage.",
        f"Bombs remaining: {current}/{maximum}.",
        *extra_notes,
    ]
    return Attack(
        id=attack_id,
        name=name,
        attack_type="Ranged",
        ability="dexterity",
        attack_bonus=0,
        damage_dice=dice,
        damage_ability=None,
        damage_multiplier=0.0,
        damage_bonus=intelligence_modifier,
        critical="20/x2",
        notes="\n".join(notes),
        equipment_id=None,
        profile_key=f"class:alchemist:bomb:{name.casefold().replace(' ', '_')}",
        damage_ability_mode="manual",
    )


def generated_class_attacks(
    repository,
    character_id: int,
    ability_modifiers: Mapping[str, int] | None = None,
) -> tuple[Attack, ...]:
    """Return archetype-aware attacks granted by retained class mechanics."""

    modifiers = ability_modifiers or {}
    result: list[Attack] = []
    modules = resolve_class_feature_modules(repository, character_id, modifiers)
    bomb_discoveries = tuple(
        option
        for option in _selected_powers(
            repository, character_id, "alchemist-discoveries"
        )
        if option.category.casefold() == "bomb"
        or "bomb" in option.name.casefold()
    )
    for module in modules:
        bombs = next((item for item in module.resources if item.key == "bombs"), None)
        if module.key != "alchemist" or bombs is None:
            continue
        selected_energy = (
            bombs.choices[0].strip().casefold() if bombs.choices else "fire"
        )
        base_variant = BombVariant(
            "d6",
            selected_energy
            if selected_energy in {"acid", "cold", "electricity", "fire"}
            else "fire",
        )
        contextual = tuple(
            f"{option.name}: {option.description}"
            for option in bomb_discoveries
            if option.name.casefold() not in ALCHEMIST_BOMB_VARIANTS
        )
        result.append(
            _bomb_attack(
                attack_id=_virtual_attack_id(module.class_level_id, 0),
                name="Bomb",
                level=module.class_level,
                intelligence_modifier=int(modifiers.get("intelligence", 0)),
                variant=base_variant,
                current=bombs.current,
                maximum=bombs.maximum,
                extra_notes=contextual,
            )
        )
        for index, option in enumerate(bomb_discoveries, 1):
            variant = ALCHEMIST_BOMB_VARIANTS.get(option.name.casefold())
            if variant is None:
                continue
            result.append(
                _bomb_attack(
                    attack_id=_virtual_attack_id(module.class_level_id, index),
                    name=option.name,
                    level=module.class_level,
                    intelligence_modifier=int(modifiers.get("intelligence", 0)),
                    variant=variant,
                    current=bombs.current,
                    maximum=bombs.maximum,
                    extra_notes=(option.description,),
                )
            )
    return tuple(result)


def class_attack_context_notes(
    repository, character_id: int, attack: Attack
) -> tuple[str, ...]:
    """Rules reminders contributed by selected powers and active class state."""

    kind = str(attack.attack_type or "").casefold()
    if "melee" not in kind:
        return ()
    notes: list[str] = []
    for module in resolve_class_feature_modules(repository, character_id):
        if module.key != "investigator":
            continue
        studied = next(
            (item for item in module.resources if item.key == "studied_combat"), None
        )
        if studied is None or not studied.active:
            continue
        target = studied.choices[0] if studied.choices else "studied target"
        notes.append(
            f"Studied Combat applies only against {target}; studying normally lasts "
            f"{studied.maximum} rounds and ends after a Studied Strike."
        )
        for option in _selected_powers(
            repository, character_id, "investigator-talents"
        ):
            folded = f"{option.name} {option.description}".casefold()
            if "studied combat" in folded or "studied strike" in folded:
                notes.append(f"{option.name}: {option.description}")
    return tuple(notes)

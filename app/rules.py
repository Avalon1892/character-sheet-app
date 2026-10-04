from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, replace
from collections.abc import Mapping

from app.models import (
    CONDITION_PRESETS,
    Attack,
    CastingProfile,
    ClassLevel,
    Condition,
    OngoingEffect,
    EquipmentItem,
    Feat,
    FeatEffect,
    MartialTalent,
    SheetEffect,
    Spell,
    Trait,
    SkillDefinition,
    SkillState,
    StatModifier,
    CharacterDetails,
)
from app.class_modifications import resolve_class_profile
from app.content import entry_by_key, item_entry
from app.item_effects import effective_item_state


STACKABLE_BONUS_TYPES = frozenset(
    {"untyped", "circumstance", "racial", "age", "dodge"}
)

SIZE_AC_MODIFIERS = {
    "Fine": 8,
    "Diminutive": 4,
    "Tiny": 2,
    "Small": 1,
    "Medium": 0,
    "Large": -1,
    "Huge": -2,
    "Gargantuan": -4,
    "Colossal": -8,
}

SIZE_LOAD_MULTIPLIERS = {
    "Fine": 1 / 8,
    "Diminutive": 1 / 4,
    "Tiny": 1 / 2,
    "Small": 3 / 4,
    "Medium": 1,
    "Large": 2,
    "Huge": 4,
    "Gargantuan": 8,
    "Colossal": 16,
}

_BASE_CARRYING_CAPACITY = (
    (0, 0, 0),
    (3, 6, 10),
    (6, 13, 20),
    (10, 20, 30),
    (13, 26, 40),
    (16, 33, 50),
    (20, 40, 60),
    (23, 46, 70),
    (26, 53, 80),
    (30, 60, 90),
    (33, 66, 100),
    (38, 76, 115),
    (43, 86, 130),
    (50, 100, 150),
    (58, 116, 175),
    (66, 133, 200),
    (76, 153, 230),
    (86, 173, 260),
    (100, 200, 300),
    (116, 233, 350),
    (133, 266, 400),
    (153, 306, 460),
    (173, 346, 520),
    (200, 400, 600),
    (233, 466, 700),
    (266, 533, 800),
    (306, 613, 920),
    (346, 693, 1040),
    (400, 800, 1200),
    (466, 933, 1400),
)


@dataclass(frozen=True, slots=True)
class Contribution:
    source: str
    bonus_type: str
    value: int
    applied: bool
    reason: str
    modifier_id: int | None = None


@dataclass(frozen=True, slots=True)
class CalculationResult:
    total: int
    ability_modifier: int
    contributions: tuple[Contribution, ...]


@dataclass(frozen=True, slots=True)
class AttackResult:
    attack_bonus: int
    damage_bonus: int
    damage_display: str
    extra_damage: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SkillResult:
    total: int
    usable: bool
    contributions: tuple[Contribution, ...]


@dataclass(frozen=True, slots=True)
class CarryingCapacity:
    light: float
    medium: float
    heavy: float

    @property
    def lift_off_ground(self) -> float:
        return self.heavy * 2

    @property
    def push_or_drag(self) -> float:
        return self.heavy * 5

    def load_for(self, weight: float) -> str:
        if weight <= self.light:
            return "Light"
        if weight <= self.medium:
            return "Medium"
        if weight <= self.heavy:
            return "Heavy"
        return "Overloaded"


@dataclass(frozen=True, slots=True)
class Encumbrance:
    """Resolved PF1e weight-load restrictions for one creature.

    Penalties are stored as positive magnitudes so callers can combine them
    with armor restrictions by taking the worse value instead of stacking the
    two systems.
    """

    load: str
    weight: float
    capacity: CarryingCapacity
    maximum_dexterity: int | None
    check_penalty: int
    speed: int
    run_multiplier: int

    @property
    def armor_category(self) -> str:
        return self.load.casefold() if self.load in {"Medium", "Heavy"} else ""


@dataclass(frozen=True, slots=True)
class CastingStatistics:
    casting_ability_modifier: int
    caster_level: int
    save_dc: int
    magic_skill_bonus: int
    magic_skill_defense: int
    concentration_bonus: int
    spell_points_maximum: int
    spell_point_contributions: tuple["SpellPointContribution", ...] = ()


@dataclass(frozen=True, slots=True)
class SpellPointContribution:
    """One independently replaceable source in a spherecaster's spell pool."""

    source: str
    value: int
    note: str = ""


def calculate_spell_point_pool(
    profile: CastingProfile,
    casting_ability_modifier: int,
    extra_sources: tuple[SpellPointContribution, ...] = (),
) -> tuple[int, tuple[SpellPointContribution, ...]]:
    """Build a spell pool from modular sources.

    Automatic pools follow the basic spherecasting rule of casting-class levels
    plus the casting ability modifier, with a minimum of one. Callers may append
    class, tradition, drawback, boon, or other sources without changing this rule.
    """
    if not profile.auto_spell_points:
        sources = (
            SpellPointContribution(
                "Manual maximum", profile.spell_points_maximum, "Automatic rules disabled"
            ),
        )
        return max(0, profile.spell_points_maximum), sources

    sources = (
        SpellPointContribution(
            "Casting-class levels", profile.casting_class_levels, "Base spherecasting pool"
        ),
        SpellPointContribution(
            "Casting ability modifier", casting_ability_modifier, "Base spherecasting pool"
        ),
        SpellPointContribution(
            "Other adjustment", profile.spell_points_misc, "Manual modular adjustment"
        ),
        *extra_sources,
    )
    raw_total = sum(source.value for source in sources)
    if raw_total < 1:
        sources = (*sources, SpellPointContribution("Minimum pool", 1 - raw_total, "Minimum 1"))
    return max(1, raw_total), sources


def score_to_modifier(score: int) -> int:
    """Convert an ability score to its PF1e modifier."""
    return (score - 10) // 2


def prodigy_level(classes: list[ClassLevel]) -> int:
    """Return combined Prodigy levels, including named archetype rows."""
    return sum(
        item.level
        for item in classes
        if item.preset_key == "prodigy" or "prodigy" in item.class_name.casefold()
    )


def prodigy_caster_level(level: int) -> int:
    """Prodigy mid-caster progression; its first class level functions at CL 1."""
    return 0 if level <= 0 else max(1, (level * 3) // 4)


def automatic_class_casting(
    classes: list[ClassLevel], class_definitions: dict[str, dict],
    archetype_keys_by_class_level: dict[int, list[str] | tuple[str, ...]] | None = None,
    archetype_definitions: dict[str, dict] | None = None,
    archetype_choice_selections_by_class_level: dict[int, dict[str, tuple[str, ...]]] | None = None,
) -> tuple[int, int, str] | None:
    """Return the highest applicable class casting level and caster level.

    PF1 classes keep separate caster levels when multiclassed. The sheet has one
    general casting display, so it reports the highest current progression rather
    than incorrectly adding unrelated spellcasting classes together.
    """
    candidates: list[tuple[int, int, str]] = []
    archetype_keys_by_class_level = archetype_keys_by_class_level or {}
    archetype_definitions = archetype_definitions or {}
    archetype_choice_selections_by_class_level = archetype_choice_selections_by_class_level or {}
    for class_level in classes:
        if class_level.preset_key == "prodigy":
            candidates.append((class_level.level, prodigy_caster_level(class_level.level), class_level.class_name))
            continue
        definition = class_definitions.get(class_level.preset_key) or class_definitions.get(
            f"pathfinder-class:{class_level.preset_key}"
        )
        archetypes = tuple(
            archetype_definitions[key]
            for key in archetype_keys_by_class_level.get(class_level.id, ())
            if key in archetype_definitions
        )
        casting = resolve_class_profile(
            definition or {}, archetypes,
            archetype_choice_selections_by_class_level.get(class_level.id, {}),
        ).casting
        sphere_progression = str(casting.get("sphere_progression") or "").casefold()
        if sphere_progression:
            if sphere_progression == "high":
                caster_level = class_level.level
            elif sphere_progression == "mid":
                caster_level = max(1, (class_level.level * 3) // 4)
            else:
                caster_level = max(1, class_level.level // 2)
            candidates.append((class_level.level, caster_level, class_level.class_name))
            continue
        if not any(casting.get(key) for key in ("ability", "progression", "spells")):
            continue
        caster_level = max(0, class_level.level + int(casting.get("caster_level_offset") or 0))
        candidates.append((class_level.level, caster_level, class_level.class_name))
    return max(candidates, key=lambda value: (value[1], value[0])) if candidates else None


def automatic_traditional_casting(
    classes: list[ClassLevel], class_definitions: dict[str, dict],
    archetype_keys_by_class_level: dict[int, list[str] | tuple[str, ...]] | None = None,
    archetype_definitions: dict[str, dict] | None = None,
    archetype_choice_selections_by_class_level: dict[int, dict[str, tuple[str, ...]]] | None = None,
) -> tuple[int, int, str] | None:
    candidates: list[tuple[int, int, str]] = []
    archetype_keys_by_class_level = archetype_keys_by_class_level or {}
    archetype_definitions = archetype_definitions or {}
    archetype_choice_selections_by_class_level = archetype_choice_selections_by_class_level or {}
    for class_level in classes:
        definition = class_definitions.get(class_level.preset_key) or class_definitions.get(
            f"pathfinder-class:{class_level.preset_key}"
        )
        archetypes = tuple(
            archetype_definitions[key]
            for key in archetype_keys_by_class_level.get(class_level.id, ())
            if key in archetype_definitions
        )
        casting = resolve_class_profile(
            definition or {}, archetypes,
            archetype_choice_selections_by_class_level.get(class_level.id, {}),
        ).casting
        if casting.get("traditional") is False or not any(
            casting.get(key) for key in ("ability", "progression", "spells")
        ):
            continue
        caster_level = max(0, class_level.level + int(casting.get("caster_level_offset") or 0))
        candidates.append((class_level.level, caster_level, class_level.class_name))
    return max(candidates, key=lambda value: (value[1], value[0])) if candidates else None


def automatic_sphere_casting(
    classes: list[ClassLevel],
    class_definitions: dict[str, dict],
    archetype_keys_by_class_level: dict[int, list[str] | tuple[str, ...]] | None = None,
    archetype_definitions: dict[str, dict] | None = None,
    archetype_choice_selections_by_class_level: dict[int, dict[str, tuple[str, ...]]] | None = None,
) -> tuple[int, int, str] | None:
    """Stack Spheres caster levels across classes, as the Spheres rules require."""

    casting_levels = 0
    caster_level = 0
    sources: list[str] = []
    archetype_keys_by_class_level = archetype_keys_by_class_level or {}
    archetype_definitions = archetype_definitions or {}
    archetype_choice_selections_by_class_level = (
        archetype_choice_selections_by_class_level or {}
    )
    for class_level in classes:
        definition = class_definitions.get(class_level.preset_key) or class_definitions.get(
            f"pathfinder-class:{class_level.preset_key}"
        )
        archetypes = tuple(
            archetype_definitions[key]
            for key in archetype_keys_by_class_level.get(class_level.id, ())
            if key in archetype_definitions
        )
        casting = resolve_class_profile(
            definition or {},
            archetypes,
            archetype_choice_selections_by_class_level.get(class_level.id, {}),
        ).casting
        progression = str(casting.get("sphere_progression") or "").casefold()
        # Compatibility for older imported archetypes that predate the
        # declarative class-modification contract. New packages should declare
        # sphere progression explicitly.
        if not progression and not any(
            isinstance(archetype.get("class_modifications"), Mapping)
            and "casting" in archetype.get("class_modifications", {})
            for archetype in archetypes
        ):
            for archetype in archetypes:
                match = re.search(
                    r"considered (?:an? )?(high|mid|low)[ -]?caster",
                    str(archetype.get("description") or ""),
                    re.I,
                )
                if match:
                    progression = match.group(1).casefold()
                    break
        if not progression:
            continue
        casting_levels += class_level.level
        if progression == "high":
            contribution = class_level.level
        elif progression == "mid":
            contribution = (class_level.level * 3) // 4
        else:
            contribution = class_level.level // 2
        caster_level += contribution
        sources.append(class_level.class_name)
    if not sources:
        return None
    return casting_levels, max(1, caster_level), ", ".join(sources)


def prodigy_sequence_maximum(level: int) -> int:
    return 4 + max(0, level) // 3


def prodigy_blended_talents(level: int) -> int:
    return max(0, level)


def prodigy_adaptation_uses(level: int) -> int:
    return 0 if level < 2 else 3 + level // 2


def prodigy_inspired_sequence_bonus(level: int, links: int, active: bool) -> int:
    if level <= 0 or not active or links <= 0:
        return 0
    return max(1, links // 2)


def carrying_capacity(strength: int, size: str = "Medium", *, size_steps: int = 0) -> CarryingCapacity:
    """Return PF1e bipedal carrying thresholds for a Strength score and size."""
    if strength <= 0:
        return CarryingCapacity(0, 0, 0)
    multiplier = 1
    base_strength = strength
    while base_strength > 29:
        base_strength -= 10
        multiplier *= 4
    light, medium, heavy = _BASE_CARRYING_CAPACITY[base_strength]
    size_multiplier = SIZE_LOAD_MULTIPLIERS.get(size, 1)
    if size_steps:
        sizes=tuple(SIZE_LOAD_MULTIPLIERS)
        index=(sizes.index(size) if size in sizes else sizes.index("Medium"))+max(0,int(size_steps))
        size_multiplier=SIZE_LOAD_MULTIPLIERS[sizes[min(index,len(sizes)-1)]]
    return CarryingCapacity(
        light * multiplier * size_multiplier,
        medium * multiplier * size_multiplier,
        heavy * multiplier * size_multiplier,
    )


def calculate_encumbrance(
    strength: int,
    size: str,
    weight: float,
    base_speed: int,
    *, size_steps: int = 0,
) -> Encumbrance:
    """Apply the PF1e encumbrance-by-weight table.

    Medium and heavy loads use the same reduced-speed progression as medium
    and heavy armor.  A load beyond the heavy threshold permits only the
    rules' staggered 5-foot movement until twice the heavy threshold, after
    which the creature cannot move the load.
    """

    capacity = carrying_capacity(strength, size,size_steps=size_steps)
    weight = max(0.0, float(weight))
    load = capacity.load_for(weight)
    if load == "Light":
        maximum_dexterity, check_penalty = None, 0
        speed, run_multiplier = max(0, int(base_speed)), 4
    elif load == "Medium":
        maximum_dexterity, check_penalty = 3, 3
        speed, run_multiplier = reduced_armor_speed(base_speed), 4
    elif load == "Heavy":
        maximum_dexterity, check_penalty = 1, 6
        speed, run_multiplier = reduced_armor_speed(base_speed), 3
    else:
        maximum_dexterity, check_penalty = 0, 6
        speed = 5 if weight <= capacity.lift_off_ground else 0
        run_multiplier = 0
    return Encumbrance(
        load, weight, capacity, maximum_dexterity, check_penalty, speed,
        run_multiplier,
    )


def calculate_casting_statistics(
    profile: CastingProfile,
    casting_ability_modifier: int,
    caster_level_bonus: int = 0,
    dc_bonus: int = 0,
    msb_bonus: int = 0,
    msd_bonus: int = 0,
    concentration_bonus: int = 0,
    spell_point_sources: tuple[SpellPointContribution, ...] = (),
) -> CastingStatistics:
    caster_level = max(0, profile.caster_level + caster_level_bonus)
    msb = profile.casting_class_levels + profile.msb_misc + msb_bonus
    maximum, pool_sources = calculate_spell_point_pool(
        profile, casting_ability_modifier, spell_point_sources
    )
    return CastingStatistics(
        casting_ability_modifier=casting_ability_modifier,
        caster_level=caster_level,
        save_dc=(
            10
            + caster_level // 2
            + casting_ability_modifier
            + profile.dc_misc
            + dc_bonus
        ),
        magic_skill_bonus=msb,
        magic_skill_defense=11 + msb + msd_bonus,
        concentration_bonus=(
            msb + casting_ability_modifier + profile.concentration_misc
            + concentration_bonus
        ),
        spell_points_maximum=max(0, maximum),
        spell_point_contributions=pool_sources,
    )


def race_modifiers(details: CharacterDetails) -> dict[str, list[StatModifier]]:
    # Compatibility facade retained for callers and third-party extensions.
    # The race system itself lives in its dedicated catalog-driven module.
    from app.race_rules import race_modifier_map

    return race_modifier_map(details)


def calculate_ability(base_score: int, modifiers: list[StatModifier]) -> CalculationResult:
    """Apply PF1e typed-bonus stacking and return an explainable result.

    Positive bonuses of the same non-stackable type use only the highest value.
    Penalties and the explicitly stackable types are all applied. Disabled and
    superseded entries remain in the breakdown so the displayed total is auditable.
    """
    enabled = [modifier for modifier in modifiers if modifier.enabled]
    best_positive: dict[str, int] = {}
    for modifier in enabled:
        if modifier.value > 0 and modifier.bonus_type not in STACKABLE_BONUS_TYPES:
            best_positive[modifier.bonus_type] = max(
                modifier.value, best_positive.get(modifier.bonus_type, modifier.value)
            )

    contributions: list[Contribution] = [
        Contribution("Base score", "base", base_score, True, "Always applied")
    ]
    total = base_score
    claimed_types: set[str] = set()

    for modifier in modifiers:
        applied = True
        reason = "Applied"
        if not modifier.enabled:
            applied = False
            reason = modifier.disabled_reason or "Disabled"
        elif modifier.value > 0 and modifier.bonus_type not in STACKABLE_BONUS_TYPES:
            best = best_positive[modifier.bonus_type]
            if modifier.value < best or modifier.bonus_type in claimed_types:
                applied = False
                reason = f"Does not stack; +{best} {modifier.bonus_type} bonus applies"
            else:
                claimed_types.add(modifier.bonus_type)

        if applied:
            total += modifier.value
        contributions.append(
            Contribution(
                source=modifier.source,
                bonus_type=modifier.bonus_type,
                value=modifier.value,
                applied=applied,
                reason=reason,
                modifier_id=modifier.id,
            )
        )

    return CalculationResult(
        total=total,
        ability_modifier=score_to_modifier(total),
        contributions=tuple(contributions),
    )


def class_bab(class_level: ClassLevel) -> int:
    if class_level.bab_progression == "Full":
        return class_level.level
    if class_level.bab_progression == "3/4":
        return (class_level.level * 3) // 4
    return class_level.level // 2


def class_save(level: int, progression: str) -> int:
    return 2 + level // 2 if progression == "Good" else level // 3


def total_bab(classes: list[ClassLevel]) -> int:
    return sum(class_bab(item) for item in classes)


def recommended_hit_points(hit_die: int, levels: int) -> int:
    if hit_die <= 0 or levels <= 0:
        return 0
    return hit_die + max(0, levels - 1) * (hit_die // 2 + 1)


def automatic_hit_points(
    classes: list[ClassLevel], constitution_modifier: int, modifiers: list[StatModifier] | None = None
) -> CalculationResult:
    components: list[tuple[str, int]] = []
    for class_level in classes:
        base_hp = class_level.hp_gained
        constitution_hp = constitution_modifier * class_level.level
        class_total = max(class_level.level, base_hp + constitution_hp)
        components.append((f"{class_level.class_name} hit points", class_total))
    if not components:
        components.append(("No class levels", 0))
    return calculate_stat(components, modifiers or [])


def automatic_class_skills(classes: list[ClassLevel]) -> set[str]:
    result: set[str] = set()
    for class_level in classes:
        preset = entry_by_key("classes", class_level.preset_key)
        if preset is not None:
            result.update(preset.get("class_skills", ()))
    return result


def racial_land_speed(details: CharacterDetails) -> int:
    """Return the normal PF1e land speed supplied by the selected race.

    Movement overrides and effects are layered on top by the calculation
    service, keeping race rules independent from widgets and saved layouts.
    """

    from app.race_rules import resolved_race

    return resolved_race(details).base_speed


def total_base_save(classes: list[ClassLevel], save_name: str) -> int:
    attribute = {
        "fortitude": "fort_progression",
        "reflex": "reflex_progression",
        "will": "will_progression",
    }[save_name]
    return sum(class_save(item.level, getattr(item, attribute)) for item in classes)


def calculate_stat(
    components: list[tuple[str, int]], modifiers: list[StatModifier]
) -> CalculationResult:
    """Calculate a derived statistic while retaining every source line."""
    component_total = sum(value for _, value in components)
    modifier_result = calculate_ability(component_total, modifiers)
    contributions = tuple(
        Contribution(source, "base", value, True, "Always applied")
        for source, value in components
    ) + modifier_result.contributions[1:]
    return CalculationResult(
        total=modifier_result.total,
        ability_modifier=score_to_modifier(modifier_result.total),
        contributions=contributions,
    )


def calculate_combat_statistics(
    size: str,
    classes: list[ClassLevel],
    ability_results: dict[str, CalculationResult],
    modifiers: dict[str, list[StatModifier]],
    equipment: list[EquipmentItem] | None = None,
    encumbrance: Encumbrance | None = None,
) -> dict[str, CalculationResult]:
    bab = total_bab(classes)
    strength = ability_results["strength"].ability_modifier
    dexterity = ability_results["dexterity"].ability_modifier
    constitution = ability_results["constitution"].ability_modifier
    wisdom = ability_results["wisdom"].ability_modifier
    ac_size = SIZE_AC_MODIFIERS[size]
    maneuver_size = -ac_size

    equipped = _active_armor_components(equipment or [])
    shield_increase = calculate_stat([], modifiers.get("shield_bonus_increase", []))
    shield_sources = "; ".join(
        f"{entry.source} ({entry.value:+d})"
        for entry in shield_increase.contributions if entry.applied and entry.value
    )
    equipment_ac = [
        StatModifier(
            None, "ac", f"Equipped: {item.name}" + (
                f"; {shield_sources}" if effective_item_state(item) == "shield" and shield_sources else ""
            ),
            "shield" if effective_item_state(item) == "shield" else "armor",
            item.ac_bonus + item.enhancement_bonus + (
                shield_increase.total if effective_item_state(item) == "shield" else 0
            ),
        )
        for item in equipped
        if item.ac_bonus or item.enhancement_bonus
    ]
    max_dex_values = [item.max_dex_bonus for item in equipped if item.max_dex_bonus is not None]
    if encumbrance is not None and encumbrance.maximum_dexterity is not None:
        max_dex_values.append(encumbrance.maximum_dexterity)
    maximum_dexterity = min(max_dex_values) if max_dex_values else None
    dexterity_to_ac = (
        min(dexterity, maximum_dexterity)
        if maximum_dexterity is not None and dexterity > maximum_dexterity
        else dexterity
    )
    dexterity_flat_footed = min(dexterity_to_ac, 0)
    all_ac_modifiers = modifiers.get("ac", []) + equipment_ac
    touch_modifiers = [
        item
        for item in all_ac_modifiers
        if item.bonus_type not in {
            "armor", "shield", "natural armor", "natural armor enhancement"
        }
    ] + modifiers.get("touch_ac", [])
    flat_footed_modifiers = [
        item for item in all_ac_modifiers if item.bonus_type != "dodge"
    ] + modifiers.get("flat_footed_ac", [])

    return {
        "initiative": calculate_stat(
            [("Dexterity modifier", dexterity)], modifiers.get("initiative", [])
        ),
        "fortitude": calculate_stat(
            [
                ("Base Fortitude save", total_base_save(classes, "fortitude")),
                ("Constitution modifier", constitution),
            ],
            modifiers.get("fortitude", []),
        ),
        "reflex": calculate_stat(
            [
                ("Base Reflex save", total_base_save(classes, "reflex")),
                ("Dexterity modifier", dexterity),
            ],
            modifiers.get("reflex", []),
        ),
        "will": calculate_stat(
            [
                ("Base Will save", total_base_save(classes, "will")),
                ("Wisdom modifier", wisdom),
            ],
            modifiers.get("will", []),
        ),
        "ac": calculate_stat(
            [
                ("Base", 10),
                (
                    "Dexterity modifier"
                    if maximum_dexterity is None or dexterity_to_ac == dexterity
                    else f"Dexterity modifier (limited to +{maximum_dexterity})",
                    dexterity_to_ac,
                ),
                (f"{size} size", ac_size),
            ],
            all_ac_modifiers,
        ),
        "touch_ac": calculate_stat(
            [("Base", 10), ("Dexterity modifier", dexterity_to_ac), (f"{size} size", ac_size)],
            touch_modifiers,
        ),
        "flat_footed_ac": calculate_stat(
            [
                ("Base", 10),
                ("Dexterity modifier while flat-footed", dexterity_flat_footed),
                (f"{size} size", ac_size),
            ],
            flat_footed_modifiers,
        ),
        "cmb": calculate_stat(
            [("BAB", bab), ("Strength modifier", strength), (f"{size} size", maneuver_size)],
            modifiers.get("cmb", []),
        ),
        "cmd": calculate_stat(
            [
                ("Base", 10),
                ("BAB", bab),
                ("Strength modifier", strength),
                ("Dexterity modifier", dexterity),
                (f"{size} size", maneuver_size),
            ],
            modifiers.get("cmd", []),
        ),
    }


def calculate_attack(
    attack: Attack,
    bab: int,
    ability_results: dict[str, CalculationResult],
    size: str,
    attack_modifiers: list[StatModifier] | None = None,
    damage_modifiers: list[StatModifier] | None = None,
    extra_damage: tuple[object, ...] = (),
) -> AttackResult:
    attack_ability = ability_results[attack.ability].ability_modifier
    attack_result = calculate_stat(
        [
            ("BAB", bab),
            (f"{attack.ability.title()} modifier", attack_ability),
            (f"{size} size", SIZE_AC_MODIFIERS[size]),
            ("Attack-specific bonus", attack.attack_bonus),
        ],
        attack_modifiers or [],
    )
    damage_ability = (
        0
        if attack.damage_ability is None
        else ability_results[attack.damage_ability].ability_modifier
    )
    scaled_damage = math.floor(damage_ability * attack.damage_multiplier)
    damage_result = calculate_stat(
        [("Ability contribution", scaled_damage), ("Damage-specific bonus", attack.damage_bonus)],
        damage_modifiers or [],
    )
    damage_total = damage_result.total
    suffix = "" if damage_total == 0 else f"{damage_total:+d}"
    components = tuple(
        (
            str(getattr(component, "dice", "")),
            str(getattr(component, "damage_type", "")),
            str(getattr(component, "source", "")),
        )
        for component in extra_damage
        if str(getattr(component, "dice", ""))
    )
    extra_display = "".join(
        (
            "+" if source.startswith("Damage bonus formula:") else " + "
        )
        + dice
        + (" " + damage_type if damage_type and damage_type != "untyped" else "")
        for dice, damage_type, source in components
    )
    return AttackResult(
        attack_result.total,
        damage_total,
        f"{attack.damage_dice}{suffix}{extra_display}",
        components,
    )


def condition_modifiers(conditions: list[Condition]) -> dict[str, list[StatModifier]]:
    result: dict[str, list[StatModifier]] = {}
    active_names = {condition.name for condition in conditions if condition.enabled}
    for condition in conditions:
        if not condition.enabled or (
            condition.name == "Fatigued" and "Exhausted" in active_names
        ):
            continue
        for target, value in CONDITION_PRESETS[condition.name]:
            result.setdefault(target, []).append(
                StatModifier(
                    None,
                    target,
                    f"Condition: {condition.name}",
                    "condition",
                    value,
                    True,
                )
            )
    return result


def ongoing_effect_modifiers(
    effects: list[OngoingEffect] | tuple[OngoingEffect, ...],
) -> dict[str, list[StatModifier]]:
    """Project active temporary effects into the shared modifier pipeline."""

    result: dict[str, list[StatModifier]] = {}
    for effect in effects:
        if not effect.enabled or not effect.target or effect.value == 0:
            continue
        result.setdefault(effect.target, []).append(
            StatModifier(
                None,
                effect.target,
                f"{effect.source_type} effect: {effect.name}",
                effect.bonus_type,
                effect.value,
                True,
            )
        )
    return result


RuleItem = Feat | Trait | MartialTalent | Spell


def _rule_source(item: RuleItem, label: str) -> str:
    choice = f" ({item.choice})" if item.choice else ""
    return f"{label}: {item.name}{choice}"


def _general_effect_value(
    effect: SheetEffect,
    skill_states: dict[str, SkillState],
    character_level: int,
    bab: int,
    equipment: list[EquipmentItem],
    rule_items: list[RuleItem] | None = None,
) -> int | None:
    if effect.formula in {"class_skill", "allow_untrained"}:
        return 0
    if effect.formula == "character_level_min_3":
        return max(3, character_level)
    if effect.formula == "half_level_round_up":
        return max(0, (character_level + 1) // 2)
    if effect.formula == "bab_step":
        return effect.value * (1 + max(0, bab) // 4)
    if effect.formula == "bab_step_5":
        return effect.value * (1 + max(0, bab) // 5)
    if effect.formula == "bab_step_7":
        return effect.value * (1 + max(0, bab) // 7)
    if effect.formula == "half_bab_min_1":
        return max(1, max(0, bab) // 2)
    if effect.formula == "bab_2_4_at_10":
        return 4 if bab >= 10 else 2
    if effect.formula == "skill_rank_base_2_step_4":
        ranks = skill_states.get(effect.scope, SkillState(effect.scope)).ranks
        return effect.value + max(0, ranks) // 4
    if effect.formula == "unarmored_bab_thirds":
        if any(
            item.equipped
            and item.quantity > 0
            and item.category.casefold() == "armor"
            for item in equipment
        ):
            return None
        # Unarmored Training normally scales from BAB.  Athletics sphere users
        # may use their Acrobatics ranks instead; always select the better legal
        # progression so gaining ranks never lowers the armor bonus.
        has_athletics = any(
            isinstance(item, MartialTalent)
            and item.enabled
            and item.sphere.casefold() == "athletics"
            and item.catalog_category.casefold() != "drawback"
            and item.talent_type.casefold() != "drawback"
            for item in (rule_items or [])
        )
        acrobatics_ranks = skill_states.get(
            "acrobatics", SkillState("acrobatics")
        ).ranks
        progression = max(0, bab)
        if has_athletics:
            progression = max(progression, max(0, acrobatics_ranks))
        return effect.value + progression // 3
    if effect.formula in {"rank_scaled_2_4", "rank_scaled_3_6"}:
        skill_key = effect.target.removeprefix("skill:")
        ranks = skill_states.get(skill_key, SkillState(skill_key)).ranks
        if effect.formula == "rank_scaled_2_4":
            return 4 if ranks >= 10 else 2
        return 6 if ranks >= 10 else 3
    if effect.formula == "equipped_category":
        if not any(
            item.equipped
            and item.quantity > 0
            and item.category.casefold() == effect.scope.casefold()
            for item in equipment
        ):
            return None
    if effect.formula == "equipped_item":
        if not any(
            item.equipped
            and item.quantity > 0
            and item.name.casefold() == effect.scope.casefold()
            for item in equipment
        ):
            return None
    return effect.value


def _rule_modifiers(
    items: list[RuleItem],
    label: str,
    include_legacy_bonus: bool,
    skill_states: dict[str, SkillState] | None = None,
    character_level: int = 0,
    bab: int = 0,
    equipment: list[EquipmentItem] | None = None,
) -> dict[str, list[StatModifier]]:
    result: dict[str, list[StatModifier]] = {}
    skill_states = skill_states or {}
    equipment = equipment or []
    for item in items:
        if not item.enabled:
            continue
        legacy_target = str(getattr(item, "target", ""))
        legacy_value = int(getattr(item, "value", 0))
        if include_legacy_bonus and legacy_target and legacy_value != 0:
            result.setdefault(legacy_target, []).append(
                StatModifier(
                    None,
                    legacy_target,
                    f"{label}: {item.name}",
                    str(getattr(item, "bonus_type", "untyped")),
                    legacy_value,
                    True,
                )
            )
        for effect in item.effects:
            if effect.target in {"attack", "damage"}:
                continue
            value = _general_effect_value(
                effect, skill_states, character_level, bab, equipment, items
            )
            if value is None or value == 0:
                continue
            result.setdefault(effect.target, []).append(
                StatModifier(
                    None,
                    effect.target,
                    _rule_source(item, label),
                    effect.bonus_type,
                    value,
                    True,
                )
            )
    return result


def feat_modifiers(
    feats: list[Feat],
    skill_states: dict[str, SkillState] | None = None,
    character_level: int = 0,
    bab: int = 0,
    equipment: list[EquipmentItem] | None = None,
) -> dict[str, list[StatModifier]]:
    # Older saves store these as separate AC/flat-footed effects. Project the
    # stock effects as an increase to the equipped shield instead; do not rewrite
    # saved selections or replace manually customized effects.
    from app.feat_automation import feat_automation

    projected = []
    for feat in feats:
        if feat.name.casefold() in {"shield focus", "greater shield focus"}:
            stock = tuple(FeatEffect(**effect) for effect in feat_automation(feat.name)["effects"])
            if feat.effects == stock:
                feat = replace(feat, effects=(replace(stock[0], target="shield_bonus_increase"),))
        projected.append(feat)
    return _rule_modifiers(
        projected, "Feat", True, skill_states, character_level, bab, equipment
    )


def trait_modifiers(
    traits: list[Trait],
    skill_states: dict[str, SkillState] | None = None,
    character_level: int = 0,
    bab: int = 0,
    equipment: list[EquipmentItem] | None = None,
) -> dict[str, list[StatModifier]]:
    return _rule_modifiers(
        traits, "Trait", True, skill_states, character_level, bab, equipment
    )


def martial_talent_modifiers(
    talents: list[MartialTalent],
    skill_states: dict[str, SkillState] | None = None,
    character_level: int = 0,
    bab: int = 0,
    equipment: list[EquipmentItem] | None = None,
) -> dict[str, list[StatModifier]]:
    return _rule_modifiers(
        talents, "Martial talent", False, skill_states, character_level, bab, equipment
    )


def magic_talent_modifiers(
    talents: list[Spell],
    skill_states: dict[str, SkillState] | None = None,
    character_level: int = 0,
    bab: int = 0,
    equipment: list[EquipmentItem] | None = None,
) -> dict[str, list[StatModifier]]:
    return _rule_modifiers(
        talents, "Magic talent", False, skill_states, character_level, bab, equipment
    )


def effect_class_skills(items: list[RuleItem]) -> set[str]:
    return {
        effect.target.removeprefix("skill:")
        for item in items
        if item.enabled
        for effect in item.effects
        if effect.formula == "class_skill" and effect.target.startswith("skill:")
    }


def effect_untrained_skills(items: list[RuleItem]) -> set[str]:
    return {
        effect.target.removeprefix("skill:")
        for item in items
        if item.enabled
        for effect in item.effects
        if effect.formula == "allow_untrained" and effect.target.startswith("skill:")
    }


def _effect_matches_attack(effect: SheetEffect, attack: Attack) -> bool:
    if not effect.scope:
        return True
    kind, separator, value = effect.scope.partition(":")
    if not separator:
        return True
    if kind.casefold() == "name":
        return attack.name.casefold() == value.casefold()
    if kind.casefold() == "type":
        return attack.attack_type.casefold() == value.casefold()
    return False


def _attack_effect_value(effect: SheetEffect, attack: Attack, bab: int) -> int:
    step = 1 + max(0, bab) // 4
    if effect.formula == "bab_step":
        return effect.value * step
    if effect.formula == "power_attack_damage":
        if attack.damage_multiplier >= 1.5:
            return 3 * step
        if attack.damage_multiplier <= 0.5:
            return step
        return 2 * step
    return effect.value


def _rule_attack_modifiers(
    items: list[RuleItem], attack: Attack, bab: int, label: str
) -> tuple[list[StatModifier], list[StatModifier]]:
    attack_modifiers: list[StatModifier] = []
    damage_modifiers: list[StatModifier] = []
    for item in items:
        if not item.enabled:
            continue
        for effect in item.effects:
            if effect.target not in {"attack", "damage"}:
                continue
            if not _effect_matches_attack(effect, attack):
                continue
            value = _attack_effect_value(effect, attack, bab)
            if value == 0:
                continue
            modifier = StatModifier(
                None,
                effect.target,
                _rule_source(item, label),
                effect.bonus_type,
                value,
                True,
            )
            if effect.target == "attack":
                attack_modifiers.append(modifier)
            else:
                damage_modifiers.append(modifier)
    return attack_modifiers, damage_modifiers


def feat_attack_modifiers(
    feats: list[Feat], attack: Attack, bab: int
) -> tuple[list[StatModifier], list[StatModifier]]:
    return _rule_attack_modifiers(feats, attack, bab, "Feat")


def trait_attack_modifiers(
    traits: list[Trait], attack: Attack, bab: int
) -> tuple[list[StatModifier], list[StatModifier]]:
    return _rule_attack_modifiers(traits, attack, bab, "Trait")


def martial_talent_attack_modifiers(
    talents: list[MartialTalent], attack: Attack, bab: int
) -> tuple[list[StatModifier], list[StatModifier]]:
    return _rule_attack_modifiers(talents, attack, bab, "Martial talent")


def magic_talent_attack_modifiers(
    talents: list[Spell], attack: Attack, bab: int
) -> tuple[list[StatModifier], list[StatModifier]]:
    return _rule_attack_modifiers(talents, attack, bab, "Magic talent")


def total_armor_check_penalty(equipment: list[EquipmentItem]) -> int:
    return sum(
        item.armor_check_penalty
        for item in _active_armor_components(equipment)
    )


def worn_armor_movement_category(
    equipment: list[EquipmentItem] | tuple[EquipmentItem, ...],
) -> tuple[str, str]:
    """Return the active armor's catalog-backed movement weight and name.

    Saved equipment intentionally uses the compact sheet category ``Armor``.
    The bundled catalog remains authoritative for whether a catalog armor is
    light, medium, or heavy. Custom and legacy armor can still use the existing
    manual armor-speed override without guessing rules from prose.
    """

    armor = next(
        (
            item
            for item in _active_armor_components(list(equipment))
            if effective_item_state(item) == "armor"
        ),
        None,
    )
    if armor is None:
        return "", ""
    if not armor.catalog_key:
        return "unknown", armor.name
    entry = item_entry(armor.catalog_key)
    category = str((entry or {}).get("category") or "").casefold()
    for weight in ("heavy", "medium", "light"):
        if re.search(rf"\barmor\s*,\s*{weight}\b", category):
            return weight, armor.name
    return "unknown", armor.name


def reduced_armor_speed(speed: int) -> int:
    """PF1e medium/heavy-armor speed, rounded up to a 5-foot step."""

    speed = max(0, int(speed))
    if speed == 0:
        return 0
    return int(math.ceil((speed * 2 / 3) / 5) * 5)


def _active_armor_components(equipment: list[EquipmentItem]) -> list[EquipmentItem]:
    """Resolve at most one armor and one shield component for coherent restrictions."""
    result: list[EquipmentItem] = []
    for state in ("armor", "shield"):
        candidates = [
            item for item in equipment
            if effective_item_state(item) == state and item.quantity > 0
        ]
        if candidates:
            result.append(
                max(candidates, key=lambda item: (item.ac_bonus + item.enhancement_bonus, -item.id))
            )
    return result


def calculate_skill(
    definition: SkillDefinition,
    state: SkillState,
    ability_result: CalculationResult,
    armor_check_penalty: int,
    global_modifiers: list[StatModifier] | None = None,
    allow_untrained: bool = False,
) -> SkillResult:
    class_skill_bonus = 3 if state.class_skill and state.ranks > 0 else 0
    applied_armor_penalty = -(armor_check_penalty * definition.armor_check_multiplier)
    result = calculate_stat(
        [
            (f"{definition.ability.title()} modifier", ability_result.ability_modifier),
            ("Ranks", state.ranks),
            ("Class skill bonus", class_skill_bonus),
            ("Miscellaneous", state.misc_bonus),
            ("Armor check penalty", applied_armor_penalty),
        ],
        global_modifiers or [],
    )
    return SkillResult(
        total=result.total,
        usable=allow_untrained or not definition.trained_only or state.ranks > 0,
        contributions=result.contributions,
    )


def parse_dice(dice: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{1,2})d(\d{1,4})\s*", dice, re.IGNORECASE)
    if match is None:
        raise ValueError("Damage dice must look like 1d8 or 2d6.")
    count, sides = (int(value) for value in match.groups())
    if count < 1 or sides < 2:
        raise ValueError("Dice require at least one die with two sides.")
    return count, sides


def roll_attack_and_damage(
    result: AttackResult, damage_dice: str, rng: random.Random | None = None
) -> tuple[int, int, int, tuple[int, ...]]:
    roller = rng or random.Random()
    natural = roller.randint(1, 20)
    attack_total = natural + result.attack_bonus
    count, sides = parse_dice(damage_dice)
    rolls_list = [roller.randint(1, sides) for _ in range(count)]
    for extra_dice, _damage_type, _source in result.extra_damage:
        extra_count, extra_sides = parse_dice(extra_dice)
        rolls_list.extend(roller.randint(1, extra_sides) for _ in range(extra_count))
    rolls = tuple(rolls_list)
    damage_total = max(1, sum(rolls) + result.damage_bonus)
    return natural, attack_total, damage_total, rolls

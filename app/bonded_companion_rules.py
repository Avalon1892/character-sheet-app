"""Registry-driven Familiar and class-companion progression rules."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from app.class_feature_context import resolved_class_features_for_level
from app.class_feature_rules import feature_token


@dataclass(frozen=True, slots=True)
class BondedCompanionDefinition:
    key: str
    name: str
    source: str
    owner_class_keys: frozenset[str]
    feature_tokens: frozenset[str]


@dataclass(frozen=True, slots=True)
class BondedCompanionProgression:
    level: int
    hit_dice: str
    bab: str
    fortitude: str
    reflex: str
    will: str
    natural_armor: int
    intelligence: int | None
    feats: int | None
    skill_ranks: int | None
    ability_increases: int
    specials: tuple[str, ...]
    ability_bonus: int = 0
    natural_attack_damage: str = "—"


@dataclass(frozen=True, slots=True)
class BondedCompanionGrant:
    """One resolved page grant, independent from its Qt presentation."""

    level: int
    variant: str
    sources: tuple[str, ...]
    class_level: int = 0
    pet_level: int = 0
    can_stack_pet: bool = False
    stacks_pet: bool = False


@dataclass(frozen=True, slots=True)
class FamiliarAttack:
    name: str
    attack_bonus: int
    damage: str
    notes: str = "Natural attack"


@dataclass(frozen=True, slots=True)
class FamiliarSheetStatistics:
    """Complete play-facing projection for a selected familiar form."""

    name: str
    source: str
    ruleset: str
    creature_type: str
    size: str
    hit_dice: str
    effective_hit_dice: int
    maximum_hp: int
    initiative: int
    armor_class: int
    touch_ac: int
    flat_footed_ac: int
    natural_armor: int
    base_attack_bonus: int
    cmb: int
    cmd: int
    saves: Mapping[str, int]
    abilities: Mapping[str, int]
    ability_modifiers: Mapping[str, int]
    speed: str
    senses: str
    attacks: tuple[FamiliarAttack, ...]
    feats: str
    skills: str
    special_qualities: str
    familiar_special: str
    spell_resistance: str
    source_url: str


FAMILIAR = BondedCompanionDefinition(
    "familiar",
    "Pet / Familiar",
    "PF1e familiar and Beastmastery Pet progression",
    frozenset(),
    frozenset({"familiar", "witch-s-familiar", "spirit-animal"}),
)

CORPSE_PUPPET = BondedCompanionDefinition(
    "corpse_puppet",
    "Corpse Puppet",
    "Necros class feature",
    frozenset({"spheres-class:necros"}),
    frozenset({"corpse-puppet"}),
)

PHANTOM = BondedCompanionDefinition(
    "phantom",
    "Phantom",
    "PF1e Spiritualist manifested phantom progression",
    frozenset({"pathfinder-class:spiritualist"}),
    frozenset({"phantom"}),
)

BONDED_COMPANION_DEFINITIONS = (FAMILIAR, CORPSE_PUPPET, PHANTOM)


@lru_cache(maxsize=1)
def familiar_catalog() -> tuple[dict, ...]:
    path = Path(__file__).resolve().parents[1] / "data" / "pf1e" / "familiars.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(dict(item) for item in payload.get("entries", ()))


def familiar_entry(key: str) -> dict | None:
    wanted = str(key or "").casefold()
    return next(
        (item for item in familiar_catalog() if str(item.get("key", "")).casefold() == wanted),
        None,
    )


_FAMILIAR_SPECIALS = {
    1: ("Alertness", "Improved Evasion", "Share Spells", "Empathic Link"),
    3: ("Deliver Touch Spells",),
    5: ("Speak with Master",),
    7: ("Speak with Animals of Its Kind",),
    11: ("Spell Resistance",),
    13: ("Scry on Familiar",),
}


_CORPSE_ROWS = (
    # level, HD, BAB, Fort, Ref, Will, skills, feats, NA, Str/Dex, specials
    (1,2,1,0,0,3,2,1,0,0,("Martial tradition","Necro Force +1","Share Spells","Unseen Evolution")),
    (2,3,2,1,1,3,3,2,0,0,("Combat Talent","Evasion")),
    (3,3,3,1,1,3,3,2,2,1,("Undead Evolution",)),
    (4,4,3,1,1,4,4,2,2,1,()),
    (5,5,3,1,1,4,5,3,2,1,("Combat Talent","Necro Force +2")),
    (6,6,4,2,2,5,6,3,4,2,("Ability-score increase","Undead Evolution")),
    (7,6,4,2,2,5,6,3,4,2,()),
    (8,7,5,2,2,5,7,4,4,2,("Combat Talent",)),
    (9,8,6,2,2,6,7,4,6,3,("Multiattack","Necro Force +3")),
    (10,9,6,3,3,6,9,5,6,3,("Greater Undead Evolution",)),
    (11,9,6,3,3,6,9,5,6,3,("Combat Talent",)),
    (12,10,7,3,3,7,10,5,8,4,()),
    (13,11,7,3,3,7,11,6,8,4,("Ability-score increase","Necro Force +4","Undead Evolution")),
    (14,12,8,4,4,8,12,6,8,4,("Combat Talent","Improved Evasion")),
    (15,12,9,4,4,8,12,6,10,5,("Ability-score increase",)),
    (16,13,9,4,4,8,13,7,10,5,("Undead Evolution",)),
    (17,14,10,4,4,9,14,7,10,5,("Combat Talent","Necro Force +5")),
    (18,15,11,5,5,9,15,8,12,6,()),
    (19,16,11,5,5,9,15,8,12,6,()),
    (20,16,12,5,5,10,16,8,12,6,("Ability-score increase","Combat Talent","Greater Undead Evolution")),
)


_PHANTOM_ROWS = (
    # level, HD, BAB, good save, bad save, skills, feats, armor, Dex/Cha, slam, specials
    (1, 1, 1, 2, 0, 2, 1, 0, 0, "1d6", ("Darkvision", "Link", "Share Spells")),
    (2, 2, 2, 3, 0, 4, 1, 2, 1, "1d6", ()),
    (3, 3, 3, 3, 1, 6, 2, 2, 1, "1d6", ("Deliver Touch Spells (30 ft.)",)),
    (4, 3, 3, 3, 1, 6, 2, 2, 1, "1d6", ("Magic Attacks",)),
    (5, 4, 4, 4, 1, 8, 2, 4, 2, "1d8", ("Ability-score increase",)),
    (6, 5, 5, 4, 1, 10, 3, 4, 2, "1d8", ("Devotion",)),
    (7, 6, 6, 5, 2, 12, 3, 6, 2, "1d8", ()),
    (8, 6, 6, 5, 2, 12, 3, 6, 3, "1d8", ()),
    (9, 7, 7, 5, 2, 14, 4, 6, 3, "1d10", ("Incorporeal Flight",)),
    (10, 8, 8, 6, 2, 16, 4, 8, 4, "1d10", ("Ability-score increase",)),
    (11, 9, 9, 6, 3, 18, 5, 8, 4, "1d10", ()),
    (12, 9, 9, 6, 3, 18, 5, 10, 5, "1d10", ("Deliver Touch Spells (50 ft.)",)),
    (13, 10, 10, 7, 3, 20, 5, 10, 5, "2d6", ()),
    (14, 11, 11, 7, 3, 22, 6, 10, 5, "2d6", ()),
    (15, 12, 12, 8, 4, 24, 6, 12, 6, "2d6", ("Ability-score increase",)),
    (16, 12, 12, 8, 4, 24, 6, 12, 6, "2d6", ()),
    (17, 13, 13, 8, 4, 26, 7, 14, 7, "2d8", ()),
    (18, 14, 14, 9, 4, 28, 7, 14, 7, "2d8", ()),
    (19, 15, 15, 9, 5, 30, 8, 14, 7, "2d8", ()),
    (20, 15, 15, 9, 5, 30, 8, 16, 8, "2d8", ()),
)


def _retained_tokens(repository, character_id: int, class_level) -> frozenset[str]:
    return frozenset(
        feature_token(str(getattr(feature, "name", "")))
        for feature in resolved_class_features_for_level(
            repository, character_id, class_level
        )
    )


def bonded_companion_levels(repository, character_id: int) -> dict[str, int]:
    """Compatibility projection for callers that only need effective levels."""

    return {
        key: grant.level
        for key, grant in bonded_companion_grants(repository, character_id).items()
    }


def bonded_companion_grants(
    repository, character_id: int
) -> dict[str, BondedCompanionGrant]:
    """Resolve class companions and the Beastmastery Pet talent in one registry."""

    class_levels = repository.list_class_levels(character_id)
    character_level = sum(row.level for row in class_levels)
    familiar_class_level = 0
    corpse_level = 0
    phantom_level = 0
    familiar_sources: list[str] = []
    corpse_sources: list[str] = []
    phantom_sources: list[str] = []
    phantom_variant = "phantom"
    selections = repository.list_class_feature_selections(character_id)
    selected_familiar = any(
        "familiar" in f"{item.name} {item.option_key}".casefold()
        for item in selections
    )
    choice_familiar_levels: dict[int, list[str]] = {}
    try:
        from app.class_choice_rules import resolve_class_choice_slots

        for slot in resolve_class_choice_slots(repository, character_id):
            for option in slot.selected_options:
                if any(
                    "familiar" in str(feature.get("name") or "").casefold()
                    for feature in option.granted_features
                    if isinstance(feature, Mapping)
                ):
                    choice_familiar_levels.setdefault(slot.class_level_id, []).append(
                        option.name
                    )
    except (AttributeError, ImportError):
        choice_familiar_levels = {}
    for class_level in class_levels:
        tokens = _retained_tokens(repository, character_id, class_level)
        has_retained_familiar = bool(tokens & FAMILIAR.feature_tokens or (
            "arcane-bond" in tokens and selected_familiar
        ))
        if has_retained_familiar:
            familiar_class_level += class_level.level
            familiar_sources.append(f"{class_level.class_name}: Familiar")
        elif choice_familiar_levels.get(class_level.id):
            familiar_class_level += class_level.level
            familiar_sources.extend(
                f"{class_level.class_name}: {name}"
                for name in choice_familiar_levels[class_level.id]
            )
        if (
            class_level.preset_key in CORPSE_PUPPET.owner_class_keys
            and "corpse-puppet" in tokens
        ):
            corpse_level += class_level.level
            corpse_sources.append(f"{class_level.class_name}: Corpse Puppet")
        has_phantom = bool(
            tokens & PHANTOM.feature_tokens
            or any(
                token.endswith("-phantom") and token != "phantom-weapon"
                for token in tokens
            )
        )
        if class_level.preset_key in PHANTOM.owner_class_keys and has_phantom:
            phantom_level += class_level.level
            phantom_sources.append(f"{class_level.class_name}: Phantom")
            if "kami-phantom" in tokens:
                phantom_variant = "kami_phantom"
    # A selected familiar class power is another common acquisition route.
    try:
        if any("familiar" in item.name.casefold() for item in repository.list_class_power_selections(character_id)):
            familiar_class_level = max(familiar_class_level, character_level)
            familiar_sources.append("Selected class power: Familiar")
    except AttributeError:
        pass

    pet_owned = any(
        item.enabled
        and item.name.casefold() == "pet"
        and item.sphere.casefold() == "beastmastery"
        for item in repository.list_martial_talents(character_id)
    )
    pet_level = 0
    if pet_owned:
        skills = repository.list_skill_states(character_id)
        handle_animal = int(getattr(skills.get("handle_animal"), "ranks", 0))
        bab = sum(
            row.level if row.bab_progression == "Full"
            else (row.level * 3) // 4 if row.bab_progression == "3/4"
            else row.level // 2
            for row in class_levels
        )
        pet_level = max(1, bab, handle_animal)
        familiar_sources.append("Beastmastery: Pet")

    stack_pet = False
    if pet_owned and familiar_class_level:
        try:
            details = json.loads(
                repository.get_bonded_companion(
                    character_id, "familiar"
                ).details_json or "{}"
            )
        except (AttributeError, TypeError, ValueError):
            details = {}
        stack_pet = bool(
            details.get("beastmastery_pet_stack", False)
            if isinstance(details, dict) else False
        )

    grants: dict[str, BondedCompanionGrant] = {}
    if familiar_class_level or pet_level:
        effective = (
            familiar_class_level + pet_level
            if familiar_class_level and pet_level and stack_pet
            else familiar_class_level if familiar_class_level
            else pet_level
        )
        grants["familiar"] = BondedCompanionGrant(
            min(character_level or effective, effective),
            "beastmastery_pet" if pet_level and not familiar_class_level else "standard",
            tuple(dict.fromkeys(familiar_sources)),
            familiar_class_level,
            pet_level,
            bool(familiar_class_level and pet_level),
            stack_pet,
        )
    if corpse_level:
        grants["corpse_puppet"] = BondedCompanionGrant(
            min(character_level or corpse_level, corpse_level),
            "corpse_puppet",
            tuple(dict.fromkeys(corpse_sources)),
            corpse_level,
        )
    if phantom_level:
        grants["phantom"] = BondedCompanionGrant(
            min(character_level or phantom_level, phantom_level),
            phantom_variant,
            tuple(dict.fromkeys(phantom_sources)),
            phantom_level,
        )
    return grants


def familiar_progression(level: int) -> BondedCompanionProgression:
    level = max(1, min(20, int(level)))
    specials = tuple(
        ability
        for gained_level, abilities in _FAMILIAR_SPECIALS.items()
        if gained_level <= level
        for ability in abilities
    )
    return BondedCompanionProgression(
        level,
        "Use familiar creature HD",
        "Use master's BAB",
        "Use master's base save if better",
        "Use master's base save if better",
        "Use master's base save if better",
        (level + 1) // 2,
        5 + (level + 1) // 2,
        None,
        None,
        0,
        specials,
    )


def beastmastery_pet_progression(level: int) -> BondedCompanionProgression:
    """Pet is a familiar with the explicitly removed Beastmastery benefits."""

    standard = familiar_progression(level)
    prohibited = {
        "Deliver Touch Spells",
        "Scry on Familiar",
        "Share Spells",
        "Speak with Animals of Its Kind",
        "Spell Resistance",
    }
    return BondedCompanionProgression(
        standard.level,
        standard.hit_dice,
        standard.bab,
        standard.fortitude,
        standard.reflex,
        standard.will,
        standard.natural_armor,
        None,
        standard.feats,
        standard.skill_ranks,
        standard.ability_increases,
        tuple(value for value in standard.specials if value not in prohibited),
    )


def corpse_puppet_progression(level: int) -> BondedCompanionProgression:
    row = _CORPSE_ROWS[max(1, min(20, int(level))) - 1]
    level, hd, bab, fort, reflex, will, skills, feats, armor, _ability_bonus, specials = row
    all_specials = tuple(
        special
        for prior in _CORPSE_ROWS[:level]
        for special in prior[-1]
    )
    return BondedCompanionProgression(
        level,
        f"{hd}d8",
        str(bab),
        str(fort),
        str(reflex),
        str(will),
        armor,
        3,
        feats,
        skills,
        sum(
            1
            for prior in _CORPSE_ROWS[:level]
            if "Ability-score increase" in prior[-1]
        ),
        all_specials,
    )


def phantom_progression(level: int) -> BondedCompanionProgression:
    """Return the official manifested-phantom table row for a Spiritualist level."""

    row = _PHANTOM_ROWS[max(1, min(20, int(level))) - 1]
    (
        level, hd, bab, good_save, bad_save, skills, feats, armor,
        ability_bonus, slam, _specials,
    ) = row
    all_specials = tuple(
        special
        for prior in _PHANTOM_ROWS[:level]
        for special in prior[-1]
    )
    return BondedCompanionProgression(
        level,
        f"{hd}d10",
        str(bab),
        f"Good +{good_save} / bad +{bad_save} (focus)",
        f"Good +{good_save} / bad +{bad_save} (focus)",
        f"Good +{good_save} / bad +{bad_save} (focus)",
        armor,
        7,
        feats,
        skills,
        sum(
            1
            for prior in _PHANTOM_ROWS[:level]
            if "Ability-score increase" in prior[-1]
        ),
        all_specials,
        ability_bonus,
        slam,
    )
def bonded_companion_progression(
    companion_key: str, level: int, variant: str = "standard"
) -> BondedCompanionProgression:
    if companion_key == "familiar":
        return (
            beastmastery_pet_progression(level)
            if variant == "beastmastery_pet"
            else familiar_progression(level)
        )
    if companion_key == "corpse_puppet":
        return corpse_puppet_progression(level)
    if companion_key == "phantom":
        progression = phantom_progression(level)
        if variant == "kami_phantom":
            hit_dice = int(progression.hit_dice.split("d", 1)[0])
            return replace(
                progression,
                hit_dice=f"{hit_dice}d8",
                bab=str((hit_dice * 3) // 4),
                specials=progression.specials + (
                    "Kami phantom: ectoplasmic manifestation only",
                ),
            )
        return progression
    raise KeyError(companion_key)


_SIZE_AC = {
    "fine": 8,
    "diminutive": 4,
    "tiny": 2,
    "small": 1,
    "medium": 0,
    "large": -1,
    "huge": -2,
    "gargantuan": -4,
    "colossal": -8,
}
_SIZE_CMB = {key: -value for key, value in _SIZE_AC.items()}
_ABILITY_NAMES = {
    "strength": "str",
    "dexterity": "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom": "wis",
    "charisma": "cha",
}


def _modifier(score: int) -> int:
    return (int(score) - 10) // 2


def _integer(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _base_hit_dice(text: str) -> int:
    match = re.search(r"(\d+)d\d+", str(text), re.I)
    return int(match.group(1)) if match else 1


def _attack_rows(text: str, attack_bonus: int) -> tuple[FamiliarAttack, ...]:
    if not text:
        return ()
    rows = []
    for value in re.split(r",\s*(?![^()]*\))", text):
        match = re.match(r"\s*(.*?)\s+[+−–-]?\d+\s*\((.+)\)\s*$", value)
        if match:
            rows.append(FamiliarAttack(match.group(1).strip(), attack_bonus, match.group(2).strip()))
        else:
            rows.append(FamiliarAttack(value.strip(), attack_bonus, "—"))
    return tuple(rows)


def calculate_familiar_statistics(
    entry: Mapping[str, object] | None,
    progression: BondedCompanionProgression,
    master_statistics: Mapping[str, object],
    *,
    variant: str = "standard",
    ability_overrides: Mapping[str, object] = {},
    details: Mapping[str, object] = {},
) -> FamiliarSheetStatistics:
    """Resolve creature statistics plus the live PF1e familiar progression.

    The selected creature contributes its immutable baseline.  The master owns
    HP, BAB, base saves, and effective Hit Dice, while the familiar progression
    owns natural armor, Intelligence, special abilities, and spell resistance.
    """

    entry = entry or {}
    base_scores = {
        key: _integer(dict(entry.get("abilities") or {}).get(key), 10)
        for key in ("str", "dex", "con", "int", "wis", "cha")
    }
    if "int" not in dict(entry.get("abilities") or {}):
        base_scores["int"] = 0
    automatic_scores = dict(base_scores)
    if variant != "beastmastery_pet" and progression.intelligence is not None:
        automatic_scores["int"] = progression.intelligence
    scores = dict(automatic_scores)
    for long_name, short_name in _ABILITY_NAMES.items():
        if long_name in ability_overrides:
            scores[short_name] = _integer(ability_overrides[long_name], scores[short_name])
        elif short_name in ability_overrides:
            scores[short_name] = _integer(ability_overrides[short_name], scores[short_name])
    modifiers = {key: _modifier(value) for key, value in scores.items()}
    base_modifiers = {key: _modifier(value) for key, value in base_scores.items()}

    size = str(entry.get("size") or details.get("size") or "Tiny")
    size_key = size.casefold().split()[0]
    size_ac = _SIZE_AC.get(size_key, 0)
    size_cmb = _SIZE_CMB.get(size_key, 0)
    dexterity_delta = modifiers["dex"] - base_modifiers["dex"]
    natural_armor_adjustment = progression.natural_armor
    armor_class = (
        _integer(entry.get("armor_class"), 10 + base_modifiers["dex"] + size_ac)
        + dexterity_delta
        + natural_armor_adjustment
        + _integer(details.get("ac_misc"))
    )
    touch_ac = (
        _integer(entry.get("touch_ac"), 10 + base_modifiers["dex"] + size_ac)
        + dexterity_delta
        + _integer(details.get("touch_ac_misc"))
    )
    flat_footed_ac = (
        _integer(entry.get("flat_footed_ac"), 10 + size_ac + _integer(entry.get("natural_armor")))
        + natural_armor_adjustment
        + _integer(details.get("flat_footed_ac_misc"))
    )
    natural_armor = _integer(entry.get("natural_armor")) + natural_armor_adjustment

    master_bab = _integer(master_statistics.get("bab"))
    master_base_saves = dict(master_statistics.get("base_saves") or {})
    save_data = (
        ("fortitude", "con"),
        ("reflex", "dex"),
        ("will", "wis"),
    )
    saves = {}
    for save_key, ability in save_data:
        creature_total = _integer(entry.get(save_key))
        creature_base = creature_total - base_modifiers[ability]
        saves[save_key] = max(creature_base, _integer(master_base_saves.get(save_key))) + modifiers[ability]
        saves[save_key] += _integer(details.get(f"{save_key}_misc"))

    maximum_hp = max(0, _integer(master_statistics.get("maximum_hp")) // 2)
    initiative = modifiers["dex"] + _integer(details.get("initiative_misc"))
    attack_bonus = master_bab + max(modifiers["str"], modifiers["dex"]) + size_ac
    attacks = (
        _attack_rows(str(entry.get("melee") or ""), attack_bonus)
        + _attack_rows(str(entry.get("ranged") or ""), master_bab + modifiers["dex"] + size_ac)
    )
    cmb = master_bab + modifiers["str"] + size_cmb + _integer(details.get("cmb_misc"))
    cmd = (
        10
        + master_bab
        + modifiers["str"]
        + modifiers["dex"]
        + size_cmb
        + _integer(details.get("cmd_misc"))
    )
    level = progression.level
    return FamiliarSheetStatistics(
        name=str(entry.get("name") or "Custom familiar"),
        source=str(entry.get("source") or "Custom"),
        ruleset=str(entry.get("ruleset") or "Custom"),
        creature_type=(
            "Animal"
            if variant == "beastmastery_pet"
            else "Magical beast"
        ),
        size=size,
        hit_dice=str(entry.get("hit_dice") or "1d8"),
        effective_hit_dice=max(_base_hit_dice(str(entry.get("hit_dice") or "1d8")), _integer(master_statistics.get("character_level"), level)),
        maximum_hp=maximum_hp,
        initiative=initiative,
        armor_class=armor_class,
        touch_ac=touch_ac,
        flat_footed_ac=flat_footed_ac,
        natural_armor=natural_armor,
        base_attack_bonus=master_bab,
        cmb=cmb,
        cmd=cmd,
        saves=saves,
        abilities=scores,
        ability_modifiers=modifiers,
        speed=str(entry.get("speed") or "—"),
        senses=str(entry.get("senses") or "—"),
        attacks=attacks,
        feats=str(entry.get("feats") or "—"),
        skills=str(entry.get("skills") or "—"),
        special_qualities=str(entry.get("special_qualities") or "—"),
        familiar_special=str(entry.get("familiar_special") or "—"),
        spell_resistance=(
            str(level + 5)
            if variant != "beastmastery_pet" and level >= 11
            else "—"
        ),
        source_url=str(entry.get("source_url") or ""),
    )


def reconcile_familiar_hit_points(record, maximum_hp: int):
    """Preserve damage while a derived familiar maximum changes.

    The previous derived maximum is stored as compatibility-safe JSON.  A
    level-up therefore increases both maximum and current HP by the same delta,
    instead of leaving a formerly healthy familiar at its old maximum.
    """

    try:
        details = json.loads(record.details_json or "{}")
    except (TypeError, ValueError):
        details = {}
    if not isinstance(details, dict):
        details = {}
    maximum_hp = max(0, int(maximum_hp))
    previous = details.get("derived_maximum_hp")
    current = max(0, int(record.current_hp))
    if previous is None:
        if current == 0 and maximum_hp:
            current = maximum_hp
    else:
        previous = max(0, _integer(previous))
        if previous != maximum_hp:
            current = max(0, min(maximum_hp, current + maximum_hp - previous))
    current = min(current, maximum_hp) if maximum_hp else 0
    details["derived_maximum_hp"] = maximum_hp
    updated = replace(record, current_hp=current, details_json=json.dumps(details))
    return updated

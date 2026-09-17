"""Pure PF1e animal-companion catalog, grant, and progression rules."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping

from app.models import ClassLevel, MartialTalent, SkillState, SKILLS
from app.class_choice_rules import decode_class_choice_option_keys


@dataclass(frozen=True, slots=True)
class CompanionGrant:
    available: bool
    effective_level: int = 0
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CompanionProgression:
    level: int
    hit_dice: int
    bab: int
    fortitude: int
    reflex: int
    will: int
    skill_ranks: int
    feats: int
    natural_armor_bonus: int
    strength_dexterity_bonus: int
    bonus_tricks: int
    special: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CompanionAttack:
    name: str
    attack_bonus: int
    damage: str
    notes: str = "Natural attack"


@dataclass(frozen=True, slots=True)
class CompanionSkill:
    key: str
    name: str
    ability: str
    ranks: int
    total: int
    class_skill: bool


@dataclass(frozen=True, slots=True)
class CompanionSheetStatistics:
    progression: CompanionProgression
    creature_type: str
    description: str
    sex: str
    size: str
    size_modifier: int
    hit_die: str
    spell_resistance: str
    damage_reduction: str
    natural_armor: int
    speeds: Mapping[str, int]
    fly_maneuverability: str
    automatic_ability_scores: Mapping[str, int]
    ability_increase_allocations: Mapping[str, int]
    ability_scores: Mapping[str, int]
    ability_modifiers: Mapping[str, int]
    maximum_hp: int
    base_attack_bonus: int
    saves: Mapping[str, int]
    armor_class: int
    flat_footed_ac: int
    touch_ac: int
    cmb: int
    cmd: int
    attacks: tuple[CompanionAttack, ...]
    skills: tuple[CompanionSkill, ...]
    special_qualities: str
    ability_increases: int


_ROWS = (
    (2,1,3,3,0,2,1,0,0,1,("Link","Share Spells")),
    (3,2,3,3,1,3,2,0,0,1,()), (3,2,3,3,1,3,2,2,1,2,("Evasion",)),
    (4,3,4,4,1,4,2,2,1,2,("Ability Score Increase",)),
    (5,3,4,4,1,5,3,2,1,2,()), (6,4,5,5,2,6,3,4,2,3,("Devotion",)),
    (6,4,5,5,2,6,3,4,2,3,()), (7,5,5,5,2,7,4,4,2,3,()),
    (8,6,6,6,2,8,4,6,3,4,("Ability Score Increase","Multiattack")),
    (9,6,6,6,3,9,5,6,3,4,()), (9,6,6,6,3,9,5,6,3,4,()),
    (10,7,7,7,3,10,5,8,4,5,()), (11,8,7,7,3,11,6,8,4,5,()),
    (12,9,8,8,4,12,6,8,4,5,("Ability Score Increase",)),
    (12,9,8,8,4,12,6,10,5,6,("Improved Evasion",)),
    (13,9,8,8,4,13,7,10,5,6,()), (14,10,9,9,4,14,7,10,5,6,()),
    (15,11,9,9,5,15,8,12,6,7,()), (15,11,9,9,5,15,8,12,6,7,()),
    (16,12,10,10,5,16,8,12,6,7,("Ability Score Increase",)),
)


def companion_progression(level: int) -> CompanionProgression:
    level = max(1, min(20, int(level)))
    row = _ROWS[level - 1]
    persistent = tuple(
        ability
        for earlier in _ROWS[:level]
        for ability in earlier[-1]
        if ability != "Ability Score Increase"
    )
    return CompanionProgression(level, *row[:-1], persistent)


@lru_cache(maxsize=1)
def companion_catalog() -> tuple[dict, ...]:
    path = Path(__file__).resolve().parents[1] / "data" / "pf1e" / "animal_companions.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    return tuple(dict(item) for item in payload.get("entries", ()))


def companion_entry(key: str) -> dict | None:
    return next((item for item in companion_catalog() if item.get("key") == key), None)


_SIZE_AC = {
    "fine": 8, "diminutive": 4, "tiny": 2, "small": 1, "medium": 0,
    "large": -1, "huge": -2, "gargantuan": -4, "colossal": -8,
}
_SIZE_CMB = {key: -value for key, value in _SIZE_AC.items()}
_FLY_SIZE = {
    "fine": 8, "diminutive": 6, "tiny": 4, "small": 2, "medium": 0,
    "large": -2, "huge": -4, "gargantuan": -6, "colossal": -8,
}
_STEALTH_SIZE = {
    "fine": 16, "diminutive": 12, "tiny": 8, "small": 4, "medium": 0,
    "large": -4, "huge": -8, "gargantuan": -12, "colossal": -16,
}
_MANEUVERABILITY = {"clumsy": -8, "poor": -4, "average": 0, "good": 4, "perfect": 8}
_ANIMAL_SKILLS = (
    "acrobatics", "climb", "escape_artist", "fly", "intimidate",
    "perception", "stealth", "survival", "swim",
)
_ANIMAL_CLASS_SKILLS = {"acrobatics", "climb", "fly", "perception", "stealth", "swim"}
_ABILITY_SHORT = {
    "strength": "STR", "dexterity": "DEX", "constitution": "CON",
    "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA",
}
_ABILITY_KEYS = ("str", "dex", "con", "int", "wis", "cha")
_ABILITY_INCREASE_LEVELS = (4, 9, 14, 20)


def companion_ability_increase_count(level: int) -> int:
    """Return the published number of +1 companion ability increases earned."""

    level = max(1, min(20, int(level)))
    return sum(1 for threshold in _ABILITY_INCREASE_LEVELS if level >= threshold)


def companion_ability_increase_allocations(
    values: Mapping[str, object], available: int
) -> dict[str, int]:
    """Normalize saved ASI choices without allowing more points than earned.

    Saved choices are not destroyed when effective companion level temporarily
    drops.  Only the currently available prefix is applied, so raising the
    effective level again restores the player's prior selections.
    """

    remaining = max(0, int(available))
    result: dict[str, int] = {}
    for key in _ABILITY_KEYS:
        try:
            requested = max(0, int(values.get(key, 0) or 0))
        except (TypeError, ValueError):
            requested = 0
        applied = min(requested, remaining)
        if applied:
            result[key] = applied
            remaining -= applied
        if remaining <= 0:
            break
    return result


def calculate_companion_statistics(
    entry: Mapping[str, object] | None,
    progression: CompanionProgression,
    *,
    ability_overrides: Mapping[str, object] = {},
    ability_increases: Mapping[str, object] = {},
    skill_ranks: Mapping[str, object] = {},
    details: Mapping[str, object] = {},
    feats: Iterable[str] = (),
) -> CompanionSheetStatistics:
    """Build every play-facing statistic from a species and the PF1e table.

    Character JSON is deliberately accepted as overlays so the rules engine is
    independent of SQLite and the page can be redesigned without moving data.
    """

    entry = entry or {}
    advanced = progression.level >= int(entry.get("advancement_level") or 999)
    advancement = str(entry.get("advancement_text") or "") if advanced else ""
    size = str(_text_value(details.get("size_override")) or (
        _rule_field(advancement, "Size") if advanced else ""
    ) or entry.get("size") or "Medium").strip()
    size_key = size.casefold().split()[0]
    size_modifier = _SIZE_AC.get(size_key, 0)

    scores = {key: int(value) for key, value in dict(entry.get("abilities") or {}).items()}
    for key in ("str", "dex", "con", "int", "wis", "cha"):
        scores.setdefault(key, 10)
    if advanced:
        for key, value in _ability_values(_rule_field(advancement, "Ability Scores")).items():
            scores[key] = scores.get(key, 10) + value
    scores["str"] += progression.strength_dexterity_bonus
    scores["dex"] += progression.strength_dexterity_bonus
    automatic_scores = dict(scores)
    available_increases = companion_ability_increase_count(progression.level)
    applied_increases = companion_ability_increase_allocations(
        ability_increases, available_increases
    )
    for key, value in applied_increases.items():
        scores[key] += value
    for key, value in ability_overrides.items():
        if key in scores:
            try: scores[key] = int(value)
            except (TypeError, ValueError): pass
    modifiers = {key: (value - 10) // 2 for key, value in scores.items()}

    natural_armor = _signed_number(str(entry.get("natural_armor") or ""))
    if advanced:
        natural_armor += _signed_number(_rule_field(advancement, "AC"))
    natural_armor += progression.natural_armor_bonus + _int_value(details.get("natural_armor_misc"))

    speed_text = str(entry.get("speed") or "")
    speeds, maneuverability = _speeds(speed_text)
    if advanced:
        advancement_speed = _rule_field(advancement, "Speed")
        if advancement_speed:
            newer, newer_maneuverability = _speeds(advancement_speed)
            speeds.update(newer)
            maneuverability = newer_maneuverability or maneuverability
    for mode in ("land", "swim", "fly", "climb", "burrow"):
        override = details.get(f"{mode}_speed_override")
        if override not in (None, ""):
            speeds[mode] = max(0, _int_value(override))

    ac_misc = _int_value(details.get("ac_misc"))
    dexterity = modifiers["dex"]
    armor_class = 10 + dexterity + size_modifier + natural_armor + ac_misc
    flat_footed = (
        10 + size_modifier + natural_armor + ac_misc
        + _int_value(details.get("flat_footed_ac_misc"))
    )
    touch = (
        10 + dexterity + size_modifier + ac_misc
        + _int_value(details.get("touch_ac_misc"))
    )
    saves = {
        "fortitude": progression.fortitude + modifiers["con"] + _int_value(details.get("fortitude_misc")),
        "reflex": progression.reflex + modifiers["dex"] + _int_value(details.get("reflex_misc")),
        "will": progression.will + modifiers["wis"] + _int_value(details.get("will_misc")),
    }
    base_attack_bonus = progression.bab + _int_value(details.get("bab_misc"))
    cmb = base_attack_bonus + modifiers["str"] + _SIZE_CMB.get(size_key, 0) + _int_value(details.get("cmb_misc"))
    cmd = 10 + base_attack_bonus + modifiers["str"] + modifiers["dex"] + _SIZE_CMB.get(size_key, 0) + _int_value(details.get("cmd_misc"))
    maximum_hp = max(1, int(progression.hit_dice * 4.5) + progression.hit_dice * modifiers["con"] + _int_value(details.get("hp_misc")))

    attack_text = _rule_field(advancement, "Attack") if advanced else ""
    attack_text = attack_text or str(entry.get("attacks") or "")
    finesse = any(str(feat).casefold() == "weapon finesse" for feat in feats)
    attack_ability = max(modifiers["str"], modifiers["dex"]) if finesse else modifiers["str"]
    attack_bonus = base_attack_bonus + attack_ability + size_modifier + _int_value(details.get("attack_misc"))
    attack_profiles = _attack_profiles(attack_text)
    damage_modifier = modifiers["str"]
    if len(attack_profiles) == 1 and damage_modifier > 0:
        damage_modifier += damage_modifier // 2
    attack_note = "Primary natural · 20/x2"
    if finesse and modifiers["dex"] > modifiers["str"]:
        attack_note += " · DEX attack (Weapon Finesse)"
    attacks = tuple(
        CompanionAttack(
            name,
            attack_bonus,
            _damage_with_modifier(damage, damage_modifier),
            attack_note,
        )
        for name, damage in attack_profiles
    )

    definitions = {item.key: item for item in SKILLS}
    normalized_ranks = _normalized_skill_ranks(skill_ranks)
    skill_rows: list[CompanionSkill] = []
    for key in _ANIMAL_SKILLS:
        definition = definitions[key]
        ranks = normalized_ranks.get(key, 0)
        class_skill = key in _ANIMAL_CLASS_SKILLS
        total = ranks + modifiers[definition.ability[:3]]
        if ranks and class_skill:
            total += 3
        if key == "stealth":
            total += _STEALTH_SIZE.get(size_key, 0)
        elif key == "fly":
            total += _FLY_SIZE.get(size_key, 0) + _MANEUVERABILITY.get(maneuverability.casefold(), 0)
        elif key == "climb" and speeds.get("climb", 0):
            total += 8
        elif key == "swim" and speeds.get("swim", 0):
            total += 8
        skill_rows.append(CompanionSkill(
            key, definition.name, _ABILITY_SHORT[definition.ability], ranks, total, class_skill
        ))

    starting_text = str(entry.get("starting_text") or "")
    special_qualities = "; ".join(dict.fromkeys(value for value in (
        _rule_field(starting_text, "Special Qualities"),
        _rule_field(starting_text, "Special Attacks"),
        str(entry.get("special_qualities") or ""),
    ) if value))
    if advanced:
        added = _rule_field(advancement, "Special Qualities") or _rule_field(advancement, "Special Attacks")
        if added:
            special_qualities = "; ".join(value for value in (special_qualities, added) if value)
    return CompanionSheetStatistics(
        progression=progression,
        creature_type=str(details.get("creature_type") or "Animal"),
        description=str(details.get("description") or ""),
        sex=str(details.get("sex") or ""),
        size=size,
        size_modifier=size_modifier,
        hit_die="d8",
        spell_resistance=str(details.get("spell_resistance") or "—"),
        damage_reduction=str(details.get("damage_reduction") or "—"),
        natural_armor=natural_armor,
        speeds=speeds,
        fly_maneuverability=maneuverability,
        automatic_ability_scores=automatic_scores,
        ability_increase_allocations=applied_increases,
        ability_scores=scores,
        ability_modifiers=modifiers,
        maximum_hp=maximum_hp,
        base_attack_bonus=base_attack_bonus,
        saves=saves,
        armor_class=armor_class,
        flat_footed_ac=flat_footed,
        touch_ac=touch,
        cmb=cmb,
        cmd=cmd,
        attacks=attacks,
        skills=tuple(skill_rows),
        special_qualities=special_qualities,
        ability_increases=available_increases,
    )


def _rule_field(text: str, label: str) -> str:
    if not text:
        return ""
    labels = r"Size|Speed|AC|Attack|Ability Scores|Special Qualities|Special Attacks|SQ"
    match = re.search(
        rf"(?:^|;\s*){re.escape(label)}\s+(.+?)(?=;\s*(?:{labels})\b|\.?$)",
        text, re.I,
    )
    return match.group(1).strip(" ;.") if match else ""


def _ability_values(text: str) -> dict[str, int]:
    return {
        key.casefold(): int(value.replace("−", "-"))
        for key, value in re.findall(r"\b(Str|Dex|Con|Int|Wis|Cha)\s*([+−-]?\d+)", text, re.I)
    }


def _signed_number(text: str) -> int:
    match = re.search(r"[+−-]?\d+", text)
    return int(match.group().replace("−", "-")) if match else 0


def _int_value(value: object) -> int:
    try: return int(value or 0)
    except (TypeError, ValueError): return 0


def _text_value(value: object) -> str:
    return "" if value is None else str(value).strip()


def _speeds(text: str) -> tuple[dict[str, int], str]:
    speeds = {mode: 0 for mode in ("land", "swim", "fly", "climb", "burrow")}
    maneuverability = ""
    for mode in ("swim", "fly", "climb", "burrow"):
        match = re.search(rf"\b{mode}\s+(\d+)\s*ft\.?(?:\s*\(([^)]+)\))?", text, re.I)
        if match:
            speeds[mode] = int(match.group(1))
            if mode == "fly" and match.group(2): maneuverability = match.group(2).strip().title()
    leading = re.match(r"\s*(\d+)\s*ft", text, re.I)
    if leading: speeds["land"] = int(leading.group(1))
    return speeds, maneuverability


def _attack_profiles(text: str) -> tuple[tuple[str, str], ...]:
    if not text:
        return ()
    parts = re.split(r",\s*(?![^()]*\))", text)
    result = []
    for part in parts:
        match = re.match(r"\s*(.*?)\s*\((.+)\)\s*$", part)
        result.append((match.group(1).strip(), match.group(2).strip()) if match else (part.strip(), "—"))
    return tuple(result)


def _damage_with_modifier(profile: str, modifier: int) -> str:
    """Insert a Strength modifier without losing grab, poison, or other riders."""

    if not modifier:
        return profile
    match = re.match(r"\s*(\d+d\d+)(.*)$", profile, re.I)
    if not match:
        return profile
    sign = "+" if modifier > 0 else ""
    return f"{match.group(1)}{sign}{modifier}{match.group(2)}"


def _normalized_skill_ranks(values: Mapping[str, object]) -> dict[str, int]:
    aliases = {item.name.casefold(): item.key for item in SKILLS}
    result = {}
    for raw_key, value in values.items():
        key = str(raw_key).casefold()
        key = aliases.get(key, key.replace(" ", "_"))
        if key in _ANIMAL_SKILLS:
            result[key] = max(0, _int_value(value))
    return result


def resolve_companion_grant(
    classes: Iterable[ClassLevel],
    resolved_features_by_class: Mapping[int, Iterable[object]],
    talents: Iterable[MartialTalent],
    skills: Mapping[str, SkillState],
    feature_selections: Iterable[object] = (),
) -> CompanionGrant:
    """Resolve the strongest eligible companion source without depending on Qt."""

    sources: list[str] = []
    levels: list[int] = []
    companion_feature_names = {
        "animal companion",
        "animal companion (hun)",
        "mount",
        "mount (cav)",
        "mount (sam)",
        "craft mount",
        "flying beast tamer",
        "exotic mount",
        "hunting pack",
        "dinosaur mount",
        "dragon companion",
    }
    for class_level in classes:
        for feature in resolved_features_by_class.get(class_level.id, ()):
            name = str(getattr(feature, "name", "")).casefold()
            description = str(getattr(feature, "description", "")).casefold()
            if name.startswith("raise animal companion"):
                continue
            if name in companion_feature_names or (
                "animal companion" in name and "forms a bond" in description
            ):
                levels.append(class_level.level)
                sources.append(
                    f"{class_level.class_name}: "
                    f"{getattr(feature, 'name', 'Animal Companion')}"
                )
    for selection in feature_selections:
        owner = next(
            (row for row in classes if row.id == getattr(selection, "class_level_id", -1)),
            None,
        )
        if owner is None:
            continue
        selected_keys = decode_class_choice_option_keys(
            str(getattr(selection, "option_key", ""))
        )
        fixed_progressions = {
            "class-choice-fixed:nature-bond:animal-companion": (
                owner.level,
                "Nature Bond: Animal Companion",
            ),
            "class-choice-fixed:hunters-bond:animal-companion": (
                max(1, owner.level - 3),
                "Hunter's Bond: Animal Companion",
            ),
            "class-choice-fixed:divine-bond:mount": (
                owner.level,
                "Divine Bond: Mount",
            ),
        }
        for key, (effective_level, label) in fixed_progressions.items():
            if key in selected_keys:
                levels.append(effective_level)
                sources.append(f"{owner.class_name}: {label}")
        animal_domain = any(
            key.endswith(":animal-domain") for key in selected_keys
        ) or (
            "animal" in str(getattr(selection, "name", "")).casefold()
            and "domain" in str(getattr(selection, "option_type", "")).casefold()
        )
        if animal_domain:
            levels.append(max(1, owner.level - 3))
            sources.append(f"{owner.class_name}: Animal Domain")

    beastmastery = [
        item for item in talents
        if item.enabled and item.name.casefold() == "animal companion"
        and item.sphere.casefold() == "beastmastery"
    ]
    base_companion_level = max(levels, default=0)
    if beastmastery:
        ranks = max(
            int(getattr(skills.get("handle_animal"), "ranks", 0)),
            int(getattr(skills.get("ride"), "ranks", 0)),
        )
        bab = sum(_bab_for(row) for row in classes)
        sphere_level = max(
            1,
            max(bab, ranks)
            - (0 if len(beastmastery) > 1 or base_companion_level else 3),
        )
        # The talent explicitly stacks its effective druid level with an
        # existing companion source, but never above total character level.
        levels.append(
            base_companion_level + sphere_level
            if base_companion_level
            else sphere_level
        )
        sources.append("Beastmastery: Animal Companion")
    character_level = sum(row.level for row in classes)
    return CompanionGrant(bool(levels), min(character_level or 20, max(levels, default=0)), tuple(sources))


def _bab_for(row: ClassLevel) -> int:
    if row.bab_progression == "Full":
        return row.level
    if row.bab_progression == "3/4":
        return (row.level * 3) // 4
    return row.level // 2

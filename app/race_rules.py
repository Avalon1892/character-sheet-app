"""Pure, catalog-driven Pathfinder race resolution.

Race data, saved character choices, calculation automation, and Qt presentation
meet at this small boundary.  New races and alternate traits therefore require
catalog data rather than new widget or calculation branches.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterator

from app.content import entry_by_key
from app.models import ABILITY_KEYS, Attack, CharacterDetails, RaceTraitChoice, StatModifier


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


@dataclass(frozen=True, slots=True)
class ResolvedRace:
    entry: dict | None
    variant: dict | None
    active_traits: tuple[dict, ...]
    alternate_traits: tuple[dict, ...]
    adjustments: dict[str, int]
    flexible_bonus: int
    size: str
    base_speed: int


@dataclass(frozen=True, slots=True)
class RacialSense:
    key: str
    name: str
    range: int = 0
    sources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RacialResistance:
    energy_type: str
    value: int
    sources: tuple[str, ...] = ()


def race_entry(key: str) -> dict | None:
    return entry_by_key("races", key) if key else None


def race_variant(entry: dict | None, key: str) -> dict | None:
    if entry is None or not key:
        return None
    return next(
        (variant for variant in entry.get("variants", ()) if variant.get("key") == key),
        None,
    )


def alternate_trait_conflicts(entry: dict, selected_keys: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    """Return selected alternates which attempt to replace the same base trait."""

    selected = [
        trait for trait in entry.get("alternate_racial_traits", ())
        if str(trait.get("key")) in selected_keys
    ]
    by_replacement: dict[str, list[str]] = {}
    for trait in selected:
        for replacement in trait.get("replaces", ()):
            normalized = _key(replacement)
            if normalized and normalized != "nothing":
                by_replacement.setdefault(normalized, []).append(str(trait["key"]))
    return {
        replacement: tuple(keys)
        for replacement, keys in by_replacement.items()
        if len(keys) > 1
    }


def race_trait_choice_map(details: CharacterDetails) -> dict[tuple[str, str], tuple[str, ...]]:
    """Return persisted racial answers indexed by trait and catalog choice key."""

    return {
        (choice.trait_key, choice.choice_key): tuple(dict.fromkeys(choice.values))
        for choice in details.race_trait_choices
        if choice.trait_key and choice.choice_key
    }


def selected_alternate_traits(entry: dict, selected_keys: tuple[str, ...]) -> tuple[dict, ...]:
    selected = set(selected_keys)
    return tuple(
        trait for trait in entry.get("alternate_racial_traits", ())
        if str(trait.get("key")) in selected
    )


def _resolved_automation_sources(details: CharacterDetails) -> Iterator[tuple[str, dict]]:
    """Yield active trait and selected-option automation without UI knowledge."""

    profile = resolved_race(details)
    if profile.entry is None:
        return
    valid_choices = not validate_race_trait_choices(
        profile.entry, details.race_alternate_trait_keys, details.race_trait_choices
    )
    choice_map = race_trait_choice_map(details) if valid_choices else {}
    for trait in (*profile.active_traits, *profile.alternate_traits):
        source = str(trait.get("name") or "Racial trait")
        automation = dict(trait.get("automation") or {})
        if automation:
            yield source, automation
        if not valid_choices:
            continue
        for spec in trait.get("choice_specs", ()):
            selected = choice_map.get(
                (str(trait.get("key") or ""), str(spec.get("key") or "")), ()
            )
            options = {
                str(option.get("key") or ""): option
                for option in spec.get("options", ())
            }
            for value in selected:
                option = options.get(value)
                if not option:
                    continue
                option_automation = dict(option.get("automation") or {})
                if option_automation:
                    label = str(option.get("label") or value)
                    yield f"{source} — {label}", option_automation


def racial_choice_specs(entry: dict, selected_keys: tuple[str, ...]) -> tuple[tuple[dict, dict], ...]:
    """Catalog-driven choice specifications for the selected racial traits."""

    return tuple(
        (trait, spec)
        for trait in selected_alternate_traits(entry, selected_keys)
        for spec in trait.get("choice_specs", ())
    )


def validate_race_trait_choices(
    entry: dict,
    selected_keys: tuple[str, ...],
    choices: tuple[RaceTraitChoice, ...],
) -> tuple[str, ...]:
    """Validate required answers without depending on presentation widgets."""

    values_by_key = {
        (choice.trait_key, choice.choice_key): tuple(choice.values)
        for choice in choices
    }
    errors: list[str] = []
    for trait, spec in racial_choice_specs(entry, selected_keys):
        key = (str(trait.get("key") or ""), str(spec.get("key") or ""))
        values = tuple(value for value in values_by_key.get(key, ()) if value)
        minimum = int(spec.get("minimum", spec.get("count", 1)) or 0)
        maximum = int(spec.get("maximum", spec.get("count", minimum)) or minimum)
        allowed = {
            str(option.get("key") or "")
            for option in spec.get("options", ())
            if option.get("key")
        }
        label = f"{trait.get('name', 'Racial trait')}: {spec.get('label', 'choice')}"
        if len(values) < minimum or len(values) > maximum:
            errors.append(f"{label} requires {minimum if minimum == maximum else f'{minimum}–{maximum}'} selection(s).")
        if spec.get("distinct", False) and len(set(values)) != len(values):
            errors.append(f"{label} cannot use the same selection twice.")
        if allowed and any(value not in allowed for value in values):
            errors.append(f"{label} contains an unavailable selection.")
    return tuple(errors)


def resolved_race(details: CharacterDetails) -> ResolvedRace:
    entry = race_entry(details.race_key)
    if entry is None:
        return ResolvedRace(None, None, (), (), {}, 0, details.size or "Medium", 30)
    variant = race_variant(entry, details.race_variant_key)
    selected_keys = set(details.race_alternate_trait_keys)
    alternates = tuple(
        trait for trait in entry.get("alternate_racial_traits", ())
        if str(trait.get("key")) in selected_keys
    )
    replaced = {
        _key(name)
        for trait in alternates
        for name in trait.get("replaces", ())
        if _key(name) != "nothing"
    }
    def is_replaced(trait: dict) -> bool:
        trait_key = _key(trait.get("name"))
        if any(
            trait_key == replacement
            or trait_key.endswith(replacement)
            or replacement.endswith(trait_key)
            for replacement in replaced
        ):
            return True
        if (variant or {}).get("alternate_skill_modifiers") and trait_key == "skilled":
            return True
        return False

    active = tuple(
        trait for trait in entry.get("racial_traits", ()) if not is_replaced(trait)
    )
    adjustments = dict(
        (variant or {}).get("adjustments") or entry.get("adjustments") or {}
    )
    flexible = int(
        (variant or {}).get("flexible_bonus") or entry.get("flexible_bonus") or 0
    )
    if flexible and any(
        is_replaced(trait)
        and re.search(r"bonus to one ability score|one ability score of their choice", str(trait.get("description") or ""), re.I)
        for trait in entry.get("racial_traits", ())
    ):
        flexible = 0
    return ResolvedRace(
        entry=entry,
        variant=variant,
        active_traits=active,
        alternate_traits=alternates,
        adjustments=adjustments,
        flexible_bonus=flexible,
        size=str((variant or {}).get("size") or entry.get("size") or details.size or "Medium"),
        base_speed=int((variant or {}).get("base_speed") or entry.get("base_speed") or 30),
    )


def race_modifier_map(details: CharacterDetails) -> dict[str, list[StatModifier]]:
    profile = resolved_race(details)
    if profile.entry is None:
        return {}
    result: dict[str, list[StatModifier]] = {}
    adjustments = dict(profile.adjustments)
    automation_sources = tuple(_resolved_automation_sources(details))
    increase_sources: dict[str, list[str]] = {}
    for source, automation in automation_sources:
        for ability, value in automation.get("ability_increases", {}).items():
            if ability in ABILITY_KEYS:
                adjustments[ability] = adjustments.get(ability, 0) + int(value)
                increase_sources.setdefault(ability, []).append(source)
    if profile.flexible_bonus and details.race_ability_choice in ABILITY_KEYS:
        adjustments[details.race_ability_choice] = (
            adjustments.get(details.race_ability_choice, 0) + profile.flexible_bonus
        )
    race_name = str(profile.entry["name"])
    variant_suffix = f" — {profile.variant['name']}" if profile.variant else ""
    for target, value in adjustments.items():
        result.setdefault(target, []).append(StatModifier(
            None, target, f"Race: {race_name}{variant_suffix}" + (
                " + " + "; ".join(increase_sources[target]) if target in increase_sources else ""
            ), "racial", int(value), True
        ))
    movement_speeds = dict(profile.entry.get("movement_speeds") or {})
    movement_speeds.update((profile.variant or {}).get("movement_speeds") or {})
    for target, value in movement_speeds.items():
        result.setdefault(str(target), []).append(StatModifier(
            None, str(target), f"Race: {race_name}{variant_suffix}", "racial", int(value), True
        ))
    choice_map = race_trait_choice_map(details)
    if validate_race_trait_choices(
        profile.entry, details.race_alternate_trait_keys, details.race_trait_choices
    ):
        # Never apply a partially configured choice-driven trait. The chooser
        # keeps new saves valid; this protects imported or manually edited data.
        choice_map = {}
    for source, automation in automation_sources:
        for modifier in automation.get("modifiers", ()):
            target = str(modifier.get("target") or "")
            if not target:
                continue
            result.setdefault(target, []).append(StatModifier(
                None,
                target,
                f"Race: {race_name} — {source}",
                str(modifier.get("bonus_type") or "racial"),
                int(modifier.get("value") or 0),
                True,
            ))
    for trait in (*profile.active_traits, *profile.alternate_traits):
        for effect in (trait.get("automation") or {}).get("choice_effects", ()):
            choice_key = str(effect.get("choice_key") or "")
            values = choice_map.get((str(trait.get("key") or ""), choice_key), ())
            for selected_value in values:
                target = selected_value if effect.get("target") == "$choice" else str(effect.get("target") or "")
                if not target:
                    continue
                result.setdefault(target, []).append(StatModifier(
                    None,
                    target,
                    f"Race: {race_name} — {trait.get('name', 'Racial trait')}",
                    str(effect.get("bonus_type") or "racial"),
                    int(effect.get("value") or 0),
                    True,
                ))
    # Several outsider bloodlines explicitly replace their normal two skill
    # bonuses.  AoN exposes those choices as structured subrace fields.
    alternate_skills = str((profile.variant or {}).get("alternate_skill_modifiers") or "")
    if alternate_skills:
        skill_names = re.split(r"\s*,\s*|\s+and\s+", alternate_skills)
        known = {
            "acrobatics": "acrobatics", "bluff": "bluff", "climb": "climb",
            "diplomacy": "diplomacy", "disguise": "disguise", "fly": "fly",
            "handle animal": "handle_animal", "heal": "heal", "intimidate": "intimidate",
            "perception": "perception", "ride": "ride", "sense motive": "sense_motive",
            "spellcraft": "spellcraft", "stealth": "stealth", "survival": "survival",
            "swim": "swim", "use magic device": "use_magic_device",
            "knowledge (planes)": "knowledge_planes",
        }
        for name in skill_names:
            skill = known.get(name.strip().casefold())
            if skill:
                result.setdefault(f"skill:{skill}", []).append(StatModifier(
                    None, f"skill:{skill}", f"Race: {race_name} — {profile.variant['name']}",
                    "racial", 2, True,
                ))
    return result


def racial_class_skills(details: CharacterDetails) -> set[str]:
    """Class skills granted by retained traits and selected racial options."""

    result: set[str] = set()
    for _source, automation in _resolved_automation_sources(details):
        result.update(
            str(value) for value in automation.get("class_skills", ()) if str(value)
        )
    return result


def racial_senses(details: CharacterDetails) -> tuple[RacialSense, ...]:
    """Resolve senses after alternate-trait replacement and option choices."""

    merged: dict[str, tuple[str, int, list[str]]] = {}
    for source, automation in _resolved_automation_sources(details):
        for sense in automation.get("senses", ()):
            key = str(sense.get("key") or "")
            if not key:
                continue
            name = str(sense.get("name") or key.replace("_", " ").title())
            distance = max(0, int(sense.get("range") or 0))
            current = merged.setdefault(key, (name, 0, []))
            current[2].append(source)
            merged[key] = (current[0], max(current[1], distance), current[2])
    return tuple(
        RacialSense(key, name, distance, tuple(dict.fromkeys(sources)))
        for key, (name, distance, sources) in sorted(merged.items())
    )


def racial_resistances(details: CharacterDetails) -> tuple[RacialResistance, ...]:
    """Resolve deterministic energy resistance, keeping the strongest value."""

    merged: dict[str, tuple[int, list[str]]] = {}
    for source, automation in _resolved_automation_sources(details):
        for resistance in automation.get("resistances", ()):
            energy = str(resistance.get("type") or "").casefold()
            if not energy:
                continue
            value = max(0, int(resistance.get("value") or 0))
            current = merged.setdefault(energy, (0, []))
            current[1].append(source)
            merged[energy] = (max(current[0], value), current[1])
    return tuple(
        RacialResistance(energy, value, tuple(dict.fromkeys(sources)))
        for energy, (value, sources) in sorted(merged.items())
    )


def racial_identity_tags(details: CharacterDetails) -> set[str]:
    """Additional races/types selected by heritage-style racial traits."""

    result = {details.race_key} if details.race_key else set()
    for _source, automation in _resolved_automation_sources(details):
        result.update(
            str(value).casefold() for value in automation.get("identity_tags", ()) if str(value)
        )
    return result


def racial_conditional_effects(details: CharacterDetails) -> tuple[dict, ...]:
    """Return situational racial rules without applying them to baseline totals."""

    result: list[dict] = []
    for source, automation in _resolved_automation_sources(details):
        for effect in automation.get("conditional_modifiers", ()):
            result.append({**effect, "source": source})
    return tuple(result)


def generated_racial_attacks(details: CharacterDetails) -> tuple[Attack, ...]:
    """Derived natural attacks granted by the currently resolved racial traits."""

    definitions: list[tuple[str, dict]] = []
    for source, automation in _resolved_automation_sources(details):
        definitions.extend(
            (source, dict(attack)) for attack in automation.get("natural_attacks", ())
        )
    result: list[Attack] = []
    index = 0
    for source, definition in definitions:
        count = max(1, int(definition.get("count") or 1))
        primary = bool(definition.get("primary", True))
        for number in range(1, count + 1):
            index += 1
            base_name = str(definition.get("name") or "Natural Attack")
            name = f"{base_name} {number}" if count > 1 else base_name
            condition = str(definition.get("condition") or "")
            notes = [
                f"Racial natural attack from {source}.",
                "Primary natural attack." if primary else "Secondary natural attack.",
                f"Damage type: {definition.get('damage_types') or 'physical'}.",
            ]
            if condition:
                notes.append(condition)
            result.append(Attack(
                id=-(2_000_000 + index),
                name=name,
                attack_type="Melee",
                ability="strength",
                attack_bonus=0,
                damage_dice=str(definition.get("damage") or "1d3"),
                damage_ability="strength",
                damage_multiplier=1.0 if primary else 0.5,
                damage_bonus=0,
                critical="20/x2",
                notes="\n".join(notes),
                equipment_id=None,
                profile_key=(
                    f"race:{details.race_key}:{_key(source).replace(' ', '_')}:"
                    f"{definition.get('key') or _key(base_name).replace(' ', '_')}:{number}"
                ),
                damage_ability_mode="automatic",
            ))
    return tuple(result)


def resolved_racial_traits(details: CharacterDetails) -> tuple[dict, ...]:
    profile = resolved_race(details)
    entries = list(profile.active_traits)
    if profile.variant:
        entries.insert(0, {
            "key": str(profile.variant.get("key") or ""),
            "name": str(profile.variant.get("name") or "Subrace"),
            "description": str(profile.variant.get("description") or ""),
        })
    choices = race_trait_choice_map(details)
    for trait in profile.alternate_traits:
        summaries: list[str] = []
        selected_option_descriptions: list[str] = []
        for spec in trait.get("choice_specs", ()):
            selected = choices.get(
                (str(trait.get("key") or ""), str(spec.get("key") or "")), ()
            )
            labels = {
                str(option.get("key") or ""): str(option.get("label") or option.get("key") or "")
                for option in spec.get("options", ())
            }
            if selected:
                summaries.append(
                    f"{spec.get('label', 'Choice')}: "
                    + ", ".join(labels.get(value, value) for value in selected)
                )
                option_map = {
                    str(option.get("key") or ""): option
                    for option in spec.get("options", ())
                }
                selected_option_descriptions.extend(
                    str(option_map[value].get("description") or "")
                    for value in selected
                    if value in option_map and option_map[value].get("description")
                )
        if summaries:
            description = str(trait.get("description") or "").rstrip()
            if any(
                str(spec.get("key") or "") == "variant_abilities"
                for spec in trait.get("choice_specs", ())
            ) and selected_option_descriptions:
                description = "Selected variant racial ability: " + "\n".join(selected_option_descriptions)
            trait = {
                **trait,
                "description": (
                    description
                    + "\nSelected: " + "; ".join(summaries) + "."
                ),
                "choice_summary": "; ".join(summaries),
            }
        entries.append(trait)
    return tuple(entries)


def racial_advancement_effects(details: CharacterDetails) -> dict[str, int]:
    """Aggregate advancement grants from the currently retained racial traits."""

    result: dict[str, int] = {}
    for _source, automation in _resolved_automation_sources(details):
        for effect in automation.get("advancement", ()):
            target = str(effect.get("target") or "")
            if target:
                result[target] = result.get(target, 0) + int(effect.get("value") or 0)
    return result

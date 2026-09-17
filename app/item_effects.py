from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from app.models import EquipmentItem, SKILLS, StatModifier


ITEM_STATES = ("stored", "carried", "worn", "wielded", "armor", "shield")
AUTOMATION_STATUSES = ("full", "partial", "choice", "rules_only", "unsupported")


@dataclass(frozen=True, slots=True)
class ItemChoiceSpec:
    key: str
    label: str
    options: tuple[tuple[str, str], ...]
    required: bool = True
    distinct_group: str = ""


@dataclass(frozen=True, slots=True)
class ItemEffectSpec:
    key: str
    target: str
    operation: str
    value: int = 0
    bonus_type: str = "untyped"
    activation: str = "carried"
    choice_group: str = ""
    component: str = ""
    label: str = ""
    description: str = ""
    confidence: str = "reviewed"
    notes: str = ""


@dataclass(frozen=True, slots=True)
class ItemAutomation:
    status: str = "rules_only"
    effects: tuple[ItemEffectSpec, ...] = ()
    choices: tuple[ItemChoiceSpec, ...] = ()
    rules_only: tuple[str, ...] = ()
    provider: str = "catalog-default"


def _bonus(name: str) -> int:
    match = re.search(r"\+(\d+)\b", name)
    return int(match.group(1)) if match else 0


def _effects(targets: tuple[str, ...], value: int, bonus_type: str, activation: str, family: str) -> tuple[ItemEffectSpec, ...]:
    return tuple(
        ItemEffectSpec(
            f"{family}:{target}", target, "add", value, bonus_type, activation,
            label=f"{target.replace('_', ' ').title()} {value:+d} {bonus_type}",
            description=f"Reviewed constant {bonus_type} bonus from the {family.replace('_', ' ')} family.",
        )
        for target in targets
    )


def automation_for_entry(entry: dict) -> ItemAutomation:
    """Return reviewed structured automation; never interprets prose."""
    name = str(entry.get("name") or "")
    folded = name.casefold()
    value = _bonus(name)
    single_abilities = {
        "belt of giant strength": "strength",
        "belt of incredible dexterity": "dexterity",
        "belt of mighty constitution": "constitution",
        "headband of vast intelligence": "intelligence",
        "headband of inspired wisdom": "wisdom",
        "headband of alluring charisma": "charisma",
    }
    for prefix, target in single_abilities.items():
        if folded.startswith(prefix) and value:
            choices: tuple[ItemChoiceSpec, ...] = ()
            rules_only: tuple[str, ...] = ()
            status = "full"
            if prefix == "headband of vast intelligence":
                choices = (ItemChoiceSpec("trained_skill", "Granted skill", tuple((skill.key, skill.name) for skill in SKILLS)),)
                rules_only = ("Granted skill ranks remain rules-only until rank grants are supported.",)
                status = "choice"
            return ItemAutomation(status, _effects((target,), value, "enhancement", "worn", prefix.replace(" ", "_")), choices, rules_only, "ability-item-family")
    if folded.startswith("belt of physical perfection") and value:
        return ItemAutomation("full", _effects(("strength", "dexterity", "constitution"), value, "enhancement", "worn", "physical_perfection"), provider="ability-item-family")
    if folded.startswith("headband of mental superiority") and value:
        return ItemAutomation("full", _effects(("intelligence", "wisdom", "charisma"), value, "enhancement", "worn", "mental_superiority"), provider="ability-item-family")
    pair_tokens = {"str": "strength", "dex": "dexterity", "con": "constitution", "int": "intelligence", "wis": "wisdom", "cha": "charisma"}
    if (folded.startswith("belt of physical might") or folded.startswith("headband of mental prowess")) and value:
        selected = tuple(target for token, target in pair_tokens.items() if re.search(rf"\b{token}\b", folded))
        if len(selected) == 2:
            return ItemAutomation("full", _effects(selected, value, "enhancement", "worn", "paired_ability_item"), provider="ability-item-family")
    if folded.startswith("cloak of resistance") and value:
        return ItemAutomation("full", _effects(("fortitude", "reflex", "will"), value, "resistance", "worn", "cloak_resistance"), provider="defense-item-family")
    if folded.startswith("ring of protection") and value:
        return ItemAutomation("full", _effects(("ac",), value, "deflection", "worn", "ring_protection"), provider="defense-item-family")
    if folded.startswith("amulet of natural armor") and value:
        return ItemAutomation("full", _effects(("ac",), value, "natural armor enhancement", "worn", "amulet_natural_armor"), provider="defense-item-family")
    if folded.startswith("bracers of armor") and value:
        return ItemAutomation("full", _effects(("ac",), value, "armor", "worn", "bracers_armor"), provider="defense-item-family")
    if folded in {"stone of good luck", "luckstone"}:
        return ItemAutomation(
            "partial",
            _effects(("fortitude", "reflex", "will", "skills"), 1, "luck", "carried", "luckstone"),
            rules_only=("The +1 luck bonus on ability checks is not yet represented.",),
            provider="reviewed-item-override",
        )
    if folded == "lucky horseshoe":
        return ItemAutomation(
            "partial",
            _effects(("fortitude", "reflex", "will"), 1, "luck", "carried", "lucky_horseshoe"),
            rules_only=("The once-per-day +4 saving-throw option remains rules-only.",),
            provider="reviewed-item-override",
        )
    if folded == "boots of striding":
        return ItemAutomation("full", _effects(("land_speed",), 10, "enhancement", "worn", "boots_striding"), provider="movement-item-family")
    skill_items = {
        "boots of elvenkind": ("acrobatics", 5),
        "cloak of elvenkind": ("stealth", 5),
        "ring of swimming": ("swim", 5),
        "ring of swimming (improved)": ("swim", 10),
    }
    if folded in skill_items:
        skill, skill_bonus = skill_items[folded]
        return ItemAutomation("full", _effects((f"skill:{skill}",), skill_bonus, "competence", "worn", folded.replace(" ", "_")), provider="skill-item-family")
    if folded == "gloves of elvenkind":
        return ItemAutomation(
            "partial",
            _effects(("skill:spellcraft",), 5, "competence", "worn", "gloves_elvenkind"),
            rules_only=("The situational concentration bonus for casting defensively remains rules-only.",),
            provider="reviewed-item-override",
        )
    if folded == "dusty rose prism ioun stone":
        return ItemAutomation(
            "partial", _effects(("ac",), 1, "insight", "carried", "dusty_rose_prism"),
            rules_only=("The resonance bonus on combat maneuver checks remains rules-only.",),
            provider="reviewed-item-override",
        )
    if folded == "talisman of spell resistance":
        return ItemAutomation(
            "partial",
            (ItemEffectSpec("spell_resistance_15", "spell_resistance", "set", 15, "untyped", "worn", label="Spell resistance 15"),),
            rules_only=("The command-word light effects remain rules-only.",),
            provider="reviewed-item-override",
        )

    legacy = entry.get("automation") or {}
    ac_bonus = int(legacy.get("ac_bonus") or 0)
    item_type = str(entry.get("item_type") or "").casefold()
    category = str(entry.get("category") or "").casefold()
    if item_type == "equipment" and ac_bonus and ("armor" in category or "shield" in category):
        component = "shield" if "shield" in category else "armor"
        return ItemAutomation(
            "full",
            (
                ItemEffectSpec(
                    f"base_{component}_bonus", "ac", "component", ac_bonus,
                    component, component, component=component,
                    label=f"Base {component} bonus +{ac_bonus}",
                    description=f"The equipped item contributes its base {component} bonus.",
                ),
            ),
            provider="armor-component-family",
        )
    if item_type in {"weapon", "ammo"}:
        weapon = entry.get("weapon") or {}
        effects = []
        if weapon.get("damage_dice"):
            effects.append(ItemEffectSpec("weapon_damage", "damage_dice", "grant_dice", activation="wielded", component="weapon", label=f"Damage {weapon['damage_dice']}"))
        if weapon.get("critical"):
            effects.append(ItemEffectSpec("weapon_critical", "critical", "set", activation="wielded", component="weapon", label=f"Critical {weapon['critical']}"))
        return ItemAutomation(
            "partial",
            tuple(effects),
            rules_only=(
                "Only the reviewed static weapon profile is automated; special, conditional, activated, ammunition, and target-dependent rules remain rules-only."
                if effects else "Weapon statistics are incomplete in the catalog."
            ,),
            provider="weapon-component-family",
        )
    return ItemAutomation("rules_only", rules_only=("No reviewed stage 1–3 effect is registered.",))


def automation_dict(automation: ItemAutomation) -> dict:
    return asdict(automation)


def automation_json(automation: ItemAutomation) -> str:
    return json.dumps(automation_dict(automation), separators=(",", ":"))


def automation_from_json(value: str) -> ItemAutomation:
    if not value:
        return ItemAutomation()
    try:
        data = json.loads(value)
        return ItemAutomation(
            str(data.get("status") or "rules_only"),
            tuple(ItemEffectSpec(**effect) for effect in data.get("effects", ())),
            tuple(ItemChoiceSpec(
                choice["key"], choice["label"],
                tuple(tuple(option) for option in choice.get("options", ())),
                bool(choice.get("required", True)), str(choice.get("distinct_group") or ""),
            ) for choice in data.get("choices", ())),
            tuple(data.get("rules_only", ())),
            str(data.get("provider") or "saved"),
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return ItemAutomation("unsupported", rules_only=("Saved automation metadata is invalid.",))


def automation_for_item(item: EquipmentItem) -> ItemAutomation:
    """Resolve saved metadata, with a non-mutating fallback for pre-automation records."""
    if item.automation_json:
        return automation_from_json(item.automation_json)
    if not item.catalog_key:
        return ItemAutomation("rules_only", rules_only=("Custom item; no catalog automation is attached.",))
    item_type = (
        "weapon" if item.category == "Weapon" else "equipment"
    )
    return automation_for_entry(
        {
            "key": item.catalog_key,
            "name": item.name,
            "item_type": item_type,
            "category": item.category,
            "automation": {
                "ac_bonus": item.ac_bonus,
                "bonus_type": item.bonus_type,
            },
            "weapon": {
                "damage_dice": item.weapon_damage_dice,
                "damage_type": item.weapon_damage_type,
                "critical": item.weapon_critical,
                "range": item.weapon_range,
            },
        }
    )


def item_choices(item: EquipmentItem) -> dict[str, str]:
    try:
        data = json.loads(item.choices_json or "{}")
        return {str(key): str(value) for key, value in data.items()}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def validate_item_choices(automation: ItemAutomation, choices: dict[str, str]) -> dict[str, str]:
    """Validate persisted choices against the catalog schema, independent of UI."""
    specs = {choice.key: choice for choice in automation.choices}
    unknown = set(choices) - set(specs)
    if unknown:
        raise ValueError(f"Unknown item choice: {sorted(unknown)[0]}")
    normalized: dict[str, str] = {}
    distinct: dict[str, set[str]] = {}
    for key, spec in specs.items():
        value = str(choices.get(key, ""))
        allowed = {option_key for option_key, _label in spec.options}
        if spec.required and not value:
            raise ValueError(f"A value is required for {spec.label}.")
        if value and value not in allowed:
            raise ValueError(f"Unsupported value for {spec.label}.")
        if value and spec.distinct_group:
            used = distinct.setdefault(spec.distinct_group, set())
            if value in used:
                raise ValueError(f"{spec.label} must use a different choice.")
            used.add(value)
        normalized[key] = value
    return normalized


def effective_item_state(item: EquipmentItem) -> str:
    """Honor legacy in-memory records that only carry the equipped boolean."""
    if item.state != "stored" or not item.equipped:
        return item.state
    if item.category == "Armor": return "armor"
    if item.category == "Shield": return "shield"
    if item.category == "Weapon": return "wielded"
    if item.slot: return "worn"
    return "carried"


def preferred_item_state(item: EquipmentItem) -> str:
    """Natural active state used by every one-click equip/wear workflow."""
    if item.category == "Armor":
        return "armor"
    if item.category == "Shield":
        return "shield"
    if item.category == "Weapon":
        return "wielded"
    return "worn" if item.slot else "carried"


def effect_is_active(item: EquipmentItem, activation: str) -> tuple[bool, str]:
    if item.quantity <= 0: return False, "Quantity is zero"
    state = effective_item_state(item)
    allowed = {
        "carried": {"carried", "worn", "wielded", "armor", "shield"},
        "worn": {"worn"}, "wielded": {"wielded"}, "armor": {"armor"}, "shield": {"shield"},
    }.get(activation, {activation})
    return (True, "Required item state is active") if state in allowed else (False, f"Requires {activation}; currently {state}")


def item_modifiers(items: list[EquipmentItem]) -> dict[str, list[StatModifier]]:
    result: dict[str, list[StatModifier]] = {}
    for item in items:
        automation = automation_for_item(item)
        choices = item_choices(item)
        for effect in automation.effects:
            if effect.operation not in {"add", "set"}: continue
            target = effect.target
            if effect.choice_group:
                target = choices.get(effect.choice_group, "")
            if not target: continue
            active, reason = effect_is_active(item, effect.activation)
            result.setdefault(target, []).append(
                StatModifier(
                    None, target, f"Item: {item.name} — {effect.label or effect.key}",
                    ("set" if effect.operation == "set" else effect.bonus_type),
                    effect.value, active, "" if active else reason,
                )
            )
    return result


def automation_summary(automation: ItemAutomation) -> str:
    labels = [effect.label or f"{effect.target} {effect.value:+d}" for effect in automation.effects]
    labels.extend(f"Choice: {choice.label}" for choice in automation.choices)
    labels.extend(automation.rules_only)
    return "; ".join(labels) or "Rules only"

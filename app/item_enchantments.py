"""Composable magic-item properties and their reviewed sheet effects.

The persistence layer stores only stable enchantment keys and user-facing
metadata.  Rules live here, so adding another weapon property does not require
new database columns or item-specific branches in the character sheet UI.
"""
from __future__ import annotations

import re
import json
from dataclasses import dataclass
from pathlib import Path

from app.models import Attack, EquipmentItem, ItemEnchantment


@dataclass(frozen=True, slots=True)
class EnchantmentEffectSpec:
    target: str
    operation: str
    value: str | int | float
    scope: str
    requires: tuple[str, ...] = ()
    bonus_type: str = "untyped"


@dataclass(frozen=True, slots=True)
class EnchantmentSpec:
    key: str
    name: str
    bonus_equivalent: int
    description: str
    applies_to: tuple[str, ...]
    effects: tuple[EnchantmentEffectSpec, ...] = ()
    source_url: str = ""
    family: str = "Weapon"
    category: str = "Universal"
    flat_price_gp: int = 0
    price_text: str = ""
    aura: str = ""
    caster_level: str = ""
    requirements: str = ""
    restrictions: tuple[str, ...] = ()
    source: str = ""
    automation_status: str = "rules_only"


@dataclass(frozen=True, slots=True)
class ItemPriceBreakdown:
    """Live market-price components derived from one saved base price."""

    base_value_gp: float
    masterwork_gp: float
    enhancement_gp: float
    flat_properties_gp: float
    total_gp: float
    modified_bonus: int


_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "pf1e" / "enchantments.json"
_EFFECTS_BY_KEY: dict[str, tuple[EnchantmentEffectSpec, ...]] = {
    "pathfinder:weapon-property:agile": (
        EnchantmentEffectSpec(
            target="damage_ability",
            operation="default",
            value="dexterity",
            scope="host_weapon_or_unarmed",
            requires=("weapon_finesse",),
        ),
        EnchantmentEffectSpec(
            target="damage_multiplier",
            operation="cap_max",
            value=1.0,
            scope="host_weapon_or_unarmed",
            requires=("weapon_finesse",),
        ),
    ),
    "pathfinder:enchantment:weapon:melee:keen": (
        EnchantmentEffectSpec(
            target="critical_profile", operation="double_threat_range",
            value=2, scope="host_weapon_or_unarmed",
        ),
    ),
    "pathfinder:enchantment:weapon:melee:impact": (
        EnchantmentEffectSpec(
            target="damage_dice", operation="scale_size_steps",
            value=1, scope="host_weapon_or_unarmed",
        ),
    ),
}

for _name, _damage_type in {
    "corrosive": "acid",
    "corrosive-burst": "acid",
    "flaming": "fire",
    "flaming-burst": "fire",
    "frost": "cold",
    "icy-burst": "cold",
    "shock": "electricity",
    "shocking-burst": "electricity",
}.items():
    _EFFECTS_BY_KEY[f"pathfinder:enchantment:weapon:universal:{_name}"] = (
        EnchantmentEffectSpec(
            target="extra_damage", operation="add_dice", value="1d6",
            scope="host_weapon_or_unarmed", bonus_type=_damage_type,
        ),
    )

_EFFECTS_BY_KEY.update({
    "pathfinder:enchantment:weapon:melee:vicious": (
        EnchantmentEffectSpec(
            target="extra_damage", operation="add_dice", value="2d6",
            scope="host_weapon_or_unarmed", bonus_type="untyped",
        ),
    ),
    "pathfinder:enchantment:weapon:universal:merciful": (
        EnchantmentEffectSpec(
            target="extra_damage", operation="add_dice", value="1d6",
            scope="host_weapon_or_unarmed", bonus_type="nonlethal",
        ),
    ),
    "pathfinder:enchantment:weapon:ranged:sonic-boom": (
        EnchantmentEffectSpec(
            target="extra_damage", operation="add_dice", value="1d6",
            scope="host_weapon_or_unarmed", bonus_type="sonic",
        ),
    ),
})


def _load_specs() -> tuple[EnchantmentSpec, ...]:
    with _DATA_FILE.open(encoding="utf-8") as file:
        entries = json.load(file).get("entries", ())
    return tuple(
        EnchantmentSpec(
            key=str(entry["key"]),
            name=str(entry["name"]),
            bonus_equivalent=int(entry.get("bonus_equivalent") or 0),
            description=str(entry.get("description") or ""),
            applies_to=tuple(str(value) for value in entry.get("applies_to", ())),
            effects=_EFFECTS_BY_KEY.get(str(entry["key"]), ()),
            source_url=str(entry.get("source_url") or ""),
            family=str(entry.get("family") or "Weapon"),
            category=str(entry.get("category") or "Universal"),
            flat_price_gp=int(entry.get("flat_price_gp") or 0),
            price_text=str(entry.get("price_text") or ""),
            aura=str(entry.get("aura") or ""),
            caster_level=str(entry.get("caster_level") or ""),
            requirements=str(entry.get("requirements") or ""),
            restrictions=tuple(str(value) for value in entry.get("restrictions", ())),
            source=str(entry.get("source") or ""),
            automation_status=str(entry.get("automation_status") or "rules_only"),
        )
        for entry in entries
    )


ENCHANTMENT_SPECS: tuple[EnchantmentSpec, ...] = _load_specs()
_SPECS_BY_KEY = {spec.key: spec for spec in ENCHANTMENT_SPECS}
AGILE = _SPECS_BY_KEY["pathfinder:weapon-property:agile"]
_EXCLUSIVE_PROPERTY_GROUPS = tuple(
    frozenset(
        {
            f"pathfinder:enchantment:weapon:universal:{base}",
            f"pathfinder:enchantment:weapon:universal:{burst}",
        }
    )
    for base, burst in (
        ("corrosive", "corrosive-burst"),
        ("flaming", "flaming-burst"),
        ("frost", "icy-burst"),
        ("shock", "shocking-burst"),
    )
)


COMPOSABLE_ITEM_ENTRIES: tuple[dict, ...] = (
    {
        "key": "reviewed:amulet-of-mighty-fists:customizable",
        "name": "Amulet of Mighty Fists",
        "source_group": "Pathfinder",
        "family": "Magic Items",
        "category": "Magic Items",
        "subcategory": "Wondrous Items / Neck",
        "description": (
            "A composable Amulet of Mighty Fists. Add an enhancement bonus or "
            "compatible melee weapon properties with Enchant selected. The "
            "amulet does not require a +1 enhancement bonus before receiving a "
            "special ability."
        ),
        "source": "Pathfinder RPG",
        "source_url": (
            "https://www.d20pfsrd.com/magic-items/wondrous-items/a-b/"
            "amulet-of-mighty-fists/"
        ),
        "price_gp": 0.0,
        "weight_lb": 0.0,
        "slot": "neck",
        "item_type": "equipment",
        "weapon": {},
        "automation": {
            "ac_bonus": 0,
            "bonus_type": "",
            "max_dex_bonus": None,
            "armor_check_penalty": 0,
            "spell_failure": 0,
        },
    },
)


def enchantment_spec(key: str) -> EnchantmentSpec | None:
    return _SPECS_BY_KEY.get(key)


def is_amulet_of_mighty_fists(item: EquipmentItem) -> bool:
    return item.name.casefold().startswith("amulet of mighty fists") or (
        item.catalog_key == "reviewed:amulet-of-mighty-fists:customizable"
    )


def effective_enhancement_bonus(item: EquipmentItem) -> int:
    """Honor explicit edits, then recover imported +1..+5 amulet variants."""
    if item.enhancement_bonus:
        return item.enhancement_bonus
    if is_amulet_of_mighty_fists(item):
        match = re.search(r"\+(\d+)\b", item.name)
        if match:
            return int(match.group(1))
    return 0


def weapon_attack_type(item: EquipmentItem) -> str:
    """Resolve melee/ranged from structured catalog data before range text.

    Older saved melee weapons commonly store ``"0"`` as their range.  Treating
    any non-empty range string as ranged caused those records to flip type.
    """
    if item.category != "Weapon":
        return "Melee"
    if item.catalog_key:
        from app.catalogs import DEFAULT_CATALOG
        entry = DEFAULT_CATALOG.item_entry(item.catalog_key)
        catalog_type = str(((entry or {}).get("weapon") or {}).get("attack_type") or "")
        if catalog_type in {"Melee", "Ranged"}:
            return catalog_type
    lowered = item.name.casefold()
    if any(word in lowered for word in ("bow", "crossbow", "firearm", "musket", "pistol", "blowgun", "sling")):
        return "Ranged"
    try:
        return "Ranged" if float(str(item.weapon_range or "0")) > 0 else "Melee"
    except ValueError:
        return "Melee" if str(item.weapon_range).strip().casefold() in {"", "0", "melee", "—", "-"} else "Ranged"


def catalog_enhancement_bonus(entry: dict) -> int:
    """Extract reviewed enhancement variants while importing catalog items."""
    name = str(entry.get("name") or "")
    if name.casefold().startswith("amulet of mighty fists"):
        match = re.search(r"\+(\d+)\b", name)
        return int(match.group(1)) if match else 0
    return int((entry.get("automation") or {}).get("enhancement_bonus") or 0)


def enchantment_applies_to_item(spec: EnchantmentSpec, item: EquipmentItem) -> bool:
    contexts: set[str] = set()
    catalog_entry = None
    if item.catalog_key:
        # Lazy import avoids coupling catalog construction to the property
        # resolver while still using the one sanctioned rules-data gateway.
        from app.catalogs import DEFAULT_CATALOG
        catalog_entry = DEFAULT_CATALOG.item_entry(item.catalog_key)
    if is_amulet_of_mighty_fists(item):
        contexts.add("weapon_melee")
    elif item.category == "Weapon":
        dedicated_ranged = weapon_attack_type(item) == "Ranged"
        if not dedicated_ranged:
            contexts.add("weapon_melee")
        try:
            has_range = float(str(item.weapon_range or "0")) > 0
        except ValueError:
            has_range = bool(str(item.weapon_range).strip())
        if dedicated_ranged or has_range:
            contexts.add("weapon_ranged")
    elif item.category == "Armor":
        contexts.add("armor")
    elif item.category == "Shield":
        contexts.add("shield")
    if not contexts.intersection(spec.applies_to):
        return False

    restrictions = " ".join(spec.restrictions).casefold()
    if is_amulet_of_mighty_fists(item) and any(
        word in restrictions for word in (
            "ranged weapon", "ammunition", "projectile", "thrown weapon", "bow",
            "crossbow", "firearm", "two-handed weapon", "manufactured weapon",
        )
    ):
        return False
    damage = item.weapon_damage_type.casefold()
    permitted_damage = {
        damage_type for damage_type in ("bludgeoning", "piercing", "slashing")
        if "only" in restrictions and damage_type in restrictions
    }
    if permitted_damage and not any(value in damage for value in permitted_damage):
        return False
    item_name = item.name.casefold()
    for terms in (
        ("bow", "bow"), ("crossbow", "crossbow"), ("firearm", "firearm"),
        ("axe", "axe"), ("sword", "sword"), ("hammer", "hammer"),
        ("spear", "spear"), ("whip", "whip"),
    ):
        rule_word, name_word = terms
        if "only" in restrictions and rule_word in restrictions and name_word not in item_name:
            return False
    if item.category == "Armor" and catalog_entry is not None:
        armor_class = str(catalog_entry.get("category") or "").casefold()
        for weight in ("light", "medium", "heavy"):
            if f"only {weight} armor" in restrictions and weight not in armor_class:
                return False
    if item.category == "Shield":
        for shield_type in ("buckler", "tower", "light", "heavy"):
            if f"only {shield_type}" in restrictions and shield_type not in item_name:
                return False
    return True


def available_enchantments(item: EquipmentItem) -> tuple[EnchantmentSpec, ...]:
    return tuple(
        spec for spec in ENCHANTMENT_SPECS if enchantment_applies_to_item(spec, item)
    )


def item_modified_bonus(
    item: EquipmentItem, enchantments: list[ItemEnchantment] | tuple[ItemEnchantment, ...]
) -> int:
    return effective_enhancement_bonus(item) + sum(
        max(0, enchantment.bonus_equivalent)
        for enchantment in enchantments
        if enchantment.equipment_id == item.id
    )


def item_price_breakdown(
    item: EquipmentItem,
    enchantments: list[ItemEnchantment] | tuple[ItemEnchantment, ...] = (),
) -> ItemPriceBreakdown:
    """Project masterwork and magic costs without rewriting the base price.

    Weapons use ``bonus² × 2,000 gp`` and armor/shields use ``bonus² ×
    1,000 gp``. Their required masterwork surcharge is shown separately. The
    Amulet of Mighty Fists uses its own ``bonus² × 4,000 gp`` progression.
    """

    applicable = tuple(
        value for value in enchantments if value.equipment_id == item.id
    )
    base_value = max(0.0, float(item.value_gp or 0.0))
    modified_bonus = item_modified_bonus(item, applicable)
    flat_properties = float(sum(
        max(0, int(spec.flat_price_gp))
        for value in applicable
        if (spec := enchantment_spec(value.key)) is not None
    ))
    masterwork_price = 0.0
    enhancement_price = 0.0

    if is_amulet_of_mighty_fists(item):
        # Imported +1..+5 variants already contain their named magic price.
        named = re.search(r"\+(\d+)\b", item.name)
        included_bonus = int(named.group(1)) if named else 0
        enhancement_price = float(
            (modified_bonus * modified_bonus - included_bonus * included_bonus)
            * 4_000
        )
    elif item.category == "Weapon":
        if item.masterwork or modified_bonus > 0:
            masterwork_price = 300.0
        enhancement_price = float(modified_bonus * modified_bonus * 2_000)
    elif item.category in {"Armor", "Shield"}:
        if item.masterwork or modified_bonus > 0:
            masterwork_price = 150.0
        enhancement_price = float(modified_bonus * modified_bonus * 1_000)

    total = max(
        0.0,
        base_value + masterwork_price + enhancement_price + flat_properties,
    )
    return ItemPriceBreakdown(
        base_value,
        masterwork_price,
        enhancement_price,
        flat_properties,
        total,
        modified_bonus,
    )


def item_market_price(
    item: EquipmentItem,
    enchantments: list[ItemEnchantment] | tuple[ItemEnchantment, ...] = (),
) -> float:
    """Return the live per-item market price for any inventory view."""

    return item_price_breakdown(item, enchantments).total_gp


def validate_enchantment_addition(
    item: EquipmentItem,
    existing: list[ItemEnchantment] | tuple[ItemEnchantment, ...],
    spec: EnchantmentSpec,
) -> None:
    if not enchantment_applies_to_item(spec, item):
        raise ValueError(f"{spec.name} cannot be applied to this item.")
    if any(value.key == spec.key for value in existing):
        raise ValueError(f"{item.name} already has the {spec.name} property.")
    existing_keys = {value.key for value in existing}
    for group in _EXCLUSIVE_PROPERTY_GROUPS:
        if spec.key in group and existing_keys.intersection(group):
            other = enchantment_spec(next(iter(existing_keys.intersection(group))))
            raise ValueError(
                f"{spec.name} already includes the effect of {other.name if other else 'the existing property'}; these properties do not stack."
            )
    base = effective_enhancement_bonus(item)
    if item.category in {"Weapon", "Armor", "Shield"}:
        base = max(1, base)
    proposed = base + sum(
        max(0, enchantment.bonus_equivalent)
        for enchantment in existing
        if enchantment.equipment_id == item.id
    ) + spec.bonus_equivalent
    if is_amulet_of_mighty_fists(item):
        if proposed > 5:
            raise ValueError("An Amulet of Mighty Fists cannot exceed a +5 modified bonus.")
    elif item.category in {"Weapon", "Armor", "Shield"}:
        if proposed > 10:
            raise ValueError(
                f"A magic {item.category.casefold()} cannot exceed a +10 modified bonus."
            )


def attack_matches_scope(
    attack: Attack, scope: str, item: EquipmentItem | None = None
) -> bool:
    """Resolve a saved property's scope against both attack and host item.

    A property can therefore use one stable effect definition while its host
    determines how it reaches the attack.  Agile on an amulet reaches unarmed
    and natural attacks; Agile on a weapon reaches only the attack linked to
    that weapon.
    """
    if scope == "unarmed_or_natural":
        return attack.profile_key in {"unarmed", "natural"}
    if scope == "linked_weapon":
        return attack.equipment_id is not None
    if scope == "host_weapon_or_unarmed" and item is not None:
        return (
            attack.profile_key in {"unarmed", "natural"}
            if is_amulet_of_mighty_fists(item)
            else attack.equipment_id == item.id
        )
    return False


def item_is_active_for_attack(item: EquipmentItem) -> bool:
    if item.quantity <= 0:
        return False
    state = item.state
    if not state and item.equipped:
        state = "wielded" if item.category == "Weapon" else "worn" if item.slot else "carried"
    if is_amulet_of_mighty_fists(item):
        return state == "worn"
    return state == "wielded"


def item_display_name(
    item: EquipmentItem,
    enchantments: list[ItemEnchantment] | tuple[ItemEnchantment, ...],
) -> str:
    names = [
        value.name
        for value in enchantments
        if value.equipment_id == item.id
    ]
    return item.name if not names else f"{item.name} [{', '.join(names)}]"


def enchantment_summary(
    item: EquipmentItem,
    enchantments: list[ItemEnchantment] | tuple[ItemEnchantment, ...],
) -> str:
    values = [value for value in enchantments if value.equipment_id == item.id]
    if not values:
        return "No enchantments"
    names = ", ".join(
        (
            f"{value.name} (+{value.bonus_equivalent} equivalent)"
            if value.bonus_equivalent
            else value.name
        )
        for value in values
    )
    return f"{names}; modified bonus +{item_modified_bonus(item, values)}"

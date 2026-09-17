"""Crafting adapters for the existing equipment pricing/compatibility engine."""
from dataclasses import replace
from functools import lru_cache
from app.catalogs import DEFAULT_CATALOG
from app.crafting_catalog import mundane_entries
from app.item_enchantments import (ENCHANTMENT_SPECS, enchantment_applies_to_item,
    enchantment_spec, item_price_breakdown, validate_enchantment_addition)
from app.models import EquipmentItem, ItemEnchantment


def property_for_recipe(recipe):
    if recipe.get('price_gp') is not None: return None
    matches = [s for s in ENCHANTMENT_SPECS if s.name.casefold() == recipe['name'].casefold()]
    return matches[0] if len(matches) == 1 else None


@lru_cache(maxsize=256)
def compatible_bases(property_key):
    spec = enchantment_spec(property_key)
    if spec is None: return ()
    result = []
    for entry in mundane_entries(DEFAULT_CATALOG):
        if entry['family'] not in {'Weapons & Ammunition','Armor & Shields'}: continue
        automation, weapon = entry.get('automation',{}), entry.get('weapon',{})
        category = 'Weapon' if entry['family']=='Weapons & Ammunition' else ('Shield' if automation.get('bonus_type')=='shield' else 'Armor')
        item = EquipmentItem(0,entry['name'],category,1,entry.get('weight_lb',0),False,
            automation.get('ac_bonus',0),automation.get('bonus_type',''),automation.get('max_dex_bonus'),
            value_gp=entry.get('price_gp',0),catalog_key=entry['key'],masterwork=True,enhancement_bonus=1,
            weapon_damage_type=weapon.get('damage_type',''),weapon_range=weapon.get('range',''),
            weapon_damage_dice=weapon.get('damage_dice',''))
        if enchantment_applies_to_item(spec,item): result.append(item)
    return tuple(sorted(result,key=lambda i:i.name.casefold()))


def configured_property_cost(base, property_key, enhancement):
    spec = enchantment_spec(property_key)
    if spec is None: raise ValueError('Unknown enchantment.')
    if not 1 <= enhancement <= 5: raise ValueError('Enhancement must be +1 to +5.')
    item = replace(base, enhancement_bonus=enhancement)
    validate_enchantment_addition(item,(),spec)
    property_ = ItemEnchantment(0,item.id,spec.key,spec.name,spec.bonus_equivalent)
    price = item_price_breakdown(item,(property_,))
    magical = price.enhancement_gp + price.flat_properties_gp
    return magical, magical/2 + price.base_value_gp + price.masterwork_gp

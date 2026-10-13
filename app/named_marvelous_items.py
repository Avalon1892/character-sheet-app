"""Reviewed named-item activation rules; catalog descriptions remain authoritative.

Source: https://spheresofpower.wikidot.com/marvelous-items
No runtime description parsing or custom-blueprint price substitution.
"""
from copy import deepcopy

NAMED_EFFECTS = {
    'spheres:marvelous-items:thunderbolt-ring': dict(
        power='Thunderbolt Ring', caster_level=4, daily_uses=1, activation='Standard action',
        damage_dice=4, die_sides=6, damage_type='electricity', damage='4d6 electricity',
        area='5-foot-wide, 140-foot line', save='Reflex half', save_dc=12,
        special='Metal-armored or primarily metal targets take -3 to the save.',
        upgrade_review='Base item only; Flask Shard upgrades require separate reviewed configuration.'),
}


def named_marvelous_effect(catalog_key):
    effect = NAMED_EFFECTS.get(catalog_key)
    return deepcopy(effect) if effect is not None else None


def named_marvelous_remaining(catalog_key, metadata):
    effect = named_marvelous_effect(catalog_key)
    if effect is None: raise ValueError('This named item has no reviewed activation adapter.')
    used = metadata.get('marvelous_uses_used', 0)
    if isinstance(used, bool) or not isinstance(used, int) or used < 0:
        raise ValueError('Invalid saved named-item usage.')
    return max(0, effect['daily_uses'] - used)

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


def named_marvelous_effect(catalog_key, metadata=None):
    effect = NAMED_EFFECTS.get(catalog_key)
    if effect is None: return None
    effect = deepcopy(effect)
    upgrades = (metadata or {}).get('marvelous_flask_shards', 0)
    if isinstance(upgrades, bool) or not isinstance(upgrades, int) or not 0 <= upgrades <= 4:
        raise ValueError('Thunderbolt Ring supports zero to four recorded Flask Shards.')
    cl = 4 * (upgrades + 1)
    effect.update(caster_level=cl, daily_uses=1 + upgrades, damage_dice=cl,
                  damage=f'{cl}d6 electricity', area=f'5-foot-wide, {100 + 10 * cl}-foot line', save_dc=10 + cl // 2)
    effect['upgrade_review'] = f'{upgrades} applied Flask Shards recorded; shard consumption must be verified separately.'
    return effect


def named_marvelous_remaining(catalog_key, metadata):
    effect = named_marvelous_effect(catalog_key, metadata)
    if effect is None: raise ValueError('This named item has no reviewed activation adapter.')
    used = metadata.get('marvelous_uses_used', 0)
    if isinstance(used, bool) or not isinstance(used, int) or used < 0:
        raise ValueError('Invalid saved named-item usage.')
    return max(0, effect['daily_uses'] - used)

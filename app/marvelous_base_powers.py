"""Structured Ultimate Spheres item base powers, not normal casting defaults.

Source: https://spheresofpower.wikidot.com/magical-items (Item Base Powers).
Special talent variants remain separate construction changes.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MarvelousBasePower:
    key: str
    sphere: str
    name: str
    range: str
    duration: str


_ROWS = (
    ('alteration:shapeshift', 'Alteration', 'Blank Transformation', 'personal', 'round'),
    ('bear:spirit', 'Bear', 'Bear spirit', 'personal', 'minute'),
    ('blood:control', 'Blood', 'Blood control', 'touch', 'round'),
    ('blood:construct', 'Blood', 'Extract blood construct', 'touch', 'round'),
    ('conjuration:companion', 'Conjuration', 'Summon companion', 'personal', 'round'),
    ('creation:alter', 'Creation', 'Repair / destroy', 'touch', 'instantaneous'),
    ('creation:create', 'Creation', 'Create object', 'personal', 'round'),
    ('dark:darkness', 'Dark', 'Darkness', 'personal', 'round'),
    ('death:ghost-strike', 'Death', 'Ghost strike', 'touch', 'variable'),
    ('death:reanimate', 'Death', 'Reanimate', 'touch', 'round'),
    ('destruction:blast', 'Destruction', 'Bludgeoning destructive blast', 'touch', 'instantaneous'),
    ('divination:divine', 'Divination', 'Divine magic', 'close', 'concentration'),
    ('divination:sense', 'Divination', 'Base sense', 'personal', 'minute'),
    ('enhancement:enhance', 'Enhancement', 'Basic enhancement', 'touch', 'round'),
    ('fallen-fey:link', 'Fallen Fey', 'Fey-link / Nature-connection', 'personal', 'minute'),
    ('fate:serendipity', 'Fate', 'Serendipity', 'personal', 'round'),
    ('illusion:figment', 'Illusion', 'Silent visual illusion', 'touch', 'round'),
    ('life:cure', 'Life', 'Cure', 'touch', 'instantaneous'),
    ('life:restore', 'Life', 'Restore', 'touch', 'instantaneous'),
    ('life:temporary-hp', 'Life', 'Temporary hit points', 'touch', 'minute'),
    ('light:glow', 'Light', 'Bright glow', 'personal', 'minute'),
    ('mana:expunge', 'Mana', 'Spellburn', 'close', 'instantaneous'),
    ('mana:manipulate', 'Mana', 'Shuffle', 'close', 'fixed-round'),
    ('mind:suggestion', 'Mind', 'Lesser Suggestion', 'touch', 'variable'),
    ('nature:geomance', 'Nature', 'Base geomancing', 'personal', 'round'),
    ('protection:aegis', 'Protection', 'Basic aegis', 'personal', 'minute'),
    ('protection:ward', 'Protection', 'Basic ward', 'personal', 'round'),
    ('technomancy:sprite', 'Technomancy', 'Base sprite', 'close', 'round'),
    ('telekinesis:force', 'Telekinesis', 'Sustained Force', 'personal', 'round'),
    ('time:haste', 'Time', 'Haste', 'personal', 'round'),
    ('time:slow', 'Time', 'Slow', 'personal', 'round'),
    ('war:totem', 'War', 'Base totem', 'personal', 'round'),
    ('warp:teleport', 'Warp', 'Teleport within close range', 'personal', 'instantaneous'),
    ('weather:control', 'Weather', 'Change one weather category', 'personal', 'round'),
)
BASE_POWERS = tuple(MarvelousBasePower(*row) for row in _ROWS)
RANGES = ('personal', 'touch', 'close', 'medium', 'long')
DURATIONS = ('round', 'minute', 'ten-minutes', 'hour')


def base_powers(sphere):
    return tuple(power for power in BASE_POWERS if power.sphere.casefold() == sphere.casefold())


def automatic_self_effect(plan):
    """Supported activation kind, independent of editable prose and Qt."""
    if plan.get('unique_changes') or plan.get('permanent'):
        return None
    if plan.get('base_power') == 'life:cure':
        return 'cure' if cure_healing_components(plan) is not None else None
    if plan.get('base_power') == 'protection:aegis':
        return 'aegis' if aegis_modifiers(plan) is not None else None
    if plan.get('contributions'): return None
    return {'life:cure': 'cure', 'life:temporary-hp': 'temporary_hp', 'protection:aegis': 'aegis'}.get(plan.get('base_power'))


def restore_condition_changes(mode, conditions, *, ongoing=()):
    """Reviewable Ultimate Restore transitions; ongoing sources need suppression.

    Results describe changes without altering persistence or losing provenance.
    Snapshot each starting condition once, so downgraded fear is not also removed.
    """
    transitions = {
        'mind': {'Dazzled': None, 'Shaken': None, 'Frightened': 'Shaken', 'Panicked': 'Frightened', 'Staggered': None},
        'body': {'Battered': None, 'Fatigued': None, 'Exhausted': 'Fatigued', 'Sickened': None, 'Nauseated': 'Sickened'},
    }
    if mode not in transitions: raise ValueError('Condition restoration requires mind or body.')
    ongoing = set(ongoing)
    return [{'condition': name, 'operation': 'suppress' if name in ongoing else 'replace' if replacement else 'remove',
             'replacement': None if name in ongoing else replacement}
            for name in dict.fromkeys(conditions) if name in transitions[mode]
            for replacement in (transitions[mode][name],)]


def aegis_modifiers(plan):
    """Supported replacement aegises; never combine unknown talents implicitly."""
    contributions = plan.get('contributions', [])
    if not contributions:
        return [('ac', 'deflection', 1 + plan['caster_level'] // 5)]
    if (len(contributions) == 1 and not contributions[0].get('alternative')
            and contributions[0].get('catalog_key') == 'protection:aegis-ward-talent:resistance-aegis'):
        return [(save, 'resistance', 1 + plan['caster_level'] // 4) for save in ('fortitude', 'reflex', 'will')]
    if (len(contributions) == 1 and not contributions[0].get('alternative')
            and contributions[0].get('catalog_key') == 'protection:aegis-ward-talent:armored-magic-aegis'):
        choice = contributions[0].get('effect_choice')
        if choice not in {'armor', 'shield'}: return None
        return [('ac', choice, (3 if choice == 'armor' else 1) + plan['caster_level'] // 5)]
    return None


def cure_healing_components(plan):
    """Verified Ultimate Life healing; unknown/choice effects remain manual.

    Restore talent benefits here affect cure healing only, not restore actions.
    Source: https://spheresofpower.wikidot.com/life
    """
    boosts = {'life:cure-talent:restore-capacity-cure', 'life:cure-talent:restore-health-cure',
              'life:cure-talent:restore-senses-cure', 'life:cure-talent:restore-spirit-cure'}
    deeper = 'life:talent:deeper-healing'
    contributions = plan.get('contributions', [])
    keys = [row.get('catalog_key') for row in contributions]
    if any(key not in boosts | {deeper} for key in keys) or len(set(keys)) != len(keys): return None
    if any(row.get('alternative') for row in contributions): return None
    cl = plan['caster_level']
    return (1 + (1 + cl // 5 if deeper in keys else 0), cl * (1 + sum(key in boosts for key in keys)))


def automatic_damage_dice(plan):
    """Supported offensive roll; target defenses/application are separate."""
    if (plan.get('base_power') != 'destruction:blast' or plan.get('contributions')
            or plan.get('unique_changes', 0)):
        return None
    return resolve_base_power(plan)['damage_dice']


def resolve_base_power(plan):
    for field in ('caster_level', 'range_steps', 'duration_steps'):
        value = plan[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('Base-power parameters must be integers.')
    if plan['caster_level'] < 1:
        raise ValueError('Item caster level must be positive.')
    key = plan.get('base_power')
    effect_steps = plan.get('effect_range_steps', 0)
    if (isinstance(effect_steps, bool) or not isinstance(effect_steps, int) or not 0 <= effect_steps <= 2
            or (effect_steps and key not in {'warp:teleport', 'weather:control'})):
        raise ValueError('Effect range steps require Warp teleport or Weather control, from zero to two.')
    boost = plan.get('full_blast_damage', False)
    if not isinstance(boost, bool) or (boost and key != 'destruction:blast'):
        raise ValueError('Full blast damage requires the Destruction blast base power.')
    power = next((p for p in BASE_POWERS if p.key == key), None)
    if power is None or power.sphere.casefold() != plan['sphere'].casefold():
        raise ValueError('Choose a base power from the selected sphere.')
    range_index = RANGES.index(power.range) + plan['range_steps']
    if not 0 <= range_index < len(RANGES):
        raise ValueError('Range adjustment exceeds the published range ladder.')
    duration = power.duration
    if duration in DURATIONS:
        duration_index = DURATIONS.index(duration) + plan['duration_steps']
        if not 0 <= duration_index < len(DURATIONS):
            raise ValueError('Duration adjustment exceeds the published duration ladder.')
        duration = DURATIONS[duration_index]
    elif plan['duration_steps']:
        raise ValueError('This base power does not use the adjustable duration ladder.')
    cl = plan['caster_level']
    if plan.get('permanent', False):
        if cl < 10 or duration != 'hour':
            raise ValueError('Permanency requires caster level 10 and an effect duration measured in hours.')
    distances = {'personal': 'Personal', 'touch': 'Touch', 'close': f'{25 + 5 * (cl // 2)} ft.',
                 'medium': f'{100 + 10 * cl} ft.', 'long': f'{400 + 40 * cl} ft.'}
    durations = {'round': f'{cl} rounds', 'minute': f'{cl} minutes',
                 'ten-minutes': f'{10 * cl} minutes', 'hour': f'{cl} hours',
                 'fixed-round': '1 round', 'instantaneous': 'Instantaneous',
                 'concentration': 'Concentration', 'variable': 'As selected effect'}
    summary = {'power': power.name, 'range': distances[RANGES[range_index]], 'duration': durations[duration],
               'caster_level': cl, 'save_dc': 10 + cl // 2, 'magic_skill_bonus': cl}
    if plan.get('permanent', False): summary['duration'] = 'Permanent (dispellable)'
    if power.key == 'life:temporary-hp': summary['temporary_hp'] = cl
    if power.key == 'protection:aegis':
        modifiers = aegis_modifiers(plan)
        if modifiers is not None:
            summary['ongoing_modifiers'] = modifiers
            if modifiers[0][0] == 'ac':
                summary[modifiers[0][1] + '_ac'] = modifiers[0][2]
                if modifiers[0][1] != 'deflection': summary['power'] = 'Armored Magic aegis (' + modifiers[0][1] + ')'
            else:
                summary['power'] = 'Resistance aegis'
                summary['resistance_saves'] = modifiers[0][2]
    if power.key == 'life:cure':
        healing = cure_healing_components(plan)
        if healing is not None:
            dice, bonus = healing
            summary['healing'] = f'{dice}d8+{bonus}'
            summary['healing_dice'] = dice; summary['healing_bonus'] = bonus
        else:
            summary['healing'] = f'Base 1d8+{cl}; selected modifications require manual resolution'
    if power.key == 'destruction:blast':
        summary['damage_dice'] = cl if boost else cl // 2
        summary['damage'] = f'{summary["damage_dice"]}d6 bludgeoning'
    if power.key == 'warp:teleport': summary['teleport_distance'] = distances[('close', 'medium', 'long')[effect_steps]]
    if power.key == 'weather:control': summary['area_radius'] = distances[('close', 'medium', 'long')[effect_steps]]
    if power.key in {'blood:construct', 'death:reanimate'}: summary['maximum_hit_dice'] = cl
    if power.key == 'dark:darkness': summary['radius'] = f'{10 + 5 * (cl // 2)} ft.'
    if power.key == 'alteration:shapeshift': summary['traits'] = 1 + cl // 5
    return summary

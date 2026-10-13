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


def resolve_base_power(plan):
    for field in ('caster_level', 'range_steps', 'duration_steps'):
        value = plan[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('Base-power parameters must be integers.')
    if plan['caster_level'] < 1:
        raise ValueError('Item caster level must be positive.')
    key = plan.get('base_power')
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
    distances = {'personal': 'Personal', 'touch': 'Touch', 'close': f'{25 + 5 * (cl // 2)} ft.',
                 'medium': f'{100 + 10 * cl} ft.', 'long': f'{400 + 40 * cl} ft.'}
    durations = {'round': f'{cl} rounds', 'minute': f'{cl} minutes',
                 'ten-minutes': f'{10 * cl} minutes', 'hour': f'{cl} hours',
                 'fixed-round': '1 round', 'instantaneous': 'Instantaneous',
                 'concentration': 'Concentration', 'variable': 'As selected effect'}
    summary = {'power': power.name, 'range': distances[RANGES[range_index]], 'duration': durations[duration]}
    if power.key == 'life:temporary-hp': summary['temporary_hp'] = cl
    if power.key == 'destruction:blast': summary['damage'] = f'{cl // 2}d6 bludgeoning'
    if power.key == 'warp:teleport': summary['teleport_distance'] = f'{25 + 5 * (cl // 2)} ft.'
    if power.key in {'blood:construct', 'death:reanimate'}: summary['maximum_hit_dice'] = cl
    if power.key == 'dark:darkness': summary['radius'] = f'{10 + 5 * (cl // 2)} ft.'
    if power.key == 'alteration:shapeshift': summary['traits'] = 1 + cl // 5
    return summary

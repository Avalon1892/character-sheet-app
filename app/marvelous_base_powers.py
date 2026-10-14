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
    ('warp:beacon', 'Warp', 'Place teleport beacon', 'touch', 'hour'),
    ('weather:control', 'Weather', 'Change one weather category', 'personal', 'round'),
)
BASE_POWERS = tuple(MarvelousBasePower(*row) for row in _ROWS)
RANGES = ('personal', 'touch', 'close', 'medium', 'long')
DURATIONS = ('round', 'minute', 'ten-minutes', 'hour')

# Reviewed Ultimate blast types: name, damage, die size, additional SP.
DESTRUCTION_BLAST_TYPES = {
    'destruction:blast-type-talent:acid-blast-blast-type-acid': ('Acid Blast', 'acid', 6, 0),
    'destruction:blast-type-talent:crystal-blast-blast-type-crystal': ('Crystal Blast', 'piercing', 4, 0),
    'destruction:blast-type-talent:electric-blast-blast-type-electricity': ('Electric Blast', 'electricity', 6, 0),
    'destruction:blast-type-talent:fire-blast-blast-type-fire': ('Fire Blast', 'fire', 6, 0),
    'destruction:blast-type-talent:force-blast-blast-type-force': ('Force Blast', 'force', 6, 1),
    'destruction:blast-type-talent:frost-blast-blast-type-cold': ('Frost Blast', 'cold', 6, 0),
}


def destructive_blast_profile(plan):
    rows = plan.get('contributions', [])
    if not rows: return ('Bludgeoning destructive blast', 'bludgeoning', 6, 0)
    if len(rows) != 1 or rows[0].get('alternative'): return None
    return DESTRUCTION_BLAST_TYPES.get(rows[0].get('catalog_key'))


def talent_effect_choices(key):
    """Reviewed construction choices, shared by the editor and projections."""
    if key == 'protection:aegis-ward-talent:armored-magic-aegis':
        return ('armor', 'shield')
    if key == 'protection:advanced-talent:spell-selectivity-dbh':
        return ('only', 'except')
    if key in {'protection:aegis-ward-talent:energy-resistance-aegis-ward',
               'protection:advanced-talent:adaptation-aegis'}:
        return ('acid', 'cold', 'electricity', 'fire', 'sonic')
    return ()


def base_powers(sphere):
    return tuple(power for power in BASE_POWERS if power.sphere.casefold() == sphere.casefold())


def item_dice_metamagic(plan):
    integrations = plan.get('feat_integrations', [])
    if not integrations: return (False, False)
    if plan.get('base_power') not in {'life:cure', 'destruction:blast'}: return None
    costs = {'maximize spell': 3, 'empower spell': 2}
    names = [feat.get('name', '').casefold() for feat in integrations]
    if len(names) != len(set(names)) or any(name not in costs or feat.get('metamagic') is not True
        or feat.get('additional_spell_points') != costs[name] for name, feat in zip(names, integrations)):
        return None
    return ('maximize spell' in names, 'empower spell' in names)


def item_dice_result(plan, count, sides, bonus, roll):
    """Maximize and Empower combine independently; Empower includes die bonuses."""
    mode = item_dice_metamagic(plan)
    if mode is None: raise ValueError('Unsupported integrated dice effects.')
    maximize, empower = mode
    rolls = [sides] * count if maximize and not empower else [roll(1, sides) for _ in range(count)]
    ordinary = sum(rolls) + bonus
    total = count * sides + bonus if maximize else ordinary
    if empower: total += ordinary // 2
    return rolls, total


def automatic_self_effect(plan):
    """Supported activation kind, independent of editable prose and Qt."""
    unsupported_drawbacks = any(row.get('source') != 'published' or row.get('catalog_key') != 'crafting:expensive'
                                for row in plan.get('drawbacks', []))
    if plan.get('unique_changes') or unsupported_drawbacks or plan.get('permanent') or item_dice_metamagic(plan) is None:
        return None
    if plan.get('base_power') == 'life:cure':
        return 'cure' if cure_healing_components(plan) is not None else None
    if plan.get('base_power') == 'protection:aegis':
        return 'aegis' if aegis_modifiers(plan) is not None else None
    if plan.get('base_power') == 'life:temporary-hp':
        return 'temporary_hp' if invigorate_temporary_hp(plan) is not None else None
    if plan.get('contributions'): return None
    return {'life:cure': 'cure', 'life:temporary-hp': 'temporary_hp', 'protection:aegis': 'aegis'}.get(plan.get('base_power'))


def restore_condition_changes(mode, conditions, *, ongoing=(), restore_health=False, restore_senses=False):
    """Reviewable Ultimate Restore transitions; ongoing sources need suppression.

    Results describe changes without altering persistence or losing provenance.
    Snapshot each starting condition once, so downgraded fear is not also removed.
    """
    transitions = {
        'mind': {'Dazzled': None, 'Shaken': None, 'Frightened': 'Shaken', 'Panicked': 'Frightened', 'Staggered': None},
        'body': {'Battered': None, 'Fatigued': None, 'Exhausted': 'Fatigued', 'Sickened': None, 'Nauseated': 'Sickened'},
    }
    if mode not in transitions: raise ValueError('Condition restoration requires mind or body.')
    if not isinstance(restore_health, bool) or not isinstance(restore_senses, bool):
        raise ValueError('Restore talent flags must be boolean.')
    if restore_health:
        transitions['body'].update(Exhausted=None, Nauseated=None)
    if restore_senses:
        transitions['mind'].update(Frightened=None, Panicked=None, Confused=None, Dazed=None,
                                   Blinded=None, Deafened=None)
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


def invigorate_temporary_hp(plan):
    """Reviewed Deeper Healing/Painkiller; other modified Invigorates stay manual."""
    contributions = plan.get('contributions', [])
    keys = [row.get('catalog_key') for row in contributions]
    if (any(key not in {'life:talent:deeper-healing', 'life:talent:painkiller'} for key in keys)
            or len(keys) != len(set(keys)) or any(row.get('alternative') for row in contributions)):
        return None
    return plan['caster_level'] * (2 if 'life:talent:deeper-healing' in keys else 1)


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
    if (plan.get('base_power') != 'destruction:blast' or destructive_blast_profile(plan) is None
            or plan.get('unique_changes', 0) or item_dice_metamagic(plan) is None):
        return None
    return resolve_base_power(plan)['damage_dice']


def resolve_base_power(plan):
    for field in ('caster_level', 'range_steps', 'duration_steps'):
        value = plan[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError('Base-power parameters must be integers.')
    if plan['caster_level'] < 1:
        raise ValueError('Item caster level must be positive.')
    for row in plan.get('contributions', []):
        choices = talent_effect_choices(row.get('catalog_key'))
        selected = row.get('effect_choice', '')
        if choices and selected != '' and selected not in choices:
            raise ValueError('Choose a supported effect option for ' + row['catalog_key'] + '.')
    key = plan.get('base_power')
    if key == 'warp:beacon':
        beacons = [row for row in plan.get('contributions', []) if row.get('catalog_key') == 'warp:space-talent:teleport-beacon-space']
        if (len(beacons) != 1 or beacons[0].get('alternative')
                or isinstance(beacons[0].get('additional_spell_points'), bool)
                or not isinstance(beacons[0].get('additional_spell_points'), int)
                or beacons[0]['additional_spell_points'] < 1):
            raise ValueError('Beacon placement requires one Teleport Beacon contribution and its one-SP cost.')
    restore_mode = plan.get('restore_mode', '')
    if restore_mode not in {'', 'mind', 'body', 'soul'} or (restore_mode and key != 'life:restore'):
        raise ValueError('Restore mode requires a Life restore base power.')
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
    mode = item_dice_metamagic(plan)
    if mode and any(mode): summary['dice_mode'] = ' + '.join(label for label, active in zip(('Maximized', 'Empowered'), mode) if active)
    if plan.get('permanent', False): summary['duration'] = 'Permanent (dispellable)'
    if power.key == 'life:temporary-hp':
        temporary = invigorate_temporary_hp(plan)
        summary['temporary_hp'] = cl if temporary is None else temporary
        if temporary is None:
            summary['temporary_hp_review'] = 'Base amount only; selected modifications require manual resolution.'
        elif any(row.get('catalog_key') == 'life:talent:painkiller' for row in plan.get('contributions', [])):
            summary['nonlethal_healing'] = temporary
    if power.key == 'life:restore':
        summary['restore_mode'] = restore_mode or 'Not selected; manual review required'
        if restore_mode in {'mind', 'body'}:
            names = ('Dazzled', 'Shaken', 'Frightened', 'Panicked', 'Staggered', 'Battered', 'Fatigued', 'Exhausted', 'Sickened', 'Nauseated',
                     'Confused', 'Dazed', 'Blinded', 'Deafened')
            # Alternative contributions are choices, not simultaneously active talents.
            keys = {row.get('catalog_key') for row in plan.get('contributions', []) if not row.get('alternative')}
            health = 'life:cure-talent:restore-health-cure' in keys
            senses = 'life:cure-talent:restore-senses-cure' in keys
            summary['restore_changes'] = restore_condition_changes(restore_mode, names, restore_health=health, restore_senses=senses)
            if restore_mode == 'body' and health:
                summary['poison_disease'] = f'Magic skill check +{cl} against each poison/disease DC; damage already suffered is not reversed.'
            if restore_mode == 'mind' and senses:
                summary['sense_restoration'] = 'Temporary or magical sense loss only; permanent loss requires additional effects. Optional sanity/strain recovery is manual.'
            summary['ongoing_conditions'] = f'Suppress for {cl} rounds instead of removing; source review required.'
        elif restore_mode == 'soul': summary['ability_damage'] = '1d4 to one chosen ability; manual recording required.'
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
    if power.key in {'protection:aegis', 'protection:ward'}:
        energy = 'protection:aegis-ward-talent:energy-resistance-aegis-ward'
        adaptation = 'protection:advanced-talent:adaptation-aegis'
        rows = [row for row in plan.get('contributions', []) if not row.get('alternative')]
        selected = next((row for row in rows if row.get('catalog_key') == adaptation), None)
        if selected is None:
            selected = next((row for row in rows if row.get('catalog_key') == energy), None)
        if selected is not None:
            choice = selected.get('effect_choice', '')
            if choice and choice not in talent_effect_choices(selected['catalog_key']):
                raise ValueError('Choose a supported energy type for this Protection effect.')
            kind = 'immunity' if selected['catalog_key'] == adaptation else 'resistance'
            summary['power'] = f'Energy {kind} ' + ('aegis' if power.key == 'protection:aegis' else 'ward')
            summary['energy_type'] = choice.title() if choice else 'Not selected; choose an energy type'
            summary['energy_protection'] = 'Immune' if kind == 'immunity' else str(10 + cl)
            if kind == 'immunity' and power.key != 'protection:aegis':
                raise ValueError('Adaptation grants an aegis, not a ward.')
        keys = {row.get('catalog_key') for row in rows}
        from app.marvelous_item_rules import spell_selectivity_options
        if options := spell_selectivity_options(plan):
            summary['spell_selectivity'] = ('Affects only ' if options['mode'] == 'only' else 'Affects all except ') + ', '.join(options['spheres']) if options['mode'] and options['spheres'] else 'Not configured; choose affected spheres and mode'
        if 'protection:aegis-ward-talent:spell-ward-aegis-ward' in keys:
            if power.key == 'protection:aegis':
                summary['power'] = 'Spell Ward aegis'
                summary['spell_resistance'] = 10 + cl
            else:
                summary['power'] = 'Spell Ward'
                summary['magic_skill_check'] = f'+{cl}; magical items resist with MSD 10 + their caster level.'
                summary['magic_skill_defense'] = 11 + cl
            if 'protection:advanced-talent:antimagic-aura' in keys:
                if power.key != 'protection:ward':
                    raise ValueError('Antimagic Aura modifies a Spell Ward ward, not its spell-resistance aegis.')
                summary['power'] = 'Antimagic Aura ward'
                summary['suppression'] = 'Stops magic and summoned creatures without a magic skill check; summoned creatures with SR still require a check against their SR.'
                summary.pop('magic_skill_check', None)
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
        profile = destructive_blast_profile(plan)
        if profile is None:
            summary['damage'] = 'Selected modifications require manual damage/type resolution.'
        else:
            name, damage_type, sides, _ = profile
            summary['power'] = name; summary['damage_type'] = damage_type
            summary['damage_die_size'] = sides
            summary['damage'] = f'{summary["damage_dice"]}d{sides} {damage_type}'
            if plan.get('contributions'):
                summary['secondary_effects'] = 'Resolve saves, secondary damage, conditions and target-specific defenses from the talent description manually.'
    if power.key == 'warp:teleport': summary['teleport_distance'] = distances[('close', 'medium', 'long')[effect_steps]]
    if power.key == 'warp:beacon':
        summary['target'] = 'One spot, object or creature; placement is manual.'
        summary['beacon'] = 'Creates a personal dimensional beacon. Travel to/from it is a separate teleport activation, on the same plane; unwilling creatures require Unwilling Teleport and a save.'
    if power.key == 'weather:control': summary['area_radius'] = distances[('close', 'medium', 'long')[effect_steps]]
    if power.key in {'blood:construct', 'death:reanimate'}: summary['maximum_hit_dice'] = cl
    if power.key == 'dark:darkness': summary['radius'] = f'{10 + 5 * (cl // 2)} ft.'
    if power.key == 'alteration:shapeshift': summary['traits'] = 1 + cl // 5
    return summary

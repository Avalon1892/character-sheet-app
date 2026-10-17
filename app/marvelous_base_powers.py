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
    ('enhancement:enhance', 'Enhancement', 'Enhance Equipment', 'touch', 'round'),
    ('fallen-fey:link', 'Fallen Fey', 'Fey-link / Nature-connection', 'personal', 'minute'),
    ('fate:serendipity', 'Fate', 'Serendipity', 'personal', 'round'),
    ('illusion:figment', 'Illusion', 'Silent visual illusion', 'touch', 'round'),
    ('life:cure', 'Life', 'Cure', 'touch', 'instantaneous'),
    ('life:restore', 'Life', 'Restore', 'touch', 'instantaneous'),
    ('life:temporary-hp', 'Life', 'Temporary hit points', 'touch', 'minute'),
    ('light:glow', 'Light', 'Bright glow', 'personal', 'minute'),
    ('light:lens', 'Light', 'Telescope lens', 'personal', 'minute'),
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
    ('warp:dimension-pierce', 'Warp', 'Dimension Pierce', 'touch', 'hour'),
    ('warp:fluctuate', 'Warp', 'Fluctuate', 'touch', 'concentration'),
    ('warp:blink', 'Warp', 'Blink', 'touch', 'concentration'),
    ('warp:create-gap', 'Warp', 'Create Gap', 'touch', 'concentration'),
    ('warp:distort-size', 'Warp', 'Distort Size', 'touch', 'concentration'),
    ('weather:control', 'Weather', 'Change one weather category', 'personal', 'round'),
)
BASE_POWERS = tuple(MarvelousBasePower(*row) for row in _ROWS)
RANGES = ('personal', 'touch', 'close', 'medium', 'long')
DURATIONS = ('round', 'minute', 'ten-minutes', 'hour')
ANTIMAGIC_AURA_KEYS = frozenset({'protection:advanced-talent:antimagic-aura',
                               'protection:advanced-talent:antimagic-aura-arcforge-addendum-lg'})

# Reviewed Ultimate blast types: name, damage, die size, additional SP.
DESTRUCTION_BLAST_TYPES = {
    'destruction:blast-type-talent:adhesive-blast-blast-type-acid': ('Adhesive Blast', 'acid', 6, 0),
    'destruction:blast-type-talent:alkali-blast-blast-type-acid': ('Alkali Blast', 'acid', 4, 0),
    'destruction:blast-type-talent:attracting-blast-blast-type-electric-lg': ('Attracting Blast', 'electricity', 6, 0),
    'destruction:blast-type-talent:battering-blast-blast-type-stone': ('Battering Blast', 'bludgeoning', 4, 0),
    'destruction:blast-type-talent:blistering-blast-blast-type-fire': ('Blistering Blast', 'fire', 6, 0),
    'destruction:blast-type-talent:drowning-blast-blast-type-cold': ('Drowning Blast', 'bludgeoning', 6, 1),
    'destruction:blast-type-talent:living-crystal-blast-blast-type-crystal': ('Living Crystal Blast', 'piercing', 6, 1),
    'destruction:blast-type-talent:numbing-blast-blast-type-cold': ('Numbing Blast', 'cold', 6, 0),
    'destruction:blast-type-talent:acid-blast-blast-type-acid': ('Acid Blast', 'acid', 6, 0),
    'destruction:blast-type-talent:crystal-blast-blast-type-crystal': ('Crystal Blast', 'piercing', 4, 0),
    'destruction:blast-type-talent:electric-blast-blast-type-electricity': ('Electric Blast', 'electricity', 6, 0),
    'destruction:blast-type-talent:fire-blast-blast-type-fire': ('Fire Blast', 'fire', 6, 0),
    'destruction:blast-type-talent:force-blast-blast-type-force': ('Force Blast', 'force', 6, 1),
    'destruction:blast-type-talent:frost-blast-blast-type-cold': ('Frost Blast', 'cold', 6, 0),
}
GUIDED_STRIKE_KEY = 'destruction:blast-shape-talent:guided-strike-blast-shape'
KNIGHTS_BLAST_KEY = 'destruction:blast-shape-talent:knight-s-blast-blast-shape-jester-s-hb'
GRANDMASTER_KEY = 'destruction:advanced-talent:grandmaster-jester-s-hb'
EXPLOSIVE_ORB_KEY = 'destruction:blast-shape-talent:explosive-orb-blast-shape'
BLAST_SALVO_KEY = 'destruction:blast-shape-talent:blast-salvo-blast-shape-bap'
SCULPT_BLAST_KEY = 'destruction:blast-shape-talent:sculpt-blast-blast-shape'
ENERGY_SPHERE_KEY = 'destruction:blast-shape-talent:energy-sphere-blast-shape'
ENERGY_WALL_KEY = 'destruction:blast-shape-talent:energy-wall-blast-shape'
ENERGY_ENHANCEMENT_KEY = 'enhancement:enhance-talent:energy-enhancement-enhance'
ALTERNATIVE_ENERGY_KEY = 'enhancement:advanced-talent:alternative-energy-jester-s-hb'
LIGHT_LENSES = {
    'light:lens-talent:aiming-scope-lens': 'Aiming Scope',
    'light:lens-talent:chameleon-lens': 'Chameleon',
    'light:lens-talent:dim-light-lens': 'Dim Light',
    'light:lens-talent:halo-effect-lens-utility': 'Halo Effect',
    'light:lens-talent:infravision-lens': 'Infravision',
    'light:lens-talent:obscure-lens': 'Obscure',
    'light:lens-talent:periscope-lens-utility': 'Periscope',
    'light:lens-talent:rose-tinted-lens-jester-s-hb': 'Rose-Tinted',
}
TELEKINESIS_LIFT_SIZES = (
    (1, 'Diminutive'), (3, 'Tiny'), (5, 'Small'), (8, 'Medium'), (11, 'Large'),
    (15, 'Huge'), (20, 'Gargantuan'), (25, 'Colossal'), (30, 'Colossal+'),
    (40, 'Colossal++'), (50, 'Colossal+++'), (60, 'Colossal++++'),
)
LIFE_VITALITY_EFFECTS = {
    'life:vitality-talent:aggressive-vitality-vitality': 'Weapon attack and damage rolls: +2 circumstance.',
    'life:vitality-talent:calming-vitality-vitality-warden': 'Concentration checks: +4 morale.',
    'life:vitality-talent:energizing-vitality-vitality': 'Existing movement speeds: +30 ft. circumstance; does not grant new movement modes.',
    'life:vitality-talent:high-on-vitality-vitality-jester-s-hb': 'Floats up to 6 inches above ground; ignores difficult terrain and ground hazards.',
    'life:vitality-talent:ruin-into-resurgence-vitality-3pp': 'For each 2 negative levels, 6 ability damage or 4 ability drain removed: +1 insight to ability checks, attacks, saves and skills, capped at +1 per 4 CL (minimum +1). Requires actual removal of those penalties.',
    'life:vitality-talent:securing-vitality-vitality-warden': 'CMB and CMD: +2 circumstance.',
    'life:vitality-talent:sustaining-vitality-vitality': 'AC and saving throws: +2 circumstance.',
}
TALENT_EFFECT_SP_CHOICES = {
    'creation:advanced-talent:dissolution-alter': {'unattended non-magical object': 1,
        'attended, magical or creature target': 2},
    # The required Change Material contribution already supplies the initial SP.
    'creation:advanced-talent:material-body-alter': {'concentration': 0,
        'sustained without concentration': 1},
    'creation:advanced-talent:fleshcraft-material': {'create or alter nonliving flesh': 0,
        'alter a living creature': 1},
    'creation:talent:altering-burst': {'ten-foot radius, half-size objects': 0,
        'twenty-foot radius, normal-size objects': 1},
    'creation:talent:restrictive-casing': {'non-harmful worn object': 0, 'full-body confinement cage': 1},
    'creation:material-talent:plasma-production-material': {'fire or burning object': 0, 'electricity': 1},
    'creation:talent:precise-destruction-utility': {'mundane device or lock': 0, 'magical trap': 1},
    'creation:alter-talent:magnify-minimize-alter': {'one size category': 0, 'additional size categories': 1},
    'creation:alter-talent:transparency-alter-utility': {'concentration': 0, 'minutes per caster level': 1},
    'creation:talent:mass-liquid-generation': {'five cubic feet per Small object': 0,
        '125 cubic feet of non-harmful liquid per Small object': 1},
    'creation:talent:potent-alteration': {'enhanced repair or destroy': 0,
        'affect magical, attended or construct target': 1},
    'time:talent:age-time': {'creature age with concentration': 1, 'creature age for minutes per caster level': 2},
    'time:talent:broken-time-time': {'concentration': 0, 'rounds per caster level': 1},
    'time:talent:rapid-response-time': {'concentration': 0, 'ten minutes per caster level': 1},
    'life:talent:adrenaline-surge': {'surge one ally': 1, 'surge multiple allies': 2},
    'life:talent:taste-of-victory': {'ordinary qualifying hit': 1, 'critical hit, unconscious or zero-HP target': 0},
    'life:talent:diagnose-utility': {'detect conditions': 0, 'condition details as standard action': 0,
        'condition details as swift action': 1},
    'enhancement:advanced-talent:inherent-enhancement-enhance-archmagi-s-hb': {
        'temporary untyped bonus: ' + ability: 1 for ability in (
            'Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma')},
    'telekinesis:advanced-talent:gravity-manipulation': {'concentration (2 SP total)': 2, 'Sustained Force (2 SP total)': 1},
    'telekinesis:talent:divided-mind-mass': {'multiple lifted objects': 0, 'multiple maneuver or push targets': 1},
    'telekinesis:talent:gravity-ward-well': {'concentration': 0, 'Sustained Force': 1},
    'telekinesis:talent:kinetic-sense': {'target without line of sight': 0, '30-foot blindsense': 1},
    'telekinesis:talent:tether': {'concentration': 0, 'Sustained Force': 1},
    'telekinesis:advanced-talent:focused-power': {'one additional size category': 1, 'two additional size categories': 2},
    'telekinesis:talent:telekinetic-push': {'aid movement or deflect': 0, 'direct push on hostile target': 1},
    'telekinesis:talent:gravity-shift': {'concentration': 0, 'Sustained Force': 1},
    'light:talent:doubled-nimbus': {'increase casting time one step': 0, 'spend SP instead of increasing casting time': 1},
    'light:talent:flash': {'choose application timing once per round': 0, 'swift-action additional application': 1},
    'light:talent:beacon-of-hope-light': {'target fear-save bonus': 0, 'fear recovery bright area': 1},
    'light:talent:blinding-light-light': {'dazzle glowing target': 0, 'blinding bright area': 1},
    'light:talent:disorienting-patterns-light': {'difficult terrain': 0, 'prone-inducing patterns': 1},
    'light:talent:purifying-light-light-crimdan': {'targeted purification': 0, 'purification bright area': 1},
    'light:talent:irradiance-light': {'sicken glowing target': 0, 'nauseating bright light': 1},
    'light:advanced-talent:star-genesis': {'expanded radius': 1, 'expanded radius with central daylight': 2},
    'enhancement:enhance-talent:energize-body-enhance': {'suppress fatigue / reduce exhaustion': 0, 'suppress exhaustion': 1},
    'enhancement:enhance-talent:ragged-edges-enhance': {'half caster level bleed': 0, 'caster level bleed': 1},
    'enhancement:enhance-talent:spectral-enhancement-enhance-gravecaller-s-hb': {
        'solid to incorporeal creatures': 0, 'ghost touch weapon': 0, 'ghost touch armor': 0,
        'empowered ghost touch weapon': 1, 'empowered ghost touch armor': 1},
    # Lighten's one SP is already included as a construction prerequisite.
    'enhancement:advanced-talent:reverse-gravity-enhance': {'concentration': 1, 'rounds per caster level': 2},
    'warp:space-talent:avert-space': {'readied standard action': 0, 'immediate action': 1, 'immediate action during total defense': 0},
    'warp:space-talent:blink-space': {'concentration': 0, 'minutes per caster level': 1,
        'penalty with concentration': 0, 'penalty for minutes per caster level': 1},
    'warp:space-talent:create-gap-space': {'concentration': 1, 'minutes per caster level': 2},
    'warp:space-talent:distort-size-space': {'concentration': 0, 'minutes per caster level': 1},
    'life:talent:greater-invigorate': {'normal HP limit': 0, 'exceed normal HP limit': 1},
    'time:talent:delay-pain-time': {'delay until next turn': 1, 'split damage across two turns': 2},
    'time:talent:time-bubble-time': {'time bubble only': 1, 'include Haste or Slow': 2},
    'time:advanced-talent:past-sight-utility': {'view hours': 1, 'view days': 2, 'view years': 3},
    'time:advanced-talent:shuffle-time-time-3pp': {'reroll initiative': 0, 'roll twice, take lower': 1},
    'warp:space-talent:fluctuate-space': {'concentration': 1, 'rounds per caster level': 2},
    'weather:talent:greater-weather': {'two weather categories': 1, 'three weather categories': 2},
    ENERGY_WALL_KEY: {'concentration cube': 0, 'straight wall': 1, 'hemisphere': 1},
    ENERGY_SPHERE_KEY: {'concentration': 0, 'rounds per caster level': 1},
    BLAST_SALVO_KEY: {'two surges': 0, 'additional surges': 1},
    SCULPT_BLAST_KEY: {'burst': 1, 'cone': 1, 'line': 1},
    EXPLOSIVE_ORB_KEY: {'single square': 0, 'expanded burst': 1},
    'destruction:advanced-talent:detonating-salvo-lg': {'5-foot radius explosions': 1, 'expanded explosions': 2},
}
TALENT_EFFECT_MINIMUM_CL = {
    ENERGY_ENHANCEMENT_KEY: {'weapon: sonic': 5, 'weapon: force': 10},
    'time:advanced-talent:past-sight-utility': {'view hours': 5, 'view days': 8, 'view years': 16},
}
DESTRUCTION_BLAST_SHAPES = {
    ENERGY_WALL_KEY: 'Energy Wall',
    ENERGY_SPHERE_KEY: 'Energy Sphere',
    GUIDED_STRIKE_KEY: 'Guided',
    KNIGHTS_BLAST_KEY: "Knight's",
    EXPLOSIVE_ORB_KEY: 'Explosive Orb',
    BLAST_SALVO_KEY: 'Salvo',
    SCULPT_BLAST_KEY: 'Sculpted',
    'destruction:blast-shape-talent:chain-blast-blast-shape': 'Chain',
    'destruction:blast-shape-talent:mutable-blast-blast-shape': 'Mutable',
}
SPACE_MODE_POWERS = {'warp:blink': 'warp:space-talent:blink-space',
    'warp:create-gap': 'warp:space-talent:create-gap-space',
    'warp:distort-size': 'warp:space-talent:distort-size-space'}


def destructive_blast_profile(plan):
    rows = plan.get('contributions', [])
    keys = [row.get('catalog_key') for row in rows]
    if any(row.get('alternative') for row in rows) or len(keys) != len(set(keys)): return None
    if any(row.get('catalog_key') in {EXPLOSIVE_ORB_KEY, BLAST_SALVO_KEY, SCULPT_BLAST_KEY, ENERGY_SPHERE_KEY, ENERGY_WALL_KEY}
           and row.get('effect_choice') not in talent_effect_choices(row['catalog_key'])
           for row in rows): return None
    if GRANDMASTER_KEY in keys:
        if KNIGHTS_BLAST_KEY not in keys: return None
        keys.remove(GRANDMASTER_KEY)
    shapes = [key for key in keys if key in DESTRUCTION_BLAST_SHAPES]
    if len(shapes) > 1: return None
    keys = [key for key in keys if key not in DESTRUCTION_BLAST_SHAPES]
    if not keys: return ('Bludgeoning destructive blast', 'bludgeoning', 6, 0)
    return DESTRUCTION_BLAST_TYPES.get(keys[0]) if len(keys) == 1 else None


ABILITY_ENHANCEMENT_CHOICES = {
    'enhancement:enhance-talent:physical-enhancement-enhance': ('Strength', 'Dexterity', 'Constitution',
        'Strength + Dexterity', 'Strength + Constitution', 'Dexterity + Constitution'),
    'enhancement:enhance-talent:mental-enhancement-enhance': ('Intelligence', 'Wisdom', 'Charisma',
        'Intelligence + Wisdom', 'Intelligence + Charisma', 'Wisdom + Charisma'),
}


def talent_effect_choices(key):
    """Reviewed construction choices, shared by the editor and projections."""
    if key in TALENT_EFFECT_SP_CHOICES:
        return tuple(TALENT_EFFECT_SP_CHOICES[key])
    if key in ABILITY_ENHANCEMENT_CHOICES:
        return ABILITY_ENHANCEMENT_CHOICES[key]
    if key == 'enhancement:enhance-talent:alter-movement-enhance':
        return ('increase one movement speed', 'halve all movement speeds')
    if key == 'enhancement:enhance-talent:enhance-focus-enhance':
        from app.models import SKILLS
        return tuple(skill.name for skill in SKILLS)
    if key == 'enhancement:enhance-talent:staunch-resistance-enhance':
        return ('Fortitude', 'Reflex', 'Will')
    if key == 'enhancement:enhance-talent:supply-vigor-enhance':
        return ('Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma')
    if key == 'enhancement:enhance-talent:harden-weaken-enhance':
        return ('increase hardness', 'decrease hardness', 'grant DR/adamantine', 'decrease bypassable DR')
    if key == ENERGY_ENHANCEMENT_KEY:
        return tuple('weapon: ' + energy for energy in ('acid', 'cold', 'electricity', 'fire', 'sonic', 'force')) + tuple(
            'consumable: ' + energy for energy in ('acid', 'cold', 'electricity', 'fire'))
    if key == 'enhancement:enhance-talent:deadly-weapon-enhance':
        return ('keen and critical confirmation', 'bypass DR: bludgeoning', 'bypass DR: cold iron',
                'bypass DR: piercing', 'bypass DR: silver', 'bypass DR: slashing')
    if key == 'enhancement:enhance-talent:ravenous-weapon-enhance-sm':
        return ('vicious weapon', 'damage wielder on a miss')
    if key == 'enhancement:enhance-talent:traveling-weapon-enhance':
        return ('non-throwing melee weapon: throwing and returning', 'ranged or throwing weapon: ignore cover')
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


def effective_base_duration(plan):
    """Duration before construction adjustments, including reviewed effect modes."""
    power = next((power for power in BASE_POWERS if power.key == plan.get('base_power')), None)
    if power is None: return 'instantaneous'
    if power.key == 'creation:create' and any(row.get('catalog_key') == 'creation:talent:practiced-creation'
            and not row.get('alternative') for row in plan.get('contributions', [])):
        return 'concentration'
    if power.key in SPACE_MODE_POWERS:
        selected = next((row for row in plan.get('contributions', []) if row.get('catalog_key') == SPACE_MODE_POWERS[power.key]), {})
        return 'minute' if 'minutes per caster level' in selected.get('effect_choice', '') else 'concentration'
    if power.key == 'warp:fluctuate':
        selected = next((row for row in plan.get('contributions', []) if row.get('catalog_key') == 'warp:space-talent:fluctuate-space'), {})
        return 'round' if selected.get('effect_choice') == 'rounds per caster level' else 'concentration'
    if power.key == 'creation:alter':
        rows = plan.get('contributions', [])
        body = 'creation:advanced-talent:material-body-alter'
        body_keys = {body, 'creation:alter-talent:change-material-alter', 'creation:material-talent:expanded-materials-material'}
        if (len(rows) == 3 and {row.get('catalog_key') for row in rows} == body_keys
                and not any(row.get('alternative') for row in rows)):
            choice = next(row.get('effect_choice') for row in rows if row.get('catalog_key') == body)
            if choice in TALENT_EFFECT_SP_CHOICES[body]:
                return 'concentration' if choice == 'concentration' else 'minute'
        if len(rows) == 1 and not rows[0].get('alternative'):
            key, choice = rows[0].get('catalog_key'), rows[0].get('effect_choice')
            if choice in TALENT_EFFECT_SP_CHOICES.get(key, {}):
                if key == 'creation:alter-talent:magnify-minimize-alter': return 'minute'
                if key == 'creation:alter-talent:transparency-alter-utility':
                    return 'concentration' if choice == 'concentration' else 'minute'
    if power.key == 'destruction:blast' and destructive_blast_profile(plan):
        persistent = next((row for row in plan.get('contributions', []) if row.get('catalog_key') in {ENERGY_SPHERE_KEY, ENERGY_WALL_KEY}), None)
        if persistent: return 'concentration' if persistent['effect_choice'] in {'concentration', 'concentration cube'} else 'round'
    return power.duration


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


def life_per_target_plan(plan):
    """Mass changes targeting, not each target's cure/invigorate amount."""
    rows = plan.get('contributions', [])
    mass = [row for row in rows if row.get('catalog_key') == 'life:talent:mass-healing-mass']
    if len(mass) == 1 and not mass[0].get('alternative'):
        return dict(plan, contributions=[row for row in rows if row is not mass[0]])
    return plan


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
    if key in SPACE_MODE_POWERS:
        talent = SPACE_MODE_POWERS[key]
        name = next(power.name for power in BASE_POWERS if power.key == key)
        selected = [row for row in plan.get('contributions', []) if row.get('catalog_key') == talent]
        if len(selected) != 1 or selected[0].get('alternative'):
            raise ValueError(f'{name} requires one fixed {name} talent contribution.')
        choices = TALENT_EFFECT_SP_CHOICES[talent]
        minimum = choices.get(selected[0].get('effect_choice'), min(choices.values()))
        points = selected[0].get('additional_spell_points', 0)
        if isinstance(points, bool) or not isinstance(points, int) or points < minimum:
            raise ValueError(f'{name} requires its {"one-SP" if minimum == 1 else str(minimum) + "-SP"} cost.')
    if key == 'warp:beacon':
        beacons = [row for row in plan.get('contributions', []) if row.get('catalog_key') == 'warp:space-talent:teleport-beacon-space']
        if (len(beacons) != 1 or beacons[0].get('alternative')
                or isinstance(beacons[0].get('additional_spell_points'), bool)
                or not isinstance(beacons[0].get('additional_spell_points'), int)
                or beacons[0]['additional_spell_points'] < 1):
            raise ValueError('Beacon placement requires one Teleport Beacon contribution and its one-SP cost.')
    if key == 'warp:dimension-pierce':
        selected = [row for row in plan.get('contributions', []) if row.get('catalog_key') == 'warp:space-talent:dimension-pierce-space']
        if (len(selected) != 1 or selected[0].get('alternative')
                or isinstance(selected[0].get('additional_spell_points'), bool)
                or not isinstance(selected[0].get('additional_spell_points'), int)
                or selected[0]['additional_spell_points'] < 1):
            raise ValueError('Dimension Pierce requires its talent contribution and one-SP cost.')
    if key == 'warp:fluctuate':
        selected = [row for row in plan.get('contributions', []) if row.get('catalog_key') == 'warp:space-talent:fluctuate-space']
        if (len(selected) != 1 or selected[0].get('alternative')
                or isinstance(selected[0].get('additional_spell_points'), bool)
                or not isinstance(selected[0].get('additional_spell_points'), int)
                or selected[0]['additional_spell_points'] < 1):
            raise ValueError('Fluctuate requires its talent contribution and one-SP cost.')
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
    duration = effective_base_duration(plan)
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
    if any(row.get('catalog_key') == 'warp:advanced-talent:time-warp-jester-s-hb' for row in plan.get('contributions', [])):
        summary['time_travel'] = f'Up to {100 * cl:,} years forward or backward, within True Teleport range; destination familiarity, mishaps and timeline consequences require GM resolution.'
        summary['spell_point_accounting'] = 'Time Warp costs 5 SP total: 2 SP from the integrated True Teleport prerequisite plus 3 additional SP. Other teleport modifiers may add costs separately.'
    if power.key in {'time:haste', 'time:slow'}:
        rows = plan.get('contributions', [])
        keys = {row.get('catalog_key') for row in rows}
        supported = {'time:talent:improved-haste', 'time:talent:improved-slow', 'time:talent:augment-healing',
                     'time:talent:mass-time-mass', 'time:advanced-talent:temporal-haste'}
        haste = power.key == 'time:haste'
        if (any(row.get('alternative') for row in rows) or len(keys) != len(rows) or keys - supported
                or ('time:advanced-talent:temporal-haste' in keys and (not haste or 'time:talent:improved-haste' not in keys))
                or ('time:talent:improved-haste' in keys and not haste)
                or ('time:talent:improved-slow' in keys and haste)):
            summary['power'] = 'Modified Time effect — manual resolution'
            summary['time_effect_review'] = 'Selected talents may replace the base effect; resolve their statistics, duration and targeting from the rules text.'
        else:
            bonus = 1 + cl // 10
            if haste:
                summary['attack_bonus'] = bonus
                summary['dodge_bonus_to_ac_and_reflex'] = bonus
                summary['movement_enhancement_bonus'] = f'+{10 + 10 * (cl // 5)} ft. to all movement modes'
                if 'time:talent:improved-haste' in keys:
                    summary['improved_haste'] = f'One extra highest-BAB attack during a full attack OR {1 + cl // 5} extra attacks of opportunity per round; not both. Does not stack with similar effects. Resolve manually.'
                if 'time:advanced-talent:temporal-haste' in keys:
                    summary['temporal_haste'] = 'One additional move or swift action each round, not an immediate action; resolve manually.'
                if 'time:talent:augment-healing' in keys: summary['fast_healing'] = 1 + cl // 5
            else:
                summary['attack_ac_and_reflex_penalty'] = -bonus
                summary['movement'] = 'All movement speeds halved, minimum 5 ft.'
                summary['saving_throw'] = 'Will negates'
                if 'time:talent:improved-slow' in keys: summary['condition'] = 'Staggered'
                if 'time:talent:augment-healing' in keys:
                    summary['healing_suppression'] = 'Stops natural healing, fast healing and suppressible regeneration; other magical/extraordinary healing still functions. Resolve manually.'
            if 'time:talent:mass-time-mass' in keys: summary['maximum_targets'] = 1 + max(1, cl // 2)
    if power.key == 'life:temporary-hp':
        temporary = invigorate_temporary_hp(life_per_target_plan(plan))
        summary['temporary_hp'] = cl if temporary is None else temporary
        if temporary is None:
            summary['temporary_hp_review'] = 'Base amount only; selected modifications require manual resolution.'
            rows = life_per_target_plan(plan).get('contributions', [])
            keys = [row.get('catalog_key') for row in rows]
            greater = 'life:talent:greater-invigorate'
            if (greater in keys and len(keys) == len(set(keys))
                    and not any(row.get('alternative') for row in rows)
                    and set(keys) <= {greater, 'life:talent:deeper-healing', 'life:talent:painkiller'}):
                selected = next(row for row in rows if row['catalog_key'] == greater)
                base = cl * (2 if 'life:talent:deeper-healing' in keys else 1)
                summary['temporary_hp_formula'] = f'{base} + applicable casting ability modifier (requires rules verification for this item; not the crafter’s live modifier)'
                mode = selected.get('effect_choice')
                summary['temporary_hp_limit'] = ('May exceed the target’s normal HP maximum.' if mode == 'exceed normal HP limit'
                    else 'Cannot exceed the target’s normal HP maximum.' if mode == 'normal HP limit'
                    else 'Choose the Greater Invigorate effect mode.')
        elif any(row.get('catalog_key') == 'life:talent:painkiller' for row in plan.get('contributions', [])):
            summary['nonlethal_healing'] = temporary
    if power.key in {'life:cure', 'life:restore', 'life:temporary-hp'}:
        life_keys = {row.get('catalog_key') for row in plan.get('contributions', [])}
        if 'life:talent:adrenaline-surge' in life_keys:
            summary['adrenaline_surge'] = 'Other allies only: immediate attack, movement, Escape Artist check (+CL), ready/draw/pick up equipment, or stand. Multiple surges require a Life effect already affecting multiple allies; resolve in initiative order.'
        if 'life:talent:taste-of-victory' in life_keys:
            summary['taste_of_victory'] = 'Requires an attack-roll hit against a creature with at least half the user\'s Hit Dice. Swift Life use costs +1 SP, waived for a critical hit, unconscious victim or victim reduced to 0 HP. Verify trigger and item activation manually.'
        if 'life:talent:violent-recuperation-alienist-hb' in life_keys:
            summary['violent_recuperation'] = 'After incoming damage is fully negated by DR, resistance or immunity, permits immediate Life use at normal SP cost. The same damage effect cannot trigger it again for one minute; verify eligibility manually.'
        if 'life:talent:diagnose-utility' in life_keys:
            summary['diagnose_review'] = 'Diagnose is a separate diagnostic use, not extra healing. Detects conditions as a swift action; details require a standard action or +1 SP for swift use. Resolve examination and item activation separately.'
        vitality = [row for row in plan.get('contributions', []) if row.get('catalog_key') in LIFE_VITALITY_EFFECTS]
        if vitality:
            summary['vitality_limits'] = 'Only one vitality benefit per target. Lasts up to one minute from application, ending when the target takes damage after a failed save or an attack hit. Apply benefits and expiration manually.'
            if any(row.get('catalog_key') == 'life:talent:lingering-vitality-warden' and not row.get('alternative')
                   for row in plan.get('contributions', [])):
                summary['vitality_damage_expiration'] = 'Lingering Vitality delays damage-triggered expiration by one additional round; resolve manually.'
            if len(vitality) == 1 and not vitality[0].get('alternative'):
                summary['vitality_benefit'] = LIFE_VITALITY_EFFECTS[vitality[0]['catalog_key']]
            else:
                summary['vitality_selection'] = 'Choose one eligible vitality benefit for each target; these talents do not stack together on a target.'
        mass = [row for row in plan.get('contributions', []) if row.get('catalog_key') == 'life:talent:mass-healing-mass']
        if len(mass) == 1 and not mass[0].get('alternative'):
            summary['maximum_targets'] = 1 + max(1, cl // 2)
            summary['targeting'] = 'Every target must be in range and receive the same Life effect; resolve the group manually.'
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
            if ANTIMAGIC_AURA_KEYS.intersection(keys):
                if power.key != 'protection:ward':
                    raise ValueError('Antimagic Aura modifies a Spell Ward ward, not its spell-resistance aegis.')
                summary['power'] = 'Antimagic Aura ward'
                summary['suppression'] = 'Stops magic and summoned creatures without a magic skill check; summoned creatures with SR still require a check against their SR.'
                summary.pop('magic_skill_check', None)
        if 'protection:aegis-ward-talent:technological-suppression-aegis-ward-lg' in keys:
            summary['magic_skill_defense'] = 11 + cl
            summary['power'] = 'Technological Suppression ' + ('aegis' if power.key == 'protection:aegis' else 'ward')
            if power.key == 'protection:aegis':
                if 'protection:advanced-talent:antimagic-aura-arcforge-addendum-lg' in keys:
                    raise ValueError('Antimagic Aura modifies a technological ward, not its aegis.')
                summary['technology_protection'] = 'Technological conditions and non-physical damage require a gizmo penetration check against this MSD; resolve manually.'
            else:
                summary['technology_check'] = f'Magic skill check +{cl}; item DC = craft DC − 4; creature DC = 10 + CR. Resolve charge use and affected creatures manually.'
                if 'protection:advanced-talent:antimagic-aura-arcforge-addendum-lg' in keys:
                    summary['power'] = 'Antimagic Aura technological ward'
                    summary['technology_check'] = 'Stops technological abilities and charge use without a check; constructs/cyborgs with SR still require a check against their SR.'
            if 'protection:aegis-ward-talent:spell-ward-aegis-ward' in keys:
                summary['power'] = 'Combined magical/technological protection — manual resolution'
    if power.key == 'telekinesis:force':
        rows = plan.get('contributions', [])
        keys = [row.get('catalog_key') for row in rows]
        allowed = {f'telekinesis:talent:{suffix}' for suffix in (
            'powerful-telekinesis', 'greater-speed', 'acceleration', 'divided-mind-mass',
            'flight', 'dampening-field', 'finesse-utility')}
        divided = next((row for row in rows if row.get('catalog_key') == 'telekinesis:talent:divided-mind-mass'), None)
        supported = (len(keys) == len(set(keys)) and not any(row.get('alternative') for row in rows)
            and set(keys) <= allowed and (divided is None or divided.get('effect_choice') == 'multiple lifted objects'))
        if supported:
            index = max(index for index, (minimum, _) in enumerate(TELEKINESIS_LIFT_SIZES) if cl >= minimum)
            index += int('telekinesis:talent:powerful-telekinesis' in keys)
            size = TELEKINESIS_LIFT_SIZES[index][1] if index < len(TELEKINESIS_LIFT_SIZES) else '1 size category above Colossal++++'
            speed = 30 + 5 * (cl // 2) if 'telekinesis:talent:greater-speed' in keys else 20 + 5 * (cl // 5)
            summary['maximum_lift_size'] = size
            summary['telekinesis_speed'] = f'{speed} ft.'
            summary['lifting_limits'] = 'Size assumes dense material. Lighter/half-weight targets count one size smaller; weightless targets count two smaller. Resolve actual target size and eligibility manually.'
            summary['bludgeon_resolution'] = 'Damage depends on the actual lifted object, not automatically the maximum lift size; resolve attacks and target defenses manually.'
            if 'telekinesis:talent:acceleration' in keys:
                summary['straight_line_movement'] = f'{speed * 2} ft.'
                summary['charge_bonus'] = 'After at least 10 ft. of straight-line movement, a Bludgeon counts as charging (+2 attack); resolve charge eligibility manually.'
            if divided is not None:
                summary['maximum_lifted_targets'] = 1 + cl
                summary['combined_size_limit'] = 'All lifted targets together must fit the maximum lift size; count them as one effective object or resolve allowed separate attacks manually.'
            if 'telekinesis:talent:flight' in keys:
                summary['granted_fly_speed'] = f'{speed} ft. (perfect)'
                summary['flight_control'] = 'The lifted creature controls its movement during the Sustained Force and need not remain within telekinesis range. Apply movement manually.'
            if 'telekinesis:talent:dampening-field' in keys:
                summary['lifted_object_hardness_bonus'] = 1 + cl // 5
                summary['lifted_object_deflection_ac_bonus'] = 1 + cl // 5
                summary['lifted_creature_damage_reduction'] = f'{cl // 2}/piercing'
                summary['dampening_limits'] = 'Lifted objects ignore broken-condition penalties; the object may avoid self-damage as a Bludgeon. Apply the creature/object benefits only to eligible targets.'
            if 'telekinesis:talent:finesse-utility' in keys:
                summary['remote_skill_penalty'] = -5
                summary['fine_manipulation'] = 'Allows appropriate remote object-related skills and first aid, but not take 10; attended-object/Sleight of Hand uses need Steal. Resolve skills and applicable item casting modifier manually.'
        else:
            summary['power'] = 'Modified telekinesis — manual resolution'
            summary['telekinesis_review'] = 'Resolve the selected talents, targeting, concentration and final duration from their rules; the item base duration alone does not verify these interactions.'
        if 'telekinesis:advanced-talent:focused-power' in keys:
            summary['concentration_review'] = 'Focused Power cannot use Sustained Force. Its concentration/base-effect conversion needs rules review before construction.'
    if power.key == 'light:lens':
        rows = plan.get('contributions', [])
        lenses = [row for row in rows if row.get('catalog_key') in LIGHT_LENSES]
        if not rows:
            summary['sight_perception_bonus'] = f'+{2 + cl // 5} circumstance'
            summary['perception_distance_increment'] = f'{10 + 10 * cl} ft. per +1 DC'
        elif len(rows) == len(lenses) == 1 and not lenses[0].get('alternative'):
            name = LIGHT_LENSES[lenses[0]['catalog_key']]
            summary['power'] = name + ' lens'
            if name == 'Aiming Scope':
                summary['ranged_attack_competence_bonus'] = 1 + cl // 10
                summary['ignored_range_increments'] = 1 + cl // 10
            elif name == 'Halo Effect':
                summary['bluff_diplomacy_circumstance_bonus'] = 2 + cl // 4
                summary['communication_limits'] = 'Only against creatures seeing the target with normal or low-light vision; Perform applicability requires GM approval.'
            elif name == 'Obscure':
                summary['defensive_uses_per_round'] = 1 + cl // 10
                summary['defense'] = 'Before an attack roll, force two rolls and use the lower. No effect on attackers relying solely on nonvisual senses or unable to see the target.'
            elif name == 'Rose-Tinted':
                summary['burst_area'] = '30-foot cone or 60-foot line'
                summary['burst_effect'] = 'Reflex save or blinded 1 round and dazzled 1 minute; wait 1d4 rounds between bursts.'
                summary['ending_burst_fire_damage'] = f'{cl}d4 fire on failed Reflex save if the lens is ended as part of the burst'
            else:
                summary['lens_resolution'] = 'Use the selected lens rules below; target-specific values and special senses are resolved manually.'
                if name == 'Chameleon': summary['casting_modifier_review'] = 'Uses the applicable item casting ability modifier; do not substitute the character’s modifier automatically.'
            summary['application'] = 'Lens effect only; does not emit the bright-glow area. Apply to the target manually.'
        else:
            summary['power'] = 'Modified lens — manual resolution'
            summary['lens_resolution'] = 'Resolve multiple, alternative or additional lens modifications from their rules; no single-lens statistics are assumed.'
    if power.key == 'light:glow':
        from app.marvelous_item_rules import advanced_construction_blockers
        rows = plan.get('contributions', [])
        keys = [row.get('catalog_key') for row in rows]
        irradiance = 'light:talent:irradiance-light'
        radiation = 'light:advanced-talent:radiation-light'
        daylight = 'light:advanced-talent:daylight-light'
        star = 'light:advanced-talent:star-genesis'
        intensity = 'light:talent:intensity-control'
        supported = (len(keys) == len(set(keys)) and not any(row.get('alternative') for row in rows)
            and set(keys) <= {irradiance, radiation, daylight, star, intensity}
            and not advanced_construction_blockers(rows, cl)
            and not (daylight in keys and (irradiance in keys or star in keys))
            and not (intensity in keys and star not in keys))
        if supported:
            radius = 30 + 5 * (cl // 2)
            summary['sunlight'] = 'Bright light is not equivalent to daylight for creatures harmed by daylight.'
            star_choice = next((row.get('effect_choice', '') for row in rows if row.get('catalog_key') == star), '')
            if star in keys:
                if not star_choice: summary['mode_review'] = 'Choose the Star Genesis mode before construction.'
                else:
                    radius += 25 + 5 * (cl // 2)
                    if star_choice == 'expanded radius with central daylight':
                        summary['daylight_equivalent_radius'] = f'{30 + 5 * (cl // 2)} ft.'
                        summary['sunlight'] = 'Only the central daylight-equivalent radius counts as daylight; the rest is ordinary bright light.'
            summary['bright_light_radius'] = f'{radius} ft.'
            summary['illumination_extension'] = f'Increase light level by one step (maximum normal) for {radius} ft. beyond the bright radius.'
            if daylight in keys:
                summary['power'] = 'Daylight — expanded bright light'
                summary['bright_light_radius'] = '2 miles'
                summary['illumination_extension'] = 'Normal light for 5 miles beyond the bright radius.'
            if irradiance in keys:
                summary['power'] = 'Radiation' if radiation in keys else 'Irradiance'
                choice = next(row.get('effect_choice', '') for row in rows if row.get('catalog_key') == irradiance)
                if not choice: summary['mode_review'] = 'Choose the Irradiance mode before construction.'
                elif choice == 'sicken glowing target':
                    summary['condition'] = 'The glowing creature is sickened: −2 to attack rolls, weapon damage, saves, skills and ability checks.'
                else:
                    summary['condition'] = 'Creatures in the bright area: Fortitude save each round; failure nauseates for 1 round, success still sickens for that round.'
                    if radiation in keys:
                        summary['radiation_exposure'] = 'Failed nausea saves also inflict low radiation. This source cannot stack with itself to raise radiation severity.'
                summary['condition_resolution'] = 'Resolve target eligibility, saving throws, conditions and radiation manually.'
        else:
            summary['power'] = 'Modified light — manual resolution'
            summary['light_resolution'] = 'Resolve the selected Light effects, area and talent interactions from their rules; the base bright-light area is not assumed.'
        for row in rows:
            if row.get('alternative'): continue
            key, choice = row.get('catalog_key'), row.get('effect_choice')
            if key == 'light:talent:doubled-nimbus':
                if choice == 'increase casting time one step':
                    summary['activation_review'] = 'Increase the glow casting time by one step; verify the item activation manually. The chosen activation is not silently rewritten.'
                elif choice == 'spend SP instead of increasing casting time':
                    summary['nimbus_timing'] = 'The paid option does not increase casting time. Overlapping nimbus areas do not apply effects twice.'
            elif key == 'light:talent:flash':
                if choice == 'choose application timing once per round':
                    summary['light_application_timing'] = 'Choose the application point during your turn as a free action, still only once per round.'
                elif choice == 'swift-action additional application':
                    summary['light_application_timing'] = 'One additional application as a swift action; no area or creature can be affected more than once per round. Resolve timing manually.'
    if power.key == 'enhancement:enhance':
        rows = plan.get('contributions', [])
        keys = [row.get('catalog_key') for row in rows]
        if 'enhancement:talent:flash-of-excellence-sm' in keys:
            summary['flash_of_excellence_review'] = 'One SP buys immediate-action enhancement with a one-round maximum duration. The ordinary item activation and duration are not automatically converted; verify this construction before use.'
        if 'enhancement:talent:power-parasitism-alienist-hb' in keys:
            summary['power_parasitism_trigger'] = 'Requires successful ability damage, drain or an ability-score penalty against a target with at least half the user\'s Hit Dice. One additional SP permits a swift-action enhancement on a willing target. Verify the trigger and item activation manually.'
        if 'enhancement:talent:ranged-enhancement-range' in keys:
            summary['ranged_enhancement_review'] = 'The talent adds no spell-point cost. Its caster-range progression is not automatically substituted for the item-specific range ladder; verify the chosen item range.'
        greater = 'enhancement:talent:greater-enhance-equipment'
        mass = 'enhancement:talent:mass-enhancement-mass'
        mode_powers = {
            ENERGY_ENHANCEMENT_KEY: 'Energy Enhancement',
            'enhancement:enhance-talent:deadly-weapon-enhance': 'Deadly Weapon',
            'enhancement:enhance-talent:ravenous-weapon-enhance-sm': 'Ravenous Weapon',
            'enhancement:enhance-talent:traveling-weapon-enhance': 'Traveling Weapon',
            'enhancement:enhance-talent:enhance-focus-enhance': 'Enhance Focus',
            'enhancement:enhance-talent:staunch-resistance-enhance': 'Staunch Resistance',
            'enhancement:enhance-talent:supply-vigor-enhance': 'Supply Vigor',
            'enhancement:enhance-talent:harden-weaken-enhance': 'Harden/Weaken',
            'enhancement:enhance-talent:improved-flexibility-enhance': 'Improved Flexibility',
            'enhancement:enhance-talent:superior-poison-enhance': 'Superior Poison',
            'enhancement:enhance-talent:alter-movement-enhance': 'Alter Movement',
            'enhancement:enhance-talent:cripple-enhance': 'Cripple',
            'enhancement:enhance-talent:superior-reflexes-enhance': 'Superior Reflexes',
            'enhancement:enhance-talent:energize-body-enhance': 'Energize Body',
            'enhancement:enhance-talent:ragged-edges-enhance': 'Ragged Edges',
            'enhancement:enhance-talent:spectral-enhancement-enhance-gravecaller-s-hb': 'Spectral Enhancement',
        }
        ability_rows = [row for row in rows if row.get('catalog_key') in {
            'enhancement:enhance-talent:physical-enhancement-enhance',
            'enhancement:enhance-talent:mental-enhancement-enhance'}]
        ability = ability_rows[0] if len(ability_rows) == 1 else None
        mode_rows = [row for row in rows if row.get('catalog_key') in mode_powers]
        selected = mode_rows[0] if len(mode_rows) == 1 else None
        allowed = {mass, 'enhancement:talent:deep-enhancement',
                   ability['catalog_key'] if ability else selected['catalog_key'] if selected else greater}
        dual = 'enhancement:talent:dual-enhancement'
        if ability: allowed.add(dual)
        if selected and selected['catalog_key'] == ENERGY_ENHANCEMENT_KEY: allowed.add(ALTERNATIVE_ENERGY_KEY)
        paired = bool(ability and ability.get('effect_choice') in ABILITY_ENHANCEMENT_CHOICES[ability['catalog_key']][3:])
        advanced_energy = bool(selected and selected['catalog_key'] == ENERGY_ENHANCEMENT_KEY
            and selected.get('effect_choice') in TALENT_EFFECT_MINIMUM_CL[ENERGY_ENHANCEMENT_KEY])
        supported = (len(keys) == len(set(keys)) and not any(row.get('alternative') for row in rows)
                     and set(keys) <= allowed and not (paired and dual not in keys)
                     and not (advanced_energy and (ALTERNATIVE_ENERGY_KEY not in keys or
                         cl < TALENT_EFFECT_MINIMUM_CL[ENERGY_ENHANCEMENT_KEY][selected['effect_choice']])))
        if supported:
            if ability:
                summary['power'] = 'Physical Enhancement' if 'physical-enhancement' in ability['catalog_key'] else 'Mental Enhancement'
                choice = ability.get('effect_choice', '')
                if choice:
                    summary['ability_score'] = choice
                    summary['ability_enhancement_bonus'] = 2 + 2 * (cl // 7)
                else:
                    summary['mode_review'] = 'Choose the ability score before construction.'
                summary['stacking'] = 'Temporary enhancement bonus to the chosen ability score; does not stack with other enhancement bonuses and does not rewrite the base score.'
            elif selected:
                key, choice = selected['catalog_key'], selected.get('effect_choice', '')
                summary['power'] = mode_powers[key]
                if talent_effect_choices(key) and choice not in talent_effect_choices(key):
                    summary['mode_review'] = 'Choose the effect mode before construction.'
                elif summary['power'] == 'Energy Enhancement':
                    target, energy = choice.split(': ', 1)
                    summary['energy_type'] = energy
                    if target == 'weapon':
                        summary['additional_energy_damage'] = f'1d6+{cl // 2} {energy}'
                        summary['energy_resolution'] = 'Equivalent elemental weapon property; apply to the enhanced weapon manually. Does not change its base damage.'
                    else:
                        summary['additional_energy_damage'] = f'{cl} {energy}'
                        summary['energy_resolution'] = 'Consumable, splash weapon or poison: applies on consumption, direct/splash damage, or a poison hit even if its save succeeds. Resolve manually.'
                elif summary['power'] == 'Deadly Weapon':
                    if choice == 'keen and critical confirmation':
                        summary['weapon_property'] = 'Keen, only if not already present; resolve threat-range stacking manually.'
                        summary['critical_confirmation_bonus'] = cl // 3
                    else:
                        summary['bypassed_damage_reduction'] = choice.removeprefix('bypass DR: ')
                    summary['weapon_resolution'] = 'Apply to the selected weapon manually; this does not add a permanent enchantment.'
                elif summary['power'] == 'Ravenous Weapon':
                    if choice == 'vicious weapon': summary['weapon_property'] = 'Vicious; resolve its normal damage to target and wielder manually.'
                    else: summary['wielder_damage_on_miss'] = f'{1 + cl // 4}d6 untyped'
                elif summary['power'] == 'Traveling Weapon':
                    if choice == 'non-throwing melee weapon: throwing and returning':
                        summary['weapon_properties'] = 'Throwing and returning; applies to a melee weapon that does not already have throwing.'
                    else:
                        summary['ignored_cover_ac_bonus'] = 2 + 2 * (cl // 7)
                        summary['cover_limits'] = 'Only ranged/throwing weapons or ammunition; does not bypass total cover.'
                    summary['weapon_resolution'] = 'Confirm the weapon category and apply manually.'
                elif summary['power'] == 'Enhance Focus':
                    summary['skill'] = choice
                    summary['skill_enhancement_bonus'] = 5 + cl // 4
                    summary['skill_targeting'] = 'Apply to the chosen skill manually; Craft, Perform and Profession require a specific specialty. Does not grant ranks or training.'
                elif summary['power'] == 'Staunch Resistance':
                    summary['saving_throw'] = choice
                    summary['untyped_save_bonus'] = 2 + cl // 5
                    summary['save_resolution'] = 'Apply only to the chosen saving throw, not all three.'
                elif summary['power'] == 'Supply Vigor':
                    summary['ability_score'] = choice
                    summary['ignored_existing_ability_damage_drain_penalty'] = 2 + 2 * (cl // 7)
                    summary['incoming_ability_damage_drain_reduction'] = 1 + cl // 7
                    summary['vigor_limits'] = 'Does not prevent ability damage/drain paid as a cost. Suppresses rather than heals existing damage, drain or penalties; apply manually.'
                elif summary['power'] == 'Harden/Weaken':
                    if choice in {'increase hardness', 'decrease hardness'}:
                        summary['hardness_adjustment'] = cl if choice == 'increase hardness' else -cl
                        if choice == 'decrease hardness': summary['fragile'] = 'The object gains fragile if it does not already have it.'
                    elif choice == 'grant DR/adamantine':
                        summary['damage_reduction'] = f'{max(1, cl // 2)}/adamantine'
                    else:
                        summary['damage_reduction_decrease'] = max(1, cl // 2)
                        summary['dr_limits'] = 'Only bypassable DR can be reduced; DR/— is unaffected.'
                    summary['hardening_resolution'] = 'Apply the selected change to the target manually; existing target hardness/DR is not assumed.'
                elif summary['power'] == 'Improved Flexibility':
                    summary['escape_artist_actions'] = 'One-minute checks become full-round actions; full-round checks become standard actions.'
                    if cl >= 6: summary['narrow_spaces'] = 'Ignore squeezing penalties and move at full speed.'
                    if cl >= 12: summary['tight_spaces'] = 'Move at full speed without losing Dexterity to AC.'
                    if cl >= 18: summary['minimum_space'] = 'Escape Artist can squeeze through any space that fits one fist.'
                    summary['flexibility_resolution'] = 'Resolve checks and available space manually.'
                elif summary['power'] == 'Superior Poison':
                    summary['additional_successful_saves_to_cure'] = 1
                    summary['poison_target'] = 'One dose of poison; adds to its required cure saves rather than increasing its DC. Resolve poison manually.'
                elif summary['power'] == 'Alter Movement':
                    if choice == 'increase one movement speed':
                        summary['movement_speed_bonus'] = f'+{10 * (1 + cl // 5)} ft. enhancement'
                        summary['movement_skill_bonus'] = 2 * (1 + cl // 5)
                        summary['movement_skill_scope'] = 'Enhancement bonus to Acrobatics, Climb, Fly or Swim checks while using the chosen speed.'
                        summary['movement_target'] = 'Choose an existing movement speed on the target; this does not grant a new movement mode. Apply manually.'
                    else:
                        summary['movement_multiplier'] = 'Half of every movement speed, minimum 5 ft.'
                        summary['five_foot_steps'] = 'Provoke attacks of opportunity unless an Acrobatics check succeeds against the enhancer’s MSD; resolve manually.'
                elif summary['power'] == 'Cripple':
                    summary['roll_penalty'] = -(2 + cl // 5)
                    summary['penalty_scope'] = 'All attack rolls, saving throws, ability checks and skill checks; apply to the target manually.'
                elif summary['power'] == 'Superior Reflexes':
                    summary['initiative_bonus'] = 1 + (cl - 1) // 4
                    summary['additional_attacks_of_opportunity'] = 1 + (cl - 1) // 4
                    summary['flat_footed_attacks_of_opportunity'] = 'Allowed; resolve attacks and initiative manually.'
                elif summary['power'] == 'Energize Body':
                    summary['condition_suppression'] = ('Suppress exhausted for the duration.' if choice == 'suppress exhaustion'
                        else 'Suppress fatigued or reduce exhausted to fatigued for the duration.')
                    summary['condition_limits'] = 'Conditions still count for effects that inflict fatigue/exhaustion; sleeping targets wake. Resolve conditions manually.'
                    summary['carrying_capacity_multiplier'] = 2 + cl // 5
                    summary['endurance'] = f'Add {cl} to Constitution only for breath-holding and running duration.'
                elif summary['power'] == 'Ragged Edges':
                    summary['additional_bleed_damage'] = cl if choice == 'caster level bleed' else max(1, cl // 2)
                    summary['bleed_resolution'] = 'Attacks with the enhanced weapon inflict this additional bleed; resolve hits, bleed and stacking manually.'
                else:
                    summary['spectral_mode'] = choice
                    summary['spectral_resolution'] = 'Resolve equipment eligibility, object size limits, incorporeal interaction and any escape save manually.'
                    if choice == 'empowered ghost touch weapon':
                        summary['undead_incorporeal_hit'] = 'Will save or sickened for 1 round, bypassing sickened immunity.'
                    elif choice == 'empowered ghost touch armor':
                        summary['negative_energy_resistance'] = cl // 2
                        summary['possession_negative_energy_save_bonus'] = 2 + cl // 5
                        summary['save_bonus_type'] = 'Circumstance'
            else:
                bonus = min(5, 1 + cl // 4)
                if greater in keys: bonus = min(6, 2 + cl // 4)
                summary['equipment_enhancement_bonus'] = bonus
                summary['equipment_targets'] = 'One weapon, suit of armor, shield, or up to 50 pieces of ammunition grouped in one container/quiver.'
                summary['stacking'] = 'Does not stack with existing enhancement bonuses; use the higher bonus. This is a temporary effect, not a permanent item enchantment.'
            if mass in keys:
                summary['maximum_targets'] = 1 + max(1, cl // 2)
                summary['targeting'] = 'Every target must be in range and receive the same enhancement and chosen ability (if applicable); each is a separate effect. Resolve target selection manually.'
        else:
            summary['power'] = 'Modified enhancement — manual resolution'
            summary['enhancement_resolution'] = 'Resolve the chosen enhancement and talent interactions from their rules; the basic equipment bonus is not assumed.'
    if power.key == 'life:cure':
        healing = cure_healing_components(life_per_target_plan(plan))
        if healing is not None:
            dice, bonus = healing
            summary['healing'] = f'{dice}d8+{bonus}'
            summary['healing_dice'] = dice; summary['healing_bonus'] = bonus
        else:
            summary['healing'] = f'Base 1d8+{cl}; selected modifications require manual resolution'
        rows = life_per_target_plan(plan).get('contributions', [])
        keys = [row.get('catalog_key') for row in rows]
        revitalize = 'life:talent:revitalize'
        if revitalize in keys:
            cure_talents = {'life:cure-talent:restore-capacity-cure', 'life:cure-talent:restore-health-cure',
                'life:cure-talent:restore-senses-cure', 'life:cure-talent:restore-spirit-cure'}
            count = keys.count(revitalize)
            supported = (count in (1, 2) and len(keys) - count == len(set(keys) - {revitalize})
                and set(keys) <= cure_talents | {revitalize} and not any(row.get('alternative') for row in rows))
            summary.pop('healing', None)
            summary['revitalize_limits'] = 'Replaces direct cure healing with fast healing; no immediate healing roll. Does not count as cure for Fount of Life or similar interactions. Resolve ongoing recovery manually.'
            if supported:
                amount = 1 + len(set(keys) & cure_talents)
                summary['power'] = 'Revitalize'
                summary['fast_healing'] = amount
                summary['duration'] = f'{cl} ' + ('minutes' if count == 1 else 'hours')
                if count == 2: summary['maximum_total_healing'] = 10 * cl * amount
                summary['fast_healing_stacking'] = 'Does not add to another fast-healing source; the target chooses which source benefits it each round.'
            else:
                summary['power'] = 'Modified Revitalize — manual resolution'
                summary['revitalize_review'] = 'Resolve the selected modifiers and duration from their rules; no automatic fast-healing amount is assumed.'
    if power.key == 'creation:create':
        rows = plan.get('contributions', [])
        keys = [row.get('catalog_key') for row in rows]
        larger, divided = 'creation:talent:larger-creation', 'creation:talent:divided-creation-mass'
        detail, force = 'creation:talent:exquisite-detail-utility', 'creation:material-talent:object-of-force-material'
        expanded = 'creation:material-talent:expanded-materials-material'
        if (len(keys) == len(set(keys)) and not any(row.get('alternative') for row in rows)
                and set(keys) <= {larger, divided, detail, force, expanded, 'creation:talent:practiced-creation'} and not {force, expanded} <= set(keys)):
            units = cl * (2 if larger in keys else 1)
            sizes = ((1, 'Small'), (2, 'Medium'), (4, 'Large'), (8, 'Huge'),
                (16, 'Gargantuan'), (32, 'Colossal'), (64, 'Colossal+'))
            summary['creation_capacity_small_objects'] = units
            summary['maximum_object_size'] = next(size for minimum, size in reversed(sizes) if units >= minimum)
            if units >= 128:
                summary['maximum_object_size'] = 'Beyond Colossal+; consult the full size table'
            summary['object_count'] = ('Multiple same-general-type objects sharing the total size capacity.' if divided in keys
                else 'One object; size capacity does not itself grant multiple objects.')
            summary['materials'] = ('Force' if force in keys else 'Expanded Materials; check the material and CL requirements manually.' if expanded in keys
                else 'Vegetable matter such as wood, hemp or cotton.')
            if force in keys:
                summary['force_object_hardness'] = cl
                summary['force_object_hp_per_inch'] = 10
                summary['force_object_weight'] = 'Weightless; may be anchored. Disappears when broken. Not the weight of the crafting device.'
            summary['craft_review'] = ('Detailed objects require their appropriate Craft checks; no automatic success.' if detail in keys
                else 'Complex objects require Craft checks; normal DC15 creation limit applies.')
            if 'creation:talent:practiced-creation' in keys:
                summary['practiced_creation'] = 'One-step slower casting reduces the casting SP cost by one (minimum zero); the object requires concentration. Only extra-SP complexity is discounted, not the fixed item base complexity.'
        else:
            summary['power'] = 'Modified creation — manual resolution'
            summary['creation_review'] = 'Resolve size, material, target and duration interactions from the integrated talents; no generic maximum object is assumed.'
    if power.key == 'creation:alter':
        rows = plan.get('contributions', [])
        potent = 'creation:talent:potent-alteration'
        if not rows:
            summary['repair_or_destroy'] = f'1d4+{cl // 2} object HP; Destroy bypasses hardness.'
        elif len(rows) == 1 and rows[0].get('catalog_key') == potent and not rows[0].get('alternative'):
            summary['repair_or_destroy'] = f'1d6+{cl} object HP; Destroy bypasses hardness.'
            summary['target_review'] = 'Check the selected Potent Alteration mode and target eligibility; artifacts cannot be altered, and expended charges are not restored.'
        elif (len(rows) == 1 and not rows[0].get('alternative')
                and rows[0].get('effect_choice') in TALENT_EFFECT_SP_CHOICES.get(rows[0].get('catalog_key'), {})
                and rows[0].get('catalog_key') in {'creation:alter-talent:magnify-minimize-alter', 'creation:alter-talent:transparency-alter-utility'}):
            key, choice = rows[0]['catalog_key'], rows[0]['effect_choice']
            if key == 'creation:alter-talent:magnify-minimize-alter':
                summary['power'] = 'Magnify / Minimize'
                summary['maximum_size_category_steps'] = 1 if choice == 'one size category' else 2 + cl // 5
                summary['size_limits'] = 'Fine through Colossal. Each step doubles/halves height and width and multiplies/divides weight by eight. Apply to the actual target manually.'
                summary['worn_equipment_review'] = 'Resized worn equipment can encumber, break or fall off; resolve its actual fit and material rules manually.'
            else:
                summary['power'] = 'Transparency'
                summary['unmodified_transparency_duration_limit'] = f'{cl} minutes'
                summary['larger_object_area_square_feet'] = 2 * cl
                summary['maximum_penetration_feet'] = cl
                summary['one_way_perception_penalty'] = -4
                summary['one_way_detection_dc'] = 15
                summary['transparency_limits'] = 'May affect an object within creation size, or the listed area of a larger object. Changes visibility, not composition or hardness; resolve line of sight and target eligibility manually.'
        else:
            summary['power'] = 'Modified alteration — manual resolution'
            summary['alteration_review'] = 'The selected talent may replace Repair/Destroy entirely; resolve its effect and duration, not a generic HP roll.'
    if power.key in {'creation:create', 'creation:alter'}:
        rows = plan.get('contributions', [])
        keys = [row.get('catalog_key') for row in rows]
        alchemical, divided = 'creation:material-talent:alchemical-creation-material', 'creation:talent:divided-creation-mass'
        if (alchemical in keys and len(keys) == len(set(keys)) and set(keys) <= {alchemical, divided}
                and not any(row.get('alternative') for row in rows)
                and (divided not in keys or power.key == 'creation:create')):
            summary['power'] = 'Alchemical Creation' if power.key == 'creation:create' else 'Enhance Mundane Alchemical Item'
            if cl == 14:
                summary['alchemical_value_review'] = 'Needs rules verification: at CL14 the text formula gives 1,050 gp but the published table lists 1,150 gp. Confirm the limit with the GM.'
            else:
                maximum = 25 * cl * (1 + cl // 5)
                summary['maximum_alchemical_value_gp'] = maximum
                if divided in keys: summary['maximum_combined_alchemical_value'] = f'{maximum / 2:g} gp'
            summary['alchemical_statistics'] = 'DC = 10 + applicable item casting modifier + half CL; HP damage adds that modifier. The item modifier is not assumed to equal the crafter’s live modifier.'
            summary['alchemical_limits'] = 'Use a normal alchemical item or poison; Spheres of Might Alchemy formulae and poisons are excluded. No items or doses are added automatically.'
            if divided in keys:
                summary['divided_alchemy'] = 'Combined size must fit creation capacity; each item counts as Small. Only one item gains the improved DC/damage; the others retain normal statistics.'
            if power.key == 'creation:alter':
                summary['alchemical_duration_review'] = 'Potency enhancement lasts for normal created-object duration, then returns to normal; verify item duration conversion. Does not stack with other DC increases.'
    if power.key == 'creation:alter':
        rows = plan.get('contributions', [])
        dissolution, potent = 'creation:advanced-talent:dissolution-alter', 'creation:talent:potent-alteration'
        body = 'creation:advanced-talent:material-body-alter'
        if (len(rows) == 3 and {row.get('catalog_key') for row in rows} == {
                body, 'creation:alter-talent:change-material-alter', 'creation:material-talent:expanded-materials-material'}
                and not any(row.get('alternative') for row in rows)
                and next(row.get('effect_choice') for row in rows if row.get('catalog_key') == body) in TALENT_EFFECT_SP_CHOICES[body]):
            summary['power'] = 'Material Body'
            summary['target'] = 'One willing creature touched'
            summary['material_defense'] = 'DR equals the chosen solid material’s hardness; adamantine bypasses it when hardness is below 20. Select a material you can create and resolve its hardness manually.'
            summary['material_body_limit'] = f'Ends after preventing damage equal to material HP per inch × {cl // 3}. Track prevented damage manually.'
            summary['unmodified_concentration_limit'] = f'{cl} minutes'
        selected = next((row for row in rows if row.get('catalog_key') == dissolution), {})
        prerequisite = next((row for row in rows if row.get('catalog_key') == potent), {})
        mode = selected.get('effect_choice')
        expected = {'unattended non-magical object': 'enhanced repair or destroy',
            'attended, magical or creature target': 'affect magical, attended or construct target'}.get(mode)
        if (len(rows) == 2 and {row.get('catalog_key') for row in rows} == {dissolution,potent}
                and not any(row.get('alternative') for row in rows) and expected
                and prerequisite.get('effect_choice') == expected):
            summary['power'] = 'Dissolution'
            if mode == 'unattended non-magical object':
                summary['disintegration_volume'] = 'Up to one 10-foot cube of nonliving matter; no HP damage roll.'
            else:
                summary['failed_fortitude_damage'] = f'{2 * cl}d6'
                summary['successful_fortitude_damage'] = f'1d6+{cl}'
                summary['dissolution_damage_rules'] = 'Bypasses hardness, resistances and DR; a target reduced to 0 HP is disintegrated. Resolve targeting, saves, damage and destruction manually.'
    if power.key == 'destruction:blast':
        summary['damage_dice'] = cl if boost else cl // 2
        profile = destructive_blast_profile(plan)
        if profile is None:
            summary['power'] = 'Modified destructive blast — manual resolution'
            summary['damage'] = 'Selected modifications require manual damage/type resolution.'
        else:
            name, damage_type, sides, _ = profile
            summary['power'] = name; summary['damage_type'] = damage_type
            summary['damage_die_size'] = sides
            summary['damage'] = f'{summary["damage_dice"]}d{sides} {damage_type}'
            shape = next((row['catalog_key'] for row in plan.get('contributions', [])
                          if row.get('catalog_key') in DESTRUCTION_BLAST_SHAPES), None)
            if shape:
                summary['power'] = DESTRUCTION_BLAST_SHAPES[shape] + ' ' + name
            if shape == GUIDED_STRIKE_KEY:
                summary['attack_circumstance_bonus'] = 20
            elif shape == ENERGY_SPHERE_KEY:
                summary['area'] = 'One 5-foot square'
                summary['fly_speed'] = f'{20 + 5 * (cl // 2)} ft. (perfect)'
                summary['saving_throw'] = 'Reflex negates'
                summary['movement'] = 'Move action to direct; must remain within blast range. Targeting, concentration and expiration are manual.'
            elif shape == ENERGY_WALL_KEY:
                choice = next(row['effect_choice'] for row in plan['contributions'] if row.get('catalog_key') == shape)
                summary['area'] = {'concentration cube': '5-foot cubic wall',
                    'straight wall': f'Straight wall up to 20 ft. high and {20 * cl} ft. wide',
                    'hemisphere': f'Hemisphere radius up to {max(5, 5 * (cl // 2))} ft.'}[choice]
                summary['saving_throw'] = 'Reflex avoids damage when created in an occupied space; creatures passing through take damage normally.'
                summary['geometry'] = 'Must fit fully within blast range; does not block sight, line of effect or projectiles. Placement, concentration and expiration are manual.'
            elif shape == EXPLOSIVE_ORB_KEY:
                choice = next(row['effect_choice'] for row in plan['contributions'] if row.get('catalog_key') == shape)
                summary['area'] = 'One 5-foot square' if choice == 'single square' else f'Burst radius up to {10 + 5 * (cl // 5)} ft.'
                summary['saving_throw'] = 'Reflex negates' if choice == 'single square' else 'Reflex half'
            elif shape == BLAST_SALVO_KEY:
                choice = next(row['effect_choice'] for row in plan['contributions'] if row.get('catalog_key') == shape)
                summary['maximum_surges'] = min(summary['damage_dice'], 2 if choice == 'two surges' else 3 + cl // 6)
                summary['damage_distribution'] = 'Distribute the total blast dice among simultaneous surges, at least one die per surge. Resolve each touch attack manually; damage dice are not multiplied by the number of surges.'
            elif shape == SCULPT_BLAST_KEY:
                choice = next(row['effect_choice'] for row in plan['contributions'] if row.get('catalog_key') == shape)
                summary['area'] = {'burst': f'Burst radius {10 + 5 * (cl // 5)} ft.',
                                   'cone': f'Cone {25 + 5 * (cl // 2)} ft.',
                                   'line': f'Line {100 + 10 * cl} ft.'}[choice]
                summary['geometry'] = 'Emanates from the user but excludes the user; Extended Range and similar effects do not enlarge this shape. Placement is manual.'
                summary['saving_throw'] = 'Reflex half'
            elif shape == KNIGHTS_BLAST_KEY:
                close = 25 + 5 * (cl // 2)
                grandmaster = any(row.get('catalog_key') == GRANDMASTER_KEY for row in plan.get('contributions', []))
                summary['maximum_path_length'] = f'{close * 3 / 2:g} ft.'
                summary['maximum_turns'] = cl if grandmaster else 1
                summary['geometry'] = ('Change direction up to 90 degrees per turn; placement is manual.' if grandmaster
                                       else f'A line up to {close} ft., then a 90-degree turn extending half the first segment again; excludes the user. Placement is manual.')
                summary['saving_throw'] = 'Reflex half'
            elif shape == 'destruction:blast-shape-talent:chain-blast-blast-shape':
                summary['maximum_targets'] = max(2, 1 + cl // 2)
                summary['maximum_jump_distance'] = f'{10 + 5 * (cl // 5)} ft.'
                summary['attack_resolution'] = 'Resolve ranged touch attacks in order; the chain stops when a target takes no damage.'
            elif shape == 'destruction:blast-shape-talent:mutable-blast-blast-shape':
                summary['maximum_cubes'] = 5 + cl // 2
                summary['geometry'] = 'Contiguous 5-foot cubes; at least one cube must be adjacent to the user. Placement is manual.'
                summary['saving_throw'] = 'Reflex half'
            if any(row.get('catalog_key') in DESTRUCTION_BLAST_TYPES for row in plan.get('contributions', [])):
                summary['secondary_effects'] = 'Resolve saves, secondary damage, conditions and target-specific defenses from the talent description manually.'
    if power.key == 'warp:teleport': summary['teleport_distance'] = distances[('close', 'medium', 'long')[effect_steps]]
    if power.key == 'warp:create-gap':
        summary['maximum_cubes'] = 1 + cl // 4
        summary['geometry'] = 'Contiguous 5-foot cubes in an inanimate object; does not damage the object or change structural integrity. Placement is manual.'
        summary['saving_throw'] = 'Reflex to move safely to the edge if the gap would cause a creature to fall.'
        summary['expiration'] = 'Occupants are shunted when the gap ends; resolve available space and any resulting damage manually.'
    if power.key == 'warp:distort-size':
        summary['space_adjustment'] = f'Up to {5 * (1 + cl // 4)} ft. larger or smaller.'
        summary['size_rules'] = 'Changes occupied space, not size category, damage, reach value or size modifiers; reach originates from the new space. Below a 5-foot cube, halve space per remaining step, rounding down to the nearest half foot (minimum 1-foot cube).'
        summary['adjustment_action'] = 'Swift action each turn or part of concentration; the caster may grant control to the target. Resolve positioning manually.'
    if power.key == 'warp:blink':
        selected = next(row for row in plan['contributions'] if row.get('catalog_key') == 'warp:space-talent:blink-space')
        penalty = selected.get('effect_choice', '').startswith('penalty')
        summary['target'] = 'One touched creature.'
        summary['miss_chance'] = f'{min(50, 20 + 5 * (cl // 3))}%'
        summary['blink_effect'] = ('The target suffers this miss chance on its attacks; Will negates.' if penalty
            else 'Attacks against the target suffer this miss chance.')
        if not selected.get('effect_choice'):
            summary['mode_review'] = 'Choose the Blink effect mode before construction.'
        summary['exceptions'] = 'Does not affect force or effects crossing coterminous planes (including ghost touch); does not stack with other blink/incorporeal miss chances. Resolve attacks manually.'
        if len(plan['contributions']) != 1:
            summary['effect_review'] = 'Blink base values shown; additional talent interactions require manual resolution.'
    if power.key == 'warp:beacon':
        summary['target'] = 'One spot, object or creature; placement is manual.'
        summary['beacon'] = 'Creates a personal dimensional beacon. Travel to/from it is a separate teleport activation, on the same plane; unwilling creatures require Unwilling Teleport and a save.'
    if power.key == 'warp:dimension-pierce':
        summary['target'] = 'One touched creature or object.'
        summary['planar_interaction'] = 'The creature can interact with ethereal/incorporeal targets without their normal 50% miss chance or reduced damage; an ethereal/incorporeal target can interact corporeally. An object gains ghost touch. Resolve target-specific interactions manually.'
    if power.key == 'warp:fluctuate':
        summary['target'] = 'One touched creature.'
        summary['teleport_distance'] = f'{10 + 5 * (cl // 4)} ft.'
        summary['teleport_action'] = 'The target may teleport as a swift action each turn; resolve movement manually.'
        selected = next(row for row in plan['contributions'] if row.get('catalog_key') == 'warp:space-talent:fluctuate-space')
        if not selected.get('effect_choice'): summary['mode_review'] = 'Choose concentration or rounds-per-caster-level mode before construction.'
    if power.key == 'weather:control':
        summary['area_radius'] = distances[('close', 'medium', 'long')[effect_steps]]
        rows = plan.get('contributions', [])
        keys = [row.get('catalog_key') for row in rows]
        greater = 'weather:talent:greater-weather'
        severe = 'weather:talent:severe-weather'
        climate = 'weather:advanced-talent:climate'
        lords = {f'weather:advanced-talent:{talent}-lord': category for talent, category in (
            ('cold', 'Cold'), ('heat', 'Heat'), ('desert', 'Aridity'), ('rain', 'Precipitation'), ('wind', 'Wind'))}
        supported_keys = {greater, severe, *lords}
        if climate in keys: supported_keys |= {climate, 'weather:talent:greater-size-range'}
        supported = (not any(row.get('alternative') for row in rows) and len(keys) == len(set(keys))
                     and set(keys) <= supported_keys
                     and not (climate in keys and (effect_steps or 'weather:talent:greater-size-range' not in keys)))
        choice = next((row.get('effect_choice', '') for row in rows if row.get('catalog_key') == greater), '')
        if not supported or (greater in keys and not choice):
            summary['power'] = 'Modified weather effect — manual resolution'
            summary['weather_resolution'] = 'Resolve the selected talents, weather categories, severity and area from their rules; the base radius above is not a resolved modified area.'
        else:
            count = {'two weather categories': 2, 'three weather categories': 3}.get(choice, 1)
            summary['power'] = power.name if count == 1 else f'Change {count} weather categories'
            summary['weather_categories'] = count
            summary['weather_resolution'] = 'Choose categories and severity changes independently; apply weather consequences manually.'
            limit = min(7, 3 + cl // 7) + (1 if severe in keys else 0)
            summary['maximum_severity'] = min(7, limit)
            if limit > 7: summary['excess_severity_bonus'] = limit - 7
            for talent, category in lords.items():
                if talent in keys:
                    summary[category.lower() + '_severity_limit'] = min(7, limit + 1)
                    if limit + 1 > 7: summary[category.lower() + '_excess_severity_bonus'] = limit - 6
            if set(keys).intersection(lords):
                summary['calm_eye'] = 'May leave a central area up to 80 feet in diameter unaffected by the matching lord’s weather category; place manually.'
            if limit > 7 or (limit == 7 and set(keys).intersection(lords)):
                summary['excess_severity'] = 'Severity stays at 7; each effective step above 7 adds +1 to associated weather numbers, DCs and penalties. Resolve those consequences manually.'
            if 'weather:advanced-talent:wind-lord' in keys:
                summary['wind_control'] = 'May turn wind up to 90 degrees and create updrafts, downdrafts or rotation. Detailed tornado-path control requires Tornado Lord.'
            if severe in keys: summary['severity_adjustment'] = 'One additional severity level, maximum severity 7.'
            if climate in keys:
                summary['area_radius'] = '2 miles'
                summary['casting_requirement'] = '20 minutes of focused casting before weather changes begin to manifest; resolve this requirement manually, without a timer.'
                summary['tornadoes'] = 'Severity-7 winds can create tornadoes; Climate alone does not control their paths.'
    if power.key == 'enhancement:enhance':
        inherent_key = 'enhancement:advanced-talent:inherent-enhancement-enhance-archmagi-s-hb'
        rows = plan.get('contributions', [])
        inherent = [row for row in rows if row.get('catalog_key') == inherent_key]
        if inherent:
            summary['inherent_ritual_review'] = 'Only the temporary untyped-bonus mode is modeled here. The separate instantaneous inherent-bonus ritual (five SP, one hour, 25,000 gp per +1, maximum +5) is not included in this item quote.'
            required = {'enhancement:talent:deep-enhancement',
                'enhancement:enhance-talent:mental-enhancement-enhance',
                'enhancement:enhance-talent:physical-enhancement-enhance', inherent_key}
            keys = [row.get('catalog_key') for row in rows]
            choice = inherent[0].get('effect_choice', '')
            if (len(keys) == len(set(keys)) and set(keys) == required
                    and not any(row.get('alternative') for row in rows)
                    and choice in TALENT_EFFECT_SP_CHOICES[inherent_key] and cl >= 17):
                summary['power'] = 'Temporary Untyped Ability Enhancement'
                summary['ability_score'] = choice.removeprefix('temporary untyped bonus: ')
                summary['ability_untyped_bonus'] = 2 + 2 * (cl // 7)
                summary['stacking'] = 'Temporary untyped bonus; stacks with a separate normal enhancement bonus. Does not permanently rewrite the base ability score.'
                summary['maximum_duration'] = f'{cl} rounds'
                summary['duration_review'] = 'Cannot exceed one round per caster level or become permanent; Deep Enhancement does not extend this limit.'
    if power.key in {'blood:construct', 'death:reanimate'}: summary['maximum_hit_dice'] = cl
    if power.key == 'dark:darkness': summary['radius'] = f'{10 + 5 * (cl // 2)} ft.'
    if power.key == 'alteration:shapeshift': summary['traits'] = 1 + cl // 5
    return summary

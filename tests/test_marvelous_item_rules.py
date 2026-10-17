import pytest
from fractions import Fraction

from app.marvelous_item_rules import effect_complexity, marvelous_crafting_quote, marvelous_item_price
from app.marvelous_item_rules import marvelous_requirements


TELEKINESIS_ADVANCED_REQUIREMENTS = {
    'affix': (10, ('telekinesis:advanced-talent:effortless-telekinesis', 'telekinesis:talent:idle-concentration')),
    'astral-affixation': (15, ('telekinesis:advanced-talent:affix', 'telekinesis:advanced-talent:effortless-telekinesis', 'telekinesis:talent:idle-concentration')),
    'brutalizing-bludgeon-lg': (5, ('telekinesis:talent:telekinetic-maneuver',)),
    'choking-grasp': (15, ('telekinesis:talent:telekinetic-crush',)),
    'disperse-force': (10, ('telekinesis:talent:quick-reactions', 'telekinesis:talent:telekinetic-push')),
    'effortless-telekinesis': (10, ()),
    'focused-power': (5, ('telekinesis:talent:powerful-telekinesis',)),
    'gravity-manipulation': (15, ('telekinesis:talent:gravity-shift',)),
    'linear-acceleration': (10, ('telekinesis:talent:acceleration', 'telekinesis:talent:greater-speed')),
    'puppet': (10, ('telekinesis:talent:finesse-utility', 'telekinesis:talent:telekinetic-maneuver')),
}


def test_every_bundled_advanced_telekinesis_talent_has_explicit_dependencies():
    from app.content import DEFAULT_CATALOG
    entries = [entry for entry in DEFAULT_CATALOG.magic_entries('Telekinesis') if entry['category'] == 'Advanced Talent']
    assert {entry['key'] for entry in entries} == {'telekinesis:advanced-talent:' + suffix for suffix in TELEKINESIS_ADVANCED_REQUIREMENTS}


@pytest.mark.parametrize('suffix,requirement', TELEKINESIS_ADVANCED_REQUIREMENTS.items())
def test_telekinesis_advanced_dependencies_are_integrated_once_and_level_gated(suffix, requirement):
    from app.marvelous_item_rules import (ADVANCED_CONSTRUCTION_REQUIREMENTS,
        missing_construction_prerequisites, advanced_construction_blockers)
    key = 'telekinesis:advanced-talent:' + suffix
    minimum, required = requirement
    assert ADVANCED_CONSTRUCTION_REQUIREMENTS[key] == requirement
    rows = [dict(catalog_key=key)]
    missing = missing_construction_prerequisites(rows)
    assert len(missing) == len(set(missing))
    assert set(required) <= set(missing)
    rows.extend(dict(catalog_key=child) for child in missing)
    assert not missing_construction_prerequisites(rows)
    assert not advanced_construction_blockers(rows, minimum)
    assert advanced_construction_blockers(rows, minimum - 1)


@pytest.mark.parametrize('suffix,points', [('affix',2), ('astral-affixation',1), ('choking-grasp',2),
    ('disperse-force',1), ('linear-acceleration',2), ('puppet',1), ('brutalizing-bludgeon-lg',0),
    ('effortless-telekinesis',0), ('focused-power',1)])
def test_reviewed_telekinesis_advanced_sp_defaults(suffix, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert talent_construction_spell_points(magic_entry('telekinesis:advanced-talent:' + suffix), reviewed_only=True) == points


@pytest.mark.parametrize('suffix,total', [('affix',2), ('astral-affixation',3), ('disperse-force',2),
    ('linear-acceleration',2), ('puppet',1), ('choking-grasp',2)])
def test_telekinesis_integrated_default_sp_totals_do_not_duplicate_dependencies(suffix, total):
    from app.content import magic_entry
    from app.marvelous_item_rules import missing_construction_prerequisites, talent_construction_spell_points
    key = 'telekinesis:advanced-talent:' + suffix
    keys = [key, *missing_construction_prerequisites([dict(catalog_key=key)])]
    points = [talent_construction_spell_points(magic_entry(child), reviewed_only=True) for child in keys]
    assert None not in points
    assert sum(points) == total


def test_every_bundled_telekinesis_talent_has_reviewed_sp_metadata():
    from app.content import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points
    entries = [entry for entry in DEFAULT_CATALOG.magic_entries('Telekinesis') if 'Talent' in entry['category']]
    assert entries
    assert not [entry['key'] for entry in entries if talent_construction_spell_points(entry, reviewed_only=True) is None]


@pytest.mark.parametrize('suffix,points', [
    *((name,1) for name in ('homing', 'kinetic-field', 'pantomime-cage-jester-s-hb')),
    *((name,0) for name in ('dampening-field', 'dancing-weapon', 'excessive-force-bap', 'flight',
        'floating-shield', 'forceful-telekinesis', 'increased-range-range', 'mobile-bludgeon',
        'orbit', 'parry', 'return', 'seizing-strike-strike-3pp', 'steal', 'sweeping-bludgeons-bap',
        'telekinetic-tools', 'whirlwind-assembly')),
])
def test_remaining_ordinary_telekinesis_defaults_match_catalog(suffix, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = magic_entry('telekinesis:talent:' + suffix)
    assert entry is not None
    assert talent_construction_spell_points(entry, reviewed_only=True) == points


@pytest.mark.parametrize('mode,child_mode,parent_sp,child_sp', [
    ('concentration (2 SP total)', 'concentration', 2, 0),
    ('Sustained Force (2 SP total)', 'Sustained Force', 1, 1),
])
def test_gravity_manipulation_replaces_instead_of_adding_to_shift_cost(mode, child_mode, parent_sp, child_sp):
    from app.marvelous_item_rules import (talent_choice_spell_points, missing_required_construction_modes,
        advanced_construction_blockers, quote_marvelous_blueprint)
    parent, child = 'telekinesis:advanced-talent:gravity-manipulation', 'telekinesis:talent:gravity-shift'
    assert talent_choice_spell_points(parent, mode) == parent_sp
    assert talent_choice_spell_points(child, child_mode) == child_sp
    rows = [dict(catalog_key=parent, effect_choice=mode, complexity=2 + parent_sp, additional_spell_points=parent_sp),
        dict(catalog_key=child, effect_choice=child_mode, complexity=1 + child_sp, additional_spell_points=child_sp)]
    assert parent_sp + child_sp == 2
    assert not missing_required_construction_modes(rows)
    assert not advanced_construction_blockers(rows, 15)
    item = dict(schema_version=1, sphere='Telekinesis', base_power='telekinesis:force', caster_level=15,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0, contributions=rows)
    assert quote_marvelous_blueprint(item)[0] == 6
    assert quote_marvelous_blueprint(item)[1].market_price_gp == 36000
    rows[1]['effect_choice'] = 'concentration' if child_mode == 'Sustained Force' else 'Sustained Force'
    assert advanced_construction_blockers(rows, 15)


def test_conflicting_gravity_parent_modes_do_not_silently_drop_a_requirement():
    from app.marvelous_item_rules import missing_required_construction_modes
    rows = [dict(catalog_key='telekinesis:advanced-talent:gravity-manipulation', effect_choice=mode)
        for mode in ('concentration (2 SP total)', 'Sustained Force (2 SP total)')]
    assert len(missing_required_construction_modes(rows)) == 2


def test_light_lens_conversion_is_paid_once_and_formula_matches_quote():
    from app.marvelous_item_rules import quote_marvelous_blueprint, marvelous_complexity_formula
    item = dict(schema_version=1, sphere='Light', base_power='light:lens', caster_level=5,
        uses=1, activation='standard', range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    assert quote_marvelous_blueprint(item)[0] == 2
    assert '1 lens conversion' in marvelous_complexity_formula(item)
    item['contributions'] = [dict(catalog_key='light:lens-talent:aiming-scope-lens', complexity=1)]
    assert quote_marvelous_blueprint(item)[0] == 2
    assert 'lens conversion' not in marvelous_complexity_formula(item)
    item['contributions'][0]['complexity'] = 4
    assert quote_marvelous_blueprint(item)[0] == 5
    item['contributions'] = [dict(catalog_key=key, complexity=1, alternative=True) for key in (
        'light:lens-talent:aiming-scope-lens', 'light:lens-talent:obscure-lens')]
    assert quote_marvelous_blueprint(item)[0] == Fraction(5, 2)
    lens = dict(item, contributions=[])
    combined = dict(item, sphere='Life', base_power='life:cure', contributions=[],
        extra_effects=[lens], combination_mode='multiple')
    assert quote_marvelous_blueprint(combined)[1].market_price_gp == 7000
    combined['combination_mode'] = 'mixed'
    assert quote_marvelous_blueprint(combined)[1].market_price_gp == 8000


def test_all_bundled_light_lenses_have_reviewed_zero_extra_sp():
    from app.content import DEFAULT_CATALOG
    from app.marvelous_base_powers import LIGHT_LENSES
    from app.marvelous_item_rules import talent_construction_spell_points
    entries = [entry for entry in DEFAULT_CATALOG.magic_entries('Light') if entry['category'] == 'Lens Talent']
    assert {entry['key'] for entry in entries} == set(LIGHT_LENSES)
    assert all(talent_construction_spell_points(entry, reviewed_only=True) == 0 for entry in entries)


def test_every_bundled_light_talent_has_explicit_sp_metadata():
    from app.content import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points
    entries = [entry for entry in DEFAULT_CATALOG.magic_entries('Light') if 'Talent' in entry['category']]
    assert entries
    assert not [entry['key'] for entry in entries if talent_construction_spell_points(entry, reviewed_only=True) is None]


LIGHT_ADVANCED_REQUIREMENTS = {
    'daylight-light': (10, ()), 'diffuse-body': (7, ('light:talent:flicker-light',)),
    'everglow': (1, ('light:talent:lingering-glow',)),
    'incarnate-glow': (15, ('light:talent:flicker-light',)),
    'light-speed': (15, ('light:talent:flicker-light', 'light:advanced-talent:incarnate-glow')),
    'prismatic-radiance-light': (15, ('light:talent:searing-light-light', 'light:talent:style-utility')),
    'radiation-light': (10, ('light:talent:irradiance-light',)),
    'star-genesis': (10, ('light:talent:intensity-control',)),
}


def test_every_bundled_advanced_light_talent_has_explicit_requirements_and_costs():
    from app.content import DEFAULT_CATALOG
    from app.marvelous_item_rules import ADVANCED_CONSTRUCTION_REQUIREMENTS, talent_construction_spell_points
    entries = [entry for entry in DEFAULT_CATALOG.magic_entries('Light') if entry['category'] == 'Advanced Talent']
    assert {entry['key'] for entry in entries} == {'light:advanced-talent:' + key for key in LIGHT_ADVANCED_REQUIREMENTS}
    assert all(entry['key'] in ADVANCED_CONSTRUCTION_REQUIREMENTS for entry in entries)
    assert all(talent_construction_spell_points(entry, reviewed_only=True) is not None for entry in entries)


@pytest.mark.parametrize('suffix,requirement', LIGHT_ADVANCED_REQUIREMENTS.items())
def test_light_advanced_construction_requires_integrated_dependencies_and_level(suffix, requirement):
    from app.marvelous_item_rules import (ADVANCED_CONSTRUCTION_REQUIREMENTS,
        missing_construction_prerequisites, advanced_construction_blockers)
    key = 'light:advanced-talent:' + suffix
    minimum, required = requirement
    assert ADVANCED_CONSTRUCTION_REQUIREMENTS[key] == requirement
    rows = [dict(catalog_key=key)]
    assert set(missing_construction_prerequisites(rows)) == set(required)
    rows.extend(dict(catalog_key=child) for child in missing_construction_prerequisites(rows))
    if suffix == 'radiation-light': rows[-1]['effect_choice'] = 'nauseating bright light'
    assert not missing_construction_prerequisites(rows)
    assert not advanced_construction_blockers(rows, minimum)
    assert advanced_construction_blockers(rows, minimum - 1)


@pytest.mark.parametrize('suffix,points', [('daylight-light',2), ('diffuse-body',0), ('everglow',1),
    ('incarnate-glow',2), ('light-speed',0), ('prismatic-radiance-light',3), ('radiation-light',1)])
def test_reviewed_advanced_light_costs_do_not_duplicate_prerequisite_sp(suffix, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert talent_construction_spell_points(magic_entry('light:advanced-talent:' + suffix), reviewed_only=True) == points


def test_radiation_requires_paid_irradiance_mode_not_possession_or_optional_row():
    from app.marvelous_item_rules import missing_required_construction_modes, advanced_construction_blockers
    parent, child = 'light:advanced-talent:radiation-light', 'light:talent:irradiance-light'
    rows = [dict(catalog_key=parent), dict(catalog_key=child, effect_choice='sicken glowing target')]
    assert missing_required_construction_modes(rows) == ((parent, child, 'nauseating bright light'),)
    assert advanced_construction_blockers(rows, 10)
    rows[1]['effect_choice'] = 'nauseating bright light'
    assert not missing_required_construction_modes(rows)
    assert not advanced_construction_blockers(rows, 10)
    rows[1]['alternative'] = True
    assert missing_required_construction_modes(rows)
    assert advanced_construction_blockers(rows, 10)


@pytest.mark.parametrize('key,points', [
    *((f'light:talent:{suffix}', 1) for suffix in ('area-glow', 'bound-light-light', 'dual-light',
        'encompassing-light-light', 'hypnotic-pattern-light', 'instill-glow-instill', 'mass-lens-mass',
        'precious-light', 'repelling-light-light', 'revealing-light-light', 'visual-overload-light')),
    *((f'light:talent:{suffix}', 0) for suffix in ('bend-radiance', 'black-light', 'dancing-lights',
        'fenestrate-light', 'flare', 'glory', 'guiding-light-light', 'inner-sun-light', 'light-link',
        'lure-light-light', 'ranged-light-range', 'revelation-light', 'shining-arsenal-light',
        'solar-strike-strike', 'sunstroke-light')),
    *((f'light:nimbus-talent:{suffix}', 0) for suffix in ('beam-nimbus', 'trail-nimbus', 'weird-radiance-nimbus')),
])
def test_reviewed_ordinary_light_sp_costs_use_real_catalog_entries(key, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = magic_entry(key)
    assert entry is not None
    assert talent_construction_spell_points(entry, reviewed_only=True) == points


@pytest.mark.parametrize('suffix,free,paid', [
    ('beacon-of-hope-light', 'target fear-save bonus', 'fear recovery bright area'),
    ('blinding-light-light', 'dazzle glowing target', 'blinding bright area'),
    ('disorienting-patterns-light', 'difficult terrain', 'prone-inducing patterns'),
    ('purifying-light-light-crimdan', 'targeted purification', 'purification bright area'),
])
def test_light_optional_paid_modes_do_not_make_target_only_effects_cost_one_sp(suffix, free, paid):
    from app.marvelous_base_powers import talent_effect_choices
    from app.marvelous_item_rules import talent_choice_spell_points
    key = 'light:talent:' + suffix
    assert talent_effect_choices(key) == (free, paid)
    assert talent_choice_spell_points(key, free) == 0
    assert talent_choice_spell_points(key, paid) == 1


@pytest.mark.parametrize('suffix,expected', [
    ('enhance-talent:steal-capacity-enhance', 1), ('enhance-talent:steal-senses-enhance', 1),
    ('enhance-talent:alter-movement-enhance', 0), ('enhance-talent:cripple-enhance', 0),
    ('enhance-talent:emphasize-belief-enhance', 0), ('enhance-talent:enhance-focus-enhance', 0),
    ('enhance-talent:enhance-potency-enhance-sm', 0), ('enhance-talent:harden-weaken-enhance', 0),
    ('enhance-talent:improved-flexibility-enhance', 0), ('enhance-talent:ravenous-weapon-enhance-sm', 0),
    ('enhance-talent:staunch-resistance-enhance', 0), ('enhance-talent:superior-poison-enhance', 0),
    ('enhance-talent:superior-reflexes-enhance', 0), ('enhance-talent:supply-vigor-enhance', 0),
    ('enhance-talent:traveling-weapon-enhance', 0), ('talent:crippling-strike-strike', 0),
    ('talent:natural-enhancement', 0),
])
def test_reviewed_enhancement_additional_spell_point_defaults(suffix, expected):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = magic_entry('enhancement:' + suffix)
    assert entry is not None
    assert talent_construction_spell_points(entry, reviewed_only=True) == expected


@pytest.mark.parametrize('energy,minimum', [('sonic',5), ('force',10)])
def test_energy_mode_requires_alternative_energy_once_and_exact_level(energy, minimum):
    from app.marvelous_base_powers import ENERGY_ENHANCEMENT_KEY, ALTERNATIVE_ENERGY_KEY
    from app.marvelous_item_rules import missing_construction_prerequisites, advanced_construction_blockers
    rows = [dict(catalog_key=ENERGY_ENHANCEMENT_KEY, effect_choice='weapon: ' + energy)]
    assert missing_construction_prerequisites(rows) == (ALTERNATIVE_ENERGY_KEY,)
    assert advanced_construction_blockers(rows, minimum)
    rows.append(dict(catalog_key=ALTERNATIVE_ENERGY_KEY))
    assert not missing_construction_prerequisites(rows)
    assert not advanced_construction_blockers(rows, minimum)
    assert advanced_construction_blockers(rows, minimum - 1)
    rows[-1]['alternative'] = True
    assert missing_construction_prerequisites(rows) == (ALTERNATIVE_ENERGY_KEY,)
    assert advanced_construction_blockers(rows, minimum)


@pytest.mark.parametrize('kind,choice', [
    ('physical', 'Strength + Dexterity'), ('physical', 'Strength + Constitution'),
    ('physical', 'Dexterity + Constitution'), ('mental', 'Intelligence + Wisdom'),
    ('mental', 'Intelligence + Charisma'), ('mental', 'Wisdom + Charisma'),
])
def test_paired_enhancement_requires_one_fixed_dual_talent(kind, choice):
    from app.marvelous_item_rules import (missing_construction_prerequisites,
        advanced_construction_blockers, talent_construction_spell_points)
    dual = 'enhancement:talent:dual-enhancement'
    rows = [dict(catalog_key=f'enhancement:enhance-talent:{kind}-enhancement-enhance', effect_choice=choice)]
    assert missing_construction_prerequisites(rows) == (dual,)
    assert advanced_construction_blockers(rows, 10)
    rows.append(dict(catalog_key=dual, alternative=True))
    assert missing_construction_prerequisites(rows) == (dual,)
    assert advanced_construction_blockers(rows, 10)
    rows[-1]['alternative'] = False
    assert not missing_construction_prerequisites(rows)
    assert not advanced_construction_blockers(rows, 10)
    assert talent_construction_spell_points(dict(key=dual), reviewed_only=True) == 1


def test_cryptwood_tradition_inherits_both_published_restrictions():
    from app.marvelous_item_rules import crafting_item_limitations, crafting_limitation_details
    plan = dict(caster_level=7, crafting_tradition={'key': 'crafting:cryptwood-artifice'},
                area_bound_mode='distance', drawbacks=[])
    assert crafting_item_limitations(plan) == {'crafting:area-bound', 'crafting:clingy'}
    details = '\n'.join(crafting_limitation_details(plan))
    assert 'DC 17' in details and '7 miles' in details
    plan['drawbacks'] = [dict(source='published', catalog_key='crafting:clingy')]
    assert len([line for line in crafting_limitation_details(plan) if line.startswith('Clingy:')]) == 1
    plan['crafting_tradition'] = {'key': 'custom:cryptwood', 'name': 'Cryptwood Artifice'}
    plan['drawbacks'] = []
    assert not crafting_item_limitations(plan)


def test_complex_drawback_skill_choice_and_live_dc():
    from app.marvelous_item_rules import complex_required_skill, crafting_limitation_details
    plan = dict(caster_level=5, drawbacks=[])
    assert complex_required_skill(plan) is None
    record = dict(source='published', catalog_key='crafting:complex', name='Complex', reduction=0)
    plan['drawbacks'] = [record]
    assert complex_required_skill(plan) == ''
    record['required_skill'] = 'acrobatics'
    assert complex_required_skill(plan) == 'Acrobatics'
    assert any('DC 10 Acrobatics' in line for line in crafting_limitation_details(plan))
    plan['caster_level'] = 9
    assert any('DC 14 Acrobatics' in line for line in crafting_limitation_details(plan))
    for invalid in ('Not a skill', 3, None):
        record['required_skill'] = invalid
        with pytest.raises(ValueError, match='known skill'):
            complex_required_skill(plan)
    record['source'] = 'custom'
    assert complex_required_skill(plan) is None


@pytest.mark.parametrize('key,points', [
    ('life:talent:break-enchantment', 1),
    ('life:talent:greater-restore-warden', 1),
    ('life:talent:mass-healing-mass', 1),
    ('life:talent:restorative-cure', 1),
    ('life:advanced-talent:hypervitalize', 2),
])
def test_reviewed_life_construction_extra_sp_costs(key, points):
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = next(entry for entry in DEFAULT_CATALOG.magic_entries('Life') if entry['key'] == key)
    assert talent_construction_spell_points(entry) == points


def test_custom_named_tradition_does_not_gain_published_boons():
    from app.marvelous_item_rules import crafting_boon_details
    assert crafting_boon_details({'crafting_tradition': {'key': 'custom:ley-linked', 'name': 'Ley-Linked'}}) == ()


def test_unknown_sp_default_is_distinct_from_reviewed_free_without_changing_drafts():
    from app.marvelous_item_rules import talent_construction_spell_points
    unknown = {'key': 'future:talent:unreviewed'}
    assert talent_construction_spell_points(unknown) == 0
    assert talent_construction_spell_points(unknown, reviewed_only=True) is None
    free = {'key': 'destruction:blast-shape-talent:energy-sphere-blast-shape'}
    assert talent_construction_spell_points(free, reviewed_only=True) == 0


@pytest.mark.parametrize('suffix', ['improved-haste', 'improved-slow', 'instill-time-instill',
    'lingering-time-3pp', 'ranged-time-range', 'time-strike-strike', 'time-zone'])
def test_reviewed_free_time_modifiers_have_catalog_backed_costs(suffix):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = magic_entry('time:talent:' + suffix)
    assert entry and talent_construction_spell_points(entry, reviewed_only=True) == 0


@pytest.mark.parametrize('suffix,mode,points', [
    ('age-time', 'creature age with concentration', 1),
    ('age-time', 'creature age for minutes per caster level', 2),
    ('broken-time-time', 'concentration', 0), ('broken-time-time', 'rounds per caster level', 1),
    ('rapid-response-time', 'concentration', 0), ('rapid-response-time', 'ten minutes per caster level', 1),
])
def test_time_concentration_modes_have_explicit_reviewed_costs(suffix, mode, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_choice_spell_points
    key = 'time:talent:' + suffix
    assert magic_entry(key)
    assert talent_choice_spell_points(key, mode) == points


@pytest.mark.parametrize('key,sphere,base', [
    ('time:talent:time-strike-strike', 'Time', 'time:haste'),
    ('life:talent:clarified-strike-strike', 'Life', 'life:cure'),
    ('creation:talent:transmuting-strike-strike-3pp', 'Creation', 'creation:alter')])
def test_strike_item_casting_cannot_be_shortened_below_standard(key, sphere, base):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    item = dict(schema_version=1, sphere=sphere, base_power=base, caster_level=10,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
        contributions=[dict(catalog_key=key, complexity=1, additional_spell_points=0)])
    assert quote_marvelous_blueprint(item)
    for activation in ('move', 'swift'):
        item['activation'] = activation
        with pytest.raises(ValueError, match='below a standard action'):
            quote_marvelous_blueprint(item)


@pytest.mark.parametrize('suffix,cost', [
    ('alter-talent:change-material-alter', 1), ('alter-talent:crack-alter-apoc', 1),
    ('alter-talent:forge-alter', 1), ('alter-talent:rigidity-alter', 1),
    ('material-talent:acidic-creation-material', 1), ('talent:larger-creation', 1),
    ('talent:lengthened-creation', 1), ('talent:replication', 1),
    ('material-talent:expanded-materials-material', 0), ('talent:distant-creation-range', 0),
    ('talent:divided-creation-mass', 0), ('talent:exquisite-detail-utility', 0),
    ('talent:transmuting-strike-strike-3pp', 0),
])
def test_reviewed_creation_costs_use_real_catalog_identities(suffix, cost):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = magic_entry('creation:' + suffix)
    assert entry and talent_construction_spell_points(entry, reviewed_only=True) == cost


def test_every_bundled_life_vitality_talent_has_reviewed_free_sp_cost():
    from app.content import DEFAULT_CATALOG
    from app.marvelous_base_powers import LIFE_VITALITY_EFFECTS
    from app.marvelous_item_rules import talent_construction_spell_points
    entries = [entry for entry in DEFAULT_CATALOG.magic_entries('Life') if entry['category'] == 'Vitality Talent']
    assert {entry['key'] for entry in entries} == set(LIFE_VITALITY_EFFECTS)
    assert len(entries) == 7
    assert all(talent_construction_spell_points(entry, reviewed_only=True) == 0 for entry in entries)


@pytest.mark.parametrize('suffix,choice,cost', [
    ('adrenaline-surge', 'surge one ally', 1), ('adrenaline-surge', 'surge multiple allies', 2),
    ('taste-of-victory', 'ordinary qualifying hit', 1),
    ('taste-of-victory', 'critical hit, unconscious or zero-HP target', 0),
    ('diagnose-utility', 'detect conditions', 0),
    ('diagnose-utility', 'condition details as standard action', 0),
    ('diagnose-utility', 'condition details as swift action', 1),
])
def test_conditional_life_costs_are_explicit_modes(suffix, choice, cost):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_choice_spell_points
    key = 'life:talent:' + suffix
    assert magic_entry(key)
    assert talent_choice_spell_points(key, choice) == cost


def test_violent_recuperation_adds_no_sp_beyond_its_life_effect():
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert talent_construction_spell_points(magic_entry('life:talent:violent-recuperation-alienist-hb'), reviewed_only=True) == 0


def test_all_ordinary_life_costs_except_empathic_reduction_are_reviewed():
    from app.content import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points
    entries = [e for e in DEFAULT_CATALOG.magic_entries('Life') if 'Talent' in e['category'] and 'Advanced' not in e['category']]
    assert [e['key'] for e in entries if talent_construction_spell_points(e, reviewed_only=True) is None] == ['life:talent:empathic-healing']


@pytest.mark.parametrize('left,right', [('affliction', 'fount-of-life'), ('instill-life-instill', 'empathic-healing')])
def test_incompatible_life_effects_are_blocked_unless_mutually_exclusive(left, right):
    from app.marvelous_item_rules import advanced_construction_blockers
    rows = [dict(catalog_key='life:talent:' + suffix) for suffix in (left, right)]
    assert len(advanced_construction_blockers(rows, 10)) == 1
    for row in rows: row.update(alternative=True, alternative_group=1)
    assert not advanced_construction_blockers(rows, 10)
    rows[1]['alternative_group'] = 2
    assert advanced_construction_blockers(rows, 10)


@pytest.mark.parametrize('suffix,cost', [('flash-of-excellence-sm', 1),
    ('power-parasitism-alienist-hb', 1), ('ranged-enhancement-range', 0)])
def test_enhancement_timing_and_range_modifiers_have_reviewed_sp_defaults(suffix, cost):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = magic_entry('enhancement:talent:' + suffix)
    assert entry and talent_construction_spell_points(entry, reviewed_only=True) == cost


@pytest.mark.parametrize('changes', [dict(duration_steps=1), dict(duration_steps=3, permanent=True)])
def test_temporary_inherent_enhancement_cannot_quote_extended_or_permanent_duration(changes):
    from app.marvelous_item_rules import quote_marvelous_blueprint, talent_choice_spell_points
    key = 'enhancement:advanced-talent:inherent-enhancement-enhance-archmagi-s-hb'
    choice = 'temporary untyped bonus: Strength'
    assert talent_choice_spell_points(key, choice) == 1
    item = dict(schema_version=1, sphere='Enhancement', base_power='enhancement:enhance', caster_level=17,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
        contributions=[dict(catalog_key=key, effect_choice=choice, complexity=3, additional_spell_points=1)])
    assert quote_marvelous_blueprint(item)[0] == 4
    item.update(changes)
    with pytest.raises(ValueError, match='one round per caster level'):
        quote_marvelous_blueprint(item)


def test_time_warp_replacement_cost_includes_true_teleport_once():
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points, missing_construction_prerequisites
    key = 'warp:advanced-talent:time-warp-jester-s-hb'
    keys = [key, *missing_construction_prerequisites([dict(catalog_key=key)])]
    assert keys.count('warp:advanced-talent:true-teleport') == 1
    assert talent_construction_spell_points(magic_entry(key), reviewed_only=True) == 3
    assert sum(talent_construction_spell_points(magic_entry(k)) for k in keys) == 5


@pytest.mark.parametrize('owner,total', [('bestow-life', 3), ('reverse-gravity-enhance', 2), ('referential-enhancements', 3)])
def test_enhancement_replacement_and_additional_costs_include_prerequisites_once(owner, total):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points, missing_construction_prerequisites
    key = 'enhancement:advanced-talent:' + owner
    keys = [key, *missing_construction_prerequisites([dict(catalog_key=key)])]
    assert all(talent_construction_spell_points(magic_entry(k), reviewed_only=True) is not None for k in keys)
    assert sum(talent_construction_spell_points(magic_entry(k)) for k in keys) == total


@pytest.mark.parametrize('suffix,cost', [('self-renewal', 1), ('sudden-invigoration', 1),
    ('deeper-healing', 0), ('painkiller', 0), ('esoteric-healing', 0), ('latent-healing', 0),
    ('lingering-resilience', 0), ('lingering-vitality-warden', 0), ('resuscitate', 0), ('stabilizing-invigoration-warden', 0)])
def test_reviewed_life_modifiers_have_explicit_sp_defaults(suffix, cost):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert talent_construction_spell_points(magic_entry('life:talent:' + suffix), reviewed_only=True) == cost


def test_greater_invigorate_optional_sp_cost():
    from app.marvelous_item_rules import talent_choice_spell_points
    key = 'life:talent:greater-invigorate'
    assert talent_choice_spell_points(key, 'normal HP limit') == 0
    assert talent_choice_spell_points(key, 'exceed normal HP limit') == 1


@pytest.mark.parametrize('suffix,mode,cost', [
    ('avert-space', 'readied standard action', 0), ('avert-space', 'immediate action', 1),
    ('avert-space', 'immediate action during total defense', 0),
    ('blink-space', 'concentration', 0), ('blink-space', 'minutes per caster level', 1),
    ('create-gap-space', 'concentration', 1), ('create-gap-space', 'minutes per caster level', 2),
    ('distort-size-space', 'concentration', 0), ('distort-size-space', 'minutes per caster level', 1),
])
def test_reviewed_space_mode_spell_point_costs(suffix, mode, cost):
    from app.marvelous_item_rules import talent_choice_spell_points
    assert talent_choice_spell_points('warp:space-talent:' + suffix, mode) == cost


@pytest.mark.parametrize('suffix', ['causality-time', 'delay-pain-time', 'eject-time', 'fast-time-time',
    'lethargy-time', 'repetition-time', 'retroactive-preparation', 'second-chance', 'temporal-trap', 'time-bubble-time'])
def test_reviewed_time_one_spell_point_construction_costs(suffix):
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Time') if e['key'] == 'time:talent:' + suffix)
    assert talent_construction_spell_points(entry) == 1


def test_cryptwood_boon_explains_material_benefits_and_unpriced_base_cost():
    from app.marvelous_item_rules import crafting_boon_details
    details = '\n'.join(crafting_boon_details({'crafting_tradition': {'key': 'crafting:cryptwood-artifice'}}))
    for text in ('Imbued (greenwood)', 'one-quarter fire damage', '25 gp per original pound',
                 'not included in the magical-effect quote', 'another special material'):
        assert text in details
    assert not crafting_boon_details({'crafting_tradition': {'key': 'custom:cryptwood', 'name': 'Cryptwood Artifice'}})


def test_mass_aegis_adds_one_spell_point_without_changing_item_duration():
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points, quote_marvelous_blueprint
    from app.marvelous_base_powers import resolve_base_power, automatic_self_effect
    key = 'protection:talent:mass-aegis-mass'
    entry = next(entry for entry in DEFAULT_CATALOG.magic_entries('Protection') if entry['key'] == key)
    assert talent_construction_spell_points(entry) == 1
    plan = dict(schema_version=1, sphere='Protection', base_power='protection:aegis', caster_level=5,
                uses=1, activation='standard', range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    before = quote_marvelous_blueprint(plan)[1].market_price_gp
    duration = resolve_base_power(plan)['duration']
    plan['contributions'] = [dict(catalog_key=key, complexity=2, additional_spell_points=1)]
    assert quote_marvelous_blueprint(plan)[1].market_price_gp == before + 4000
    assert resolve_base_power(plan)['duration'] == duration
    assert automatic_self_effect(plan) is None


@pytest.mark.parametrize('key', ['warp:talent:segmented-warp', 'warp:space-talent:dimension-pierce-space',
                               'warp:space-talent:fluctuate-space'])
def test_reviewed_warp_activation_costs_are_one_sp(key):
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points
    entry = next(entry for entry in DEFAULT_CATALOG.magic_entries('Warp') if entry['key'] == key)
    assert talent_construction_spell_points(entry) == 1


@pytest.mark.parametrize('key,minimum,required,points', [
    ('warp:advanced-talent:dimensional-lock-space', 15, 'warp:space-talent:plane-manipulator-space', 2),
    ('warp:advanced-talent:extradimensional-capacity-utility-apoc', 0, 'warp:space-talent:extradimensional-storage-space-utility', 0),
    ('warp:advanced-talent:extradimensional-torpor-space-apoc', 0, 'warp:space-talent:extradimensional-storage-space-utility', 1),
])
def test_additional_warp_prerequisites_and_minimum_levels(key, minimum, required, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import missing_construction_prerequisites, advanced_construction_blockers, talent_construction_spell_points
    assert magic_entry(key) and magic_entry(required)
    rows = [dict(catalog_key=key)]
    assert missing_construction_prerequisites(rows) == (required,)
    rows.append(dict(catalog_key=required))
    assert not advanced_construction_blockers(rows, max(1, minimum))
    if minimum: assert advanced_construction_blockers(rows, minimum - 1)
    assert talent_construction_spell_points(magic_entry(key)) == points


@pytest.mark.parametrize('key,level', [
    ('warp:advanced-talent:lethal-teleport-apoc', 5),
    ('warp:advanced-talent:portal-interstice-sm', 5),
    ('warp:advanced-talent:portal-security-space-sm', 5),
    ('warp:advanced-talent:universal-teleport', 17),
    ('warp:advanced-talent:brain-preservation-alienist-hb', 15),
    ('warp:advanced-talent:organ-detachment-space-alienist-hb', 10),
    ('warp:advanced-talent:randomized-planeshift-sm', 5),
    ('warp:advanced-talent:repel-the-unnatural-alienist-hb', 0),
    ('warp:advanced-talent:warp-manipulator', 1),
    ('warp:advanced-talent:manifest-planar-zone-space-dbh', 5),
    ('warp:advanced-talent:greater-planar-zone-sm', 5),
    ('warp:advanced-talent:planting-warp-3pp', 0),
    ('warp:advanced-talent:store-structure', 1),
    ('warp:advanced-talent:teleport-structure', 5),
    ('warp:advanced-talent:warping-frenzy-lg', 5),
    ('warp:advanced-talent:create-demiplane-utility', 15),
    ('warp:advanced-talent:time-warp-jester-s-hb', 20),
    ('warp:advanced-talent:timeline-drift-lg', 10),
])
def test_warp_chain_expansion_adds_all_dependencies_once_and_checks_level(key, level):
    from app.content import magic_entry
    from app.marvelous_item_rules import missing_construction_prerequisites, advanced_construction_blockers
    rows = [dict(catalog_key=key)]
    missing = missing_construction_prerequisites(rows)
    assert all(magic_entry(required) for required in missing)
    assert len(missing) == len(set(missing))
    rows.extend(dict(catalog_key=required) for required in missing)
    assert not missing_construction_prerequisites(rows)
    assert not advanced_construction_blockers(rows, max(1, level))
    if level: assert advanced_construction_blockers(rows, level - 1)


@pytest.mark.parametrize('key,options', [
    ('warp:advanced-talent:dimensional-tracery-3pp', ('warp:space-talent:teleport-beacon-space', 'warp:space-talent:warp-link-space')),
    ('warp:advanced-talent:brutalizing-shunt-apoc', ('warp:space-talent:create-gap-space', 'warp:talent:unseeing-teleport')),
])
def test_warp_either_or_dependency_does_not_require_both(key, options):
    from app.marvelous_item_rules import missing_construction_alternatives, advanced_construction_blockers
    assert missing_construction_alternatives([dict(catalog_key=key)]) == ((key, options),)
    for selected in options:
        rows = [dict(catalog_key=key), dict(catalog_key=selected)]
        assert not advanced_construction_blockers(rows, 1)
        rows[-1]['alternative'] = True
        assert advanced_construction_blockers(rows, 1)


@pytest.mark.parametrize('sphere, commentary', [
    ('Warp', 'warp:advanced-talent:warping-structures-store-and-teleport-structure'),
    ('Time', 'time:advanced-talent:reversion-and-complete-reversion'),
    ('Life', None),
    ('Protection', None),
    ('Enhancement', None),
])
def test_bundled_advanced_entries_have_explicit_construction_requirement_metadata(sphere, commentary):
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import ADVANCED_CONSTRUCTION_REQUIREMENTS
    entries = {entry['key'] for entry in DEFAULT_CATALOG.magic_entries(sphere)
               if 'advanced' in entry.get('category', '').casefold()
               and entry['key'] != commentary}
    assert entries <= ADVANCED_CONSTRUCTION_REQUIREMENTS.keys()


@pytest.mark.parametrize('mode, cost, minimum', [('view hours', 1, 5), ('view days', 2, 8), ('view years', 3, 16)])
def test_past_sight_modes_price_and_enforce_item_caster_level(mode, cost, minimum):
    from app.marvelous_item_rules import talent_choice_spell_points, advanced_construction_blockers
    key = 'time:advanced-talent:past-sight-utility'
    rows = [dict(catalog_key=key, effect_choice=mode)]
    assert talent_choice_spell_points(key, mode) == cost
    assert advanced_construction_blockers(rows, minimum - 1)
    assert not advanced_construction_blockers(rows, minimum)


def test_weather_construction_sp_defaults_and_modes_are_catalog_backed():
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points, talent_choice_spell_points
    entries = {entry['key']: entry for entry in DEFAULT_CATALOG.magic_entries('Weather')}
    for key in ('weather:talent:greater-weather', 'weather:talent:severe-weather'):
        assert talent_construction_spell_points(entries[key]) == 1
    assert talent_choice_spell_points('weather:talent:greater-weather', 'two weather categories') == 1
    assert talent_choice_spell_points('weather:talent:greater-weather', 'three weather categories') == 2


def test_weather_advanced_metadata_covers_every_bundled_entry():
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import ADVANCED_CONSTRUCTION_REQUIREMENTS, missing_construction_prerequisites, advanced_construction_blockers
    entries = {e['key'] for e in DEFAULT_CATALOG.magic_entries('Weather') if 'advanced' in e['category'].lower()}
    assert len(entries) == 21
    for key in entries:
        minimum, _ = ADVANCED_CONSTRUCTION_REQUIREMENTS[key]
        rows = [dict(catalog_key=k) for k in [key, *missing_construction_prerequisites([dict(catalog_key=key)])]]
        assert not advanced_construction_blockers(rows, max(20, minimum))
        assert advanced_construction_blockers(rows, minimum - 1)


def test_weather_advanced_spell_point_defaults_cover_catalog_and_exact_costs():
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points
    paid = {'cacophonic-clap': 1, 'climate': 1, 'climatic-shift': 3, 'dehydration-pulse': 2,
            'radiation-lord-cata-hb': 2, 'rain-bomb': 1, 'volcano-lord': 2}
    entries = [e for e in DEFAULT_CATALOG.magic_entries('Weather') if 'advanced' in e['category'].lower()]
    assert len(entries) == 21
    for entry in entries:
        assert talent_construction_spell_points(entry, reviewed_only=True) == paid.get(entry['key'].split(':')[-1], 0)


@pytest.mark.parametrize('talent', ['stability-bottleneck-sm', 'voiding-suppression-3pp'])
@pytest.mark.parametrize('selectivity', ['spell-selectivity-dbh', 'spell-selectivity-arcforge-addendum-lg'])
def test_protection_filter_upgrades_accept_either_selectivity_and_require_ward(talent, selectivity):
    from app.marvelous_item_rules import advanced_construction_blockers
    rows = [dict(catalog_key='protection:advanced-talent:' + talent),
            dict(catalog_key='protection:advanced-talent:' + selectivity),
            dict(catalog_key='protection:aegis-ward-talent:spell-ward-aegis-ward')]
    assert not advanced_construction_blockers(rows, 10)
    assert advanced_construction_blockers(rows, 9)
    assert advanced_construction_blockers(rows[:-1], 10)


def test_repeated_complex_checks_preserve_each_roll_and_validate_skills():
    from app.marvelous_item_rules import complex_additional_skills, complex_crafting_skills, crafting_limitation_details
    record = dict(source='published', catalog_key='crafting:complex', required_skill='Acrobatics',
                  additional_skills=['Linguistics', 'Acrobatics'])
    plan = dict(caster_level=5, drawbacks=[record])
    assert complex_additional_skills(plan) == ('Linguistics', 'Acrobatics')
    assert complex_crafting_skills(plan) == ('Acrobatics', 'Linguistics')
    assert sum('DC 10' in line for line in crafting_limitation_details(plan)) == 3
    for invalid in ('Acrobatics', [None], ['Unknown']):
        record['additional_skills'] = invalid
        with pytest.raises(ValueError, match='known skills'):
            complex_additional_skills(plan)


def test_expensive_item_drawback_changes_materials_not_price_and_rejects_cheap():
    from app.marvelous_item_rules import quote_marvelous_blueprint
    from app.marvelous_base_powers import automatic_self_effect
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=5,
                uses=1, range_steps=0, duration_steps=0, activation='standard', unique_changes=0,
                contributions=[], drawbacks=[dict(source='published', catalog_key='crafting:expensive', name='Expensive', reduction=0)])
    _, price, quote = quote_marvelous_blueprint(plan)
    assert price.market_price_gp == 2000 and quote.cost_gp == 1250
    assert automatic_self_effect(plan) == 'cure'
    plan['extra_effects'] = [{key: value for key, value in plan.items() if key != 'drawbacks'}]
    assert quote_marvelous_blueprint(plan)[2].cost_gp == 3125
    plan['extra_effects'][0]['drawbacks'] = list(plan['drawbacks'])
    with pytest.raises(ValueError, match='whole item'): quote_marvelous_blueprint(plan)
    plan.pop('extra_effects')
    plan['crafting_tradition'] = {'key': 'crafting:diviner-s-sight'}
    with pytest.raises(ValueError, match='mutually exclusive'): quote_marvelous_blueprint(plan)


@pytest.mark.parametrize('tradition', ['crafting:city-construction', 'crafting:evil-artifice'])
def test_fragile_rejects_resilient_traditions(tradition):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    plan = dict(schema_version=1, caster_level=5, uses=1, range_steps=0,
                duration_steps=0, activation='standard', unique_changes=0, contributions=[],
                crafting_tradition={'key': tradition}, drawbacks=[dict(source='published',
                    catalog_key='crafting:fragile', name='Fragile', reduction=0)])
    with pytest.raises(ValueError, match='Fragile is incompatible'):
        quote_marvelous_blueprint(plan)
    plan['crafting_tradition'] = {'key': 'crafting:diviner-s-sight'}
    assert quote_marvelous_blueprint(plan)[0] == 1
    plan['crafting_tradition'] = {'key': tradition}
    plan['drawbacks'][0]['source'] = 'custom'
    assert quote_marvelous_blueprint(plan)[0] == 1


def test_complexity_formula_exposes_sp_alternatives_and_reductions():
    from app.marvelous_item_rules import marvelous_complexity_formula, quote_marvelous_blueprint
    plan = dict(schema_version=1, caster_level=20, uses=1, range_steps=1, duration_steps=-1,
                activation='move', unique_changes=0, contributions=[
                    dict(catalog_key='test:a', complexity=3, additional_spell_points=2),
                    dict(catalog_key='test:b', complexity=4, alternative=True),
                    dict(catalog_key='test:c', complexity=2, alternative=True)],
                drawbacks=[dict(source='custom', name='Restriction', reduction=1)])
    result = marvelous_complexity_formula(plan)
    assert '+ 1 talents + 2 extra SP + 5 choices + 1 range − 2 duration + 3 activation − 1 drawbacks' in result
    assert result.endswith('= ' + str(quote_marvelous_blueprint(plan)[0]))
    plan['contributions'] = []; plan.update(range_steps=0, duration_steps=0, activation='full-round')
    assert marvelous_complexity_formula(plan) == 'max(1, 1 base − 1 activation − 1 drawbacks) = 1'


def test_warp_construction_dependency_chains_and_beacon_sp():
    from app.marvelous_item_rules import missing_construction_prerequisites, advanced_construction_blockers, talent_construction_spell_points
    from app.content import magic_entry
    assert talent_construction_spell_points(magic_entry('warp:space-talent:teleport-beacon-space')) == 1
    portal = [dict(catalog_key='warp:advanced-talent:portal-network-dbh')]
    missing = missing_construction_prerequisites(portal)
    assert len(missing) == len(set(missing))
    assert {'warp:advanced-talent:enduring-portal', 'warp:advanced-talent:portal',
            'warp:space-talent:teleport-beacon-space', 'warp:space-talent:wormhole-space'} <= set(missing)
    assert all(magic_entry(key) is not None for key in missing)
    complete = portal + [dict(catalog_key=key) for key in missing]
    assert not advanced_construction_blockers(complete, 15)
    assert advanced_construction_blockers(complete, 14)
    assert missing_construction_prerequisites([dict(catalog_key='warp:space-talent:teleport-beacon-space')]) == ()


@pytest.mark.parametrize('key,points', [('true-teleport', 2), ('planeshift', 2), ('portal', 1), ('enduring-portal', 1)])
def test_reviewed_warp_selected_effect_sp_defaults(key, points):
    from app.marvelous_item_rules import talent_construction_spell_points
    from app.content import magic_entry
    assert talent_construction_spell_points(magic_entry('warp:advanced-talent:' + key)) == points


def test_live_formula_reports_slotless_limited_and_combined_quotes():
    from app.marvelous_item_rules import marvelous_price_formula
    plan = dict(schema_version=1, caster_level=5, uses=50, range_steps=0,
                duration_steps=0, activation='standard', unique_changes=0,
                contributions=[], no_space_limitation=True)
    formula = marvelous_price_formula(plan)
    assert '2.5 (50 total uses) × 2 (slotless)' in formula and '= 10000 gp' in formula
    plan.update(uses=1, no_space_limitation=False,
                extra_effects=[dict(schema_version=1, caster_level=5, uses=1, range_steps=0,
                                    duration_steps=0, activation='standard', unique_changes=0, contributions=[])])
    assert marvelous_price_formula(plan) == '2000 + (4000 − 2000) × 1.5 = 5000 gp'
    plan['combination_mode'] = 'mixed'
    assert marvelous_price_formula(plan) == '2000 + (4000 − 2000) × 2 = 6000 gp'


@pytest.mark.parametrize('suffix,minimum,required,points', [
    ('adaptation-aegis', 10, 'protection:aegis-ward-talent:energy-resistance-aegis-ward', 1),
    ('antimagic-aura', 10, 'protection:aegis-ward-talent:spell-ward-aegis-ward', 1),
    ('automatic-fortification-3pp', 5, 'protection:talent:fortifier-3pp', 1),
    ('complex-glyph', 5, 'protection:talent:glyph', 0),
    ('improved-negation-3pp', 10, 'protection:succor-talent:negation-succor-3pp', 0),
    ('layered-glyph-3pp', 0, 'protection:talent:glyph', 0),
    ('mobile-ward-alienist-hb', 5, None, 0),
    ('permanent-ward', 10, 'protection:talent:enduring-protection', 0),
    ('planar-refuge-aegis-ward-rw-hb', 5, None, 0),
    ('preserve-integrity-aegis-alienist-hb', 10, None, 0),
    ('rapid-glyph-3pp', 0, 'protection:talent:glyph', 0),
    ('spell-eater-aegis-3pp', 10, 'protection:succor-talent:negation-succor-3pp', 2),
    ('spell-selectivity-dbh', 10, 'protection:aegis-ward-talent:spell-ward-aegis-ward', 1),
    ('subtle-aegis', 5, None, 0),
    ('true-protection', 10, None, 0),
    ('undying-aegis', 7, 'protection:aegis-ward-talent:deathless-aegis', 1),
    ('unplottable-aegis', 15, 'protection:aegis-ward-talent:resistance-aegis', 0),
])
def test_reviewed_protection_construction_requirements(suffix, minimum, required, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import (missing_construction_prerequisites,
        advanced_construction_blockers, talent_construction_spell_points)
    key = 'protection:advanced-talent:' + suffix
    rows = [dict(catalog_key=key)]
    assert magic_entry(key) is not None
    assert missing_construction_prerequisites(rows) == ((required,) if required else ())
    if required:
        assert magic_entry(required) is not None
        assert advanced_construction_blockers(rows, max(1, minimum))
        rows.append(dict(catalog_key=required))
    assert not advanced_construction_blockers(rows, max(1, minimum))
    if minimum:
        assert advanced_construction_blockers(rows, minimum - 1)
    assert talent_construction_spell_points(magic_entry(key)) == points


def test_mobile_and_permanent_ward_cannot_be_integrated_together():
    from app.marvelous_item_rules import advanced_construction_blockers
    rows = [dict(catalog_key='protection:advanced-talent:' + suffix)
            for suffix in ('mobile-ward-alienist-hb', 'permanent-ward')]
    assert any('cannot benefit' in issue for issue in advanced_construction_blockers(rows, 20))


@pytest.mark.parametrize('key', ['crafting:evil-artifice', 'crafting:sacred-artifice'])
def test_simple_boon_reduces_complexity_before_pricing_and_combining(key):
    from app.marvelous_item_rules import (quote_marvelous_blueprint, marvelous_complexity_formula,
        marvelous_price_formula, marvelous_effect_plan)
    plan = dict(schema_version=1, caster_level=5, uses=1, range_steps=0, duration_steps=0,
                activation='standard', unique_changes=2, contributions=[], crafting_tradition={'key': key})
    complexity, price, quote = quote_marvelous_blueprint(plan)
    assert complexity == 2 and price.market_price_gp == 4000 and quote.cost_gp == 2000
    assert '− 1 Simple boon' in marvelous_complexity_formula(plan)
    plan['extra_effects'] = [{k: v for k, v in plan.items() if k not in {'extra_effects', 'crafting_tradition'}}]
    assert quote_marvelous_blueprint(plan)[1].market_price_gp == 10000
    assert marvelous_price_formula(plan) == '4000 + (8000 − 4000) × 1.5 = 10000 gp'
    simple_copy = marvelous_effect_plan(plan, 1)
    assert simple_copy['crafting_tradition']['key'] == key
    assert 'crafting_tradition' not in plan['extra_effects'][0]
    plan['combination_mode'] = 'mixed'
    assert quote_marvelous_blueprint(plan)[1].market_price_gp == 12000
    plan.pop('extra_effects'); plan['unique_changes'] = 0
    assert quote_marvelous_blueprint(plan)[0] == 1


@pytest.mark.parametrize('tradition', ['bad', {}, {'key': []}])
def test_malformed_tradition_rejects_before_simple_pricing(tradition):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    plan = dict(schema_version=1, caster_level=5, uses=1, range_steps=0, duration_steps=0,
                activation='standard', unique_changes=0, contributions=[], crafting_tradition=tradition)
    with pytest.raises(ValueError, match='catalog identity'):
        quote_marvelous_blueprint(plan)


@pytest.mark.parametrize('key,invalid,valid,message', [
    ('charged', 1, 5, 'unlimited-use'), ('sacrificing', 5, 2, 'limited daily'),
])
def test_item_limitation_use_contracts_apply_to_every_power(key, invalid, valid, message):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    plan = dict(schema_version=1, caster_level=5, uses=invalid, range_steps=0, duration_steps=0,
                activation='standard', unique_changes=0, contributions=[],
                drawbacks=[dict(source='published', catalog_key='crafting:' + key, name=key, reduction=0)])
    with pytest.raises(ValueError, match=message): quote_marvelous_blueprint(plan)
    plan['uses'] = valid
    quote_marvelous_blueprint(plan)
    plan['extra_effects'] = [{k: v for k, v in plan.items() if k not in {'drawbacks', 'extra_effects'}}]
    plan['extra_effects'][0]['uses'] = invalid
    with pytest.raises(ValueError, match=message): quote_marvelous_blueprint(plan)


def test_tradition_limits_are_identity_based_and_taxing_excludes_permanency():
    from app.marvelous_item_rules import quote_marvelous_blueprint
    plan = dict(schema_version=1, sphere='Protection', base_power='protection:aegis', caster_level=10,
                uses=50, range_steps=0, duration_steps=2, activation='standard', unique_changes=0,
                contributions=[], crafting_tradition={'key': 'crafting:evil-artifice'})
    with pytest.raises(ValueError, match='limited daily'): quote_marvelous_blueprint(plan)
    plan.update(uses=1, permanent=True, crafting_tradition={'key': 'crafting:ley-linked'})
    with pytest.raises(ValueError, match='unlimited duration'): quote_marvelous_blueprint(plan)
    plan.pop('crafting_tradition'); plan['drawbacks'] = [dict(source='custom', name='Taxing', reduction=0)]
    quote_marvelous_blueprint(plan)


def test_charged_descriptor_includes_integrated_metamagic_sp():
    from app.marvelous_item_rules import crafting_limitation_details
    plan = dict(schema_version=1, caster_level=10, uses=5, range_steps=0, duration_steps=0,
                activation='standard', unique_changes=0, contributions=[],
                feat_integrations=[dict(name='Empower Spell', metamagic=True, additional_spell_points=2)],
                drawbacks=[dict(source='published', catalog_key='crafting:charged', name='Charged', reduction=0)])
    assert '6 charges per activation' in crafting_limitation_details(plan)[0]


def test_charged_alternatives_keep_fixed_and_metamagic_sp_in_base():
    from app.marvelous_item_rules import crafting_limitation_details, quote_marvelous_blueprint
    plan = dict(schema_version=1, caster_level=20, uses=5, range_steps=0, duration_steps=0,
                activation='standard', unique_changes=0,
                contributions=[dict(catalog_key='fixed', complexity=3, additional_spell_points=2),
                    dict(catalog_key='option-a', complexity=2, additional_spell_points=1, alternative=True),
                    dict(catalog_key='option-b', complexity=4, additional_spell_points=3, alternative=True)],
                feat_integrations=[dict(name='Empower Spell', metamagic=True, additional_spell_points=2)],
                drawbacks=[dict(source='published', catalog_key='crafting:charged', name='Charged', reduction=0)])
    complexity = quote_marvelous_blueprint(plan)[0]
    text = crafting_limitation_details(plan)[0]
    assert f'{complexity + 4} base charges' in text
    assert 'selected alternative in each group' in text


def test_charged_multi_power_description_does_not_claim_primary_cost_is_total():
    from app.marvelous_item_rules import crafting_limitation_details
    power = dict(schema_version=1, caster_level=10, uses=5, range_steps=0, duration_steps=0,
                 activation='standard', unique_changes=0, contributions=[])
    plan = dict(power, extra_effects=[dict(power)],
                drawbacks=[dict(source='published', catalog_key='crafting:charged', name='Charged', reduction=0)])
    text = '\n'.join(crafting_limitation_details(plan))
    assert 'primary power only' in text and 'not a whole-item activation total' in text


def test_spell_selectivity_choice_limit_duplicate_validation_and_antimagic_conflict():
    from app.marvelous_item_rules import spell_selectivity_options
    row = dict(catalog_key='protection:advanced-talent:spell-selectivity-dbh', effect_choice='only', effect_spheres=['Life', 'Warp'])
    plan = dict(caster_level=5, contributions=[row])
    assert spell_selectivity_options(plan)['maximum'] == 2
    plan['caster_level'] = 4
    with pytest.raises(ValueError, match='exceed'): spell_selectivity_options(plan)
    plan['caster_level'] = 10; row['effect_spheres'] = ['Life', 'life']
    with pytest.raises(ValueError, match='duplicates'): spell_selectivity_options(plan)
    row['effect_spheres'] = ['Life']; row['effect_choice'] = 'except'
    plan['contributions'].append(dict(catalog_key='protection:advanced-talent:antimagic-aura'))
    with pytest.raises(ValueError, match='except-mode'): spell_selectivity_options(plan)
    row['effect_choice'] = 'only'
    assert spell_selectivity_options(plan)['spheres'] == ('Life',)


def test_explicit_weight_applies_bulky_once_and_preserves_unknown():
    from app.marvelous_item_rules import marvelous_item_weight
    assert marvelous_item_weight({}) is None
    plan = dict(base_weight_lb=2, crafting_tradition={'key': 'crafting:city-construction'},
                drawbacks=[dict(source='published', catalog_key='crafting:bulky')])
    assert marvelous_item_weight(plan) == 400
    plan['base_weight_lb'] = 0
    assert marvelous_item_weight(plan) == 0
    plan['base_weight_lb'] = 2; plan.pop('crafting_tradition'); plan['drawbacks'][0]['source'] = 'custom'
    assert marvelous_item_weight(plan) == 2


@pytest.mark.parametrize('weight', [-1, True, '2', float('inf'), float('nan')])
def test_invalid_base_weight_is_rejected(weight):
    from app.marvelous_item_rules import marvelous_item_weight
    with pytest.raises(ValueError): marvelous_item_weight({'base_weight_lb': weight})


def test_reviewed_destruction_alternative_prerequisites_accept_one_not_both():
    from app.content import magic_entry
    from app.marvelous_item_rules import missing_construction_alternatives, advanced_construction_blockers
    rows = [dict(catalog_key='destruction:advanced-talent:calamity-blast-shape')]
    owner, options = missing_construction_alternatives(rows)[0]
    assert len(options) == 2 and all(magic_entry(key) for key in options)
    assert any('include one' in blocker for blocker in advanced_construction_blockers(rows, 10))
    for key in options:
        complete = [*rows, dict(catalog_key=key)]
        assert not missing_construction_alternatives(complete)
        assert not advanced_construction_blockers(complete, 10)
        assert advanced_construction_blockers(complete, 9)


def test_reviewed_destruction_fixed_prerequisites_have_catalog_identities_and_paid_defaults():
    from app.content import magic_entry
    from app.marvelous_item_rules import ADVANCED_CONSTRUCTION_REQUIREMENTS, talent_construction_spell_points
    from app.marvelous_base_powers import KNIGHTS_BLAST_KEY, GRANDMASTER_KEY
    from app.marvelous_item_rules import missing_construction_prerequisites
    assert talent_construction_spell_points(magic_entry(KNIGHTS_BLAST_KEY)) == 1
    assert missing_construction_prerequisites([dict(catalog_key=GRANDMASTER_KEY)]) == (KNIGHTS_BLAST_KEY,)
    for key, (minimum, required) in ADVANCED_CONSTRUCTION_REQUIREMENTS.items():
        if key.startswith('destruction:'):
            assert magic_entry(key) and all(magic_entry(dependency) for dependency in required)
    assert talent_construction_spell_points(magic_entry('destruction:advanced-talent:energy-cloud-blast-shape')) == 3
    assert talent_construction_spell_points(magic_entry('destruction:advanced-talent:calamity-blast-shape')) == 2
    from app.marvelous_item_rules import ALTERNATIVE_CONSTRUCTION_REQUIREMENTS
    for key, groups in ALTERNATIVE_CONSTRUCTION_REQUIREMENTS.items():
        assert magic_entry(key) and all(magic_entry(option) for options in groups for option in options)


@pytest.mark.parametrize('owner,minimum', [('crystal-cocoon', 10), ('radiation-blast-blast-type-fire-light', 5)])
def test_group_prerequisites_require_distinct_applied_talents(owner, minimum):
    from app.marvelous_item_rules import (COUNTED_ALTERNATIVE_CONSTRUCTION_REQUIREMENTS,
        missing_construction_alternatives, advanced_construction_blockers, talent_construction_spell_points)
    from app.content import magic_entry
    key = 'destruction:advanced-talent:' + owner
    count, options = COUNTED_ALTERNATIVE_CONSTRUCTION_REQUIREMENTS[key]
    assert count == 2 and all(magic_entry(option) for option in options)
    rows = [dict(catalog_key=key), dict(catalog_key=options[0]), dict(catalog_key=options[0])]
    missing = missing_construction_alternatives(rows)
    assert missing and all(options[0] not in choices for _, choices in missing)
    rows.append(dict(catalog_key=options[1], alternative=True))
    assert missing_construction_alternatives(rows)
    rows[-1]['alternative'] = False
    assert not missing_construction_alternatives(rows)
    assert not advanced_construction_blockers(rows, minimum)
    assert advanced_construction_blockers(rows, minimum - 1)
    if owner.startswith('radiation'):
        assert talent_construction_spell_points(magic_entry(key)) == 2
    else:
        assert talent_construction_spell_points(magic_entry(key)) == 1


@pytest.mark.parametrize('level,penalty', [(1, 1), (3, 1), (4, 2), (19, 5), (20, 6), (24, 6)])
def test_crafting_penalty_and_curse_descriptors_scale_from_item_level(level, penalty):
    from app.marvelous_item_rules import crafting_limitation_details
    blueprint = dict(caster_level=level, drawbacks=[dict(source='published', catalog_key='crafting:unwieldy'),
                                                  dict(source='published', catalog_key='crafting:clingy')])
    text = '\n'.join(crafting_limitation_details(blueprint))
    assert f'Unwieldy: −{penalty}' in text and f'DC {10 + level}' in text
    blueprint['drawbacks'] = [dict(source='custom', name='Unwieldy'), dict(source='custom', name='Clingy')]
    assert not crafting_limitation_details(blueprint)
    blueprint['crafting_tradition'] = dict(key='crafting:evil-artifice')
    assert any(f'Clingy: curse suppression normally requires a check against DC {10 + level}' in line
               for line in crafting_limitation_details(blueprint))


@pytest.mark.parametrize('owner,minimum,required', [
    ('group-teleport', 10, ('warp:talent:mass-teleport-mass', 'warp:talent:ranged-warp-range')),
    ('universal-teleport', 17, ('warp:talent:distant-teleport', 'warp:advanced-talent:flawless-teleport-utility',
                              'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    ('extradimensional-capacity-utility-apoc', 0, ('warp:space-talent:extradimensional-storage-space-utility',)),
])
def test_reviewed_warp_prerequisite_chains(owner, minimum, required):
    from app.marvelous_item_rules import missing_construction_prerequisites, advanced_construction_blockers
    from app.content import magic_entry
    key = 'warp:advanced-talent:' + owner
    assert magic_entry(key) and all(magic_entry(dependency) for dependency in required)
    rows = [dict(catalog_key=key)]
    assert set(missing_construction_prerequisites(rows)) == set(required)
    rows.extend(dict(catalog_key=dependency) for dependency in required)
    assert not advanced_construction_blockers(rows, max(1, minimum))
    if minimum: assert advanced_construction_blockers(rows, minimum - 1)


@pytest.mark.parametrize('name', ['mass-teleport-mass', 'emergency-teleport', 'instill-teleport-instill', 'unwilling-teleport'])
def test_reviewed_warp_paid_talents_have_one_extra_sp(name):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert talent_construction_spell_points(magic_entry('warp:talent:' + name)) == 1


def test_group_teleport_pays_two_sp_across_integrated_prerequisites():
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert sum(talent_construction_spell_points(magic_entry(key)) for key in
               ('warp:advanced-talent:group-teleport', 'warp:talent:mass-teleport-mass')) == 2


@pytest.mark.parametrize('selected', [['Life', 'life'], ['Life'] * 4, [''], 'Life', [True]])
def test_educated_choices_reject_malformed_or_duplicate_spheres(selected):
    from app.marvelous_item_rules import educated_required_spheres
    with pytest.raises(ValueError, match='Educated'):
        educated_required_spheres(dict(drawbacks=[dict(source='published', catalog_key='crafting:educated', required_spheres=selected)]))


def test_reviewed_time_prerequisites_have_catalog_identities_and_correct_gates():
    from app.content import magic_entry
    from app.marvelous_item_rules import ADVANCED_CONSTRUCTION_REQUIREMENTS, advanced_construction_blockers, missing_construction_prerequisites
    for key, (minimum, required) in ADVANCED_CONSTRUCTION_REQUIREMENTS.items():
        if not key.startswith('time:'): continue
        assert magic_entry(key) and all(magic_entry(dependency) for dependency in required)
        rows = [dict(catalog_key=key)]
        assert set(missing_construction_prerequisites(rows)) == set(required)
        rows.extend(dict(catalog_key=dependency) for dependency in required)
        assert not advanced_construction_blockers(rows, max(1, minimum))
        if minimum: assert advanced_construction_blockers(rows, minimum - 1)


@pytest.mark.parametrize('key,points', [('time:talent:mass-time-mass', 1), ('time:talent:augment-healing', 1),
    ('time:talent:retry-time', 2), ('time:talent:shift-time-time', 1), ('time:talent:steal-time-time', 1),
    ('time:talent:stretch-time-time', 1), ('time:talent:time-freeze-time', 1),
    ('time:advanced-talent:past-sight-utility', 1), ('time:advanced-talent:query-self-utility', 2),
    ('time:advanced-talent:reversion-utility', 10), ('time:advanced-talent:temporal-haste', 1),
    ('time:advanced-talent:temporal-stasis', 3)])
def test_reviewed_time_costs(key, points):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert talent_construction_spell_points(magic_entry(key)) == points


@pytest.mark.parametrize('level,strength', [(1, 'Faint'), (5, 'Faint'), (6, 'Moderate'), (11, 'Moderate'),
                                         (12, 'Strong'), (20, 'Strong'), (21, 'Overwhelming')])
def test_item_aura_strength_uses_caster_level_bands(level, strength):
    from app.marvelous_item_rules import marvelous_aura_strength
    assert marvelous_aura_strength(level) == strength


@pytest.mark.parametrize('level', [0, -1, True, 5.5, '5'])
def test_item_aura_strength_rejects_invalid_levels(level):
    from app.marvelous_item_rules import marvelous_aura_strength
    with pytest.raises(ValueError): marvelous_aura_strength(level)


def test_counted_prerequisites_require_two_applied_extended_ranges():
    from app.marvelous_item_rules import missing_construction_prerequisites, advanced_construction_blockers
    key = 'destruction:talent:extended-range-range'
    rows = [dict(catalog_key='destruction:advanced-talent:extreme-range')]
    assert missing_construction_prerequisites(rows) == (key, key)
    rows.append(dict(catalog_key=key))
    assert missing_construction_prerequisites(rows) == (key,)
    assert any('requires 2, included 1' in text for text in advanced_construction_blockers(rows, 5))
    rows.append(dict(catalog_key=key, alternative=True))
    assert missing_construction_prerequisites(rows) == (key,)
    rows[-1]['alternative'] = False
    assert not missing_construction_prerequisites(rows)
    assert not advanced_construction_blockers(rows, 5)
    assert advanced_construction_blockers(rows, 4)


@pytest.mark.parametrize('suffix', ['antimagic-aura', 'spell-selectivity'])
def test_arcforge_protection_accepts_either_magic_or_technology_prerequisite(suffix):
    from app.marvelous_item_rules import missing_construction_alternatives, advanced_construction_blockers, talent_construction_spell_points
    from app.content import magic_entry
    key = 'protection:advanced-talent:' + suffix + '-arcforge-addendum-lg'
    rows = [dict(catalog_key=key)]
    assert missing_construction_alternatives(rows)
    for dependency in ('protection:aegis-ward-talent:spell-ward-aegis-ward',
                       'protection:aegis-ward-talent:technological-suppression-aegis-ward-lg'):
        complete = [*rows, dict(catalog_key=dependency)]
        assert not missing_construction_alternatives(complete)
        assert not advanced_construction_blockers(complete, 10)
        assert advanced_construction_blockers(complete, 9)
    assert talent_construction_spell_points(magic_entry(key)) == 1


def test_pithing_requires_each_independent_choice_group():
    from app.marvelous_item_rules import missing_construction_alternatives, advanced_construction_blockers
    key = 'protection:advanced-talent:pithing-protection-arcforge-addendum-lg'
    rows = [dict(catalog_key=key)]
    assert len(missing_construction_alternatives(rows)) == 2
    rows.append(dict(catalog_key='protection:advanced-talent:spell-selectivity-arcforge-addendum-lg'))
    assert len([group for owner, group in missing_construction_alternatives(rows) if owner == key]) == 1
    rows.append(dict(catalog_key='protection:aegis-ward-talent:technological-suppression-aegis-ward-lg'))
    assert not missing_construction_alternatives(rows)
    assert not advanced_construction_blockers(rows, 10)
    assert advanced_construction_blockers(rows, 9)


def test_optional_alternative_does_not_satisfy_an_applied_prerequisite():
    from app.marvelous_item_rules import missing_construction_prerequisites, missing_construction_alternatives, advanced_construction_blockers
    rows = [dict(catalog_key='warp:advanced-talent:true-teleport'),
            dict(catalog_key='warp:talent:distant-teleport', alternative=True),
            dict(catalog_key='warp:talent:unseeing-teleport')]
    assert missing_construction_prerequisites(rows) == ('warp:talent:distant-teleport',)
    assert advanced_construction_blockers(rows, 10)
    rows[1]['alternative'] = False
    assert not advanced_construction_blockers(rows, 10)
    rows = [dict(catalog_key='destruction:advanced-talent:calamity-blast-shape'),
            dict(catalog_key='destruction:blast-shape-talent:explosive-orb-blast-shape', alternative=True)]
    assert missing_construction_alternatives(rows)


@pytest.mark.parametrize('same_group', [True, False])
def test_mobile_permanent_conflict_respects_mutually_exclusive_groups(same_group):
    from app.marvelous_item_rules import advanced_construction_blockers
    rows = [dict(catalog_key='protection:advanced-talent:mobile-ward-alienist-hb', alternative=True, alternative_group=1),
            dict(catalog_key='protection:advanced-talent:permanent-ward', alternative=True, alternative_group=1 if same_group else 2),
            dict(catalog_key='protection:talent:enduring-protection')]
    blockers = advanced_construction_blockers(rows, 10)
    assert any('cannot benefit' in issue for issue in blockers) is not same_group


def test_selectivity_antimagic_conflict_only_when_options_can_coexist():
    from app.marvelous_item_rules import spell_selectivity_options
    rows = [dict(catalog_key='protection:advanced-talent:spell-selectivity-dbh', effect_choice='except',
                 effect_spheres=['Life'], alternative=True, alternative_group=1),
            dict(catalog_key='protection:advanced-talent:antimagic-aura', alternative=True, alternative_group=1)]
    plan = dict(caster_level=10, contributions=rows)
    assert spell_selectivity_options(plan)['mode'] == 'except'
    rows[1]['alternative_group'] = 2
    with pytest.raises(ValueError, match='except-mode'): spell_selectivity_options(plan)
    rows[1]['alternative_group'] = 1; rows[1]['alternative'] = False
    with pytest.raises(ValueError, match='except-mode'): spell_selectivity_options(plan)


@pytest.mark.parametrize('suffix', ['chain-blast-blast-shape', 'energy-aura-blast-shape',
    'energy-leap-blast-shape', 'guided-strike-blast-shape', 'mutable-blast-blast-shape', 'retributive-blast-blast-shape'])
def test_reviewed_mandatory_shape_sp_defaults(suffix):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points, talent_construction_cost
    entry = magic_entry('destruction:blast-shape-talent:' + suffix)
    assert entry is not None
    assert talent_construction_spell_points(entry) == 1
    assert talent_construction_cost(entry, additional_spell_points=1) == 2


def test_optional_energy_sphere_sustain_is_not_assumed_mandatory():
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points
    assert talent_construction_spell_points(magic_entry('destruction:blast-shape-talent:energy-sphere-blast-shape')) == 0


def test_cheap_tradition_applies_once_to_combined_design():
    from app.marvelous_item_rules import quote_marvelous_blueprint, marvelous_price_formula
    base = dict(schema_version=1, caster_level=5, uses=1, range_steps=0,
                duration_steps=0, activation='standard', unique_changes=0, contributions=[])
    plan = dict(base, extra_effects=[dict(base)], crafting_tradition={'key': 'crafting:city-construction'})
    _, price, quote = quote_marvelous_blueprint(plan)
    assert price.market_price_gp == 4500 and quote.cost_gp == 2250
    assert quote.days == 5  # Work is based on the unmodified 5,000 gp value.
    assert '× 0.9 (Cheap) = 4500 gp' in marvelous_price_formula(plan)
    plan['extra_effects'][0]['crafting_tradition'] = {'key': 'crafting:diviner-s-sight'}
    assert marvelous_price_formula(plan) == '2000 + (4000 − 2000) × 1.5 = 5000 gp → × 0.9 (Cheap) = 4500 gp'


def test_reviewed_drawback_reductions_and_validation():
    from app.marvelous_item_rules import quote_marvelous_blueprint, drawback_complexity
    plan = dict(schema_version=1, caster_level=5, uses=1, range_steps=0, duration_steps=0,
                activation='standard', unique_changes=3, contributions=[],
                drawbacks=[dict(source='custom', name='Dawn only', description='Only at sunrise', reduction=2)])
    assert quote_marvelous_blueprint(plan)[0] == 2
    assert quote_marvelous_blueprint(plan)[1].market_price_gp == 4000
    plan['drawbacks'][0]['reduction'] = 100
    assert quote_marvelous_blueprint(plan)[0] == 1
    for invalid in (-1, 1.5, True, '2', 101):
        plan['drawbacks'][0]['reduction'] = invalid
        with pytest.raises(ValueError, match='reduction'): quote_marvelous_blueprint(plan)
    record = dict(source='custom', name='Dawn only', reduction=1)
    with pytest.raises(ValueError, match='Duplicate'): drawback_complexity([record, record])


def test_base_and_use_modes():
    quote = marvelous_item_price(3, 2)
    assert (quote.market_price_gp, quote.save_dc, quote.daily_uses) == (2400, 11, 1)
    assert marvelous_item_price(3, 2, daily_uses=4).market_price_gp == 9600
    unlimited = marvelous_item_price(3, 2, daily_uses=5)
    assert unlimited.market_price_gp == 12000
    assert unlimited.daily_uses is None and unlimited.total_uses is None
    limited = marvelous_item_price(3, 2, limited_uses=True)
    assert limited.market_price_gp == 6000
    assert limited.daily_uses is None and limited.total_uses == 50


@pytest.mark.parametrize("kwargs", [
    {"caster_level": 0}, {"complexity": -1}, {"complexity": 1.5},
    {"caster_level": True}, {"daily_uses": 0}, {"daily_uses": 6},
    {"daily_uses": 2, "limited_uses": True},
])
def test_invalid_construction(kwargs):
    values = {"caster_level": 1, "complexity": 1, **kwargs}
    with pytest.raises(ValueError):
        marvelous_item_price(**values)


def test_exact_variable_complexity_and_caster_level_gate():
    complexity = effect_complexity(talent_costs=(1,), alternative_costs=(1, 2))
    assert complexity == Fraction(9, 2)
    assert marvelous_item_price(5, complexity).market_price_gp == 9000
    with pytest.raises(ValueError, match="caster level"):
        marvelous_item_price(4, complexity)


def test_construction_adjustments_and_minimum():
    assert effect_complexity(range_steps=2, duration_steps=1, activation="move") == 8
    assert effect_complexity(range_steps=-2, duration_steps=-1, activation="full-round") == 1
    assert effect_complexity(talent_costs=(3,), unique_changes=-1) == 3


def test_spheres_crafting_dc_materials_and_work_conditions():
    price = marvelous_item_price(3, 2)
    normal = marvelous_crafting_quote(price, 3, missing_talents=2)
    assert (normal.cost_gp, normal.dc, normal.days) == (1200, 23, 2.4)
    assert marvelous_crafting_quote(price, 3, distracting=True).days == 4.8
    assert marvelous_crafting_quote(price, 3, adventuring=True, distracting=True).days == 9.6
    assert marvelous_crafting_quote(marvelous_item_price(1, 1), 1).days == 1


def test_talent_construction_defaults_and_admixture_exception():
    from app.marvelous_item_rules import talent_construction_cost
    assert talent_construction_cost({'key': 'destruction:talent:admixture', 'category': 'Talent'}) == 0
    assert talent_construction_cost({'category': 'Talent'}, additional_spell_points=2) == 3
    assert talent_construction_cost({'category': 'Advanced Talent'}, additional_spell_points=1) == 3
    assert talent_construction_cost({'category': 'Advanced Talent'}, additional_spell_points=1, mythic_crafter=True) == 2
    with pytest.raises(ValueError): talent_construction_cost({}, mythic_crafter=1)
    assert talent_construction_cost({'key': 'alteration:talent:mass-alteration-mass', 'category': 'Talent'}) == 2
    assert talent_construction_cost({'key': 'illusion:talent:suppression-glamer', 'category': 'Talent'}) == 2
    with pytest.raises(ValueError): talent_construction_cost({}, additional_spell_points=True)


def test_mana_transfer_cannot_be_applied_to_crafted_manipulation():
    from app.marvelous_item_rules import quote_marvelous_blueprint
    plan = dict(schema_version=1, sphere='Mana', base_power='mana:manipulate', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[dict(
                    catalog_key='mana:manipulation-talent:transfer-manipulation', complexity=1)])
    with pytest.raises(ValueError, match='Mana Transfer'):
        quote_marvelous_blueprint(plan)


def test_crafting_tradition_costs_preserve_base_price_and_apply_floor():
    from app.marvelous_item_rules import tradition_costs
    assert tradition_costs(1000, cheap=True) == (450, 900)
    assert tradition_costs(1000, expensive=True) == (625, 1000)
    assert tradition_costs(1000, cheap=True, other_reduction=Fraction(1, 5)) == (400, 800)
    with pytest.raises(ValueError): tradition_costs(1000, cheap=True, expensive=True)


def test_explicit_feat_integration_costs_and_duplicate_validation():
    from app.marvelous_item_rules import feat_integration_complexity
    assert feat_integration_complexity([dict(name='Maximize Spell', metamagic=True, additional_spell_points=3)]) == 4
    assert feat_integration_complexity([dict(name='Example feat')]) == 1
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='A'), dict(name='a')])
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='A', additional_spell_points=1)])
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='Maximize Spell')])
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='Maximize Spell', metamagic=True, additional_spell_points=2)])
    assert feat_integration_complexity([dict(name='Empower Spell', metamagic=True, additional_spell_points=2)]) == 3


@pytest.mark.parametrize("kwargs", [{"talent_costs": (-1,)}, {"alternative_costs": (0.5,)},
                                    {"activation": "free"}, {"range_steps": 1.5}])
def test_invalid_effect_contributions(kwargs):
    with pytest.raises(ValueError):
        effect_complexity(**kwargs)


def test_missing_ordinary_talent_is_bypassable_but_advanced_is_not():
    result = marvelous_requirements(caster_level=5, sphere_levels={"Life": 5},
        feats=("Craft Marvelous Item",), required_spheres=("Life",),
        required_talents=("Restore", "Resurrection"), advanced_talents=("Resurrection",))
    assert not result.eligible
    assert result.dc_increase == 5
    assert result.bypassed == ("Missing talent: Restore",)
    assert result.blockers == ("Missing talent: Resurrection",)


def test_versatile_crafter_waives_sphere_and_level_not_protected_features():
    result = marvelous_requirements(caster_level=3, sphere_levels={},
        feats=("Craft Wondrous Item", "Versatile Crafter"), required_spheres=("Life",),
        protected_requirements=("Mythic Crafter",), prohibited_abilities=("Healing",))
    assert result.dc_increase == 20
    assert len(result.blockers) == 2
    assert len(result.bypassed) == 2


def test_cooperative_access_and_case_insensitive_identity():
    result = marvelous_requirements(caster_level=3, sphere_levels={"life": 3},
        feats=("CRAFT MARVELOUS ITEM",), required_spheres=("Life",),
        required_talents=("Resurrection",), available_talents=("resurrection",),
        advanced_talents=("Resurrection",))
    assert result.eligible and not result.bypassed and result.dc_increase == 0


def test_missing_creation_feat_cannot_be_waived():
    result = marvelous_requirements(caster_level=1, sphere_levels={"Life": 1},
        feats=("Versatile Crafter",), required_spheres=("Life",))
    assert not result.eligible
    with pytest.raises(ValueError, match="not met"):
        marvelous_crafting_quote(marvelous_item_price(1, 1), 1, requirements=result)


def test_validated_versatile_dc_flows_into_quote_once():
    result = marvelous_requirements(caster_level=3, sphere_levels={"Life": 1},
        feats=("Craft Marvelous Item", "Versatile Crafter"), required_spheres=("Life", "life"))
    quote = marvelous_crafting_quote(marvelous_item_price(3, 1), 3, requirements=result)
    assert quote.dc == 23
    with pytest.raises(ValueError, match="second"):
        marvelous_crafting_quote(marvelous_item_price(3, 1), 3, requirements=result, missing_talents=1)

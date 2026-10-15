import pytest
from fractions import Fraction

from app.marvelous_item_rules import effect_complexity, marvelous_crafting_quote, marvelous_item_price
from app.marvelous_item_rules import marvelous_requirements


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


def test_weather_construction_sp_defaults_and_modes_are_catalog_backed():
    from app.catalogs import DEFAULT_CATALOG
    from app.marvelous_item_rules import talent_construction_spell_points, talent_choice_spell_points
    entries = {entry['key']: entry for entry in DEFAULT_CATALOG.magic_entries('Weather')}
    for key in ('weather:talent:greater-weather', 'weather:talent:severe-weather'):
        assert talent_construction_spell_points(entries[key]) == 1
    assert talent_choice_spell_points('weather:talent:greater-weather', 'two weather categories') == 1
    assert talent_choice_spell_points('weather:talent:greater-weather', 'three weather categories') == 2


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

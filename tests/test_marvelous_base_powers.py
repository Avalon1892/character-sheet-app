import pytest
from app.marvelous_base_powers import BASE_POWERS, resolve_base_power


def plan(key, cl=5, **changes):
    power = next(p for p in BASE_POWERS if p.key == key)
    if key == 'warp:beacon':
        changes.setdefault('contributions', [dict(catalog_key='warp:space-talent:teleport-beacon-space', complexity=2, additional_spell_points=1)])
    if key == 'warp:dimension-pierce':
        changes.setdefault('contributions', [dict(catalog_key='warp:space-talent:dimension-pierce-space', complexity=2, additional_spell_points=1)])
    if key == 'warp:fluctuate':
        changes.setdefault('contributions', [dict(catalog_key='warp:space-talent:fluctuate-space', complexity=2, additional_spell_points=1)])
    if key == 'warp:blink':
        changes.setdefault('contributions', [dict(catalog_key='warp:space-talent:blink-space', complexity=1, additional_spell_points=0, effect_choice='concentration')])
    if key in {'warp:create-gap', 'warp:distort-size'}:
        points = 1 if key == 'warp:create-gap' else 0
        changes.setdefault('contributions', [dict(catalog_key='warp:space-talent:' + key.split(':')[1] + '-space', complexity=1 + points, additional_spell_points=points, effect_choice='concentration')])
    return dict(base_power=key, sphere=power.sphere, caster_level=cl,
                range_steps=0, duration_steps=0, **changes)


@pytest.mark.parametrize('power', BASE_POWERS)
def test_every_base_power_has_a_resolvable_projection(power):
    result = resolve_base_power(plan(power.key))
    assert result['power'] == power.name
    assert result['range'] and result['duration']
    assert result['caster_level'] == 5 and result['save_dc'] == 12 and result['magic_skill_bonus'] == 5


def test_enhancement_timing_modifiers_keep_item_conversion_limits_visible():
    rows = [dict(catalog_key='enhancement:talent:' + suffix) for suffix in (
        'flash-of-excellence-sm', 'power-parasitism-alienist-hb', 'ranged-enhancement-range')]
    result = resolve_base_power(plan('enhancement:enhance', contributions=rows))
    assert 'one-round maximum' in result['flash_of_excellence_review']
    assert 'half the user' in result['power_parasitism_trigger']
    assert 'item-specific range ladder' in result['ranged_enhancement_review']
    assert 'manual' in result['power']


@pytest.mark.parametrize('base', ['life:cure', 'life:restore', 'life:temporary-hp'])
def test_life_vitality_previews_do_not_stack_or_invent_duration_tracking(base):
    key = 'life:vitality-talent:sustaining-vitality-vitality'
    rows = [dict(catalog_key=key)]
    result = resolve_base_power(plan(base, contributions=rows))
    assert '+2 circumstance' in result['vitality_benefit']
    assert 'one minute' in result['vitality_limits']
    rows.append(dict(catalog_key='life:vitality-talent:aggressive-vitality-vitality'))
    result = resolve_base_power(plan(base, contributions=rows))
    assert 'vitality_benefit' not in result
    assert 'do not stack' in result['vitality_selection']
    rows[:] = [dict(catalog_key=key, alternative=True)]
    assert 'vitality_benefit' not in resolve_base_power(plan(base, contributions=rows))


def test_lingering_vitality_keeps_its_damage_expiration_exception():
    rows = [dict(catalog_key='life:vitality-talent:energizing-vitality-vitality'),
        dict(catalog_key='life:talent:lingering-vitality-warden')]
    result = resolve_base_power(plan('life:cure', contributions=rows))
    assert '+30 ft.' in result['vitality_benefit']
    assert 'one additional round' in result['vitality_damage_expiration']


@pytest.mark.parametrize('copies', [1, 2])
@pytest.mark.parametrize('talents', range(5))
def test_revitalize_replaces_healing_roll_and_counts_only_integrated_cure_talents(copies, talents):
    cure = ['restore-capacity-cure', 'restore-health-cure', 'restore-senses-cure', 'restore-spirit-cure']
    rows = [dict(catalog_key='life:talent:revitalize') for _ in range(copies)]
    rows += [dict(catalog_key='life:cure-talent:' + suffix) for suffix in cure[:talents]]
    result = resolve_base_power(plan('life:cure', cl=10, contributions=rows))
    assert result['fast_healing'] == 1 + talents and 'healing' not in result
    assert result['duration'] == ('10 minutes' if copies == 1 else '10 hours')
    assert result.get('maximum_total_healing') == (100 * (1 + talents) if copies == 2 else None)


def test_unknown_revitalize_combination_does_not_claim_a_resolved_healing_amount():
    rows = [dict(catalog_key='life:talent:revitalize'), dict(catalog_key='life:talent:deeper-healing')]
    result = resolve_base_power(plan('life:cure', contributions=rows))
    assert 'manual resolution' in result['power']
    assert 'healing' not in result and 'fast_healing' not in result


@pytest.mark.parametrize('cl,size', [(1,'Small'), (2,'Medium'), (4,'Large'), (8,'Huge'),
    (16,'Gargantuan'), (32,'Colossal'), (64,'Colossal+')])
def test_creation_size_uses_integrated_capacity_not_character_state(cl, size):
    result = resolve_base_power(plan('creation:create', cl=cl))
    assert result['creation_capacity_small_objects'] == cl
    assert result['maximum_object_size'] == size
    assert 'One object' in result['object_count']
    assert result['duration'] == f'{cl} rounds'


def test_force_creation_combines_size_and_shared_object_limits():
    rows = [dict(catalog_key='creation:' + suffix) for suffix in ('talent:larger-creation',
        'talent:divided-creation-mass', 'material-talent:object-of-force-material')]
    result = resolve_base_power(plan('creation:create', cl=10, contributions=rows))
    assert result['creation_capacity_small_objects'] == 20 and result['maximum_object_size'] == 'Gargantuan'
    assert 'sharing' in result['object_count']
    assert result['force_object_hardness'] == 10 and result['force_object_hp_per_inch'] == 10
    assert 'Not the weight of the crafting device' in result['force_object_weight']
    rows.append(dict(catalog_key='creation:talent:replication'))
    result = resolve_base_power(plan('creation:create', cl=10, contributions=rows))
    assert 'manual resolution' in result['power'] and 'maximum_object_size' not in result


@pytest.mark.parametrize('cl,maximum', [(1,25),(4,100),(5,250),(10,750),(13,975),(15,1500),(20,2500)])
def test_alchemical_creation_value_progression_and_divided_limits(cl, maximum):
    rows = [dict(catalog_key='creation:material-talent:alchemical-creation-material')]
    result = resolve_base_power(plan('creation:create', cl=cl, contributions=rows))
    assert result['maximum_alchemical_value_gp'] == maximum
    assert 'crafter’s live modifier' in result['alchemical_statistics']
    rows.append(dict(catalog_key='creation:talent:divided-creation-mass'))
    result = resolve_base_power(plan('creation:create', cl=cl, contributions=rows))
    assert result['maximum_combined_alchemical_value'] == f'{maximum / 2:g} gp'
    assert 'Only one item' in result['divided_alchemy']


def test_alchemical_creation_cl14_conflict_is_not_silently_resolved():
    rows = [dict(catalog_key='creation:material-talent:alchemical-creation-material')]
    result = resolve_base_power(plan('creation:create', cl=14, contributions=rows))
    assert 'Needs rules verification' in result['alchemical_value_review']
    assert 'maximum_alchemical_value_gp' not in result
    rows[0]['alternative'] = True
    assert 'alchemical_statistics' not in resolve_base_power(plan('creation:create', cl=14, contributions=rows))


@pytest.mark.parametrize('larger,capacity', [(False, 10), (True, 20)])
def test_create_materials_is_instantaneous_with_live_capacity_and_material_limits(larger, capacity):
    rows = [dict(catalog_key='creation:advanced-talent:create-materials'),
        dict(catalog_key='creation:talent:lengthened-creation'),
        dict(catalog_key='creation:material-talent:expanded-materials-material')]
    if larger: rows.append(dict(catalog_key='creation:talent:larger-creation'))
    result = resolve_base_power(plan('creation:create', cl=10, contributions=rows))
    assert result['power'] == 'Create Materials' and result['duration'] == 'Instantaneous'
    assert result['creation_capacity_small_objects'] == capacity
    assert 'Costly Creation' in result['material_limits']
    assert 'Fabricate' in result['craft_review']
    rows[0]['alternative'] = True
    assert resolve_base_power(plan('creation:create', cl=10, contributions=rows))['power'] != 'Create Materials'


def test_material_body_hour_mode_needs_fixed_lengthened_creation_for_duration_projection():
    rows = [dict(catalog_key='creation:advanced-talent:material-body-alter', effect_choice='hours per caster level with Lengthened Creation'),
        dict(catalog_key='creation:alter-talent:change-material-alter'),
        dict(catalog_key='creation:material-talent:expanded-materials-material')]
    assert resolve_base_power(plan('creation:alter', cl=10, contributions=rows))['power'] != 'Material Body'
    rows.append(dict(catalog_key='creation:talent:lengthened-creation'))
    result = resolve_base_power(plan('creation:alter', cl=10, contributions=rows))
    assert result['power'] == 'Material Body' and result['duration'] == '10 hours'
    assert 'unmodified_concentration_limit' not in result
    rows[-1]['alternative'] = True
    assert resolve_base_power(plan('creation:alter', cl=10, contributions=rows))['power'] != 'Material Body'


@pytest.mark.parametrize('instant', [False, True])
def test_duplicate_object_modes_show_copy_limits_and_correct_duration(instant):
    rows = [dict(catalog_key='creation:advanced-talent:duplicate', effect_choice='instantaneous object copy' if instant else 'temporary object copy'),
        dict(catalog_key='creation:talent:exquisite-detail-utility')]
    if instant:
        rows += [dict(catalog_key='creation:advanced-talent:create-materials'), dict(catalog_key='creation:talent:lengthened-creation')]
    result = resolve_base_power(plan('creation:create', cl=10, contributions=rows))
    assert result['power'] == 'Duplicate Object'
    assert result['duration'] == ('Instantaneous' if instant else '10 rounds')
    assert 'Magical properties are never copied' in result['copy_limits']
    assert result['copy_aura'].startswith('No lingering' if instant else 'Lingering')
    rows[0]['alternative'] = True
    assert resolve_base_power(plan('creation:create', cl=10, contributions=rows))['power'] != 'Duplicate Object'


def test_ooze_originator_projects_chosen_hd_but_not_unselected_species_statistics():
    rows = [dict(catalog_key='creation:advanced-talent:ooze-originator-create', effect_choice='8 HD ooze'),
        dict(catalog_key='creation:material-talent:acidic-creation-material')]
    result = resolve_base_power(plan('creation:create', cl=10, contributions=rows))
    assert result['power'] == 'Ooze Originator'
    assert result['ooze_hit_dice'] == 8 and result['maximum_controlled_ooze_hit_dice'] == 10
    assert 'maximum_object_size' not in result
    assert resolve_base_power(plan('creation:create', cl=7, contributions=rows))['power'] != 'Ooze Originator'


def test_potent_alteration_uses_dice_and_does_not_restore_expended_charges():
    assert resolve_base_power(plan('creation:alter', cl=5))['repair_or_destroy'].startswith('1d4+2')
    rows = [dict(catalog_key='creation:talent:potent-alteration', effect_choice='enhanced repair or destroy')]
    result = resolve_base_power(plan('creation:alter', cl=5, contributions=rows))
    assert result['repair_or_destroy'].startswith('1d6+5')
    assert 'charges are not restored' in result['target_review']
    rows = [dict(catalog_key='creation:alter-talent:forge-alter')]
    assert 'repair_or_destroy' not in resolve_base_power(plan('creation:alter', contributions=rows))


@pytest.mark.parametrize('mode,child', [('unattended non-magical object', 'enhanced repair or destroy'),
    ('attended, magical or creature target', 'affect magical, attended or construct target')])
def test_dissolution_projects_only_the_valid_fixed_target_mode(mode, child):
    rows = [dict(catalog_key='creation:advanced-talent:dissolution-alter', effect_choice=mode),
        dict(catalog_key='creation:talent:potent-alteration', effect_choice=child)]
    result = resolve_base_power(plan('creation:alter', cl=10, contributions=rows))
    assert result['power'] == 'Dissolution' and 'repair_or_destroy' not in result
    if mode == 'unattended non-magical object':
        assert '10-foot cube' in result['disintegration_volume']
        assert 'failed_fortitude_damage' not in result
    else:
        assert result['failed_fortitude_damage'] == '20d6'
        assert result['successful_fortitude_damage'] == '1d6+10'
    rows[-1]['effect_choice'] = ''
    assert resolve_base_power(plan('creation:alter', cl=10, contributions=rows))['power'] != 'Dissolution'


@pytest.mark.parametrize('mode,duration', [('concentration', 'Concentration'), ('sustained without concentration', '10 minutes')])
def test_material_body_projects_fixed_expanded_material_duration_without_inventing_hardness(mode, duration):
    rows = [dict(catalog_key='creation:advanced-talent:material-body-alter', effect_choice=mode),
        dict(catalog_key='creation:alter-talent:change-material-alter'),
        dict(catalog_key='creation:material-talent:expanded-materials-material')]
    result = resolve_base_power(plan('creation:alter', cl=10, contributions=rows))
    assert result['power'] == 'Material Body' and result['duration'] == duration
    assert 'hardness manually' in result['material_defense']
    assert '× 3' in result['material_body_limit']
    assert 'repair_or_destroy' not in result
    rows[0]['alternative'] = True
    assert resolve_base_power(plan('creation:alter', cl=10, contributions=rows))['power'] != 'Material Body'


@pytest.mark.parametrize('choice,steps', [('one size category', 1), ('additional size categories', 4)])
def test_magnify_preview_replaces_repair_roll_and_uses_talent_duration(choice, steps):
    rows = [dict(catalog_key='creation:alter-talent:magnify-minimize-alter', effect_choice=choice)]
    result = resolve_base_power(plan('creation:alter', cl=10, contributions=rows))
    assert result['maximum_size_category_steps'] == steps and result['duration'] == '10 minutes'
    assert 'repair_or_destroy' not in result
    extended = plan('creation:alter', cl=10, contributions=rows)
    extended['duration_steps'] = 1
    assert resolve_base_power(extended)['duration'] == '100 minutes'


@pytest.mark.parametrize('choice,duration', [('concentration', 'Concentration'), ('minutes per caster level', '10 minutes')])
def test_transparency_preview_exposes_selected_duration_and_limits(choice, duration):
    rows = [dict(catalog_key='creation:alter-talent:transparency-alter-utility', effect_choice=choice)]
    result = resolve_base_power(plan('creation:alter', cl=10, contributions=rows))
    assert result['duration'] == duration
    assert result['larger_object_area_square_feet'] == 20 and result['maximum_penetration_feet'] == 10
    assert result['one_way_perception_penalty'] == -4 and result['one_way_detection_dc'] == 15
    rows[0]['alternative'] = True
    result = resolve_base_power(plan('creation:alter', cl=10, contributions=rows))
    assert 'larger_object_area_square_feet' not in result


def test_conditional_life_descriptors_keep_trigger_and_activation_constraints():
    rows = [dict(catalog_key='life:talent:' + suffix) for suffix in (
        'adrenaline-surge', 'taste-of-victory', 'violent-recuperation-alienist-hb', 'diagnose-utility')]
    result = resolve_base_power(plan('life:cure', contributions=rows))
    assert 'Other allies only' in result['adrenaline_surge']
    assert 'half the user' in result['taste_of_victory']
    assert 'same damage effect' in result['violent_recuperation']
    assert 'not extra healing' in result['diagnose_review']


@pytest.mark.parametrize('ability', ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma'])
def test_temporary_inherent_enhancement_displays_untyped_not_permanent_bonus(ability):
    key = 'enhancement:advanced-talent:inherent-enhancement-enhance-archmagi-s-hb'
    rows = [dict(catalog_key=k) for k in ('enhancement:talent:deep-enhancement',
        'enhancement:enhance-talent:mental-enhancement-enhance',
        'enhancement:enhance-talent:physical-enhancement-enhance')]
    rows.append(dict(catalog_key=key, effect_choice='temporary untyped bonus: ' + ability))
    result = resolve_base_power(plan('enhancement:enhance', cl=17, contributions=rows))
    assert result['ability_score'] == ability and result['ability_untyped_bonus'] == 6
    assert 'ability_enhancement_bonus' not in result
    assert result['maximum_duration'] == '17 rounds'
    assert '25,000 gp' in result['inherent_ritual_review']


def test_dimension_pierce_is_not_a_teleport_and_requires_its_own_talent_cost():
    result = resolve_base_power(plan('warp:dimension-pierce'))
    assert result['range'] == 'Touch' and result['duration'] == '5 hours'
    assert 'ghost touch' in result['planar_interaction'] and 'teleport_distance' not in result


def test_greater_invigorate_projection_keeps_unknown_item_modifier_explicit():
    from app.marvelous_base_powers import automatic_self_effect
    rows = [dict(catalog_key='life:talent:greater-invigorate', effect_choice='exceed normal HP limit'),
            dict(catalog_key='life:talent:deeper-healing')]
    item = plan('life:temporary-hp', cl=7, contributions=rows)
    details = resolve_base_power(item)
    assert details['temporary_hp_formula'].startswith('14 + applicable casting ability modifier')
    assert 'May exceed' in details['temporary_hp_limit']
    assert automatic_self_effect(item) is None
    item['caster_level'] = 10
    rows[0]['effect_choice'] = 'normal HP limit'
    details = resolve_base_power(item)
    assert details['temporary_hp_formula'].startswith('20 +')
    assert 'Cannot exceed' in details['temporary_hp_limit']


def test_blink_modes_duration_scaling_cost_and_no_automatic_application():
    from app.marvelous_base_powers import automatic_self_effect
    item = plan('warp:blink', cl=6)
    effect = resolve_base_power(item)
    assert effect['miss_chance'] == '30%' and effect['duration'] == 'Concentration'
    assert 'teleport_distance' not in effect and automatic_self_effect(item) is None
    row = item['contributions'][0]
    row['effect_choice'] = 'penalty for minutes per caster level'
    with pytest.raises(ValueError, match='one-SP'):
        resolve_base_power(item)
    row['additional_spell_points'] = 1
    effect = resolve_base_power(item)
    assert effect['duration'] == '6 minutes' and 'Will negates' in effect['blink_effect']
    item['caster_level'] = 30
    assert resolve_base_power(item)['miss_chance'] == '50%'
    row['alternative'] = True
    with pytest.raises(ValueError, match='fixed Blink'):
        resolve_base_power(item)


@pytest.mark.parametrize('key', ['warp:create-gap', 'warp:distort-size'])
def test_space_geometry_modes_scale_without_teleport_or_automatic_application(key):
    from app.marvelous_base_powers import automatic_self_effect
    item = plan(key, cl=8)
    effect = resolve_base_power(item)
    assert effect['duration'] == 'Concentration' and 'teleport_distance' not in effect
    assert automatic_self_effect(item) is None
    if key == 'warp:create-gap':
        assert effect['maximum_cubes'] == 3
    else:
        assert '15 ft.' in effect['space_adjustment'] and 'not size category' in effect['size_rules']
    row = item['contributions'][0]
    row['effect_choice'] = 'minutes per caster level'
    with pytest.raises(ValueError, match='SP'):
        resolve_base_power(item)
    row['additional_spell_points'] += 1
    assert resolve_base_power(item)['duration'] == '8 minutes'


def test_climate_projects_area_and_casting_requirement_without_guessing_range_interactions():
    rows = [dict(catalog_key='weather:advanced-talent:climate'),
            dict(catalog_key='weather:talent:greater-size-range')]
    item = plan('weather:control', cl=10, contributions=rows)
    effect = resolve_base_power(item)
    assert effect['area_radius'] == '2 miles'
    assert '20 minutes' in effect['casting_requirement']
    assert 'does not control' in effect['tornadoes']
    item['effect_range_steps'] = 1
    effect = resolve_base_power(item)
    assert 'manual resolution' in effect['power'] and 'casting_requirement' not in effect
    item['effect_range_steps'] = 0
    rows[0]['alternative'] = True
    assert 'manual resolution' in resolve_base_power(item)['power']


@pytest.mark.parametrize('cl,maximum', [(1,3), (6,3), (7,4), (14,5), (21,6), (28,7), (35,7)])
def test_weather_item_maximum_severity_uses_caster_level(cl, maximum):
    assert resolve_base_power(plan('weather:control', cl=cl))['maximum_severity'] == maximum


def test_weather_lords_scale_category_limits_and_keep_severity_seven_cap():
    rows = [dict(catalog_key='weather:talent:severe-weather'),
            dict(catalog_key='weather:advanced-talent:cold-lord'),
            dict(catalog_key='weather:advanced-talent:wind-lord')]
    item = plan('weather:control', cl=7, contributions=rows)
    effect = resolve_base_power(item)
    assert effect['maximum_severity'] == 5 and effect['cold_severity_limit'] == 6
    assert effect['wind_severity_limit'] == 6 and '90 degrees' in effect['wind_control']
    item['caster_level'] = 28
    effect = resolve_base_power(item)
    assert effect['maximum_severity'] == 7 and effect['excess_severity_bonus'] == 1
    assert effect['cold_severity_limit'] == 7 and effect['cold_excess_severity_bonus'] == 2
    assert 'Severity stays at 7' in effect['excess_severity']


@pytest.mark.parametrize('cl,bonus', [(1,1), (3,1), (4,2), (8,3), (16,5), (20,5)])
def test_enhance_equipment_item_bonus_uses_ultimate_progression(cl, bonus):
    effect = resolve_base_power(plan('enhancement:enhance', cl=cl))
    assert effect['equipment_enhancement_bonus'] == bonus
    assert 'Does not stack' in effect['stacking'] and '50 pieces' in effect['equipment_targets']


def test_greater_and_mass_equipment_projection_does_not_invent_unknown_effects():
    rows = [dict(catalog_key='enhancement:talent:greater-enhance-equipment'),
            dict(catalog_key='enhancement:talent:mass-enhancement-mass')]
    item = plan('enhancement:enhance', cl=20, contributions=rows)
    effect = resolve_base_power(item)
    assert effect['equipment_enhancement_bonus'] == 6 and effect['maximum_targets'] == 11
    assert effect['duration'] == '20 rounds'
    rows.append(dict(catalog_key='enhancement:advanced-talent:bestow-life'))
    effect = resolve_base_power(item)
    assert 'manual resolution' in effect['power'] and 'equipment_enhancement_bonus' not in effect


@pytest.mark.parametrize('suffix,choice,field,expected', [
    ('energize-body-enhance', 'suppress fatigue / reduce exhaustion', 'carrying_capacity_multiplier', 4),
    ('energize-body-enhance', 'suppress exhaustion', 'carrying_capacity_multiplier', 4),
    ('ragged-edges-enhance', 'half caster level bleed', 'additional_bleed_damage', 6),
    ('ragged-edges-enhance', 'caster level bleed', 'additional_bleed_damage', 12),
    ('spectral-enhancement-enhance-gravecaller-s-hb', 'empowered ghost touch armor', 'negative_energy_resistance', 6),
    ('spectral-enhancement-enhance-gravecaller-s-hb', 'empowered ghost touch armor', 'possession_negative_energy_save_bonus', 4),
    ('spectral-enhancement-enhance-gravecaller-s-hb', 'empowered ghost touch weapon', 'undead_incorporeal_hit', 'Will save or sickened for 1 round, bypassing sickened immunity.'),
])
def test_enhancement_mode_projects_its_own_effect_not_equipment_bonus(suffix, choice, field, expected):
    rows = [dict(catalog_key='enhancement:enhance-talent:' + suffix, effect_choice=choice)]
    item = plan('enhancement:enhance', cl=12, contributions=rows)
    effect = resolve_base_power(item)
    assert effect[field] == expected and 'equipment_enhancement_bonus' not in effect
    assert effect['duration'] == '12 rounds'
    rows[0]['effect_choice'] = ''
    assert 'mode_review' in resolve_base_power(item)
    assert field not in resolve_base_power(item)
    rows[0]['effect_choice'] = choice
    rows[0]['alternative'] = True
    assert field not in resolve_base_power(item)


def test_spectral_object_and_unempowered_armor_do_not_claim_empowered_benefits():
    key = 'enhancement:enhance-talent:spectral-enhancement-enhance-gravecaller-s-hb'
    for mode in ('solid to incorporeal creatures', 'ghost touch armor', 'ghost touch weapon'):
        effect = resolve_base_power(plan('enhancement:enhance', cl=12, contributions=[dict(catalog_key=key, effect_choice=mode)]))
        assert effect['spectral_mode'] == mode
        assert 'negative_energy_resistance' not in effect and 'undead_incorporeal_hit' not in effect


@pytest.mark.parametrize('cl,bleed,multiplier', [(1,1,2), (4,2,2), (5,2,3), (10,5,4)])
def test_enhancement_mode_low_level_floors_and_scaling(cl, bleed, multiplier):
    effect = resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[dict(
        catalog_key='enhancement:enhance-talent:ragged-edges-enhance', effect_choice='half caster level bleed')]))
    assert effect['additional_bleed_damage'] == bleed
    effect = resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[dict(
        catalog_key='enhancement:enhance-talent:energize-body-enhance', effect_choice='suppress exhaustion')]))
    assert effect['carrying_capacity_multiplier'] == multiplier


def test_mixed_enhancement_payloads_do_not_claim_one_supported_effect():
    rows = [dict(catalog_key='enhancement:enhance-talent:energize-body-enhance', effect_choice='suppress exhaustion'),
            dict(catalog_key='enhancement:enhance-talent:ragged-edges-enhance', effect_choice='caster level bleed')]
    effect = resolve_base_power(plan('enhancement:enhance', cl=10, contributions=rows))
    assert 'manual resolution' in effect['power']
    assert 'carrying_capacity_multiplier' not in effect and 'additional_bleed_damage' not in effect


@pytest.mark.parametrize('cl,speed,skill,penalty,reflexes', [
    (1,10,2,-2,1), (4,10,2,-2,1), (5,20,4,-3,2),
    (8,20,4,-3,2), (9,20,4,-3,3), (10,30,6,-4,3), (13,30,6,-4,4),
])
def test_movement_cripple_and_reflexes_project_distinct_level_progressions(cl, speed, skill, penalty, reflexes):
    row = dict(catalog_key='enhancement:enhance-talent:alter-movement-enhance', effect_choice='increase one movement speed')
    item = plan('enhancement:enhance', cl=cl, contributions=[row])
    effect = resolve_base_power(item)
    assert effect['movement_speed_bonus'] == f'+{speed} ft. enhancement'
    assert effect['movement_skill_bonus'] == skill
    assert 'does not grant' in effect['movement_target']
    row['effect_choice'] = 'halve all movement speeds'
    effect = resolve_base_power(item)
    assert 'minimum 5 ft.' in effect['movement_multiplier']
    assert 'movement_speed_bonus' not in effect
    row.clear(); row['catalog_key'] = 'enhancement:enhance-talent:cripple-enhance'
    effect = resolve_base_power(item)
    assert effect['roll_penalty'] == penalty
    row['catalog_key'] = 'enhancement:enhance-talent:superior-reflexes-enhance'
    effect = resolve_base_power(item)
    assert effect['initiative_bonus'] == reflexes
    assert effect['additional_attacks_of_opportunity'] == reflexes
    assert 'Allowed' in effect['flat_footed_attacks_of_opportunity']
    assert 'equipment_enhancement_bonus' not in effect


def test_alter_movement_requires_mode_and_does_not_project_unknown_combinations():
    rows = [dict(catalog_key='enhancement:enhance-talent:alter-movement-enhance')]
    item = plan('enhancement:enhance', cl=10, contributions=rows)
    assert 'mode_review' in resolve_base_power(item)
    rows[0]['effect_choice'] = 'increase one movement speed'
    rows.append(dict(catalog_key='enhancement:talent:mass-enhancement-mass'))
    effect = resolve_base_power(item)
    assert effect['maximum_targets'] == 6 and effect['duration'] == '10 rounds'
    rows.append(dict(catalog_key='enhancement:enhance-talent:cripple-enhance'))
    effect = resolve_base_power(item)
    assert 'manual resolution' in effect['power']
    assert 'movement_speed_bonus' not in effect and 'roll_penalty' not in effect


@pytest.mark.parametrize('cl,skill,save,vigor,reduction', [(1,5,2,2,1), (4,6,2,2,1), (5,6,3,2,1), (7,6,3,4,2), (14,8,4,6,3)])
def test_skill_save_and_vigor_enhancements_scale_independently(cl, skill, save, vigor, reduction):
    for suffix,choice,expected in [
        ('enhance-focus-enhance', 'Acrobatics', {'skill': 'Acrobatics', 'skill_enhancement_bonus': skill}),
        ('staunch-resistance-enhance', 'Will', {'saving_throw': 'Will', 'untyped_save_bonus': save}),
        ('supply-vigor-enhance', 'Constitution', {'ability_score': 'Constitution',
            'ignored_existing_ability_damage_drain_penalty': vigor, 'incoming_ability_damage_drain_reduction': reduction}),
    ]:
        row = dict(catalog_key='enhancement:enhance-talent:' + suffix, effect_choice=choice)
        item = plan('enhancement:enhance', cl=cl, contributions=[row])
        effect = resolve_base_power(item)
        assert all(effect[field] == value for field, value in expected.items())
        assert 'equipment_enhancement_bonus' not in effect
        row['effect_choice'] = ''
        assert 'mode_review' in resolve_base_power(item)


@pytest.mark.parametrize('cl', [1, 2, 5, 14])
def test_harden_weaken_modes_keep_object_and_creature_effects_separate(cl):
    for mode,field,expected in [('increase hardness', 'hardness_adjustment', cl),
        ('decrease hardness', 'hardness_adjustment', -cl),
        ('grant DR/adamantine', 'damage_reduction', f'{max(1, cl // 2)}/adamantine'),
        ('decrease bypassable DR', 'damage_reduction_decrease', max(1, cl // 2))]:
        effect = resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[dict(
            catalog_key='enhancement:enhance-talent:harden-weaken-enhance', effect_choice=mode)]))
        assert effect[field] == expected
        assert ('fragile' in effect) == (mode == 'decrease hardness')
        assert ('dr_limits' in effect) == (mode == 'decrease bypassable DR')
        assert 'equipment_enhancement_bonus' not in effect


@pytest.mark.parametrize('cl', [1,5,6,11,12,17,18])
def test_flexibility_unlocks_only_earned_tiers_and_poison_does_not_invent_dc(cl):
    effect = resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[dict(
        catalog_key='enhancement:enhance-talent:improved-flexibility-enhance')]))
    for field,minimum in [('narrow_spaces',6), ('tight_spaces',12), ('minimum_space',18)]:
        assert (field in effect) == (cl >= minimum)
    effect = resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[dict(
        catalog_key='enhancement:enhance-talent:superior-poison-enhance')]))
    assert effect['additional_successful_saves_to_cure'] == 1
    assert 'rather than increasing its DC' in effect['poison_target']


@pytest.mark.parametrize('cl', [1,3,4,7,10,14])
def test_weapon_enhancement_modes_preserve_dice_and_separate_benefits(cl):
    for suffix,choice,field,expected in [
        ('energy-enhancement-enhance', 'weapon: fire', 'additional_energy_damage', f'1d6+{cl // 2} fire'),
        ('energy-enhancement-enhance', 'consumable: cold', 'additional_energy_damage', f'{cl} cold'),
        ('deadly-weapon-enhance', 'keen and critical confirmation', 'critical_confirmation_bonus', cl // 3),
        ('deadly-weapon-enhance', 'bypass DR: cold iron', 'bypassed_damage_reduction', 'cold iron'),
        ('ravenous-weapon-enhance-sm', 'damage wielder on a miss', 'wielder_damage_on_miss', f'{1 + cl // 4}d6 untyped'),
        ('traveling-weapon-enhance', 'ranged or throwing weapon: ignore cover', 'ignored_cover_ac_bonus', 2 + 2 * (cl // 7)),
    ]:
        row = dict(catalog_key='enhancement:enhance-talent:' + suffix, effect_choice=choice)
        item = plan('enhancement:enhance', cl=cl, contributions=[row])
        effect = resolve_base_power(item)
        assert effect[field] == expected and 'equipment_enhancement_bonus' not in effect
        row['effect_choice'] = ''
        assert 'mode_review' in resolve_base_power(item)


@pytest.mark.parametrize('energy,minimum', [('sonic',5), ('force',10)])
def test_alternative_energy_projection_requires_fixed_talent_and_mode_level(energy, minimum):
    from app.marvelous_base_powers import ENERGY_ENHANCEMENT_KEY, ALTERNATIVE_ENERGY_KEY
    rows = [dict(catalog_key=ENERGY_ENHANCEMENT_KEY, effect_choice='weapon: ' + energy)]
    item = plan('enhancement:enhance', cl=minimum, contributions=rows)
    assert 'additional_energy_damage' not in resolve_base_power(item)
    rows.append(dict(catalog_key=ALTERNATIVE_ENERGY_KEY))
    assert resolve_base_power(item)['energy_type'] == energy
    item['caster_level'] = minimum - 1
    assert 'additional_energy_damage' not in resolve_base_power(item)
    item['caster_level'] = minimum
    rows[-1]['alternative'] = True
    assert 'additional_energy_damage' not in resolve_base_power(item)


def test_weapon_property_modes_do_not_gain_other_modes_benefits():
    cases = [
        ('traveling-weapon-enhance', 'non-throwing melee weapon: throwing and returning', 'weapon_properties', 'ignored_cover_ac_bonus'),
        ('ravenous-weapon-enhance-sm', 'vicious weapon', 'weapon_property', 'wielder_damage_on_miss'),
        ('deadly-weapon-enhance', 'bypass DR: silver', 'bypassed_damage_reduction', 'critical_confirmation_bonus'),
    ]
    for suffix,mode,present,absent in cases:
        effect = resolve_base_power(plan('enhancement:enhance', cl=10, contributions=[dict(
            catalog_key='enhancement:enhance-talent:' + suffix, effect_choice=mode)]))
        assert present in effect and absent not in effect


@pytest.mark.parametrize('cl,radius', [(1,30), (4,40), (10,55), (15,65)])
def test_light_item_bright_radius_preserves_item_duration_and_is_not_sunlight(cl, radius):
    effect = resolve_base_power(plan('light:glow', cl=cl))
    assert effect['bright_light_radius'] == f'{radius} ft.'
    assert f'{radius} ft. beyond' in effect['illumination_extension']
    assert effect['duration'] == f'{cl} minutes'
    assert 'not equivalent to daylight' in effect['sunlight']


def test_daylight_area_and_star_genesis_central_daylight_are_distinct():
    effect = resolve_base_power(plan('light:glow', cl=10, contributions=[dict(catalog_key='light:advanced-talent:daylight-light')]))
    assert effect['bright_light_radius'] == '2 miles'
    assert '5 miles beyond' in effect['illumination_extension']
    assert 'daylight_equivalent_radius' not in effect
    rows = [dict(catalog_key='light:advanced-talent:star-genesis', effect_choice='expanded radius'),
            dict(catalog_key='light:talent:intensity-control')]
    item = plan('light:glow', cl=10, contributions=rows)
    effect = resolve_base_power(item)
    assert effect['bright_light_radius'] == '105 ft.'
    assert 'daylight_equivalent_radius' not in effect
    rows[0]['effect_choice'] = 'expanded radius with central daylight'
    assert resolve_base_power(item)['daylight_equivalent_radius'] == '55 ft.'
    rows.append(dict(catalog_key='light:advanced-talent:daylight-light'))
    effect = resolve_base_power(item)
    assert 'manual resolution' in effect['power'] and 'bright_light_radius' not in effect


def test_irradiance_and_radiation_modes_show_only_supported_condition_effects():
    rows = [dict(catalog_key='light:talent:irradiance-light', effect_choice='sicken glowing target')]
    item = plan('light:glow', cl=10, contributions=rows)
    effect = resolve_base_power(item)
    assert 'glowing creature is sickened' in effect['condition']
    assert 'radiation_exposure' not in effect
    rows[0]['effect_choice'] = 'nauseating bright light'
    assert 'success still sickens' in resolve_base_power(item)['condition']
    rows.append(dict(catalog_key='light:advanced-talent:radiation-light'))
    assert 'low radiation' in resolve_base_power(item)['radiation_exposure']
    rows[0]['effect_choice'] = 'sicken glowing target'
    assert 'radiation_exposure' not in resolve_base_power(item)
    assert 'manual resolution' in resolve_base_power(item)['power']


@pytest.mark.parametrize('rows', [
    [dict(catalog_key='light:advanced-talent:daylight-light', alternative=True)],
    [dict(catalog_key='light:advanced-talent:daylight-light')] * 2,
    [dict(catalog_key='light:talent:style-utility')],
    [dict(catalog_key='light:advanced-talent:everglow'), dict(catalog_key='light:talent:lingering-glow')],
])
def test_unsupported_light_modifications_do_not_claim_basic_bright_area(rows):
    effect = resolve_base_power(plan('light:glow', cl=10, contributions=rows))
    assert 'manual resolution' in effect['power']
    assert 'bright_light_radius' not in effect


@pytest.mark.parametrize('cl', [1,5,10,20])
def test_light_lens_base_and_numeric_variants_do_not_emit_bright_light(cl):
    effect = resolve_base_power(plan('light:lens', cl=cl))
    assert effect['sight_perception_bonus'] == f'+{2 + cl // 5} circumstance'
    assert effect['perception_distance_increment'] == f'{10 + 10 * cl} ft. per +1 DC'
    for suffix,field,expected in [
        ('aiming-scope-lens', 'ranged_attack_competence_bonus', 1 + cl // 10),
        ('halo-effect-lens-utility', 'bluff_diplomacy_circumstance_bonus', 2 + cl // 4),
        ('obscure-lens', 'defensive_uses_per_round', 1 + cl // 10),
        ('rose-tinted-lens-jester-s-hb', 'ending_burst_fire_damage', f'{cl}d4 fire on failed Reflex save if the lens is ended as part of the burst'),
    ]:
        item = plan('light:lens', cl=cl, contributions=[dict(catalog_key='light:lens-talent:' + suffix)])
        effect = resolve_base_power(item)
        assert effect[field] == expected
        assert 'bright_light_radius' not in effect and effect['duration'] == f'{cl} minutes'


def test_lens_unresolved_modifiers_and_multiple_payloads_do_not_invent_statistics():
    rows = [dict(catalog_key='light:lens-talent:aiming-scope-lens'), dict(catalog_key='light:lens-talent:obscure-lens')]
    effect = resolve_base_power(plan('light:lens', cl=10, contributions=rows))
    assert 'manual resolution' in effect['power'] and 'ranged_attack_competence_bonus' not in effect
    effect = resolve_base_power(plan('light:lens', cl=10, contributions=[dict(catalog_key='light:lens-talent:chameleon-lens')]))
    assert 'do not substitute' in effect['casting_modifier_review']


@pytest.mark.parametrize('suffix,mode,field,phrase', [
    ('doubled-nimbus', 'increase casting time one step', 'activation_review', 'not silently rewritten'),
    ('doubled-nimbus', 'spend SP instead of increasing casting time', 'nimbus_timing', 'does not increase casting time'),
    ('flash', 'choose application timing once per round', 'light_application_timing', 'only once per round'),
    ('flash', 'swift-action additional application', 'light_application_timing', 'no area or creature'),
])
def test_light_timing_modes_are_explicit_without_changing_item_activation(suffix, mode, field, phrase):
    item = plan('light:glow', cl=10, activation='standard', contributions=[dict(
        catalog_key='light:talent:' + suffix, effect_choice=mode)])
    assert phrase in resolve_base_power(item)[field]
    assert item['activation'] == 'standard'


def test_telekinesis_metadata_does_not_claim_unimplemented_effect_or_concentration_rules():
    effect = resolve_base_power(plan('telekinesis:force', cl=15, contributions=[dict(
        catalog_key='telekinesis:advanced-talent:focused-power', effect_choice='one additional size category')]))
    assert 'manual resolution' in effect['power']
    assert 'cannot use Sustained Force' in effect['concentration_review']
    assert 'final duration' in effect['telekinesis_review']


@pytest.mark.parametrize('cl,size,speed', [(1,'Diminutive',20), (3,'Tiny',20), (5,'Small',25),
    (8,'Medium',25), (11,'Large',30), (15,'Huge',35), (20,'Gargantuan',40),
    (25,'Colossal',45), (30,'Colossal+',50), (40,'Colossal++',60),
    (50,'Colossal+++',70), (60,'Colossal++++',80)])
def test_telekinesis_item_base_uses_reviewed_size_and_speed_progressions(cl, size, speed):
    effect = resolve_base_power(plan('telekinesis:force', cl=cl))
    assert effect['maximum_lift_size'] == size
    assert effect['telekinesis_speed'] == f'{speed} ft.'
    assert effect['duration'] == f'{cl} rounds'
    assert 'actual lifted object' in effect['bludgeon_resolution']
    assert 'granted_fly_speed' not in effect


def test_supported_telekinesis_modifiers_combine_without_guessing_target_statistics():
    rows = [dict(catalog_key='telekinesis:talent:' + suffix) for suffix in (
        'powerful-telekinesis', 'greater-speed', 'acceleration', 'flight', 'dampening-field', 'finesse-utility')]
    rows.append(dict(catalog_key='telekinesis:talent:divided-mind-mass', effect_choice='multiple lifted objects'))
    effect = resolve_base_power(plan('telekinesis:force', cl=10, contributions=rows))
    assert effect['maximum_lift_size'] == 'Large'
    assert effect['telekinesis_speed'] == '55 ft.' and effect['straight_line_movement'] == '110 ft.'
    assert effect['granted_fly_speed'] == '55 ft. (perfect)' and effect['maximum_lifted_targets'] == 11
    assert effect['lifted_object_hardness_bonus'] == 3 and effect['lifted_object_deflection_ac_bonus'] == 3
    assert effect['lifted_creature_damage_reduction'] == '5/piercing'
    assert effect['remote_skill_penalty'] == -5
    assert effect['duration'] == '10 rounds'


def test_telekinesis_low_level_dr_and_above_table_size_are_not_invented():
    rows = [dict(catalog_key='telekinesis:talent:dampening-field')]
    assert resolve_base_power(plan('telekinesis:force', cl=1, contributions=rows))['lifted_creature_damage_reduction'] == '0/piercing'
    rows = [dict(catalog_key='telekinesis:talent:powerful-telekinesis')]
    assert 'above Colossal++++' in resolve_base_power(plan('telekinesis:force', cl=60, contributions=rows))['maximum_lift_size']


@pytest.mark.parametrize('rows', [
    [dict(catalog_key='telekinesis:talent:greater-speed', alternative=True)],
    [dict(catalog_key='telekinesis:talent:greater-speed')] * 2,
    [dict(catalog_key='telekinesis:talent:divided-mind-mass', effect_choice='multiple maneuver or push targets')],
    [dict(catalog_key='telekinesis:advanced-talent:effortless-telekinesis')],
])
def test_unsupported_telekinesis_modifiers_do_not_keep_stale_lifting_values(rows):
    effect = resolve_base_power(plan('telekinesis:force', cl=10, contributions=rows))
    assert 'manual resolution' in effect['power']
    assert 'maximum_lift_size' not in effect and 'telekinesis_speed' not in effect


@pytest.mark.parametrize('kind,choice', [('physical', 'Strength + Dexterity'), ('mental', 'Wisdom + Charisma')])
def test_paired_ability_projection_requires_fixed_dual_enhancement(kind, choice):
    rows = [dict(catalog_key=f'enhancement:enhance-talent:{kind}-enhancement-enhance', effect_choice=choice)]
    item = plan('enhancement:enhance', cl=14, contributions=rows)
    assert 'ability_score' not in resolve_base_power(item)
    rows.append(dict(catalog_key='enhancement:talent:dual-enhancement'))
    effect = resolve_base_power(item)
    assert effect['ability_score'] == choice
    assert effect['ability_enhancement_bonus'] == 6
    rows[-1]['alternative'] = True
    assert 'ability_score' not in resolve_base_power(item)


@pytest.mark.parametrize('kind,choice', [('physical', 'Dexterity'), ('mental', 'Wisdom')])
@pytest.mark.parametrize('cl,bonus', [(1,2), (7,4), (14,6), (21,8)])
def test_ability_enhancement_projects_selected_score_without_equipment_bonus(kind, choice, cl, bonus):
    row = dict(catalog_key=f'enhancement:enhance-talent:{kind}-enhancement-enhance', effect_choice=choice)
    effect = resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[row]))
    assert effect['ability_score'] == choice and effect['ability_enhancement_bonus'] == bonus
    assert 'equipment_enhancement_bonus' not in effect and 'Temporary' in effect['stacking']
    row['effect_choice'] = ''
    effect = resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[row]))
    assert 'mode_review' in effect and 'ability_enhancement_bonus' not in effect
    row['effect_choice'] = 'unsupported saved mode'
    with pytest.raises(ValueError, match='supported effect option'):
        resolve_base_power(plan('enhancement:enhance', cl=cl, contributions=[row]))
    with pytest.raises(ValueError, match='talent contribution'):
        resolve_base_power(plan('warp:dimension-pierce', contributions=[]))
    with pytest.raises(ValueError, match='one-SP'):
        resolve_base_power(plan('warp:dimension-pierce', contributions=[dict(
            catalog_key='warp:space-talent:dimension-pierce-space', additional_spell_points=0)]))


def test_fluctuate_modes_use_their_own_duration_and_teleport_distance():
    selected = dict(catalog_key='warp:space-talent:fluctuate-space', additional_spell_points=1, effect_choice='concentration')
    value = plan('warp:fluctuate', 8, contributions=[selected])
    result = resolve_base_power(value)
    assert result['duration'] == 'Concentration' and result['teleport_distance'] == '20 ft.'
    assert result['range'] == 'Touch'
    selected.update(effect_choice='rounds per caster level', additional_spell_points=2)
    assert resolve_base_power(value)['duration'] == '8 rounds'
    with pytest.raises(ValueError, match='talent contribution'):
        resolve_base_power(plan('warp:fluctuate', contributions=[]))


def test_level_scaling_and_instantaneous_effects():
    assert resolve_base_power(plan('life:temporary-hp', 7))['temporary_hp'] == 7
    # Item construction explicitly differs from ordinary Invigorate's one hour.
    assert resolve_base_power(plan('life:temporary-hp', 7))['duration'] == '7 minutes'
    assert resolve_base_power(plan('destruction:blast', 6))['damage'] == '3d6 bludgeoning'
    assert resolve_base_power(plan('warp:teleport', 6))['teleport_distance'] == '40 ft.'
    assert resolve_base_power(plan('alteration:shapeshift', 10))['traits'] == 3


@pytest.mark.parametrize('base', ['protection:aegis', 'protection:ward'])
def test_energy_resistance_choice_scales_and_rejects_unknown_energy(base):
    row = dict(catalog_key='protection:aegis-ward-talent:energy-resistance-aegis-ward', effect_choice='fire')
    result = resolve_base_power(plan(base, 10, contributions=[row]))
    assert result['energy_type'] == 'Fire' and result['energy_protection'] == '20'
    row['effect_choice'] = 'force'
    with pytest.raises(ValueError, match='supported effect option'):
        resolve_base_power(plan(base, 10, contributions=[row]))


def test_adaptation_immunity_takes_precedence_over_prerequisite_resistance():
    from app.marvelous_base_powers import automatic_self_effect
    rows = [dict(catalog_key='protection:aegis-ward-talent:energy-resistance-aegis-ward'),
            dict(catalog_key='protection:advanced-talent:adaptation-aegis', effect_choice='cold')]
    result = resolve_base_power(plan('protection:aegis', 10, contributions=rows))
    assert result['power'] == 'Energy immunity aegis'
    assert result['energy_type'] == 'Cold' and result['energy_protection'] == 'Immune'
    assert 'deflection_ac' not in result
    assert automatic_self_effect(plan('protection:aegis', 10, contributions=rows)) is None
    with pytest.raises(ValueError, match='not a ward'):
        resolve_base_power(plan('protection:ward', 10, contributions=rows))
    rows[-1]['alternative'] = True
    result = resolve_base_power(plan('protection:aegis', 10, contributions=rows))
    assert result['energy_protection'] == '20' and 'Not selected' in result['energy_type']


def test_spell_ward_modes_and_antimagic_upgrade_descriptors():
    rows = [dict(catalog_key='protection:aegis-ward-talent:spell-ward-aegis-ward')]
    result = resolve_base_power(plan('protection:aegis', 10, contributions=rows))
    assert result['spell_resistance'] == 20 and result['power'] == 'Spell Ward aegis'
    result = resolve_base_power(plan('protection:ward', 10, contributions=rows))
    assert '+10' in result['magic_skill_check'] and result['magic_skill_defense'] == 21
    rows.append(dict(catalog_key='protection:advanced-talent:antimagic-aura'))
    result = resolve_base_power(plan('protection:ward', 10, contributions=rows))
    assert 'without a magic skill check' in result['suppression']
    assert 'magic_skill_check' not in result
    with pytest.raises(ValueError, match='not its spell-resistance'):
        resolve_base_power(plan('protection:aegis', 10, contributions=rows))


@pytest.mark.parametrize('suffix,kind,sides', [
    ('acid-blast-blast-type-acid', 'acid', 6), ('crystal-blast-blast-type-crystal', 'piercing', 4),
    ('electric-blast-blast-type-electricity', 'electricity', 6), ('fire-blast-blast-type-fire', 'fire', 6),
    ('force-blast-blast-type-force', 'force', 6), ('frost-blast-blast-type-cold', 'cold', 6),
    ('adhesive-blast-blast-type-acid', 'acid', 6), ('alkali-blast-blast-type-acid', 'acid', 4),
    ('attracting-blast-blast-type-electric-lg', 'electricity', 6), ('battering-blast-blast-type-stone', 'bludgeoning', 4),
    ('blistering-blast-blast-type-fire', 'fire', 6), ('drowning-blast-blast-type-cold', 'bludgeoning', 6),
    ('living-crystal-blast-blast-type-crystal', 'piercing', 6), ('numbing-blast-blast-type-cold', 'cold', 6),
])
def test_reviewed_blast_type_changes_damage_projection(suffix, kind, sides):
    from app.content import magic_entry
    from app.marvelous_base_powers import automatic_damage_dice
    key = 'destruction:blast-type-talent:' + suffix
    assert magic_entry(key) is not None
    blueprint = plan('destruction:blast', 6, contributions=[dict(catalog_key=key)])
    result = resolve_base_power(blueprint)
    assert result['damage'] == f'3d{sides} {kind}'
    assert automatic_damage_dice(blueprint) == 3
    assert 'manually' in result['secondary_effects']
    blueprint['contributions'][0]['alternative'] = True
    assert automatic_damage_dice(blueprint) is None
    assert 'manual' in resolve_base_power(blueprint)['damage']
    assert 'Bludgeoning' not in resolve_base_power(blueprint)['power']


@pytest.mark.parametrize('suffix', ['drowning-blast-blast-type-cold', 'living-crystal-blast-blast-type-crystal'])
def test_reviewed_paid_blast_profiles_supply_additional_sp(suffix):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points, talent_construction_cost
    entry = magic_entry('destruction:blast-type-talent:' + suffix)
    points = talent_construction_spell_points(entry)
    assert points == 1
    assert talent_construction_cost(entry, additional_spell_points=points) == 2


def test_arcforge_technology_ward_upgrade_and_aegis_are_distinct():
    rows = [dict(catalog_key='protection:aegis-ward-talent:technological-suppression-aegis-ward-lg')]
    result = resolve_base_power(plan('protection:ward', 10, contributions=rows))
    assert 'craft DC − 4' in result['technology_check']
    result = resolve_base_power(plan('protection:aegis', 10, contributions=rows))
    assert result['magic_skill_defense'] == 21 and 'non-physical' in result['technology_protection']
    rows.append(dict(catalog_key='protection:advanced-talent:antimagic-aura-arcforge-addendum-lg'))
    result = resolve_base_power(plan('protection:ward', 10, contributions=rows))
    assert result['power'] == 'Antimagic Aura technological ward'
    assert 'without a check' in result['technology_check']
    with pytest.raises(ValueError, match='not its aegis'):
        resolve_base_power(plan('protection:aegis', 10, contributions=rows))


def test_guided_base_blast_and_unsupported_shape_combinations():
    from app.marvelous_base_powers import GUIDED_STRIKE_KEY, automatic_damage_dice
    rows = [dict(catalog_key=GUIDED_STRIKE_KEY)]
    blueprint = plan('destruction:blast', 6, contributions=rows)
    result = resolve_base_power(blueprint)
    assert result['damage'] == '3d6 bludgeoning' and result['attack_circumstance_bonus'] == 20
    assert automatic_damage_dice(blueprint) == 3
    rows.append(dict(catalog_key='destruction:blast-shape-talent:chain-blast-blast-shape'))
    assert automatic_damage_dice(blueprint) is None
    assert 'attack_circumstance_bonus' not in resolve_base_power(blueprint)


@pytest.mark.parametrize('shape', ['chain-blast-blast-shape', 'mutable-blast-blast-shape'])
def test_instant_shape_geometry_scales_without_changing_blast_dice(shape):
    from app.marvelous_base_powers import automatic_damage_dice
    rows = [dict(catalog_key='destruction:blast-shape-talent:' + shape),
            dict(catalog_key='destruction:blast-type-talent:crystal-blast-blast-type-crystal')]
    blueprint = plan('destruction:blast', 6, contributions=rows)
    result = resolve_base_power(blueprint)
    assert result['damage'] == '3d4 piercing' and automatic_damage_dice(blueprint) == 3
    if shape.startswith('chain'):
        assert result['maximum_targets'] == 4 and result['maximum_jump_distance'] == '15 ft.'
    else:
        assert result['maximum_cubes'] == 8 and result['saving_throw'] == 'Reflex half'
    blueprint['caster_level'] = 10
    result = resolve_base_power(blueprint)
    if shape.startswith('chain'):
        assert result['maximum_targets'] == 6 and result['maximum_jump_distance'] == '20 ft.'
    else:
        assert result['maximum_cubes'] == 10


def test_knights_blast_and_grandmaster_preserve_typed_dice_and_scale_path():
    from app.marvelous_base_powers import KNIGHTS_BLAST_KEY, GRANDMASTER_KEY, automatic_damage_dice
    rows = [dict(catalog_key=KNIGHTS_BLAST_KEY),
            dict(catalog_key='destruction:blast-type-talent:crystal-blast-blast-type-crystal')]
    blueprint = plan('destruction:blast', 6, contributions=rows)
    result = resolve_base_power(blueprint)
    assert result['damage'] == '3d4 piercing' and automatic_damage_dice(blueprint) == 3
    assert result['maximum_path_length'] == '60 ft.' and result['maximum_turns'] == 1
    rows.append(dict(catalog_key=GRANDMASTER_KEY))
    assert resolve_base_power(blueprint)['maximum_turns'] == 6
    blueprint['caster_level'] = 10
    result = resolve_base_power(blueprint)
    assert result['maximum_path_length'] == '75 ft.' and result['maximum_turns'] == 10
    rows.pop(0)
    assert automatic_damage_dice(blueprint) is None


@pytest.mark.parametrize('choice,area,save', [('single square', 'One 5-foot square', 'Reflex negates'),
                                          ('expanded burst', 'Burst radius up to 20 ft.', 'Reflex half')])
def test_explosive_orb_modes_preserve_typed_damage(choice, area, save):
    from app.marvelous_base_powers import EXPLOSIVE_ORB_KEY, automatic_damage_dice
    blueprint = plan('destruction:blast', 10, contributions=[dict(catalog_key=EXPLOSIVE_ORB_KEY, effect_choice=choice),
        dict(catalog_key='destruction:blast-type-talent:crystal-blast-blast-type-crystal')])
    effect = resolve_base_power(blueprint)
    assert effect['area'] == area and effect['saving_throw'] == save
    assert effect['damage'] == '5d4 piercing' and automatic_damage_dice(blueprint) == 5
    blueprint['contributions'][0].pop('effect_choice')
    assert automatic_damage_dice(blueprint) is None


@pytest.mark.parametrize('choice,maximum', [('two surges', 2), ('additional surges', 5)])
def test_salvo_distributes_instead_of_multiplying_damage(choice, maximum):
    from app.marvelous_base_powers import BLAST_SALVO_KEY, automatic_damage_dice
    blueprint = plan('destruction:blast', 12, contributions=[dict(catalog_key=BLAST_SALVO_KEY, effect_choice=choice)])
    result = resolve_base_power(blueprint)
    assert result['maximum_surges'] == maximum
    assert automatic_damage_dice(blueprint) == 6
    blueprint['caster_level'] = 4
    assert resolve_base_power(blueprint)['maximum_surges'] == 2


@pytest.mark.parametrize('choice,area', [('burst', 'Burst radius 20 ft.'), ('cone', 'Cone 50 ft.'), ('line', 'Line 200 ft.')])
def test_sculpt_geometry_scales_from_caster_level(choice, area):
    from app.marvelous_base_powers import SCULPT_BLAST_KEY
    result = resolve_base_power(plan('destruction:blast', 10,
        contributions=[dict(catalog_key=SCULPT_BLAST_KEY, effect_choice=choice)]))
    assert result['area'] == area and result['saving_throw'] == 'Reflex half'


@pytest.mark.parametrize('choice,duration', [('concentration', 'Concentration'), ('rounds per caster level', '10 rounds')])
def test_energy_sphere_mode_controls_duration_and_keeps_typed_dice(choice, duration):
    from app.marvelous_base_powers import ENERGY_SPHERE_KEY
    blueprint = plan('destruction:blast', 10, contributions=[dict(catalog_key=ENERGY_SPHERE_KEY, effect_choice=choice),
        dict(catalog_key='destruction:blast-type-talent:crystal-blast-blast-type-crystal')])
    result = resolve_base_power(blueprint)
    assert result['duration'] == duration and result['fly_speed'] == '45 ft. (perfect)'
    assert result['damage'] == '5d4 piercing' and result['saving_throw'] == 'Reflex negates'
    blueprint['duration_steps'] = 1
    if choice == 'concentration':
        with pytest.raises(ValueError, match='duration ladder'): resolve_base_power(blueprint)
    else:
        assert resolve_base_power(blueprint)['duration'] == '10 minutes'


@pytest.mark.parametrize('choice,area,duration', [
    ('concentration cube', '5-foot cubic wall', 'Concentration'),
    ('straight wall', 'Straight wall up to 20 ft. high and 200 ft. wide', '10 rounds'),
    ('hemisphere', 'Hemisphere radius up to 25 ft.', '10 rounds')])
def test_energy_wall_geometry_duration_and_damage(choice, area, duration):
    from app.marvelous_base_powers import ENERGY_WALL_KEY
    result = resolve_base_power(plan('destruction:blast', 10,
        contributions=[dict(catalog_key=ENERGY_WALL_KEY, effect_choice=choice)]))
    assert result['area'] == area and result['duration'] == duration
    assert result['damage'] == '5d6 bludgeoning'
    assert 'does not block sight' in result['geometry']


@pytest.mark.parametrize('level,speed,bonus', [(1, 10, 1), (5, 20, 1), (10, 30, 2), (20, 50, 3)])
def test_ultimate_haste_item_values_scale_from_item_level(level, speed, bonus):
    result = resolve_base_power(plan('time:haste', level))
    assert result['attack_bonus'] == bonus and result['dodge_bonus_to_ac_and_reflex'] == bonus
    assert result['movement_enhancement_bonus'] == f'+{speed} ft. to all movement modes'


def test_reviewed_time_upgrades_and_unsupported_effects_are_not_confused():
    rows = [dict(catalog_key=key) for key in ('time:talent:improved-haste',
        'time:advanced-talent:temporal-haste', 'time:talent:augment-healing', 'time:talent:mass-time-mass')]
    result = resolve_base_power(plan('time:haste', 10, contributions=rows))
    assert result['fast_healing'] == 3 and result['maximum_targets'] == 6
    assert '3 extra attacks of opportunity' in result['improved_haste']
    assert 'move or swift' in result['temporal_haste']
    slow = resolve_base_power(plan('time:slow', 10, contributions=[dict(catalog_key='time:talent:improved-slow')]))
    assert slow['condition'] == 'Staggered' and slow['attack_ac_and_reflex_penalty'] == -2
    unsupported = resolve_base_power(plan('time:haste', 10, contributions=[dict(catalog_key='time:talent:retry-time')]))
    assert 'manual resolution' in unsupported['power'] and 'attack_bonus' not in unsupported


def test_beacon_placement_range_duration_and_required_contribution():
    result = resolve_base_power(plan('warp:beacon', 7))
    assert result['range'] == 'Touch' and result['duration'] == '7 hours'
    assert 'teleport_distance' not in result
    with pytest.raises(ValueError, match='Beacon contribution'):
        resolve_base_power(plan('warp:beacon', contributions=[]))
    with pytest.raises(ValueError, match='one-SP'):
        resolve_base_power(plan('warp:beacon', contributions=[dict(catalog_key='warp:space-talent:teleport-beacon-space', complexity=1, additional_spell_points=0)]))


@pytest.mark.parametrize('key,field', [('warp:teleport', 'teleport_distance'), ('weather:control', 'area_radius')])
def test_effect_range_is_separate_from_target_range(key, field):
    result = resolve_base_power(plan(key, 5, effect_range_steps=2))
    assert result[field] == '600 ft.' and result['range'] == 'Personal'
    with pytest.raises(ValueError): resolve_base_power(plan(key, effect_range_steps=3))


@pytest.mark.parametrize('key', ['life:cure', 'life:restore', 'life:temporary-hp'])
@pytest.mark.parametrize('level,targets', [(1, 2), (5, 3), (10, 6)])
def test_mass_healing_projects_target_limit_without_applying_an_alternative(key, level, targets):
    mass = dict(catalog_key='life:talent:mass-healing-mass')
    assert resolve_base_power(plan(key, level, contributions=[mass]))['maximum_targets'] == targets
    mass['alternative'] = True
    assert 'maximum_targets' not in resolve_base_power(plan(key, level, contributions=[mass]))


def test_mass_healing_keeps_per_target_amount_but_does_not_enable_single_target_automation():
    from app.marvelous_base_powers import automatic_self_effect
    rows = [dict(catalog_key='life:talent:mass-healing-mass'), dict(catalog_key='life:talent:deeper-healing')]
    cure = plan('life:cure', 10, contributions=rows)
    result = resolve_base_power(cure)
    assert result['healing'] == '4d8+10' and result['maximum_targets'] == 6
    assert automatic_self_effect(cure) is None
    invigorate = plan('life:temporary-hp', 10, contributions=rows)
    assert resolve_base_power(invigorate)['temporary_hp'] == 20
    assert automatic_self_effect(invigorate) is None
    rows.append(dict(catalog_key='life:talent:revitalize'))
    modified = resolve_base_power(cure)
    assert 'healing' not in modified and 'manual resolution' in modified['power']


def test_weather_category_projection_tracks_modes_and_does_not_guess_unknown_combinations():
    greater = dict(catalog_key='weather:talent:greater-weather', effect_choice='three weather categories')
    severe = dict(catalog_key='weather:talent:severe-weather')
    result = resolve_base_power(plan('weather:control', contributions=[greater, severe]))
    assert result['weather_categories'] == 3 and result['power'] == 'Change 3 weather categories'
    assert 'maximum severity 7' in result['severity_adjustment']
    greater['effect_choice'] = 'two weather categories'
    assert resolve_base_power(plan('weather:control', contributions=[greater]))['weather_categories'] == 2
    for rows in ([dict(greater, alternative=True)], [greater, greater],
                 [dict(catalog_key='weather:advanced-talent:climate')], [dict(greater, effect_choice='')]):
        modified = resolve_base_power(plan('weather:control', contributions=rows))
        assert 'manual resolution' in modified['power'] and 'weather_categories' not in modified


def test_restore_transitions_preserve_downgrades_and_ongoing_sources():
    from app.marvelous_base_powers import restore_condition_changes
    result = restore_condition_changes('body', ['Exhausted', 'Sickened', 'Battered'], ongoing=['Sickened'])
    assert result == [dict(condition='Exhausted', operation='replace', replacement='Fatigued'),
                      dict(condition='Sickened', operation='suppress', replacement=None),
                      dict(condition='Battered', operation='remove', replacement=None)]
    assert restore_condition_changes('mind', ['Panicked', 'Panicked'])[0]['replacement'] == 'Frightened'
    with pytest.raises(ValueError): restore_condition_changes('soul', [])


@pytest.mark.parametrize('mode,key,conditions', [
    ('body', 'restore-health', ('Exhausted', 'Nauseated')),
    ('mind', 'restore-senses', ('Frightened', 'Panicked', 'Confused', 'Dazed', 'Blinded', 'Deafened')),
])
def test_restore_talent_projection_removes_upgraded_conditions(mode, key, conditions):
    contribution = dict(catalog_key=f'life:cure-talent:{key}-cure')
    result = resolve_base_power(plan('life:restore', restore_mode=mode, contributions=[contribution]))
    changes = {change['condition']: change for change in result['restore_changes']}
    assert all(changes[name]['operation'] == 'remove' for name in conditions)
    assert all(changes[name]['replacement'] is None for name in conditions)
    contribution['alternative'] = True
    alternative = resolve_base_power(plan('life:restore', restore_mode=mode, contributions=[contribution]))
    assert alternative['restore_changes'] != result['restore_changes']


def test_upgraded_restore_preserves_ongoing_suppression_and_mode_boundaries():
    from app.marvelous_base_powers import restore_condition_changes
    assert restore_condition_changes('body', ['Exhausted'], ongoing=['Exhausted'], restore_health=True) == [
        dict(condition='Exhausted', operation='suppress', replacement=None)]
    assert restore_condition_changes('body', ['Confused'], restore_senses=True) == []
    assert restore_condition_changes('mind', ['Exhausted'], restore_health=True) == []
    with pytest.raises(ValueError, match='boolean'):
        restore_condition_changes('body', [], restore_health=1)


def test_range_duration_ladders_and_exclusions():
    p = plan('protection:aegis'); p.update(range_steps=2, duration_steps=2)
    result = resolve_base_power(p)
    assert result['range'] == '35 ft.'
    assert result['duration'] == '5 hours'
    p = plan('life:cure'); p['duration_steps'] = 1
    with pytest.raises(ValueError, match='duration ladder'): resolve_base_power(p)
    p = plan('warp:teleport'); p['range_steps'] = -1
    with pytest.raises(ValueError, match='range ladder'): resolve_base_power(p)


def test_wrong_sphere_and_invalid_level_rejected():
    p = plan('life:cure'); p['sphere'] = 'Destruction'
    with pytest.raises(ValueError, match='selected sphere'): resolve_base_power(p)
    p = plan('life:cure'); p['caster_level'] = 0
    with pytest.raises(ValueError, match='positive'): resolve_base_power(p)

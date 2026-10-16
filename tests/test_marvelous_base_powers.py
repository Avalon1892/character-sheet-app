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
    assert 'manual resolution' in resolve_base_power(cure)['healing']


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

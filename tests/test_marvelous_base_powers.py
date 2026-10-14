import pytest
from app.marvelous_base_powers import BASE_POWERS, resolve_base_power


def plan(key, cl=5, **changes):
    power = next(p for p in BASE_POWERS if p.key == key)
    if key == 'warp:beacon':
        changes.setdefault('contributions', [dict(catalog_key='warp:space-talent:teleport-beacon-space', complexity=2, additional_spell_points=1)])
    return dict(base_power=key, sphere=power.sphere, caster_level=cl,
                range_steps=0, duration_steps=0, **changes)


@pytest.mark.parametrize('power', BASE_POWERS)
def test_every_base_power_has_a_resolvable_projection(power):
    result = resolve_base_power(plan(power.key))
    assert result['power'] == power.name
    assert result['range'] and result['duration']
    assert result['caster_level'] == 5 and result['save_dc'] == 12 and result['magic_skill_bonus'] == 5


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

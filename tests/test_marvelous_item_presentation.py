from app.marvelous_item_presentation import ITEM_FIELDS, item_card_fields, item_card_html


def blueprint():
    return dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[])


def test_item_block_descriptors_and_all_field_locks():
    plan = blueprint()
    fields = item_card_fields(plan, name='Healing gem', slot='Neck', description='A bright gem.')
    assert fields['price'] == '2,000.00 gp' and fields['construction_cost'] == '1,000.00 gp'
    assert fields['range'] == 'Touch' and fields['duration'] == 'Instantaneous'
    html = item_card_html(fields)
    assert all(label in html for label in ('Aura', 'CL', 'Slot', 'Price', 'Weight', 'Activation', 'Uses', 'DESCRIPTION', 'CONSTRUCTION'))
    plan['display_overrides'] = {key: dict(locked=True, value=f'Manual {key}') for key in ITEM_FIELDS}
    changed = item_card_fields(plan, name='Other', slot='', description='Changed')
    assert all(changed[key] == f'Manual {key}' for key in ITEM_FIELDS)
    plan['display_overrides']['range']['locked'] = False
    assert item_card_fields(plan, name='Other', slot='', description='Changed')['range'] == 'Touch'


def test_sample_tradition_boons_are_concrete_but_do_not_invent_item_statistics():
    plan = blueprint()
    for key, phrase in [('city-construction', '+2 hardness'), ('evil-artifice', '25% more item HP'),
                        ('fey-touched', '8 continuous hours'), ('ley-linked', '+2 effective caster levels'),
                        ('cryptwood-artifice', '25 gp per original pound')]:
        plan['crafting_tradition'] = dict(key='crafting:' + key, name=key, description='')
        fields = item_card_fields(plan, name='Gem', slot='', description='')
        assert phrase in fields['description']
        assert fields['caster_level'] == '5'
        plan['display_overrides'] = {'description': dict(locked=True, value='Manual')}
        assert item_card_fields(plan, name='Gem', slot='', description='')['description'] == 'Manual'
        plan.pop('display_overrides')


def test_cross_sphere_requirements_appear_in_item_card_and_respect_lock():
    plan = dict(blueprint(), sphere='Warp', base_power='warp:teleport', caster_level=15,
                contributions=[dict(catalog_key='warp:advanced-talent:create-demiplane-utility', complexity=5, additional_spell_points=3),
                               dict(catalog_key='warp:space-talent:extradimensional-room-space', complexity=1)])
    fields = item_card_fields(plan, name='World seed', slot='', description='')
    assert 'Creation sphere / Expanded Materials' in fields['construction_requirements']
    plan['display_overrides'] = {'construction_requirements': dict(locked=True, value='Reviewed by GM')}
    assert item_card_fields(plan, name='World seed', slot='', description='')['construction_requirements'] == 'Reviewed by GM'


def test_item_block_escapes_manual_html():
    fields = item_card_fields(blueprint(), name='<script>bad</script>', slot='', description='<img src=x>\nSecond line')
    html = item_card_html(fields)
    assert '<script>' not in html and '<img src=x>' not in html
    assert '&lt;script&gt;' in html and '&lt;img src=x&gt;<br>Second line' in html


def test_unreviewed_sp_cost_is_visible_without_changing_quote_or_manual_lock():
    plan = blueprint()
    plan['contributions'] = [dict(catalog_key='life:talent:empathic-healing', complexity=3, additional_spell_points=2)]
    fields = item_card_fields(plan, name='Gem', slot='', description='')
    assert 'SP cost requires review' in fields['construction_requirements']
    assert fields['price'] == '8,000.00 gp'
    plan['display_overrides'] = {'construction_requirements': dict(locked=True, value='Reviewed manually')}
    assert item_card_fields(plan, name='Gem', slot='', description='')['construction_requirements'] == 'Reviewed manually'


def test_cost_details_use_saved_manual_costs_and_name_alternatives_and_drawbacks():
    from app.marvelous_item_presentation import contribution_cost_details
    plan = dict(contributions=[dict(catalog_key='life:talent:deeper-healing', complexity=7,
        additional_spell_points=3, alternative=True, alternative_group=2, effect_choice='custom review')],
        drawbacks=[dict(name='Custom limitation', reduction=2)])
    result = contribution_cost_details(plan)
    assert 'Deeper Healing (custom review) [alternative group 2]' in result
    assert '4 talent + 3 extra SP = 7 complexity' in result
    assert 'Custom limitation: −2 complexity' in result


def test_aura_updates_with_real_caster_level_and_respects_its_own_lock():
    plan = blueprint()
    assert item_card_fields(plan, name='Gem', slot='', description='')['aura'] == 'Faint (school not specified)'
    plan['caster_level'] = 12
    plan['display_overrides'] = dict(caster_level=dict(locked=True, value='1'))
    fields = item_card_fields(plan, name='Gem', slot='', description='')
    assert fields['caster_level'] == '1' and fields['aura'] == 'Strong (school not specified)'
    plan['display_overrides']['aura'] = dict(locked=True, value='No visible aura')
    plan['caster_level'] = 21
    assert item_card_fields(plan, name='Gem', slot='', description='')['aura'] == 'No visible aura'


def test_custom_prose_keeps_live_effect_summary_until_description_is_locked():
    plan = blueprint()
    fields = item_card_fields(plan, name='Gem', slot='', description='A small red gem.')
    assert fields['description'].startswith('A small red gem.')
    assert 'Healing: 1d8+5' in fields['description']
    plan['caster_level'] = 8
    assert 'Healing: 1d8+8' in item_card_fields(plan, name='Gem', slot='', description='A small red gem.')['description']
    plan['display_overrides'] = {'description': dict(locked=True, value='Fully manual effect')}
    assert item_card_fields(plan, name='Gem', slot='', description='Other prose')['description'] == 'Fully manual effect'


def test_tradition_rules_appear_in_item_description_without_overriding_lock():
    plan = blueprint()
    plan['crafting_tradition'] = dict(key='crafting:diviner-s-sight', name='Diviner’s Sight',
                                    description='Drawbacks: Educated, Fragile. Boon: Cheap.', notes='Divination requirement')
    fields = item_card_fields(plan, name='Gem', slot='', description='A gem.')
    assert 'Fragile' in fields['description'] and 'Divination requirement' in fields['description']
    assert fields['price'] == '1,800.00 gp'
    plan['display_overrides'] = {'description': dict(locked=True, value='Locked text')}
    assert item_card_fields(plan, name='Gem', slot='', description='A gem.')['description'] == 'Locked text'


def test_activation_requirement_values_update_without_overwriting_description_lock():
    plan = blueprint()
    plan['crafting_tradition'] = dict(key='crafting:fey-touched', name='Fey-Touched', description='Tradition')
    fields = item_card_fields(plan, name='Gem', slot='', description='')
    assert 'DC 10 Knowledge (nature)' in fields['description']
    plan['caster_level'] = 7
    assert 'DC 12 Knowledge (nature)' in item_card_fields(plan, name='Gem', slot='', description='')['description']
    plan['crafting_tradition']['key'] = 'crafting:evil-artifice'
    assert 'at least 4 HD' in item_card_fields(plan, name='Gem', slot='', description='')['description']
    plan['display_overrides'] = {'description': dict(locked=True, value='Manual description')}
    assert item_card_fields(plan, name='Gem', slot='', description='')['description'] == 'Manual description'


def test_multiple_powers_show_each_limit_description_and_child_locks():
    plan = blueprint()
    extra = dict(blueprint(), uses=50, effect_name='Reserve cure', effect_description='<custom> reserve effect',
                 display_overrides={'duration': dict(locked=True, value='Reviewed duration'),
                                    'caster_level': dict(locked=True, value='Reviewed CL')})
    plan['extra_effects'] = [extra]
    fields = item_card_fields(plan, name='Dual gem', slot='', description='Primary text')
    assert 'Independent' in fields['uses']
    assert '1/day' in fields['description'] and '50 total activations' in fields['description']
    assert 'Reserve cure' in fields['description'] and 'Reviewed duration' in fields['description']
    assert 'CL: Reviewed CL' in fields['description'] and 'Healing: 1d8+5' in fields['description']
    assert '&lt;custom&gt;' in item_card_html(fields)
    assert 'Power 2:' in fields['construction_requirements']
    plan['combination_mode'] = 'mixed'
    assert item_card_fields(plan, name='Dual gem', slot='', description='')['uses'] == 'All component limits apply'
    plan['display_overrides'] = {'description': dict(locked=True, value='Whole item locked')}
    assert item_card_fields(plan, name='Dual gem', slot='', description='')['description'] == 'Whole item locked'

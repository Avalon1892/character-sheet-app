import json
from dataclasses import replace
import pytest
from app.database import CharacterRepository
from app.services.crafting import CraftingService
from app.marvelous_item_rules import marvelous_remaining_uses
from app.recovery import FullRestEngine


@pytest.fixture
def crafter(tmp_path):
    repo = CharacterRepository(tmp_path / 'test.db')
    cid = repo.create_character('Crafter', 'Spheres')
    repo.add_feat(cid, 'Craft Marvelous Item')
    repo.update_hit_points(replace(repo.get_hit_points(cid), maximum=20, current=10, auto_calculate=False))
    yield repo, cid
    repo.close()


def item(repo, cid, uses=1):
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp',
                caster_level=5, activation='standard', uses=uses, range_steps=0,
                duration_steps=0, unique_changes=0, contributions=[])
    return CraftingService(repo, cid).save_marvelous_design(plan, name='Device', slot='', description='Custom')


def metadata(repo, cid, iid):
    return json.loads(next(i for i in repo.list_equipment(cid) if i.id == iid).automation_json)


def test_diviners_sight_requires_enabled_base_training_before_any_writes(crafter):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp', caster_level=5,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
        contributions=[], crafting_tradition=dict(key='crafting:diviner-s-sight'))
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Educated gem', slot='', description='')
    original = metadata(repo, cid, iid)
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='Use Magic Device cannot bypass'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo._connection.total_changes == before and metadata(repo, cid, iid) == original
    repo.add_spell(cid, 'A Divination talent', system='Sphere', school_or_sphere='Divination',
        catalog_key='divination:talent:expanded-divinations', catalog_category='Talent')
    assert repo.marvelous_activation_blockers(cid, plan)
    sphere_id = repo.add_spell(cid, 'Divination', system='Sphere', school_or_sphere='Divination',
        catalog_key='divination:base', catalog_category='Base Sphere')
    repo.set_spell_enabled(cid, sphere_id, False)
    assert repo.marvelous_activation_blockers(cid, plan)
    repo.set_spell_enabled(cid, sphere_id, True)
    assert not repo.marvelous_activation_blockers(cid, plan)
    repo.consume_marvelous_item_use(cid, iid)
    assert metadata(repo, cid, iid)['marvelous_uses_used'] == 1


def test_educated_requires_every_selected_magic_and_martial_base(crafter):
    repo, cid = crafter
    plan = dict(drawbacks=[dict(source='published', catalog_key='crafting:educated', required_spheres=['Life', 'Boxing'])])
    assert len(repo.marvelous_activation_blockers(cid, plan)) == 2
    repo.add_spell(cid, 'Life', system='Sphere', school_or_sphere='Life', catalog_key='life:base', catalog_category='Base Sphere')
    assert len(repo.marvelous_activation_blockers(cid, plan)) == 1
    repo.add_martial_talent(cid, 'Boxing', sphere='Boxing', catalog_key='boxing:base', catalog_category='Base Sphere')
    assert not repo.marvelous_activation_blockers(cid, plan)
    plan['drawbacks'][0]['required_spheres'] = []
    assert 'choose required spheres' in repo.marvelous_activation_blockers(cid, plan)[0]


def test_educated_save_rejects_unknown_spheres_without_writes_and_preserves_choices(crafter):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=5,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0, contributions=[],
        drawbacks=[dict(source='published', catalog_key='crafting:educated', name='Educated', reduction=0, required_spheres=['Unknown sphere'])])
    service = CraftingService(repo, cid)
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='unknown sphere'):
        service.save_marvelous_design(plan, name='Educated', slot='', description='')
    assert repo._connection.total_changes == before
    plan['drawbacks'][0]['required_spheres'] = ['Life', 'Boxing']
    iid = service.save_marvelous_design(plan, name='Educated', slot='', description='')
    assert metadata(repo, cid, iid)['marvelous_blueprint']['drawbacks'][0]['required_spheres'] == ['Life', 'Boxing']


def test_character_transfer_preserves_blueprint_project_and_independent_counters(crafter, tmp_path, monkeypatch):
    from app.transfer import export_character, import_character
    from app.marvelous_item_rules import MarvelousRequirements
    repo, cid = crafter
    repo.update_currency_purse(replace(repo.get_currency_purse(cid), gold=10000))
    service = CraftingService(repo, cid)
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=1,
                activation='standard', uses=2, range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[])
    plan['extra_effects'] = [{**plan, 'uses': 50}]
    slot = repo.list_worn_slots(cid)[0]
    iid = service.save_marvelous_design(plan, name='Transferred device', slot=slot, description='Manual description')
    monkeypatch.setattr(service, 'marvelous_plan_requirements', lambda p: MarvelousRequirements((), (), 0))
    service.start_marvelous_construction(iid)
    for day in ('2026-10-13', '2026-10-14', '2026-10-15'):
        repo.advance_marvelous_project(cid, iid, day=day, hours=8)
    repo.advance_marvelous_project(cid, iid, check_total=11)
    repo.consume_marvelous_item_use(cid, iid)
    repo.consume_marvelous_item_use(cid, iid, effect_index=1)
    before = metadata(repo, cid, iid)
    path = tmp_path / 'crafted.character.json'
    export_character(repo, cid, path)
    imported = import_character(repo, path)
    transferred = next(i for i in repo.list_equipment(imported) if i.name == 'Transferred device')
    assert transferred.id != iid and transferred.notes == 'Manual description' and transferred.slot == slot
    assert json.loads(transferred.automation_json) == before
    repo.consume_marvelous_item_use(imported, transferred.id, effect_index=1)
    after = metadata(repo, imported, transferred.id)
    assert marvelous_remaining_uses(after, 0) == 1 and marvelous_remaining_uses(after, 1) == 48
    assert metadata(repo, cid, iid) == before


def test_atomic_activation_and_zero_floor(crafter):
    repo, cid = crafter; iid = item(repo, cid)
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo.get_hit_points(cid).temporary == 5
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 0
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='No item uses'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('source', ['tradition', 'drawback'])
def test_sacrificing_preserves_spent_uses_on_rest_and_requires_confirmed_recharge(crafter, source):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp', caster_level=5,
                activation='standard', uses=2, range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    if source == 'tradition':
        plan['crafting_tradition'] = {'key': 'crafting:evil-artifice'}
    else:
        plan['drawbacks'] = [dict(source='published', catalog_key='crafting:sacrificing', name='Sacrificing', reduction=0)]
    plan['extra_effects'] = [{key: value for key, value in plan.items() if key not in {'crafting_tradition', 'drawbacks'}}]
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Sacrificial device', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid)
    repo.consume_marvelous_item_use(cid, iid, effect_index=1)
    assert repo.reset_marvelous_daily_uses(cid) == 0
    FullRestEngine(repo, cid).perform({'marvelous_items.daily_uses': True})
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1
    assert marvelous_remaining_uses(metadata(repo, cid, iid), 1) == 1
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='Confirm'):
        repo.record_marvelous_recharge(cid, iid)
    assert repo._connection.total_changes == before
    assert repo.record_marvelous_recharge(cid, iid, confirmed=True) == 2
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 2
    assert marvelous_remaining_uses(metadata(repo, cid, iid), 1) == 2
    assert repo.record_marvelous_recharge(cid, iid, confirmed=True) == 0
    other = repo.create_character('Other owner', 'Spheres')
    with pytest.raises(ValueError, match='owned'):
        repo.record_marvelous_recharge(other, iid, confirmed=True)


def test_custom_drawback_name_does_not_invent_special_recharge(crafter):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[], drawbacks=[dict(source='custom', name='Sacrificing', reduction=0)])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Custom limit', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid)
    assert repo.reset_marvelous_daily_uses(cid) == 1
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='no supported'):
        repo.record_marvelous_recharge(cid, iid, confirmed=True)
    assert repo._connection.total_changes == before


def test_editing_legacy_design_keeps_inventory_weight_unless_explicitly_replaced(crafter):
    repo, cid = crafter
    service = CraftingService(repo, cid)
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[], base_weight_lb=3)
    iid = service.save_marvelous_design(plan, name='Weighted device', slot='', description='')
    plan.pop('base_weight_lb')
    service.save_marvelous_design(plan, name='Old design', slot='', description='', item_id=iid)
    assert next(item for item in repo.list_equipment(cid) if item.id == iid).weight == 3
    plan['base_weight_lb'] = 0
    service.save_marvelous_design(plan, name='Weightless device', slot='', description='', item_id=iid)
    assert next(item for item in repo.list_equipment(cid) if item.id == iid).weight == 0


@pytest.mark.parametrize('suffix,sides,kind', [('crystal-blast-blast-type-crystal', 4, 'piercing'),
                                             ('force-blast-blast-type-force', 6, 'force')])
@pytest.mark.parametrize('guided', [False, True])
def test_blast_type_damage_roll_uses_selected_die_size_and_type(crafter, monkeypatch, suffix, sides, kind, guided):
    from app.content import magic_entry
    from app.marvelous_item_rules import talent_construction_spell_points, talent_construction_cost
    repo, cid = crafter
    entry = magic_entry('destruction:blast-type-talent:' + suffix)
    points = talent_construction_spell_points(entry)
    assert points == (1 if kind == 'force' else 0)
    plan = dict(schema_version=1, sphere='Destruction', base_power='destruction:blast', caster_level=6,
                activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[dict(catalog_key=entry['key'], additional_spell_points=points,
                                    complexity=talent_construction_cost(entry, additional_spell_points=points))])
    if guided:
        plan['contributions'].append(dict(catalog_key='destruction:blast-shape-talent:guided-strike-blast-shape',
                                          additional_spell_points=1, complexity=2))
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Blast device', slot='', description='')
    monkeypatch.setattr('random.randint', lambda low, high: high)
    result = repo.consume_marvelous_item_use(cid, iid)
    assert result['damage_rolls'] == [sides] * 3 and result['damage_rolled'] == sides * 3
    assert kind in result['damage_application'] and 'manually' in result['damage_application']
    if guided: assert result['attack_circumstance_bonus'] == 20


@pytest.mark.parametrize('mode', ['', 'distance', 'recharge'])
@pytest.mark.parametrize('source', ['tradition', 'drawback'])
def test_area_bound_recovery_follows_selected_variant_without_guessing_legacy_mode(crafter, mode, source):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp', caster_level=5,
                activation='standard', uses=2, range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[], crafting_tradition={'key': 'crafting:city-construction'}, area_bound_mode=mode)
    if source == 'drawback':
        plan.pop('crafting_tradition')
        plan['drawbacks'] = [dict(source='published', catalog_key='crafting:area-bound', name='Area-Bound', reduction=0)]
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Bound device', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid)
    assert repo.reset_marvelous_daily_uses(cid) == (1 if mode == 'distance' else 0)
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == (2 if mode == 'distance' else 1)
    if mode == 'recharge':
        assert repo.record_marvelous_recharge(cid, iid, confirmed=True) == 1
    else:
        with pytest.raises(ValueError, match='no supported'):
            repo.record_marvelous_recharge(cid, iid, confirmed=True)


def test_deeper_healing_invigorate_applies_and_spends_atomically(crafter):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp',
                caster_level=5, activation='standard', uses=2, range_steps=0,
                duration_steps=0, unique_changes=0,
                contributions=[dict(catalog_key='life:talent:deeper-healing', complexity=1)])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Deep vigor', slot='', description='')
    effect = repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert effect['temporary_hp'] == 10 and effect['duration'] == '5 minutes'
    assert repo.get_hit_points(cid).temporary == 10
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=19, temporary=12))
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo.get_hit_points(cid).temporary == 12
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 0


@pytest.mark.parametrize('nonlethal,remaining', [(15, 5), (3, 0)])
def test_painkiller_heals_potential_not_capped_temporary_hp(crafter, nonlethal, remaining):
    repo, cid = crafter
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=19, nonlethal=nonlethal))
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[dict(catalog_key=key, complexity=1) for key in
                               ('life:talent:painkiller', 'life:talent:deeper-healing')])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Pain relief', slot='', description='')
    result = repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    hp = repo.get_hit_points(cid)
    assert hp.current == 19 and hp.temporary == 1 and hp.nonlethal == remaining
    assert result['temporary_hp_granted'] == 1 and result['nonlethal_healed'] == nonlethal - remaining
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 0


def test_cure_recipient_is_separate_from_item_owner(crafter, monkeypatch):
    repo, cid = crafter
    recipient = repo.create_character('Recipient', 'Spheres')
    repo.update_hit_points(replace(repo.get_hit_points(recipient), maximum=30, current=5, auto_calculate=False))
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=5,
        activation='standard', uses=2, range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Cure device', slot='', description='')
    monkeypatch.setattr('random.randint', lambda a, b: 4)
    effect = repo.consume_marvelous_item_use(cid, iid, apply_to_self=True, target_character_id=recipient)
    assert effect['recipient_character_id'] == recipient
    assert repo.get_hit_points(recipient).current == 14 and repo.get_hit_points(cid).current == 10
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='existing recipient'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True, target_character_id=-1)
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('sphere,power', [('Life','life:cure'), ('Destruction','destruction:blast')])
def test_maximize_integrated_dice_without_random_rolls(crafter, monkeypatch, sphere, power):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere=sphere, base_power=power, caster_level=5,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0, contributions=[],
        feat_integrations=[dict(name='Maximize Spell', metamagic=True, additional_spell_points=3)])
    iid = CraftingService(repo,cid).save_marvelous_design(plan,name='Maximum',slot='',description='')
    monkeypatch.setattr('random.randint', lambda a,b: pytest.fail('Maximized dice must not roll.'))
    effect = repo.consume_marvelous_item_use(cid,iid,apply_to_self=sphere=='Life')
    assert effect['dice_mode'] == 'Maximized'
    assert effect['healing_rolled' if sphere=='Life' else 'damage_rolled'] == (13 if sphere=='Life' else 12)
    assert marvelous_remaining_uses(metadata(repo,cid,iid)) == 0


@pytest.mark.parametrize('sphere,power,empowered,combined', [('Life','life:cure',16,21), ('Destruction','destruction:blast',18,30)])
@pytest.mark.parametrize('maximize', [False, True])
def test_empower_and_maximize_apply_separate_benefits(crafter, monkeypatch, sphere, power, empowered, combined, maximize):
    repo, cid = crafter
    feats = [dict(name='Empower Spell', metamagic=True, additional_spell_points=2)]
    if maximize: feats.append(dict(name='Maximize Spell', metamagic=True, additional_spell_points=3))
    plan = dict(schema_version=1,sphere=sphere,base_power=power,caster_level=8,activation='standard',uses=1,
                range_steps=0,duration_steps=0,unique_changes=0,contributions=[],feat_integrations=feats)
    iid = CraftingService(repo,cid).save_marvelous_design(plan,name='Empowered',slot='',description='')
    monkeypatch.setattr('random.randint', lambda a,b: 3)
    result = repo.consume_marvelous_item_use(cid,iid,apply_to_self=sphere=='Life')
    assert result['healing_rolled' if sphere=='Life' else 'damage_rolled'] == (combined if maximize else empowered)
    assert result['save_dc'] == 14


def test_aegis_creates_shared_ongoing_deflection_effect_atomically(crafter):
    from app.rules import ongoing_effect_modifiers
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Protection', base_power='protection:aegis', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Aegis charm', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    effects = repo.list_ongoing_effects(cid)
    assert len(effects) == 1 and effects[0].duration == '5 minutes'
    assert effects[0].name == 'Basic aegis — Aegis charm'
    assert ongoing_effect_modifiers(effects)['ac'][0].value == 2
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='No item uses'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo._connection.total_changes == before and len(repo.list_ongoing_effects(cid)) == 1


def test_personal_aegis_rejects_other_recipient_without_spending(crafter):
    repo, cid = crafter
    recipient = repo.create_character('Other', 'Spheres')
    plan = dict(schema_version=1, sphere='Protection', base_power='protection:aegis', caster_level=5,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Personal', slot='', description='')
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='personal-range'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True, target_character_id=recipient)
    assert repo._connection.total_changes == before


def test_supported_mixed_cure_and_aegis_apply_and_spend_atomically(crafter, monkeypatch):
    repo, cid = crafter
    base = dict(schema_version=1,caster_level=5,activation='standard',uses=2,range_steps=0,
                duration_steps=0,unique_changes=0,contributions=[])
    plan = {**base,'sphere':'Life','base_power':'life:cure','combination_mode':'mixed',
            'extra_effects':[{**base,'sphere':'Protection','base_power':'protection:aegis','uses':1}]}
    iid = CraftingService(repo,cid).save_marvelous_design(plan,name='Mixed',slot='',description='')
    other = repo.create_character('Other', 'Spheres')
    original = metadata(repo,cid,iid)
    with pytest.raises(ValueError, match='personal-range'):
        repo.consume_marvelous_item_use(cid,iid,apply_to_self=True,target_character_id=other)
    assert repo.get_hit_points(cid).current == 10 and metadata(repo,cid,iid) == original
    monkeypatch.setattr('random.randint', lambda a,b:4)
    apply = repo._apply_marvelous_effect
    def fail_second(*args):
        if args[4] == 1: raise ValueError('Simulated component failure')
        return apply(*args)
    with monkeypatch.context() as patch:
        patch.setattr(repo, '_apply_marvelous_effect', fail_second)
        with pytest.raises(ValueError, match='Simulated component'):
            repo.consume_marvelous_item_use(cid,iid,apply_to_self=True)
    assert repo.get_hit_points(cid).current == 10 and metadata(repo,cid,iid) == original
    assert repo.list_ongoing_effects(cid) == []
    result = repo.consume_marvelous_item_use(cid,iid,apply_to_self=True)
    assert repo.get_hit_points(cid).current == 19 and len(repo.list_ongoing_effects(cid)) == 1
    assert result['application'] == 'Applied to selected recipient'
    saved = metadata(repo,cid,iid)
    assert marvelous_remaining_uses(saved,0) == 1 and marvelous_remaining_uses(saved,1) == 0
    with pytest.raises(ValueError, match='no uses remaining'):
        repo.consume_marvelous_item_use(cid,iid,apply_to_self=True)
    assert repo.get_hit_points(cid).current == 19 and len(repo.list_ongoing_effects(cid)) == 1


def test_aegis_deflection_reaches_all_ac_profiles_and_does_not_stack(crafter):
    from app.services.character_calculations import CharacterCalculationService
    repo, cid = crafter
    def defenses():
        results = CharacterCalculationService(repo, cid).combat_results()
        return tuple(results[key].total for key in ('ac', 'touch_ac', 'flat_footed_ac'))
    before = defenses()
    plan = dict(schema_version=1, sphere='Protection', base_power='protection:aegis', caster_level=5,
                activation='standard', uses=2, range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Aegis', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert defenses() == tuple(value + 2 for value in before)
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert defenses() == tuple(value + 2 for value in before)
    other = repo.add_ongoing_effect(cid, 'Stronger deflection', target='ac', bonus_type='deflection', value=3)
    assert defenses() == tuple(value + 3 for value in before)
    repo.set_ongoing_effect_enabled(cid, other, False)
    assert defenses() == tuple(value + 2 for value in before)


def test_resistance_aegis_replaces_deflection_and_uses_ultimate_progression(crafter):
    from app.services.character_calculations import CharacterCalculationService
    repo, cid = crafter
    before = CharacterCalculationService(repo, cid).combat_results()
    plan = dict(schema_version=1, sphere='Protection', base_power='protection:aegis', caster_level=8,
                activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[dict(catalog_key='protection:aegis-ward-talent:resistance-aegis', complexity=1)])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Resistance', slot='', description='')
    effect = repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert effect['resistance_saves'] == 3 and 'deflection_ac' not in effect
    after = CharacterCalculationService(repo, cid).combat_results()
    assert after['ac'].total == before['ac'].total
    for save in ('fortitude', 'reflex', 'will'):
        assert after[save].total == before[save].total + 3


@pytest.mark.parametrize('choice,bonus', [('armor', 4), ('shield', 2)])
def test_armored_magic_aegis_uses_selected_ac_type(crafter, choice, bonus):
    from app.services.character_calculations import CharacterCalculationService
    repo, cid = crafter
    before = CharacterCalculationService(repo, cid).combat_results()
    plan = dict(schema_version=1, sphere='Protection', base_power='protection:aegis', caster_level=5,
        activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
        contributions=[dict(catalog_key='protection:aegis-ward-talent:armored-magic-aegis', complexity=1, effect_choice=choice)])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Armor device', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    after = CharacterCalculationService(repo, cid).combat_results()
    assert after['ac'].total == before['ac'].total + bonus
    assert after['flat_footed_ac'].total == before['flat_footed_ac'].total + bonus
    assert after['touch_ac'].total == before['touch_ac'].total


@pytest.mark.parametrize('boost,count', [(False, 2), (True, 5)])
def test_base_destructive_item_rolls_damage_and_spends_once(crafter, monkeypatch, boost, count):
    repo, cid = crafter
    plan = dict(schema_version=1, sphere='Destruction', base_power='destruction:blast',
                caster_level=5, activation='standard', uses=1, range_steps=0,
                duration_steps=0, unique_changes=0, contributions=[], full_blast_damage=boost)
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Blast', slot='', description='')
    monkeypatch.setattr('random.randint', lambda low, high: 4)
    effect = repo.consume_marvelous_item_use(cid, iid)
    assert effect['damage_rolls'] == [4] * count and effect['damage_rolled'] == 4 * count
    assert effect['save_dc'] == 12 and effect['magic_skill_bonus'] == 5
    assert repo.get_hit_points(cid).current == 10
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 0


def test_full_rest_daily_only_and_unlimited(crafter):
    repo, cid = crafter
    daily, limited, unlimited = [item(repo, cid, uses) for uses in (2, 50, 5)]
    for iid in (daily, limited, unlimited): repo.consume_marvelous_item_use(cid, iid)
    FullRestEngine(repo, cid).perform({'marvelous_items.daily_uses': True})
    assert marvelous_remaining_uses(metadata(repo, cid, daily)) == 2
    assert marvelous_remaining_uses(metadata(repo, cid, limited)) == 49
    assert marvelous_remaining_uses(metadata(repo, cid, unlimited)) is None


def test_ownership_and_unsupported_application_do_not_spend(crafter):
    repo, cid = crafter; iid = item(repo, cid)
    other = repo.create_character('Other', 'Spheres')
    with pytest.raises(ValueError, match='belong'):
        repo.consume_marvelous_item_use(other, iid)
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1


def test_temp_hp_does_not_stack_or_reduce_a_larger_pool(crafter):
    repo, cid = crafter; iid = item(repo, cid)
    repo.update_hit_points(replace(repo.get_hit_points(cid), temporary=9))
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo.get_hit_points(cid).temporary == 9


def test_invigorate_caps_to_missing_hp_and_rejects_uninjured_without_spending(crafter):
    repo, cid = crafter; iid = item(repo, cid, 2)
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=18))
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo.get_hit_points(cid).temporary == 2
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=20))
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='injured'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo._connection.total_changes == before
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1


def test_unsupported_modified_effect_fails_before_usage_write(crafter):
    repo, cid = crafter; iid = item(repo, cid)
    data = metadata(repo, cid, iid)
    data['marvelous_blueprint']['unique_changes'] = 1
    repo._connection.execute('UPDATE equipment SET automation_json=? WHERE id=?', (json.dumps(data), iid))
    repo._connection.commit()
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='not supported'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo._connection.total_changes == before
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1


def test_basic_cure_rolls_and_heals_nonlethal_atomically(crafter, monkeypatch):
    repo, cid = crafter; iid = item(repo, cid)
    data = metadata(repo, cid, iid); data['marvelous_blueprint']['base_power'] = 'life:cure'
    repo._connection.execute('UPDATE equipment SET automation_json=? WHERE id=?', (json.dumps(data), iid)); repo._connection.commit()
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=18, nonlethal=12))
    monkeypatch.setattr('random.randint', lambda low, high: 4)
    effect = repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert effect['healing'] == '1d8+5' and effect['healing_rolled'] == 9
    assert repo.get_hit_points(cid).current == 20
    assert repo.get_hit_points(cid).nonlethal == 3
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 0


def test_separate_meld_design_saves_independent_uses_and_recovers_without_applying_healing(crafter):
    from app.content import magic_entry
    from app.marvelous_item_rules import dark_meld_blueprint
    from uuid import uuid4
    repo, cid = crafter
    primary = dark_meld_blueprint(magic_entry('dark:meld-talent:clearsight-meld'), caster_level=10, uses=2, activation='standard')
    extra = dark_meld_blueprint(magic_entry('dark:meld-talent:feed-on-darkness-meld'), caster_level=10, uses=1, activation='standard')
    extra['effect_id'] = str(uuid4())
    primary.update(extra_effects=[extra], combination_mode='multiple')
    service = CraftingService(repo, cid)
    iid = service.save_marvelous_design(primary, name='Two melds', slot='', description='')
    saved = metadata(repo, cid, iid)['marvelous_blueprint']
    assert saved['extra_effects'][0]['effect_id'] == extra['effect_id']
    hp = repo.get_hit_points(cid)
    effect = repo.consume_marvelous_item_use(cid, iid, effect_index=1)
    assert effect['fast_healing'] == 2 and repo.get_hit_points(cid) == hp
    data = metadata(repo, cid, iid)
    assert marvelous_remaining_uses(data) == 2 and marvelous_remaining_uses(data, 1) == 0
    service.save_marvelous_design(saved, name='Renamed melds', slot='', description='', item_id=iid)
    data = metadata(repo, cid, iid)
    assert marvelous_remaining_uses(data) == 2 and marvelous_remaining_uses(data, 1) == 0
    writes = repo._connection.total_changes
    with pytest.raises(ValueError, match='Automatic self-application is not supported'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo._connection.total_changes == writes and repo.get_hit_points(cid) == hp
    FullRestEngine(repo, cid).perform({'marvelous_items.daily_uses': True})
    data = metadata(repo, cid, iid)
    assert marvelous_remaining_uses(data) == 2 and marvelous_remaining_uses(data, 1) == 1


def test_reordering_meld_powers_keeps_spent_uses_attached_to_their_identity(crafter):
    from app.content import magic_entry
    from app.marvelous_item_rules import dark_meld_blueprint
    from uuid import uuid4
    repo, cid = crafter
    powers = [dark_meld_blueprint(magic_entry('dark:meld-talent:' + suffix), caster_level=10, uses=2, activation='standard')
        for suffix in ('clearsight-meld', 'feed-on-darkness-meld', 'step-through-darkness-meld')]
    for power in powers[1:]: power['effect_id'] = str(uuid4())
    primary = powers[0]; primary.update(extra_effects=powers[1:], combination_mode='multiple')
    service = CraftingService(repo, cid)
    iid = service.save_marvelous_design(primary, name='Three melds', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid, effect_index=2)
    saved = metadata(repo, cid, iid)['marvelous_blueprint']
    saved['extra_effects'].reverse()
    service.save_marvelous_design(saved, name='Reordered melds', slot='', description='', item_id=iid)
    data = metadata(repo, cid, iid)
    assert data['marvelous_blueprint']['extra_effects'][0]['effect_name'] == 'Step Through Darkness (meld)'
    assert marvelous_remaining_uses(data, 1) == 1 and marvelous_remaining_uses(data, 2) == 2


def test_meld_use_dialog_cancel_is_noop_and_confirm_spends_only_selected_power(crafter, monkeypatch):
    from app.content import magic_entry
    from app.marvelous_item_rules import dark_meld_blueprint
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    from PySide6.QtWidgets import QApplication, QMessageBox
    from uuid import uuid4
    app = QApplication.instance() or QApplication([])
    repo, cid = crafter
    primary = dark_meld_blueprint(magic_entry('dark:meld-talent:clearsight-meld'), caster_level=10, uses=2, activation='standard')
    extra = dark_meld_blueprint(magic_entry('dark:meld-talent:feed-on-darkness-meld'), caster_level=10, uses=1, activation='standard')
    extra['effect_id'] = str(uuid4()); primary.update(extra_effects=[extra], combination_mode='multiple')
    iid = CraftingService(repo, cid).save_marvelous_design(primary, name='Two melds', slot='', description='')
    dialog = MarvelousItemUseDialog(repo, cid)
    assert dialog.table.item(1, 2).text() == 'Feed On Darkness (meld)'
    hp = repo.get_hit_points(cid); writes = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    dialog.table.cellWidget(1, 3).click()
    assert repo._connection.total_changes == writes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    dialog.table.cellWidget(1, 3).click()
    data = metadata(repo, cid, iid)
    assert marvelous_remaining_uses(data) == 2 and marvelous_remaining_uses(data, 1) == 0
    assert repo.get_hit_points(cid) == hp
    assert dialog.table.cellWidget(0, 3).isEnabled() and not dialog.table.cellWidget(1, 3).isEnabled()
    dialog.close()


def test_combined_design_saves_price_and_independent_recovery(crafter):
    repo, cid = crafter; iid = item(repo, cid, 2)
    data = metadata(repo, cid, iid); plan = data['marvelous_blueprint']
    extra = dict(plan, uses=50, base_power='life:cure')
    plan['extra_effects'] = [extra]; plan['combination_mode'] = 'multiple'
    service = CraftingService(repo, cid)
    service.save_marvelous_design(plan, name='Two powers', slot='', description='', item_id=iid)
    saved = repo.list_equipment(cid)[0]
    assert saved.value_gp == 11000
    repo.consume_marvelous_item_use(cid, iid)
    repo.consume_marvelous_item_use(cid, iid, effect_index=1)
    data = metadata(repo, cid, iid)
    assert marvelous_remaining_uses(data) == 1
    assert marvelous_remaining_uses(data, 1) == 49
    repo.reset_marvelous_daily_uses(cid)
    data = metadata(repo, cid, iid)
    assert marvelous_remaining_uses(data) == 2
    assert marvelous_remaining_uses(data, 1) == 49
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='Unknown item effect'):
        repo.consume_marvelous_item_use(cid, iid, effect_index=2)
    assert repo._connection.total_changes == before


def test_use_dialog_lists_and_activates_the_exact_extra_power(crafter, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    app = QApplication.instance() or QApplication([])
    repo, cid = crafter; iid = item(repo, cid, 2)
    plan = metadata(repo, cid, iid)['marvelous_blueprint']
    plan['extra_effects'] = [dict(plan, base_power='life:cure', uses=1)]
    CraftingService(repo, cid).save_marvelous_design(plan, name='Two powers', slot='', description='', item_id=iid)
    monkeypatch.setattr('random.randint', lambda low, high: 1)
    dialog = MarvelousItemUseDialog(repo, cid)
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(1, 2).text() == 'Cure'
    dialog.table.cellWidget(1, 3).click()
    assert repo.get_hit_points(cid).current == 16
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 2
    assert marvelous_remaining_uses(metadata(repo, cid, iid), 1) == 0
    assert dialog.table.cellWidget(0, 3).isEnabled()
    assert not dialog.table.cellWidget(1, 3).isEnabled()
    dialog.close()


def test_removing_first_extra_keeps_second_extra_spent_uses(crafter):
    repo, cid = crafter; iid = item(repo, cid, 2)
    plan = metadata(repo, cid, iid)['marvelous_blueprint']
    plan['extra_effects'] = [dict(plan, base_power='life:cure', uses=2), dict(plan, uses=50)]
    service = CraftingService(repo, cid)
    service.save_marvelous_design(plan, name='Three powers', slot='', description='', item_id=iid)
    repo.consume_marvelous_item_use(cid, iid, effect_index=2)
    saved = metadata(repo, cid, iid)['marvelous_blueprint']
    saved['extra_effects'].pop(0)
    service.save_marvelous_design(saved, name='Two powers', slot='', description='', item_id=iid)
    assert marvelous_remaining_uses(metadata(repo, cid, iid), 1) == 49
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 2


def test_modified_cure_rolls_every_die_and_applies_talent_bonus(crafter, monkeypatch):
    repo, cid = crafter; iid = item(repo, cid)
    plan = metadata(repo, cid, iid)['marvelous_blueprint']
    plan['base_power'] = 'life:cure'
    plan['contributions'] = [dict(catalog_key=key, complexity=1) for key in
        ('life:talent:deeper-healing', 'life:cure-talent:restore-health-cure')]
    CraftingService(repo, cid).save_marvelous_design(plan, name='Healing device', slot='', description='', item_id=iid)
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=0))
    rolls = iter((1, 2, 3))
    monkeypatch.setattr('random.randint', lambda low, high: next(rolls))
    effect = repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert effect['healing_rolled'] == 16
    assert repo.get_hit_points(cid).current == 16
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 0


def test_mixed_activation_is_all_or_nothing(crafter):
    repo, cid = crafter; iid = item(repo, cid, 2)
    plan = metadata(repo, cid, iid)['marvelous_blueprint']
    plan['extra_effects'] = [dict(plan, uses=1, base_power='life:cure')]
    plan['combination_mode'] = 'mixed'
    CraftingService(repo, cid).save_marvelous_design(plan, name='Mixed power', slot='', description='', item_id=iid)
    result = repo.consume_marvelous_item_use(cid, iid)
    assert len(result['combined_effects']) == 2
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1
    assert marvelous_remaining_uses(metadata(repo, cid, iid), 1) == 0
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='component'):
        repo.consume_marvelous_item_use(cid, iid)
    assert repo._connection.total_changes == before
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 1
    with pytest.raises(ValueError, match='complete mixed'):
        repo.consume_marvelous_item_use(cid, iid, effect_index=1)


def test_activation_dialog_updates_available_state(crafter):
    from PySide6.QtWidgets import QApplication
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    app = QApplication.instance() or QApplication([])
    repo, cid = crafter; iid = item(repo, cid)
    dialog = MarvelousItemUseDialog(repo, cid)
    assert dialog.table.cellWidget(0, 3).isEnabled()
    dialog.activate(iid, True)
    assert dialog.changed
    assert not dialog.table.cellWidget(0, 3).isEnabled()
    assert repo.get_hit_points(cid).temporary == 5
    dialog.close()

from dataclasses import replace
import pytest
from app.database import CharacterRepository
from app.services.crafting import CraftingService
from app.catalogs import DEFAULT_CATALOG


@pytest.fixture
def crafter(tmp_path):
    repo = CharacterRepository(tmp_path / 'crafter.db')
    cid = repo.create_character('Crafter', 'Spheres')
    repo.add_class_level(cid, 'Prodigy', 8, '3/4', 'Poor', 'Good', 'Good', preset_key='prodigy')
    repo.add_feat(cid, 'Craft Marvelous Item')
    repo.add_spell(cid, 'Life Sphere', system='Sphere', school_or_sphere='Life',
                   catalog_key='life:base', catalog_category='Base Sphere')
    yield repo, cid
    repo.close()


def test_demiplane_checks_foreign_prerequisite_without_adding_a_foreign_effect(crafter):
    repo, cid = crafter
    service = CraftingService(repo, cid)
    keys = ['warp:advanced-talent:create-demiplane-utility', 'warp:space-talent:extradimensional-room-space']
    plan = dict(sphere='Warp', base_power='warp:teleport', caster_level=15,
                range_steps=0, duration_steps=0, contributions=[dict(catalog_key=key) for key in keys])
    access = dict(sphere_levels={'Warp': 15}, available_talents=[service.magic_entries_by_key[key]['name'] for key in keys])
    missing = service.marvelous_plan_requirements(plan, access=access)
    assert not missing.eligible and any('Creation base sphere' in text for text in missing.blockers)
    access['sphere_levels']['Creation'] = 1
    assert not service.marvelous_plan_requirements(plan, access=access).eligible
    access['available_talents'].append(service.magic_entries_by_key['creation:material-talent:expanded-materials-material']['name'])
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    assert [row['catalog_key'] for row in plan['contributions']] == keys
    plan['caster_level'] = 14
    assert not service.marvelous_plan_requirements(plan, access=access).eligible


def test_time_warp_requires_time_sphere_without_inventing_a_time_cl_gate(crafter):
    from app.marvelous_item_rules import missing_construction_prerequisites
    repo, cid = crafter
    service = CraftingService(repo, cid)
    rows = [dict(catalog_key='warp:advanced-talent:time-warp-jester-s-hb')]
    rows.extend(dict(catalog_key=key) for key in missing_construction_prerequisites(rows))
    plan = dict(sphere='Warp', base_power='warp:teleport', caster_level=20,
                range_steps=0, duration_steps=0, contributions=rows)
    access = dict(sphere_levels={'Warp': 20}, available_talents=[service.magic_entries_by_key[row['catalog_key']]['name'] for row in rows])
    assert any('Time base sphere' in text for text in service.marvelous_plan_requirements(plan, access=access).blockers)
    access['sphere_levels']['Time'] = 1
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    from app.marvelous_base_powers import resolve_base_power
    assert 'five-SP activation' in resolve_base_power(plan)['pricing_review']


def test_required_effect_mode_blocks_construction_until_selected(crafter):
    repo, cid = crafter
    service = CraftingService(repo, cid)
    key = 'weather:talent:greater-weather'
    name = service.magic_entries_by_key[key]['name']
    contribution = dict(catalog_key=key, complexity=2, additional_spell_points=1)
    plan = dict(sphere='Weather', base_power='weather:control', caster_level=5,
                range_steps=0, duration_steps=0, contributions=[contribution])
    access = dict(sphere_levels={'Weather': 5}, available_talents=[name])
    result = service.marvelous_plan_requirements(plan, access=access)
    assert not result.eligible and any('choose the effect mode' in text for text in result.blockers)
    draft = dict(plan, schema_version=1, uses=1, activation='standard', unique_changes=0)
    assert service.save_marvelous_design(draft, name='Unfinished weather device', slot='', description='')
    contribution['effect_choice'] = 'two weather categories'
    assert service.marvelous_plan_requirements(plan, access=access).eligible


def test_complex_training_uses_current_effective_ranks(crafter, monkeypatch):
    repo, cid = crafter
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
                duration_steps=0, contributions=[], drawbacks=[dict(source='published',
                    catalog_key='crafting:complex', required_skill='Acrobatics')])
    service = CraftingService(repo, cid)
    assert any('trained in Acrobatics' in text for text in service.marvelous_plan_requirements(plan).blockers)
    state = repo.list_skill_states(cid)['acrobatics']
    repo.update_skill_state(cid, replace(state, ranks=1))
    assert service.marvelous_plan_requirements(plan).eligible
    repo.update_skill_state(cid, replace(state, ranks=0))
    monkeypatch.setattr('app.services.character_calculations.CharacterCalculationService.effective_skill_ranks',
                        lambda self: {'acrobatics': 5})
    assert service.marvelous_plan_requirements(plan).eligible
    plan['crafting_tradition'] = {'key': 'crafting:ridiculously-complicated'}
    result = service.marvelous_plan_requirements(plan)
    assert not result.eligible and any('trained in Disable Device' in text for text in result.blockers)
    plan['crafting_tradition'] = {'key': 'crafting:fey-touched'}
    assert any('trained in Knowledge (nature)' in text for text in service.marvelous_plan_requirements(plan).blockers)


def test_shared_warp_structure_rules_are_not_offered_as_an_item_talent(crafter):
    repo, cid = crafter
    key = 'warp:advanced-talent:warping-structures-store-and-teleport-structure'
    repo.add_spell(cid, 'Warping Structures', system='Sphere', school_or_sphere='Warp',
                   catalog_key=key, catalog_category='Advanced Talent')
    assert key not in {entry['key'] for entry in CraftingService(repo, cid).accessible_marvelous_effects('Warp')}
    assert any(row.catalog_key == key for row in repo.list_spells(cid))


def test_effect_picker_access_includes_effective_not_disabled_or_unowned(crafter, monkeypatch):
    from app.models import Spell
    repo, cid = crafter
    deeper = 'life:talent:deeper-healing'
    painkiller = 'life:talent:painkiller'
    repo.add_spell(cid, 'Renamed deeper healing', system='Sphere', school_or_sphere='Life',
                   catalog_key=deeper, catalog_category='Talent')
    stored = repo.list_spells(cid)
    flexible = Spell(-1, 'Flexible Painkiller', system='Sphere', school_or_sphere='Life',
                     catalog_key=painkiller, catalog_category='Talent')
    disabled = replace(flexible, catalog_key='life:talent:greater-invigorate', enabled=False)
    monkeypatch.setattr('app.exploitant_rules.effective_magic_talents', lambda r, c: [*stored, flexible, flexible, disabled])
    service = CraftingService(repo, cid)
    assert {entry['key'] for entry in service.accessible_marvelous_effects('Life')} == {deeper, painkiller}
    assert service.accessible_marvelous_effects('Warp') == ()
    assert 'Painkiller' not in service.permanent_marvelous_access()['available_talents']


def test_class_progression_excludes_saved_live_level_boost(crafter):
    repo, cid = crafter
    repo.update_casting_profile(replace(repo.get_casting_profile(cid), caster_level=30))
    access = CraftingService(repo, cid).permanent_marvelous_access()
    assert access['sphere_levels'] == {'Life': 6}


def test_talent_does_not_silently_supply_a_missing_base_sphere(crafter):
    repo, cid = crafter
    repo.add_spell(cid, 'Haste', system='Sphere', school_or_sphere='Time', catalog_category='Talent')
    access = CraftingService(repo, cid).permanent_marvelous_access()
    assert 'Time' not in access['sphere_levels']
    assert 'Haste' in access['available_talents']


def test_owned_catalog_identity_survives_display_name_override(crafter):
    repo, cid = crafter
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if e['category'] == 'Talent')
    repo.add_spell(cid, 'My renamed talent', system='Sphere', school_or_sphere='Life',
                   catalog_key=entry['key'], catalog_category=entry['category'])
    service = CraftingService(repo, cid)
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
                duration_steps=0, contributions=[dict(catalog_key=entry['key'], complexity=1)])
    result = service.marvelous_plan_requirements(plan)
    assert result.eligible and not result.bypassed


def test_foreign_catalog_contribution_is_rejected(crafter):
    repo, cid = crafter
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Destruction') if e['category'] == 'Talent')
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
                duration_steps=0, contributions=[dict(catalog_key=entry['key'], complexity=1)])
    with pytest.raises(ValueError, match='base sphere'):
        CraftingService(repo, cid).marvelous_plan_requirements(plan)


def test_combined_requirements_check_all_spheres_and_deduplicate_shared_talents(crafter):
    repo, cid = crafter
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if e['category'] == 'Talent')
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
                duration_steps=0, contributions=[dict(catalog_key=entry['key'], complexity=1)])
    extra = dict(plan)
    plan['extra_effects'] = [extra]
    service = CraftingService(repo, cid)
    result = service.marvelous_plan_requirements(plan)
    assert result.eligible and result.dc_increase == 5
    plan['extra_effects'] = [dict(sphere='Time', base_power='time:haste', caster_level=5,
        range_steps=0, duration_steps=0, contributions=[])]
    result = service.marvelous_plan_requirements(plan)
    assert not result.eligible and any('Time' in blocker for blocker in result.blockers)


def test_hypervitalize_requires_item_level_and_prerequisite_effects(crafter):
    repo, cid = crafter
    keys = ['life:advanced-talent:hypervitalize', 'life:cure-talent:restore-health-cure', 'life:talent:revitalize']
    service = CraftingService(repo, cid)
    access = dict(sphere_levels={'Life': 20}, available_talents=[service.magic_entries_by_key[key]['name'] for key in keys])
    plan = dict(sphere='Life', base_power='life:cure', caster_level=10, range_steps=0, duration_steps=0,
                contributions=[dict(catalog_key=keys[0], complexity=2)])
    result = service.marvelous_plan_requirements(plan, access=access)
    assert not result.eligible and len(result.blockers) == 3
    plan['caster_level'] = 15
    plan['contributions'].extend(dict(catalog_key=key, complexity=1) for key in keys[1:])
    assert service.marvelous_plan_requirements(plan, access=access).eligible


def test_integrated_feat_cannot_be_bypassed_as_a_missing_talent(crafter):
    repo, cid = crafter
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
                duration_steps=0, contributions=[], feat_integrations=[dict(name='Maximize Spell', metamagic=True, additional_spell_points=3)])
    result = CraftingService(repo, cid).marvelous_plan_requirements(plan)
    assert not result.eligible and any('Maximize Spell' in blocker for blocker in result.blockers)
    repo.add_feat(cid, 'Maximize Spell')
    assert CraftingService(repo, cid).marvelous_plan_requirements(plan).eligible


@pytest.mark.parametrize('key', ['life:advanced-talent:make-whole', 'life:advanced-talent:resurrection',
    'life:advanced-talent:resurrection-greater', 'life:advanced-talent:resurrection-supreme-warden',
    'life:advanced-talent:feline-good-catgirl-hb', 'life:advanced-talent:transfiguration',
    'life:advanced-talent:reincarnation-utility-3pp', 'life:advanced-talent:reincarnation-instant-3pp',
    'life:advanced-talent:reincarnation-manipulated-utility-3pp'])
def test_reviewed_life_chains_require_each_component_and_item_level(crafter, key):
    from app.marvelous_item_rules import ADVANCED_CONSTRUCTION_REQUIREMENTS
    repo, cid = crafter
    service = CraftingService(repo, cid)
    minimum, required = ADVANCED_CONSTRUCTION_REQUIREMENTS[key]
    keys = [key, *required]
    access = dict(sphere_levels={'Life': 20}, available_talents=[service.magic_entries_by_key[k]['name'] for k in keys])
    plan = dict(sphere='Life', base_power='life:restore', caster_level=minimum, range_steps=0,
                duration_steps=0, contributions=[dict(catalog_key=k, complexity=2) for k in keys])
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    plan['caster_level'] = minimum - 1
    assert not service.marvelous_plan_requirements(plan, access=access).eligible
    plan['caster_level'] = minimum
    plan['contributions'].pop()
    assert not service.marvelous_plan_requirements(plan, access=access).eligible

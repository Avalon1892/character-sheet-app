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

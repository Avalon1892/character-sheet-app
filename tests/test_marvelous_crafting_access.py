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


@pytest.mark.parametrize('mode,sphere', [('material sense', 'Creation'), ('see in darkness', 'Dark'),
    ('spirit sense', 'Death'), ('lifesense', 'Life'), ('thoughtsense', 'Mind'),
    ('unrestricted thoughtsense', 'Mind'), ('touchsight', 'Telekinesis'), ('storm vision', 'Weather')])
def test_advanced_divination_sense_checks_only_its_selected_foreign_sphere(crafter, mode, sphere):
    repo, cid = crafter
    service = CraftingService(repo, cid)
    key = 'divination:advanced-talent:alternate-divinations-advanced-sense-origin'
    row = dict(catalog_key=key, effect_choice=mode)
    plan = dict(sphere='Divination', base_power='divination:sense', caster_level=5,
                range_steps=0, duration_steps=0, contributions=[row])
    access = dict(sphere_levels={'Divination': 5}, available_talents=[service.magic_entries_by_key[key]['name']])
    before = repo._connection.total_changes
    missing = service.marvelous_plan_requirements(plan, access=access)
    assert any(f'{sphere} base sphere' in text for text in missing.blockers)
    access['sphere_levels'][sphere] = 1
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('mode,sphere,package', [('darkvision', None, None),
    ('see in darkness', 'Dark', None), ('lifesense', 'Life', None),
    ('thoughtsense', 'Mind', None), ('touchsight', 'Telekinesis', None),
    ('stone vision', 'Nature', 'Earth'), ('tremorsense', 'Nature', 'Earth'),
    ('smoke vision', 'Nature', 'Fire'), ('scent metal', 'Nature', 'Metal'),
    ('plant vision', 'Nature', 'Plant'), ('water vision', 'Nature', 'Water')])
def test_superior_senses_construction_checks_selected_sphere_and_package(crafter, mode, sphere, package):
    repo, cid = crafter
    service = CraftingService(repo, cid)
    key = 'conjuration:form-talent:superior-senses-form'
    plan = dict(sphere='Conjuration', base_power='conjuration:companion', caster_level=5,
                range_steps=0, duration_steps=0, contributions=[dict(catalog_key=key, effect_choice=mode)])
    access = dict(sphere_levels={'Conjuration': 5}, available_talents=[service.magic_entries_by_key[key]['name']])
    writes = repo._connection.total_changes
    if sphere:
        assert any(f'{sphere} base sphere' in text for text in service.marvelous_plan_requirements(plan, access=access).blockers)
        access['sphere_levels'][sphere] = 1
    if package:
        result = service.marvelous_plan_requirements(plan, access=access)
        assert any(f'Nature ({package} package)' in text for text in result.blockers)
        access['available_requirements'] = [f'Nature ({package} package)']
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('mode', ['scrying', 'teleport'])
def test_speak_and_i_listen_checks_foreign_access_only_for_teleport(crafter, mode):
    from app.marvelous_item_rules import missing_construction_prerequisites
    repo, cid = crafter
    service = CraftingService(repo, cid)
    rows = [dict(catalog_key='divination:advanced-talent:speak-and-i-listen-dbh', effect_choice=mode)]
    rows.extend(dict(catalog_key=key) for key in missing_construction_prerequisites(rows))
    plan = dict(sphere='Divination', base_power='divination:divine', caster_level=10,
                range_steps=0, duration_steps=0, contributions=rows)
    access = dict(sphere_levels={'Divination': 10},
        available_talents=[service.magic_entries_by_key[row['catalog_key']]['name'] for row in rows])
    before = repo._connection.total_changes
    result = service.marvelous_plan_requirements(plan, access=access)
    if mode == 'teleport':
        assert not result.eligible and any('Warp base sphere' in text for text in result.blockers)
        access['sphere_levels']['Warp'] = 1
        assert service.marvelous_plan_requirements(plan, access=access).eligible
    else:
        assert result.eligible
    assert repo._connection.total_changes == before


def test_imported_subsections_are_not_offered_as_accessible_item_talents(crafter):
    from app.content import magic_entry
    from app.marvelous_item_rules import MARVELOUS_SUBSECTION_KEYS
    repo, cid = crafter
    for key in MARVELOUS_SUBSECTION_KEYS:
        entry = magic_entry(key)
        repo.add_spell(cid, entry['name'], system='Sphere', school_or_sphere=entry['sphere'],
                       catalog_key=key, catalog_category=entry['category'])
    before = repo._connection.total_changes
    entries = CraftingService(repo, cid).accessible_marvelous_effects()
    assert not MARVELOUS_SUBSECTION_KEYS.intersection(entry['key'] for entry in entries)
    assert repo._connection.total_changes == before


def test_demiplane_requires_integrated_foreign_talent_not_just_owned_access(crafter):
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
    assert not service.marvelous_plan_requirements(plan, access=access).eligible
    keys.append('creation:material-talent:expanded-materials-material')
    plan['contributions'].append(dict(catalog_key=keys[-1]))
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    assert [row['catalog_key'] for row in plan['contributions']] == keys
    plan['caster_level'] = 14
    assert not service.marvelous_plan_requirements(plan, access=access).eligible
    plan['contributions'].pop(0)
    with pytest.raises(ValueError, match='blueprint base sphere'):
        service.marvelous_plan_requirements(plan, access=access)


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
    assert '5 SP total' in resolve_base_power(plan)['spell_point_accounting']


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


def test_soul_consumption_requires_integrated_death_talent_and_base_access(crafter):
    repo, cid = crafter
    service = CraftingService(repo, cid)
    keys = ['life:advanced-talent:soul-consumption-dbh', 'life:talent:revitalize']
    plan = dict(sphere='Life', base_power='life:cure', caster_level=8,
                range_steps=0, duration_steps=0, contributions=[dict(catalog_key=key) for key in keys])
    gem = 'death:advanced-talent:create-soul-gem-dbh'
    access = dict(sphere_levels={'Life': 8, 'Death': 8},
        available_talents=[service.magic_entries_by_key[key]['name'] for key in [*keys, gem]])
    assert not service.marvelous_plan_requirements(plan, access=access).eligible
    plan['contributions'].append(dict(catalog_key=gem))
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    access['sphere_levels'].pop('Death')
    assert not service.marvelous_plan_requirements(plan, access=access).eligible


@pytest.mark.parametrize('suffix', ['radiation-lord-cata-hb', 'biohazard-cata-hb',
    'contaminated-blows-mantle-radiation-cata-hb', 'contamination-lord-cata-hb',
    'interference-cloud-shroud-radiation-cata-hb', 'melt-skin-shroud-radiation-cata-hb',
    'radiotherapy-mantle-radiation-cata-hb'])
def test_radiation_weather_construction_requires_destruction_base(crafter, suffix):
    from app.marvelous_item_rules import missing_construction_prerequisites
    repo, cid = crafter
    service = CraftingService(repo, cid)
    owner = 'weather:advanced-talent:' + suffix
    keys = [owner, *missing_construction_prerequisites([dict(catalog_key=owner)])]
    plan = dict(sphere='Weather', base_power='weather:control', caster_level=10,
                range_steps=0, duration_steps=0, contributions=[dict(catalog_key=key) for key in keys])
    access = dict(sphere_levels={'Weather': 10},
        available_talents=[service.magic_entries_by_key[key]['name'] for key in keys])
    result = service.marvelous_plan_requirements(plan, access=access)
    assert not result.eligible and any('Destruction base sphere' in line for line in result.blockers)
    access['sphere_levels']['Destruction'] = 1
    assert service.marvelous_plan_requirements(plan, access=access).eligible


def test_permanent_nature_package_access_uses_saved_choices_not_flexible_selections(crafter):
    repo, cid = crafter
    repo.add_spell(cid, 'Nature', system='Sphere', school_or_sphere='Nature',
        catalog_key='nature:base', catalog_category='Base Sphere', choice='Fire')
    repo.add_spell(cid, 'Expanded Geomancing', system='Sphere', school_or_sphere='Nature',
        catalog_key='nature:talent:expanded-geomancing', catalog_category='Talent', choice='Earth')
    assert set(CraftingService(repo, cid).permanent_marvelous_access()['available_requirements']) == {
        'Nature (Fire package)', 'Nature (Earth package)'}


@pytest.mark.parametrize('suffix,packages', [('fire-tornadoes', ('Nature (Fire package)',)),
    ('volcano-lord', ('Nature (Earth package)', 'Nature (Fire package)'))])
def test_weather_nature_package_requirements_cannot_be_waived(crafter, suffix, packages):
    from app.marvelous_item_rules import missing_construction_prerequisites
    repo, cid = crafter
    repo.add_feat(cid, 'Versatile Crafter')
    service = CraftingService(repo, cid)
    key = 'weather:advanced-talent:' + suffix
    keys = [key, *missing_construction_prerequisites([dict(catalog_key=key)])]
    plan = dict(sphere='Weather', base_power='weather:control', caster_level=15,
        range_steps=0, duration_steps=0, contributions=[dict(catalog_key=k) for k in keys])
    access = dict(sphere_levels={'Weather': 15, 'Nature': 15},
        available_talents=[service.magic_entries_by_key[k]['name'] for k in keys])
    result = service.marvelous_plan_requirements(plan, access=access)
    assert not result.eligible and any('package' in line for line in result.blockers)
    access['available_requirements'] = packages
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    assert 'protected_requirements' not in access


@pytest.mark.parametrize('owner,sphere,foreign', [
    ('enhancement:advanced-talent:antimagic-aegis', 'Protection', 'protection:aegis-ward-talent:spell-ward-aegis-ward'),
    ('enhancement:advanced-talent:heart-of-hope-and-fear-sm', 'Fate', 'fate:advanced-talent:hold-on-hope-word-sm'),
])
def test_enhancement_cross_sphere_prerequisites_need_integrated_talent_and_access(crafter, owner, sphere, foreign):
    from app.marvelous_item_rules import missing_construction_prerequisites
    repo, cid = crafter
    service = CraftingService(repo, cid)
    keys = [owner, *missing_construction_prerequisites([dict(catalog_key=owner)])]
    plan = dict(sphere='Enhancement', base_power='enhancement:enhance', caster_level=20,
        range_steps=0, duration_steps=0, contributions=[dict(catalog_key=k) for k in keys])
    access = dict(sphere_levels={'Enhancement': 20},
        available_talents=[service.magic_entries_by_key[k]['name'] for k in keys])
    assert not service.marvelous_plan_requirements(plan, access=access).eligible
    access['sphere_levels'][sphere] = 1
    assert service.marvelous_plan_requirements(plan, access=access).eligible
    plan['contributions'] = [r for r in plan['contributions'] if r['catalog_key'] != foreign]
    assert not service.marvelous_plan_requirements(plan, access=access).eligible


@pytest.mark.parametrize('suffix,choice', [
    ('physical-enhancement-enhance', 'Strength'), ('mental-enhancement-enhance', 'Charisma'),
    ('energize-body-enhance', 'suppress exhaustion'), ('ragged-edges-enhance', 'caster level bleed'),
    ('alter-movement-enhance', 'increase one movement speed'),
    ('enhance-focus-enhance', 'Perception'), ('staunch-resistance-enhance', 'Reflex'),
    ('supply-vigor-enhance', 'Dexterity'), ('harden-weaken-enhance', 'grant DR/adamantine'),
    ('energy-enhancement-enhance', 'weapon: fire'), ('deadly-weapon-enhance', 'bypass DR: silver'),
    ('ravenous-weapon-enhance-sm', 'damage wielder on a miss'),
    ('traveling-weapon-enhance', 'ranged or throwing weapon: ignore cover'),
    ('spectral-enhancement-enhance-gravecaller-s-hb', 'empowered ghost touch armor'),
])
def test_enhancement_requires_explicit_mode_before_construction(crafter, suffix, choice):
    repo, cid = crafter
    service = CraftingService(repo, cid)
    key = 'enhancement:enhance-talent:' + suffix
    row = dict(catalog_key=key)
    plan = dict(sphere='Enhancement', base_power='enhancement:enhance', caster_level=8,
        range_steps=0, duration_steps=0, contributions=[row])
    access = dict(sphere_levels={'Enhancement': 8}, available_talents=[service.magic_entries_by_key[key]['name']])
    result = service.marvelous_plan_requirements(plan, access=access)
    assert not result.eligible and any('choose the effect mode' in line for line in result.blockers)
    row['effect_choice'] = choice
    assert service.marvelous_plan_requirements(plan, access=access).eligible


@pytest.mark.parametrize('suffix,minimum', [('daylight-light',10), ('diffuse-body',7), ('everglow',1),
    ('incarnate-glow',15), ('light-speed',15), ('prismatic-radiance-light',15),
    ('radiation-light',10), ('star-genesis',10)])
def test_light_advanced_dependencies_are_enforced_by_shared_construction_service(crafter, suffix, minimum):
    from app.marvelous_item_rules import missing_construction_prerequisites
    repo, cid = crafter
    service = CraftingService(repo, cid)
    key = 'light:advanced-talent:' + suffix
    rows = [dict(catalog_key=key)]
    rows.extend(dict(catalog_key=child) for child in missing_construction_prerequisites(rows))
    if suffix == 'radiation-light': rows[-1]['effect_choice'] = 'nauseating bright light'
    if suffix == 'star-genesis': rows[0]['effect_choice'] = 'expanded radius'
    access = dict(sphere_levels={'Light': 20}, available_talents=[service.magic_entries_by_key[row['catalog_key']]['name'] for row in rows])
    item = dict(sphere='Light', base_power='light:glow', caster_level=minimum,
        range_steps=0, duration_steps=0, contributions=rows)
    assert service.marvelous_plan_requirements(item, access=access).eligible
    if minimum > 1:
        item['caster_level'] = minimum - 1
        assert not service.marvelous_plan_requirements(item, access=access).eligible
        item['caster_level'] = minimum
    if len(rows) > 1:
        rows.pop()
        assert not service.marvelous_plan_requirements(item, access=access).eligible


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


@pytest.mark.parametrize('sphere, key', [
    ('Warp', 'warp:advanced-talent:warping-structures-store-and-teleport-structure'),
    ('Time', 'time:advanced-talent:reversion-and-complete-reversion'),
])
def test_shared_rules_commentary_is_not_offered_as_an_item_talent(crafter, sphere, key):
    repo, cid = crafter
    repo.add_spell(cid, 'Rules commentary', system='Sphere', school_or_sphere=sphere,
                   catalog_key=key, catalog_category='Advanced Talent')
    assert key not in {entry['key'] for entry in CraftingService(repo, cid).accessible_marvelous_effects(sphere)}
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
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if e['key'] == 'life:talent:deeper-healing')
    repo.add_spell(cid, 'My renamed talent', system='Sphere', school_or_sphere='Life',
                   catalog_key=entry['key'], catalog_category=entry['category'])
    service = CraftingService(repo, cid)
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
                duration_steps=0, contributions=[dict(catalog_key=entry['key'], complexity=1)])
    result = service.marvelous_plan_requirements(plan)
    assert result.eligible and not result.bypassed


def test_adrenaline_construction_requires_explicit_mode_even_when_owned(crafter):
    repo, cid = crafter
    key = 'life:talent:adrenaline-surge'
    repo.add_spell(cid, 'Adrenaline Surge', system='Sphere', school_or_sphere='Life',
        catalog_key=key, catalog_category='Talent')
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
        duration_steps=0, contributions=[dict(catalog_key=key, complexity=2, additional_spell_points=1)])
    service = CraftingService(repo, cid)
    assert any('choose the effect mode' in message for message in service.marvelous_plan_requirements(plan).blockers)
    plan['contributions'][0]['effect_choice'] = 'surge one ally'
    assert service.marvelous_plan_requirements(plan).eligible


def test_foreign_catalog_contribution_is_rejected(crafter):
    repo, cid = crafter
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Destruction') if e['category'] == 'Talent')
    plan = dict(sphere='Life', base_power='life:cure', caster_level=5, range_steps=0,
                duration_steps=0, contributions=[dict(catalog_key=entry['key'], complexity=1)])
    with pytest.raises(ValueError, match='base sphere'):
        CraftingService(repo, cid).marvelous_plan_requirements(plan)


def test_combined_requirements_check_all_spheres_and_deduplicate_shared_talents(crafter):
    repo, cid = crafter
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if e['key'] == 'life:talent:deeper-healing')
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

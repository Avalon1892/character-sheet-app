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


def test_atomic_activation_and_zero_floor(crafter):
    repo, cid = crafter; iid = item(repo, cid)
    repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo.get_hit_points(cid).temporary == 5
    assert marvelous_remaining_uses(metadata(repo, cid, iid)) == 0
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='No item uses'):
        repo.consume_marvelous_item_use(cid, iid, apply_to_self=True)
    assert repo._connection.total_changes == before


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

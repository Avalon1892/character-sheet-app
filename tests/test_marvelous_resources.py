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

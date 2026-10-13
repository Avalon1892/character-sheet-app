import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import pytest
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.marvelous_crafting import MarvelousCraftingDialog


@pytest.fixture
def composer(tmp_path):
    app = QApplication.instance() or QApplication([])
    repo = CharacterRepository(tmp_path / 'character.db')
    cid = repo.create_character('Crafter', 'Spheres')
    repo.add_feat(cid, 'Craft Marvelous Item')
    dialog = MarvelousCraftingDialog(repo, cid)
    yield dialog, repo, cid
    dialog.close()
    repo.close()


def test_live_price_and_cancel_no_writes(composer):
    dialog, repo, cid = composer
    before = repo._connection.total_changes
    dialog.cl.setValue(5)
    dialog.range_steps.setValue(1)
    assert dialog.quotation()[1].market_price_gp == 4000
    dialog.uses.setCurrentIndex(4)
    assert dialog.quotation()[1].market_price_gp == 20000
    dialog.reject()
    assert repo._connection.total_changes == before
    assert not repo.list_equipment(cid)


def test_extra_spell_points_change_price_and_restore_without_double_counting(composer):
    dialog, repo, cid = composer
    dialog.cl.setValue(10)
    dialog.add_contribution()
    before = dialog.quotation()[1].market_price_gp
    dialog.table.cellWidget(0, 4).setValue(2)
    assert dialog.quotation()[1].market_price_gp == before + 8000
    plan = dialog.blueprint()
    assert plan['contributions'][0]['additional_spell_points'] == 2
    dialog.load_plan(plan)
    assert dialog.blueprint()['contributions'] == plan['contributions']


def test_overrides_and_blueprint_persist_without_activating_effects(composer):
    dialog, repo, cid = composer
    dialog.name.setText('My crafted device')
    dialog.description.setPlainText('A custom description')
    dialog.slot.setCurrentIndex(1)
    dialog.review.setChecked(True)
    assert dialog.save.isEnabled()
    dialog.save_item()
    item = repo.list_equipment(cid)[0]
    assert item.name == 'My crafted device'
    assert item.notes == 'A custom description'
    assert item.slot == dialog.slot.currentData()
    assert not item.equipped
    plan = json.loads(item.automation_json)['marvelous_blueprint']
    assert plan['caster_level'] == 1
    assert plan['automation_status'] == 'rules_only'


def test_illegal_complexity_blocks_save(composer):
    dialog, repo, cid = composer
    dialog.review.setChecked(True)
    dialog.activation.setCurrentIndex(3)
    assert not dialog.save.isEnabled()
    assert 'caster level' in dialog.result.text()


def test_changing_sphere_does_not_retain_foreign_contributions(composer):
    dialog, repo, cid = composer
    dialog.add_contribution()
    assert dialog.table.rowCount() == 1
    dialog.sphere.setCurrentIndex(1)
    assert dialog.table.rowCount() == 0


def test_edit_design_preserves_identity_and_spent_uses(composer):
    dialog, repo, cid = composer
    dialog.review.setChecked(True); dialog.save_item()
    iid = dialog.item_id
    repo.consume_marvelous_item_use(cid, iid)
    edit = MarvelousCraftingDialog(repo, cid, item_id=iid)
    edit.name.setText('Renamed device'); edit.cl.setValue(3)
    edit.review.setChecked(True); edit.save_item()
    items = repo.list_equipment(cid)
    assert len(items) == 1 and items[0].id == iid
    assert items[0].name == 'Renamed device'
    metadata = json.loads(items[0].automation_json)
    assert metadata['marvelous_blueprint']['caster_level'] == 3
    from app.marvelous_item_rules import marvelous_remaining_uses
    assert marvelous_remaining_uses(metadata) == 0
    edit.close()


def test_cancel_edit_does_not_write(composer):
    dialog, repo, cid = composer
    dialog.review.setChecked(True); dialog.save_item()
    before = repo._connection.total_changes
    edit = MarvelousCraftingDialog(repo, cid, item_id=dialog.item_id)
    edit.name.setText('Not saved'); edit.reject()
    assert repo._connection.total_changes == before
    edit.close()


def test_preview_distinguishes_supported_and_manual_effects(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life')
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('life:cure'))
    assert 'heal a living self' in dialog.preview.toPlainText()
    dialog.cl.setValue(5); dialog.unique.setValue(1)
    assert 'requires manual application' in dialog.preview.toPlainText()


def test_additional_power_draft_does_not_write_and_parent_preserves_it(composer):
    dialog, repo, cid = composer
    before = repo._connection.total_changes
    child = MarvelousCraftingDialog(repo, cid, draft_effect=True)
    child.sphere.setCurrentText('Life')
    child.base_power.setCurrentIndex(child.base_power.findData('life:cure'))
    child.review.setChecked(True); child.save_item()
    assert repo._connection.total_changes == before
    plan = child.blueprint(); plan.pop('extra_effects'); plan.pop('combination_mode')
    dialog.extra_effects.append(plan); dialog.refresh_extra_picker()
    assert dialog.extra_picker.count() == 1
    assert dialog.quotation()[1].market_price_gp == 1000
    dialog.review.setChecked(True); dialog.save_item()
    assert len(repo.list_equipment(cid)) == 1
    edit = MarvelousCraftingDialog(repo, cid, item_id=dialog.item_id)
    assert len(edit.extra_effects) == 1
    assert {key: value for key, value in edit.extra_effects[0].items() if key != 'effect_id'} == plan
    assert 'Cure' in edit.preview.toPlainText()
    edit.close(); child.close()

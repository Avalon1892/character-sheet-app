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


def test_full_blast_option_prices_and_restores(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(5)
    before = dialog.quotation()[1].market_price_gp
    dialog.full_blast.setChecked(True)
    assert dialog.quotation()[1].market_price_gp == before + 2000
    plan = dialog.blueprint(); dialog.load_plan(plan)
    assert dialog.full_blast.isChecked()
    dialog.sphere.setCurrentText('Life')
    assert not dialog.blueprint()['full_blast_damage']


@pytest.mark.parametrize('sphere', ['Warp', 'Weather'])
def test_effect_range_prices_and_restores_independently(composer, sphere):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText(sphere); dialog.cl.setValue(5)
    before = dialog.quotation()[1].market_price_gp
    dialog.effect_range.setValue(2)
    assert dialog.quotation()[1].market_price_gp == before + 8000
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.effect_range.value() == 2 and dialog.range_steps.value() == 0
    dialog.sphere.setCurrentText('Life')
    assert dialog.effect_range.value() == 0


def test_armored_magic_choice_survives_editing_and_column_is_conditional(composer):
    from app.marvelous_base_powers import automatic_self_effect, resolve_base_power
    dialog, repo, cid = composer
    assert dialog.table.isColumnHidden(5)
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(5)
    key = 'protection:aegis-ward-talent:armored-magic-aegis'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    assert not dialog.table.isColumnHidden(5)
    assert automatic_self_effect(dialog.blueprint()) is None
    dialog.table.cellWidget(0, 5).setCurrentIndex(2)
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'] == saved['contributions']
    assert resolve_base_power(dialog.blueprint())['shield_ac'] == 2
    dialog.table.selectRow(0); dialog.remove_contribution()
    assert dialog.table.isColumnHidden(5)


def test_restore_mode_is_explicit_saved_and_cleared_for_other_powers(composer):
    from app.marvelous_base_powers import resolve_base_power
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life')
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('life:restore'))
    assert dialog.restore_mode.currentData() == ''
    dialog.restore_mode.setCurrentIndex(dialog.restore_mode.findData('body'))
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.restore_mode.currentData() == 'body'
    assert resolve_base_power(saved)['restore_mode'] == 'body'
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('life:cure'))
    assert dialog.blueprint()['restore_mode'] == ''


def test_composer_adds_reviewed_prerequisites_without_duplicates_or_writes(composer):
    from app.marvelous_item_rules import advanced_construction_blockers
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(20)
    key = 'life:advanced-talent:resurrection-supreme-warden'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    before = repo._connection.total_changes
    assert dialog.add_prerequisites.isEnabled()
    dialog.add_required_contributions()
    contributions = dialog.blueprint()['contributions']
    assert not advanced_construction_blockers(contributions, 20)
    assert len(contributions) == len({row['catalog_key'] for row in contributions})
    assert not dialog.add_prerequisites.isEnabled() and repo._connection.total_changes == before
    dialog.add_required_contributions()
    assert dialog.blueprint()['contributions'] == contributions


def test_mythic_crafter_advanced_default_uses_existing_feature_access(composer):
    dialog, repo, cid = composer
    repo.add_feat(cid, 'Mythic Crafter')
    mythic = MarvelousCraftingDialog(repo, cid)
    mythic.sphere.setCurrentText('Life'); mythic.cl.setValue(15)
    key = 'life:advanced-talent:hypervitalize'
    index = next(i for i in range(mythic.talent.count()) if mythic.talent.itemData(i)['key'] == key)
    mythic.talent.setCurrentIndex(index); mythic.add_contribution()
    assert mythic.table.cellWidget(0, 1).value() == 1
    mythic.table.cellWidget(0, 4).setValue(2)
    assert mythic.blueprint()['contributions'][0]['complexity'] == 3
    mythic.close()


def test_feat_editor_is_draft_only_and_preserves_live_pricing(composer):
    from app.ui.marvelous_crafting import MarvelousFeatDialog
    dialog, repo, cid = composer
    before = repo._connection.total_changes
    editor = MarvelousFeatDialog(['Maximize Spell'], [])
    assert editor.table.rowCount() == 0
    editor.feat.setCurrentIndex(1); editor.add_selected(); editor.add_selected()
    assert editor.table.rowCount() == 1
    assert editor.table.cellWidget(0, 1).isChecked() and editor.table.cellWidget(0, 2).value() == 3
    editor.table.cellWidget(0, 1).setChecked(True)
    editor.table.cellWidget(0, 2).setValue(3)
    records = editor.records(); editor.confirm()
    dialog.cl.setValue(5); price = dialog.quotation()[1].market_price_gp
    dialog.feat_integrations = records; dialog.update_preview()
    assert dialog.quotation()[1].market_price_gp == price + 8000
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.feat_integrations == records
    cancelled = MarvelousFeatDialog(['Maximize Spell'], records)
    cancelled.table.cellWidget(0, 2).setValue(4); cancelled.reject()
    assert dialog.feat_integrations == records and repo._connection.total_changes == before
    editor.close(); cancelled.close()


def test_recipient_ui_disables_personal_effect_and_cancel_spends_nothing(composer, monkeypatch):
    from dataclasses import replace
    from PySide6.QtWidgets import QMessageBox
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    other = repo.create_character('Recipient', 'Spheres')
    repo.update_hit_points(replace(repo.get_hit_points(other), current=5, maximum=20, auto_calculate=False))
    service = CraftingService(repo, cid)
    base = dict(schema_version=1, caster_level=5, activation='standard', uses=1,
                range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    aegis = service.save_marvelous_design({**base, 'sphere':'Protection', 'base_power':'protection:aegis'}, name='Personal', slot='', description='')
    cure = service.save_marvelous_design({**base, 'sphere':'Life', 'base_power':'life:cure'}, name='Cure', slot='', description='')
    book = MarvelousItemUseDialog(repo, cid)
    book.recipient.setCurrentIndex(book.recipient.findData(other))
    from PySide6.QtCore import Qt
    rows = {book.table.item(row, 0).data(Qt.ItemDataRole.UserRole):row for row in range(book.table.rowCount())}
    assert not book.table.cellWidget(rows[aegis], 3).isEnabled()
    assert book.table.cellWidget(rows[cure], 3).isEnabled()
    before = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    book.activate(cure, True)
    assert repo._connection.total_changes == before and not book.changed
    book.close()


@pytest.mark.parametrize('sphere,key', [('Alteration', 'alteration:talent:mass-alteration-mass'),
                                       ('Illusion', 'illusion:talent:suppression-glamer')])
def test_published_talent_exceptions_default_to_two_complexity(composer, sphere, key):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText(sphere); dialog.cl.setValue(5)
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    assert dialog.table.cellWidget(0, 1).value() == 2
    assert dialog.quotation()[0] == 3


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

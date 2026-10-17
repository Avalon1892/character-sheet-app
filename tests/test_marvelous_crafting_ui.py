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


def test_visible_construction_status_opens_review_without_disabling_draft_save(composer):
    dialog, repo, cid = composer
    dialog.review.setChecked(True)
    dialog.update_preview()
    assert 'construction requirement' in dialog.construction_status.text()
    assert 'Missing base sphere' in dialog.construction_status.toolTip()
    assert dialog.save.isEnabled()
    dialog.review_requirements.click()
    assert dialog.card_tabs.currentWidget() is dialog.preview
    dialog.cl.setValue(100)
    assert dialog.construction_status.toolTip()


@pytest.mark.parametrize('theme', ['classic', 'dark'])
def test_effect_rows_fit_controls_when_theme_is_applied_after_loading(composer, theme):
    from app.ui.dialog_theme import dialog_stylesheet
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    for key in ('creation:talent:larger-creation', 'creation:material-talent:object-of-force-material'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    dialog.setStyleSheet(dialog_stylesheet(theme))
    dialog.show(); QApplication.processEvents()
    for row in range(dialog.table.rowCount()):
        for column in (1,4):
            control = dialog.table.cellWidget(row, column)
            assert dialog.table.rowHeight(row) >= control.sizeHint().height()


def test_base_effect_selection_is_visible_outside_collapsed_settings(composer):
    dialog, repo, cid = composer
    assert dialog.settings_panel.isHidden()
    assert not dialog.base_selection.isHidden()
    assert dialog.base_selection.isAncestorOf(dialog.sphere)
    assert dialog.base_selection.isAncestorOf(dialog.base_power)
    assert not dialog.settings_panel.isAncestorOf(dialog.sphere)
    dialog.sphere.setCurrentText('Weather')
    assert dialog.base_power.currentData() == 'weather:control'


def test_empty_marvelous_window_can_open_designer_without_writes(composer, monkeypatch):
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    from PySide6.QtWidgets import QDialog
    designer, repo, cid = composer
    window = MarvelousItemUseDialog(repo, cid)
    before = repo._connection.total_changes
    opened = []
    def inspect(child):
        assert isinstance(child, MarvelousCraftingDialog)
        assert child.parent() is window
        assert child.tradition_button.isEnabled()
        assert child.effects_button.isEnabled()
        assert child.drawbacks_button.isEnabled()
        opened.append(child)
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(MarvelousCraftingDialog, 'exec', inspect)
    assert window.new_design.isEnabled()
    assert not window.edit_design_button.isEnabled()
    window.new_design.click()
    assert len(opened) == 1 and not window.changed
    window.edit_design(-1, 0)
    assert repo._connection.total_changes == before
    window.close()


def test_demiplane_inserts_and_prices_foreign_prerequisite_then_reopens(composer):
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(15)
    key = 'warp:advanced-talent:create-demiplane-utility'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution(); dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert {row['catalog_key'] for row in rows} == {key, 'warp:space-talent:extradimensional-room-space',
                                                  'creation:material-talent:expanded-materials-material'}
    assert dialog.sphere.currentText() == 'Warp'
    assert dialog.quotation()[0] == 8 and dialog.quotation()[1].market_price_gp == 48000
    assert 'Required cross-sphere talent' in dialog.item_preview.toPlainText()
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='World seed', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    try:
        assert reopened.blueprint()['contributions'] == rows
        assert reopened.quotation()[1].market_price_gp == 48000
    finally:
        reopened.close()


def test_dimensional_tracery_prerequisite_choice_is_atomic(composer, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(10)
    key = 'warp:advanced-talent:dimensional-tracery-3pp'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    snapshot = dialog.blueprint()
    before = repo._connection.total_changes
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: ('', False))
    dialog.add_required_contributions()
    assert dialog.blueprint() == snapshot
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: ('Warp Link (space)', True))
    dialog.add_required_contributions()
    keys = {row['catalog_key'] for row in dialog.blueprint()['contributions']}
    assert keys == {key, 'warp:space-talent:warp-link-space'}
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('key,required,level,points', [
    ('warp:advanced-talent:dimensional-lock-space', 'warp:space-talent:plane-manipulator-space', 15, 2),
    ('warp:advanced-talent:brain-preservation-alienist-hb', 'warp:advanced-talent:organ-detachment-space-alienist-hb', 15, 0),
])
def test_warp_advanced_effect_adds_prerequisite_and_enforces_level(composer, key, required, level, points):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(level)
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    assert dialog.add_prerequisites.isEnabled()
    dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert {row['catalog_key'] for row in rows} == {key, required}
    assert next(row for row in rows if row['catalog_key'] == key)['additional_spell_points'] == points
    if 'brain-preservation' in key:
        assert next(row for row in rows if row['catalog_key'] == required)['additional_spell_points'] == 3
    dialog.cl.setValue(level - 1)
    assert str(level) in dialog.construction_status.toolTip()


def test_fluctuate_picker_updates_cost_duration_and_survives_reopen(composer, monkeypatch):
    from app.content import magic_entry
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.services.crafting import CraftingService
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    entry = magic_entry('warp:space-talent:fluctuate-space')
    repo.add_spell(cid, entry['name'], system='Sphere', school_or_sphere='Warp',
                   catalog_key=entry['key'], catalog_category=entry['category'])
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(8)
    def choose(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', choose)
    dialog.choose_accessible_effects()
    assert dialog.base_power.currentData() == 'warp:fluctuate'
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('concentration'))
    price = dialog.quotation()[1].market_price_gp
    assert not dialog.duration_steps.isEnabled()
    choice.setCurrentIndex(choice.findData('rounds per caster level'))
    assert dialog.duration_steps.isEnabled()
    assert dialog.quotation()[1].market_price_gp == price + 3200
    assert '8 rounds' in dialog.item_preview.toPlainText()
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Flicker charm', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    try:
        assert reopened.base_power.currentData() == 'warp:fluctuate'
        assert reopened.blueprint()['contributions'][0]['additional_spell_points'] == 2
        assert '8 rounds' in reopened.item_preview.toPlainText()
    finally:
        reopened.close()


def test_dimension_pierce_picker_uses_space_effect_not_teleport(composer, monkeypatch):
    from app.content import magic_entry
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    entry = magic_entry('warp:space-talent:dimension-pierce-space')
    repo.add_spell(cid, entry['name'], system='Sphere', school_or_sphere='Warp',
                   catalog_key=entry['key'], catalog_category=entry['category'])
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(5)
    def choose(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', choose)
    dialog.choose_accessible_effects()
    assert dialog.base_power.currentData() == 'warp:dimension-pierce'
    assert dialog.blueprint()['contributions'][0]['additional_spell_points'] == 1
    text = dialog.item_preview.toPlainText()
    assert 'Dimension Pierce' in text and '5 hours' in text and 'ghost touch' in text
    assert 'Teleport Distance' not in text
    from app.services.crafting import CraftingService
    service = CraftingService(repo, cid)
    iid = service.save_marvelous_design(dialog.blueprint(), name='Planar glove', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    try:
        assert reopened.base_power.currentData() == 'warp:dimension-pierce'
        assert '5 hours' in reopened.item_preview.toPlainText()
        invalid = reopened.blueprint()
        invalid['contributions'] = []
        before = repo._connection.total_changes
        with pytest.raises(ValueError, match='talent contribution'):
            service.save_marvelous_design(invalid, name='Invalid glove', slot='', description='', item_id=iid)
        assert repo._connection.total_changes == before
    finally:
        reopened.close()


def test_complete_design_workflow_keeps_live_price_separate_from_locked_card(composer, monkeypatch):
    from app.content import magic_entry
    from app.optional_traditions import catalog
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    entry = magic_entry('life:talent:mass-healing-mass')
    repo.add_spell(cid, entry['name'], system='Sphere', school_or_sphere='Life',
                   catalog_key=entry['key'], catalog_category=entry['category'])
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(10)
    def choose(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', choose)
    dialog.choose_accessible_effects()
    assert dialog.quotation()[1].market_price_gp == 12000
    dialog.crafting_tradition = dict(next(row for row in catalog()['entries'] if row['key'] == 'crafting:diviner-s-sight'))
    dialog.drawbacks = [dict(source='custom', name='Only at sunrise', description='Requires visible sunrise.', reduction=1)]
    dialog.update_preview()
    assert dialog.quotation()[1].market_price_gp == 7200
    assert '7200' in dialog.cost_formula.text()
    dialog.card_locks['price'].setChecked(True)
    dialog.card_edits['price'].setText('GM-negotiated price')
    dialog.review.setChecked(True)
    dialog.save_item()
    assert QDialog.result(dialog) == QDialog.DialogCode.Accepted
    reopened = MarvelousCraftingDialog(repo, cid, item_id=dialog.item_id)
    try:
        assert reopened.drawbacks[0]['reduction'] == 1
        assert reopened.crafting_tradition['key'] == 'crafting:diviner-s-sight'
        assert reopened.card_edits['price'].text() == 'GM-negotiated price'
        assert reopened.quotation()[1].market_price_gp == 7200
        assert 'Mass Healing' in reopened.item_preview.toPlainText()
    finally:
        reopened.close()


def test_invalid_design_clears_stale_calculations_but_keeps_locked_text(composer):
    dialog, repo, cid = composer
    dialog.card_locks['description'].setChecked(True)
    dialog.card_edits['description'].setPlainText('Keep my text')
    original_price = dialog.card_edits['price'].text()
    dialog.permanent.setChecked(True)
    assert 'Invalid design:' in dialog.preview.toPlainText()
    assert dialog.card_edits['price'].text() == '—'
    assert dialog.card_edits['description'].toPlainText() == 'Keep my text'
    assert not dialog.save.isEnabled()
    dialog.permanent.setChecked(False)
    assert dialog.card_edits['price'].text() == original_price
    assert dialog.card_edits['description'].toPlainText() == 'Keep my text'
    assert 'Invalid design:' not in dialog.preview.toPlainText()


def test_every_item_field_lock_survives_repository_roundtrip_and_later_changes(composer):
    from app.marvelous_item_presentation import ITEM_FIELDS
    from app.services.crafting import CraftingService
    from PySide6.QtWidgets import QTextEdit
    dialog, repo, cid = composer
    for key in ITEM_FIELDS:
        dialog.card_locks[key].setChecked(True)
        editor = dialog.card_edits[key]
        if isinstance(editor, QTextEdit): editor.setPlainText('Manual ' + key)
        else: editor.setText('Manual ' + key)
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='All locked', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    try:
        reopened.cl.setValue(8)
        reopened.uses.setCurrentIndex(reopened.uses.findData(3))
        assert reopened.quotation()[1].market_price_gp == 9600
        overrides = reopened.blueprint()['display_overrides']
        for key in ITEM_FIELDS:
            assert reopened.card_locks[key].isChecked()
            assert overrides[key] == dict(locked=True, value='Manual ' + key)
        reopened.card_locks['price'].setChecked(False)
        assert reopened.card_edits['price'].text() == '9,600.00 gp'
        assert reopened.card_locks['description'].isChecked()
    finally:
        reopened.close()


def test_item_card_locks_survive_changes_save_and_reopen(composer):
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.cl.setValue(5)
    dialog.card_locks['price'].setChecked(True)
    dialog.card_edits['price'].setText('Priceless')
    assert 'Priceless' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(6)
    assert dialog.card_edits['price'].text() == 'Priceless'
    assert dialog.card_edits['caster_level'].text() == '6'
    assert dialog.quotation()[1].market_price_gp == 2400
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Locked card', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.card_locks['price'].isChecked()
    assert reopened.card_edits['price'].text() == 'Priceless'
    reopened.card_locks['price'].setChecked(False)
    assert reopened.card_edits['price'].text() == '2,400.00 gp'
    assert reopened.card_edits['price'].isReadOnly()
    reopened.close()


def test_invalid_item_card_override_performs_no_writes(composer):
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    plan = dialog.blueprint(); plan['display_overrides'] = {'price': {'locked': 'yes', 'value': 'free'}}
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='boolean lock'):
        CraftingService(repo, cid).save_marvelous_design(plan, name='Invalid', slot='', description='')
    assert repo._connection.total_changes == before


def test_energy_choice_updates_card_cost_and_survives_saved_design(composer):
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(10)
    key = 'protection:advanced-talent:adaptation-aegis'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    dialog.add_required_contributions()
    choice = dialog.table.cellWidget(0, 5)
    assert choice.isEnabled() and not dialog.table.isColumnHidden(5)
    assert dialog.table.cellWidget(0, 4).value() == 1
    choice.setCurrentIndex(choice.findData('cold'))
    assert 'Energy Type: Cold' in dialog.item_preview.toPlainText()
    assert 'Energy Protection: Immune' in dialog.item_preview.toPlainText()
    assert dialog.quotation()[0] == 5
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Cold aegis', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.table.cellWidget(0, 5).currentData() == 'cold'
    assert 'Energy Protection: Immune' in reopened.item_preview.toPlainText()
    reopened.close()


def test_unrecognized_saved_effect_choice_is_preserved_and_can_be_corrected(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(5)
    key = 'protection:aegis-ward-talent:armored-magic-aegis'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    saved = dialog.blueprint(); saved['contributions'][0]['effect_choice'] = 'unsupported-value'
    before = repo._connection.total_changes
    dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'][0]['effect_choice'] == 'unsupported-value'
    assert 'Unrecognized:' in dialog.table.cellWidget(0, 5).currentText()
    assert 'supported effect option' in dialog.cost_formula.text()
    assert not dialog.save.isEnabled()
    assert repo._connection.total_changes == before
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('armor'))
    assert dialog.blueprint()['contributions'][0]['effect_choice'] == 'armor'
    assert 'Armored Magic aegis (armor)' in dialog.item_preview.toPlainText()


def test_special_recharge_control_requires_confirmation_and_refreshes_counts(composer, monkeypatch):
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    from app.services.crafting import CraftingService
    from PySide6.QtWidgets import QMessageBox
    dialog, repo, cid = composer
    plan = dialog.blueprint(); plan['crafting_tradition'] = {'key': 'crafting:evil-artifice'}
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Restricted device', slot='', description='')
    repo.consume_marvelous_item_use(cid, iid)
    window = MarvelousItemUseDialog(repo, cid)
    window.table.selectRow(0)
    assert window.recharge.isEnabled() and window.table.item(0, 1).text() == '0'
    before = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    window.record_recharge()
    assert repo._connection.total_changes == before and not window.changed
    def confirm(*args):
        assert 'once per day' in args[2] and '5 feet' in args[2]
        return QMessageBox.StandardButton.Yes
    monkeypatch.setattr(QMessageBox, 'question', confirm)
    window.record_recharge()
    assert window.changed and window.table.item(0, 1).text() == '1'
    window.close()


def test_area_bound_choice_updates_descriptors_and_survives_save(composer):
    from app.optional_traditions import catalog
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    assert dialog.area_bound.isHidden()
    dialog.cl.setValue(5)
    dialog.crafting_tradition = next(e for e in catalog()['entries'] if e['key'] == 'crafting:city-construction')
    dialog.update_preview()
    assert not dialog.area_bound.isHidden()
    assert 'choose distance-limited use' in dialog.item_preview.toPlainText()
    dialog.area_bound.setCurrentIndex(dialog.area_bound.findData('distance'))
    assert 'within 5 miles' in dialog.item_preview.toPlainText()
    price = dialog.quotation()[1].market_price_gp
    dialog.area_bound.setCurrentIndex(dialog.area_bound.findData('recharge'))
    assert 'at least 5 minutes' in dialog.item_preview.toPlainText()
    assert dialog.quotation()[1].market_price_gp == price
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Bound item', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.area_bound.currentData() == 'recharge'
    reopened.close()


def test_bulky_weight_updates_card_inventory_and_reopens_without_double_multiplier(composer):
    from app.optional_traditions import catalog
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.cl.setValue(5); dialog.base_weight.setValue(2)
    dialog.crafting_tradition = next(e for e in catalog()['entries'] if e['key'] == 'crafting:city-construction')
    dialog.area_bound.setCurrentIndex(dialog.area_bound.findData('distance')); dialog.update_preview()
    assert dialog.card_edits['weight'].text() == '400 lb.'
    price = dialog.quotation()[1].market_price_gp
    dialog.card_locks['weight'].setChecked(True); dialog.card_edits['weight'].setText('Manual weight label')
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Heavy item', slot='', description='')
    item = next(item for item in repo.list_equipment(cid) if item.id == iid)
    assert item.weight == 400 and item.value_gp == price
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.base_weight.value() == 2
    assert reopened.card_edits['weight'].text() == 'Manual weight label'
    reopened.card_locks['weight'].setChecked(False)
    assert reopened.card_edits['weight'].text() == '400 lb.'
    reopened.remove_crafting_tradition()
    assert reopened.card_edits['weight'].text() == '2 lb.'
    reopened.close()


@pytest.mark.parametrize('weight', [0.0000125, 1000000001.25])
def test_loaded_base_weight_is_not_silently_rounded_or_clamped(composer, weight):
    dialog, repo, cid = composer
    saved = dialog.blueprint(); saved['base_weight_lb'] = weight
    before = repo._connection.total_changes
    dialog.load_plan(saved)
    assert dialog.blueprint()['base_weight_lb'] == weight
    assert repo._connection.total_changes == before


def test_invalid_loaded_weight_is_rejected_before_editor_normalization(composer):
    dialog, repo, cid = composer
    saved = dialog.blueprint(); saved['base_weight_lb'] = True
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='finite nonnegative'):
        dialog.load_plan(saved)
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('guided', [False, True])
def test_force_blast_updates_live_cost_damage_and_saved_preview(composer, guided):
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(6)
    key = 'destruction:blast-type-talent:force-blast-blast-type-force'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    if guided:
        key = 'destruction:blast-shape-talent:guided-strike-blast-shape'
        index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
        dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    assert dialog.table.cellWidget(0, 4).value() == 1
    assert dialog.quotation()[0] == (5 if guided else 3)
    assert '3d6 force' in dialog.item_preview.toPlainText()
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Force device', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert '3d6 force' in reopened.item_preview.toPlainText()
    if guided: assert 'Attack Circumstance Bonus: 20' in reopened.item_preview.toPlainText()
    reopened.close()


def test_pricing_columns_are_prioritized_and_alternative_groups_are_conditional(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5)
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == 'life:talent:deeper-healing')
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    assert dialog.table.horizontalHeader().visualIndex(4) == 2
    assert dialog.table.isColumnHidden(3)
    checkbox = dialog.table.cellWidget(0, 2)
    checkbox.setChecked(True)
    assert not dialog.table.isColumnHidden(3)
    dialog.table.cellWidget(0, 3).setValue(2)
    checkbox.setChecked(False)
    assert dialog.table.isColumnHidden(3)
    checkbox.setChecked(True)
    assert dialog.blueprint()['contributions'][0]['alternative_group'] == 2


def test_alternative_prerequisite_choice_is_atomic_and_prices_only_chosen_talent(composer, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from app.marvelous_item_rules import missing_construction_alternatives
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(10)
    key = 'destruction:advanced-talent:calamity-blast-shape'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    before = dialog.blueprint()['contributions']; writes = repo._connection.total_changes
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: ('', False))
    dialog.add_required_contributions()
    assert dialog.blueprint()['contributions'] == before
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: (args[3][1], True))
    dialog.add_required_contributions()
    contributions = dialog.blueprint()['contributions']
    assert len(contributions) == 2
    assert contributions[1]['catalog_key'] == 'destruction:blast-shape-talent:sculpt-blast-blast-shape'
    assert not missing_construction_alternatives(contributions)
    assert dialog.table.cellWidget(0, 4).value() == 2
    assert repo._connection.total_changes == writes
    dialog.add_required_contributions()
    assert dialog.blueprint()['contributions'] == contributions


def test_multiple_prerequisite_choices_cancel_atomically_and_share_dependencies(composer, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    from app.marvelous_item_rules import advanced_construction_blockers
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(10)
    key = 'protection:advanced-talent:pithing-protection-arcforge-addendum-lg'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    original = dialog.blueprint()['contributions']; before = repo._connection.total_changes
    prompts = []
    def cancel_second(*args):
        prompts.append(args[3])
        return (args[3][-1], True) if len(prompts) == 1 else ('', False)
    monkeypatch.setattr(QInputDialog, 'getItem', cancel_second)
    dialog.add_required_contributions()
    assert len(prompts) == 2 and dialog.blueprint()['contributions'] == original
    prompts.clear()
    def choose(*args):
        prompts.append(args[3]); return args[3][-1], True
    monkeypatch.setattr(QInputDialog, 'getItem', choose)
    dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert len(prompts) == 2 and len(rows) == 3
    assert not advanced_construction_blockers(rows, 10)
    assert repo._connection.total_changes == before
    dialog.add_required_contributions()
    assert len(prompts) == 2 and dialog.blueprint()['contributions'] == rows


def test_optional_prerequisite_promotion_requires_confirmation_without_duplicates(composer, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app.marvelous_item_rules import advanced_construction_blockers
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(10)
    for key in ('warp:advanced-talent:true-teleport', 'warp:talent:distant-teleport', 'warp:talent:unseeing-teleport'):
        index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
        dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    dialog.table.cellWidget(1, 2).setChecked(True); dialog.table.cellWidget(2, 2).setChecked(True)
    original = dialog.blueprint()['contributions']; before = repo._connection.total_changes
    assert advanced_construction_blockers(original, 10)
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    dialog.add_required_contributions()
    assert dialog.blueprint()['contributions'] == original
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert len(rows) == 3 and not advanced_construction_blockers(rows, 10)
    assert dialog.quotation()[0] == 7
    assert repo._connection.total_changes == before


def test_loading_plan_calculates_once_and_keeps_live_updates_after_failure(composer, monkeypatch):
    dialog, repo, cid = composer
    saved = dialog.blueprint()
    saved.update(sphere='Life', base_power='life:cure', caster_level=10, uses=3, unique_changes=1,
                 contributions=[dict(catalog_key='life:talent:deeper-healing', complexity=1, additional_spell_points=0)])
    saved['display_overrides'] = {'description': dict(locked=True, value='Locked manual text')}
    quote = dialog.quotation
    calls = []
    def counted():
        calls.append(True); return quote()
    monkeypatch.setattr(dialog, 'quotation', counted)
    before = repo._connection.total_changes
    dialog.load_plan(saved)
    assert len(calls) == 1
    assert dialog.card_edits['description'].toPlainText() == 'Locked manual text'
    dialog.cl.setValue(11)
    assert len(calls) == 2 and dialog.card_edits['description'].toPlainText() == 'Locked manual text'
    invalid = {**saved, 'base_weight_lb': True}
    with pytest.raises(ValueError): dialog.load_plan(invalid)
    assert not dialog.loading_plan
    dialog.cl.setValue(12)
    assert len(calls) == 3
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('already_applied', [0, 1, 2])
def test_counted_prerequisite_addition_is_idempotent_and_does_not_write(composer, already_applied):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(10)
    key = 'destruction:advanced-talent:extreme-range'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    extended = 'destruction:talent:extended-range-range'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == extended))
    for _ in range(already_applied): dialog.add_contribution()
    before = repo._connection.total_changes
    dialog.add_required_contributions()
    keys = [row['catalog_key'] for row in dialog.blueprint()['contributions']]
    assert keys.count('destruction:talent:extended-range-range') == 2
    price = dialog.quotation()[1].market_price_gp
    dialog.add_required_contributions()
    assert dialog.table.rowCount() == 3 and dialog.quotation()[1].market_price_gp == price
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('cancel_second', [False, True])
@pytest.mark.parametrize('owner', ['crystal-cocoon', 'radiation-blast-blast-type-fire-light'])
def test_group_prerequisite_choices_are_distinct_and_cancel_atomically(composer, monkeypatch, cancel_second, owner):
    from PySide6.QtWidgets import QInputDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(10)
    key = 'destruction:advanced-talent:' + owner
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    before = repo._connection.total_changes
    choices = []
    def choose(*args):
        labels = args[3]
        choices.append(labels[0])
        return labels[0], not (cancel_second and len(choices) == 2)
    monkeypatch.setattr(QInputDialog, 'getItem', choose)
    dialog.add_required_contributions()
    assert len(choices) == 2 and choices[0] != choices[1]
    assert dialog.table.rowCount() == (1 if cancel_second else 3)
    assert repo._connection.total_changes == before


def test_prerequisite_batch_calculates_final_preview_once(composer, monkeypatch):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(20)
    key = 'warp:advanced-talent:enduring-portal'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    calls = []
    original = dialog.quotation
    monkeypatch.setattr(dialog, 'quotation', lambda: (calls.append(True), original())[1])
    dialog.add_required_contributions()
    assert calls == [True]
    assert not dialog.loading_plan
    assert dialog.table.rowCount() > 2


def test_prerequisite_batch_releases_preview_guard_after_failure(composer, monkeypatch):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(10)
    key = 'destruction:advanced-talent:extreme-range'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    original = dialog.add_contribution
    def fail(): raise RuntimeError('Interrupted draft addition')
    monkeypatch.setattr(dialog, 'add_contribution', fail)
    with pytest.raises(RuntimeError, match='Interrupted draft'):
        dialog.add_required_contributions()
    assert not dialog.loading_plan
    monkeypatch.setattr(dialog, 'add_contribution', original)
    dialog.add_required_contributions()
    assert dialog.table.rowCount() == 3


def test_invalid_draft_keeps_equation_visible_without_stale_price(composer):
    dialog, repo, cid = composer
    dialog.cl.setValue(5)
    valid = dialog.cost_formula.text()
    assert '400 gp' in valid
    dialog.unique.setValue(100)
    invalid = dialog.cost_formula.text()
    assert '400 gp × caster level × complexity × uses factor' in invalid
    assert 'invalid design' in invalid
    assert 'Complexity:' not in invalid
    assert not dialog.save.isEnabled()
    dialog.unique.setValue(0)
    assert dialog.cost_formula.text() == valid


def test_drawback_item_values_update_live_without_overwriting_description_lock(composer):
    dialog, repo, cid = composer
    dialog.cl.setValue(4)
    dialog.drawbacks = [dict(source='published', catalog_key='crafting:unwieldy', name='Unwieldy', description='', reduction=0),
                        dict(source='published', catalog_key='crafting:clingy', name='Clingy', description='', reduction=0)]
    dialog.update_preview()
    assert 'Unwieldy: −2' in dialog.item_preview.toPlainText()
    assert 'DC 14' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(8)
    assert 'Unwieldy: −3' in dialog.item_preview.toPlainText()
    assert 'DC 18' in dialog.item_preview.toPlainText()
    dialog.card_locks['description'].setChecked(True)
    dialog.card_edits['description'].setPlainText('Locked item prose')
    dialog.cl.setValue(12)
    assert 'Locked item prose' in dialog.item_preview.toPlainText()
    assert 'Unwieldy: −4' not in dialog.item_preview.toPlainText()


def test_group_teleport_adds_and_prices_mass_prerequisite_without_changing_saved_overrides(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(10)
    key = 'warp:advanced-talent:group-teleport'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution(); dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    mass = next(row for row in rows if row['catalog_key'] == 'warp:talent:mass-teleport-mass')
    assert mass['additional_spell_points'] == 1 and mass['complexity'] == 2
    assert dialog.quotation()[0] == 7
    saved = dialog.blueprint()
    mass = next(row for row in saved['contributions'] if row['catalog_key'] == 'warp:talent:mass-teleport-mass')
    mass['additional_spell_points'] = 0; mass['complexity'] = 1
    dialog.load_plan(saved)
    assert dialog.quotation()[0] == 6
    group = next(row for row in saved['contributions'] if row['catalog_key'] == key)
    group['additional_spell_points'] = 0; group['complexity'] = 2
    dialog.load_plan(saved)
    assert dialog.quotation()[0] == 5


@pytest.mark.parametrize('charged', [False, True])
def test_preview_reuses_one_fresh_base_quote_per_edit(composer, monkeypatch, charged):
    from app import marvelous_item_rules as rules, marvelous_item_presentation as presentation
    from app.ui import marvelous_crafting as ui
    dialog, repo, cid = composer
    if charged:
        dialog.uses.setCurrentIndex(dialog.uses.findData(5))
        dialog.drawbacks = [dict(source='published', catalog_key='crafting:charged', name='Charged', description='', reduction=0)]
    original = rules.quote_marvelous_blueprint
    calls = []
    def quote(plan):
        calls.append(plan['caster_level'])
        return original(plan)
    for module in (rules, presentation, ui): monkeypatch.setattr(module, 'quote_marvelous_blueprint', quote)
    dialog.cl.setValue(5)
    assert calls == [5]
    assert ('10,000.00 gp' if charged else '2,000.00 gp') in dialog.item_preview.toPlainText()
    calls.clear()
    dialog.cl.setValue(6)
    assert calls == [6]
    assert ('12,000.00 gp' if charged else '2,400.00 gp') in dialog.item_preview.toPlainText()
    assert ('12000 gp' if charged else '2400 gp') in dialog.cost_formula.text()


def test_explosive_orb_choice_updates_price_after_row_removal_and_preserves_saved_override(composer):
    from app.marvelous_base_powers import EXPLOSIVE_ORB_KEY
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(10)
    for key in ('destruction:blast-type-talent:acid-blast-blast-type-acid', EXPLOSIVE_ORB_KEY):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    choice = dialog.table.cellWidget(1, 5)
    dialog.table.selectRow(0); dialog.remove_contribution()
    choice.setCurrentIndex(choice.findData('single square'))
    assert dialog.quotation()[0] == 2
    assert 'Reflex negates' in dialog.item_preview.toPlainText()
    choice.setCurrentIndex(choice.findData('expanded burst'))
    assert dialog.quotation()[0] == 3
    assert 'Burst radius up to 20 ft.' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(15)
    assert 'Burst radius up to 25 ft.' in dialog.item_preview.toPlainText()
    dialog.table.cellWidget(0, 4).setValue(4)
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.table.cellWidget(0, 4).value() == 4
    assert dialog.blueprint()['contributions'] == saved['contributions']


def test_detonating_salvo_mode_updates_cost_and_visible_selection(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(15)
    key = 'destruction:advanced-talent:detonating-salvo-lg'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('5-foot radius explosions'))
    small = dialog.quotation()[1].market_price_gp
    assert dialog.table.cellWidget(0, 4).value() == 1
    assert 'Selected option: 5-foot radius explosions' in dialog.item_preview.toPlainText()
    choice.setCurrentIndex(choice.findData('expanded explosions'))
    assert dialog.table.cellWidget(0, 4).value() == 2
    assert dialog.quotation()[1].market_price_gp == small + 400 * 15
    assert 'Selected option: expanded explosions' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'] == saved['contributions']


def test_salvo_mode_adds_one_sp_and_live_surges_without_multiplying_dice(composer):
    from app.marvelous_base_powers import BLAST_SALVO_KEY
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(12)
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == BLAST_SALVO_KEY))
    dialog.add_contribution()
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('two surges'))
    assert dialog.quotation()[0] == 2
    assert 'Maximum Surges: 2' in dialog.item_preview.toPlainText()
    choice.setCurrentIndex(choice.findData('additional surges'))
    assert dialog.quotation()[0] == 3
    text = dialog.item_preview.toPlainText()
    assert 'Maximum Surges: 5' in text and 'Damage: 6d6 bludgeoning' in text


def test_energy_sphere_duration_mode_price_and_saved_adjustment_stay_in_sync(composer):
    from app.marvelous_base_powers import ENERGY_SPHERE_KEY
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(10)
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == ENERGY_SPHERE_KEY))
    dialog.add_contribution()
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('concentration'))
    assert not dialog.duration_steps.isEnabled() and dialog.quotation()[0] == 2
    assert 'Duration Concentration' in dialog.item_preview.toPlainText()
    choice.setCurrentIndex(choice.findData('rounds per caster level'))
    assert dialog.duration_steps.isEnabled() and dialog.quotation()[0] == 3
    assert 'Duration 10 rounds' in dialog.item_preview.toPlainText()
    dialog.duration_steps.setValue(1)
    assert dialog.quotation()[0] == 5 and 'Duration 10 minutes' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.duration_steps.value() == 1 and dialog.blueprint()['duration_steps'] == 1
    assert 'Duration 10 minutes' in dialog.item_preview.toPlainText()
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('concentration'))
    assert dialog.duration_steps.value() == 0 and dialog.quotation()[0] == 2


def test_energy_wall_modes_coordinate_sp_duration_geometry_and_reopen(composer):
    from app.marvelous_base_powers import ENERGY_WALL_KEY
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(10)
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == ENERGY_WALL_KEY))
    dialog.add_contribution()
    choice = dialog.table.cellWidget(0, 5)
    for mode, cost, text in [('concentration cube', 2, 'Duration Concentration'),
                             ('straight wall', 3, '200 ft. wide'), ('hemisphere', 3, 'Hemisphere radius up to 25 ft.')]:
        choice.setCurrentIndex(choice.findData(mode))
        assert dialog.quotation()[0] == cost and text in dialog.item_preview.toPlainText()
    dialog.cl.setValue(12)
    assert 'Hemisphere radius up to 30 ft.' in dialog.item_preview.toPlainText()
    dialog.duration_steps.setValue(1)
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'] == saved['contributions']
    assert dialog.duration_steps.value() == 1 and 'Duration 12 minutes' in dialog.item_preview.toPlainText()


def test_diviners_sight_use_button_tracks_training_and_explains_requirement(composer):
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    plan = dialog.blueprint()
    plan['crafting_tradition'] = dict(key='crafting:diviner-s-sight')
    CraftingService(repo, cid).save_marvelous_design(plan, name='Educated device', slot='', description='')
    window = MarvelousItemUseDialog(repo, cid)
    button = window.table.cellWidget(0, 3)
    assert not button.isEnabled() and 'Divination sphere training' in button.toolTip()
    repo.add_spell(cid, 'Divination', system='Sphere', school_or_sphere='Divination',
        catalog_key='divination:base', catalog_category='Base Sphere')
    window.refresh()
    assert window.table.cellWidget(0, 3).isEnabled()
    window.close()


def test_educated_sphere_editor_saves_choices_and_cancellation_does_not_write(composer, monkeypatch):
    from PySide6.QtWidgets import QDialog, QListWidget, QDialogButtonBox
    dialog, repo, cid = composer
    dialog.drawbacks = [dict(source='published', catalog_key='crafting:educated', name='Educated', description='', reduction=0)]
    dialog.update_preview()
    before = repo._connection.total_changes
    def choose(child):
        picker = child.findChild(QListWidget, 'educatedSpheres')
        buttons = child.findChild(QDialogButtonBox)
        assert not buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        for index in range(picker.count()):
            if picker.item(index).text() in {'Life', 'Boxing'}: picker.item(index).setSelected(True)
        assert buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', choose)
    dialog.edit_drawback(0)
    assert set(dialog.drawbacks[0]['required_spheres']) == {'Life', 'Boxing'}
    saved = dialog.blueprint()
    monkeypatch.setattr(QDialog, 'exec', lambda child: QDialog.DialogCode.Rejected)
    dialog.edit_drawback(0)
    assert dialog.blueprint()['drawbacks'] == saved['drawbacks']
    assert repo._connection.total_changes == before


def test_mass_healing_contribution_includes_its_extra_sp_in_live_price(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(10)
    initial = dialog.quotation()[1].market_price_gp
    key = 'life:talent:mass-healing-mass'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    row = dialog.blueprint()['contributions'][0]
    assert row['additional_spell_points'] == 1 and row['complexity'] == 2
    assert dialog.quotation()[1].market_price_gp == initial + 8000


def test_greater_weather_mode_changes_live_sp_and_price(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Weather'); dialog.cl.setValue(10)
    key = 'weather:talent:greater-weather'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('two weather categories'))
    initial = dialog.quotation()[1].market_price_gp
    assert dialog.blueprint()['contributions'][0]['additional_spell_points'] == 1
    choice.setCurrentIndex(choice.findData('three weather categories'))
    assert dialog.blueprint()['contributions'][0]['additional_spell_points'] == 2
    assert dialog.quotation()[1].market_price_gp == initial + 4000
    assert 'three weather categories' in dialog.item_preview.toPlainText()
    assert 'Change 3 weather categories' in dialog.item_preview.toPlainText()
    # Loading a reviewed mode must preserve the user's explicitly edited cost.
    dialog.table.cellWidget(0, 4).setValue(4)
    from app.services.crafting import CraftingService
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Weather device', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    try:
        saved = reopened.blueprint()['contributions'][0]
        assert saved['effect_choice'] == 'three weather categories'
        assert saved['additional_spell_points'] == 4
        reopened.table.cellWidget(0, 5).setCurrentIndex(choice.findData('two weather categories'))
        assert reopened.blueprint()['contributions'][0]['additional_spell_points'] == 1
    finally:
        reopened.close()


def test_repeated_complex_checks_save_reopen_and_preserve_description_lock(composer):
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.cl.setValue(5)
    dialog.drawbacks = [dict(source='published', catalog_key='crafting:complex', name='Complex',
        description='', reduction=0, required_skill='Acrobatics', additional_skills=['Linguistics', 'Acrobatics'])]
    dialog.update_preview()
    assert dialog.item_preview.toPlainText().count('DC 10') == 3
    dialog.card_locks['description'].setChecked(True)
    dialog.card_edits['description'].setPlainText('My locked description')
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Complex device', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    try:
        assert reopened.drawbacks[0]['additional_skills'] == ['Linguistics', 'Acrobatics']
        reopened.cl.setValue(8)
        assert 'My locked description' in reopened.item_preview.toPlainText()
        assert 'DC 13' not in reopened.item_preview.toPlainText()
        reopened.card_locks['description'].setChecked(False)
        assert reopened.item_preview.toPlainText().count('DC 13') == 3
    finally:
        reopened.close()


def test_complex_skill_editor_requires_choice_and_cancel_preserves_draft(composer, monkeypatch):
    from PySide6.QtWidgets import QDialog, QComboBox, QDialogButtonBox, QPushButton, QListWidget
    dialog, repo, cid = composer
    dialog.drawbacks = [dict(source='published', catalog_key='crafting:complex', name='Complex', description='', reduction=0)]
    before = repo._connection.total_changes
    def choose(child):
        picker = child.findChild(QComboBox, 'complexSkill')
        button = child.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
        assert picker.currentData() == '' and not button.isEnabled()
        picker.setCurrentIndex(picker.findData('Acrobatics'))
        assert button.isEnabled()
        add = next(button for button in child.findChildren(QPushButton) if button.text() == 'Add another check for chosen skill')
        add.click()
        picker.setCurrentIndex(picker.findData('Linguistics'))
        add.click()
        picker.setCurrentIndex(picker.findData('Acrobatics'))
        assert child.findChild(QListWidget, 'complexAdditionalSkills').count() == 2
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', choose)
    dialog.edit_drawback(0)
    assert dialog.drawbacks[0]['required_skill'] == 'Acrobatics'
    assert dialog.drawbacks[0]['additional_skills'] == ['Acrobatics', 'Linguistics']
    saved = dialog.blueprint()
    monkeypatch.setattr(QDialog, 'exec', lambda child: QDialog.DialogCode.Rejected)
    dialog.edit_drawback(0)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == before


def test_temporal_haste_adds_required_talent_and_sp_to_live_price(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Time'); dialog.cl.setValue(10)
    key = 'time:advanced-talent:temporal-haste'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution(); dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert {row['catalog_key'] for row in rows} == {key, 'time:talent:improved-haste'}
    assert next(row for row in rows if row['catalog_key'] == key)['additional_spell_points'] == 1
    assert dialog.quotation()[0] == 5
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'] == rows


@pytest.mark.parametrize('key, first_mode, second_mode, cost', [
    ('telekinesis:talent:divided-mind-mass', 'multiple lifted objects', 'multiple maneuver or push targets', 1),
    ('telekinesis:talent:gravity-ward-well', 'concentration', 'Sustained Force', 1),
    ('telekinesis:talent:kinetic-sense', 'target without line of sight', '30-foot blindsense', 1),
    ('telekinesis:talent:tether', 'concentration', 'Sustained Force', 1),
    ('telekinesis:advanced-talent:focused-power', 'one additional size category', 'two additional size categories', 2),
    ('telekinesis:talent:telekinetic-push', 'aid movement or deflect', 'direct push on hostile target', 1),
    ('telekinesis:talent:gravity-shift', 'concentration', 'Sustained Force', 1),
    ('light:talent:doubled-nimbus', 'increase casting time one step', 'spend SP instead of increasing casting time', 1),
    ('light:talent:flash', 'choose application timing once per round', 'swift-action additional application', 1),
    ('light:talent:beacon-of-hope-light', 'target fear-save bonus', 'fear recovery bright area', 1),
    ('light:talent:blinding-light-light', 'dazzle glowing target', 'blinding bright area', 1),
    ('light:talent:disorienting-patterns-light', 'difficult terrain', 'prone-inducing patterns', 1),
    ('light:talent:purifying-light-light-crimdan', 'targeted purification', 'purification bright area', 1),
    ('light:talent:irradiance-light', 'sicken glowing target', 'nauseating bright light', 1),
    ('light:advanced-talent:star-genesis', 'expanded radius', 'expanded radius with central daylight', 2),
    ('enhancement:enhance-talent:energize-body-enhance', 'suppress fatigue / reduce exhaustion', 'suppress exhaustion', 1),
    ('enhancement:enhance-talent:ragged-edges-enhance', 'half caster level bleed', 'caster level bleed', 1),
    ('enhancement:enhance-talent:spectral-enhancement-enhance-gravecaller-s-hb', 'ghost touch armor', 'empowered ghost touch armor', 1),
    ('time:advanced-talent:shuffle-time-time-3pp', 'reroll initiative', 'roll twice, take lower', 1),
    ('time:advanced-talent:past-sight-utility', 'view hours', 'view days', 2),
    ('time:talent:delay-pain-time', 'delay until next turn', 'split damage across two turns', 2),
    ('time:talent:time-bubble-time', 'time bubble only', 'include Haste or Slow', 2),
    ('warp:space-talent:avert-space', 'readied standard action', 'immediate action', 1),
    ('warp:space-talent:blink-space', 'concentration', 'minutes per caster level', 1),
    ('warp:space-talent:create-gap-space', 'concentration', 'minutes per caster level', 2),
    ('warp:space-talent:distort-size-space', 'concentration', 'minutes per caster level', 1),
    ('enhancement:advanced-talent:reverse-gravity-enhance', 'concentration', 'rounds per caster level', 2),
])
def test_effect_mode_updates_price_and_preserves_saved_manual_cost(composer, key, first_mode, second_mode, cost):
    from app.content import magic_entry
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText(magic_entry(key)['sphere']); dialog.cl.setValue(10)
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData(first_mode))
    initial = dialog.quotation()
    choice.setCurrentIndex(choice.findData(second_mode))
    assert dialog.blueprint()['contributions'][0]['additional_spell_points'] == cost
    assert dialog.quotation()[0] == initial[0] + 1
    assert dialog.quotation()[1].market_price_gp > initial[1].market_price_gp
    assert second_mode in dialog.item_preview.toPlainText()
    dialog.table.cellWidget(0, 4).setValue(3)
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'] == saved['contributions']
    assert dialog.table.cellWidget(0, 4).value() == 3


def test_time_item_card_updates_haste_and_fast_healing_from_caster_level(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Time'); dialog.cl.setValue(5)
    key = 'time:talent:augment-healing'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    text = dialog.item_preview.toPlainText()
    assert 'Attack Bonus: 1' in text and 'Fast Healing: 2' in text
    dialog.cl.setValue(10)
    text = dialog.item_preview.toPlainText()
    assert 'Attack Bonus: 2' in text and 'Fast Healing: 3' in text
    assert '+30 ft. to all movement modes' in text


@pytest.mark.parametrize('talent,power,mode,detail', [
    ('blink-space', 'warp:blink', 'penalty for minutes per caster level', '30%'),
    ('create-gap-space', 'warp:create-gap', 'minutes per caster level', 'Contiguous 5-foot cubes'),
    ('distort-size-space', 'warp:distort-size', 'minutes per caster level', '10 ft.'),
])
def test_space_effect_picker_selects_derived_power_and_updates_duration(composer, monkeypatch, talent, power, mode, detail):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.content import magic_entry
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(6)
    entry = magic_entry('warp:space-talent:' + talent)
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def accept(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', accept)
    dialog.choose_accessible_effects()
    assert dialog.base_power.currentData() == power
    picker = dialog.table.cellWidget(0, 5)
    picker.setCurrentIndex(picker.findData(mode))
    text = dialog.item_preview.toPlainText()
    assert '6 minutes' in text and detail in text
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert dialog.duration_steps.isEnabled()


def test_dual_enhancement_mode_adds_prices_and_restores_prerequisite(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(6)
    key = 'enhancement:enhance-talent:physical-enhancement-enhance'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    picker = dialog.table.cellWidget(0, 5)
    picker.setCurrentIndex(picker.findData('Strength'))
    original_complexity = dialog.quotation()[0]
    writes = repo._connection.total_changes
    picker.setCurrentIndex(picker.findData('Strength + Dexterity'))
    rows = dialog.blueprint()['contributions']
    assert [row['catalog_key'] for row in rows].count('enhancement:talent:dual-enhancement') == 1
    assert dialog.quotation()[0] == original_complexity + 2
    picker.setCurrentIndex(picker.findData('Strength + Constitution'))
    assert dialog.table.rowCount() == 2
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    legacy = dict(saved, contributions=[saved['contributions'][0]])
    dialog.load_plan(legacy)
    assert dialog.table.rowCount() == 1
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,field,initial,updated', [
    ('alter-movement-enhance', 'Movement Speed Bonus', '+10 ft. enhancement', '+20 ft. enhancement'),
    ('cripple-enhance', 'Roll Penalty', '-2', '-3'),
    ('superior-reflexes-enhance', 'Initiative Bonus', '1', '2'),
])
def test_enhancement_live_card_updates_level_values_without_character_writes(composer, suffix, field, initial, updated):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(4)
    key = 'enhancement:enhance-talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    before = repo._connection.total_changes
    dialog.add_contribution()
    if suffix == 'alter-movement-enhance':
        picker = dialog.table.cellWidget(0, 5)
        picker.setCurrentIndex(picker.findData('increase one movement speed'))
    assert f'{field}: {initial}' in dialog.item_preview.toPlainText()
    assert 'Equipment Enhancement Bonus:' not in dialog.item_preview.toPlainText()
    dialog.cl.setValue(5)
    assert f'{field}: {updated}' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert f'{field}: {updated}' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('suffix,choice,field,initial,updated', [
    ('enhance-focus-enhance', 'Perception', 'Skill Enhancement Bonus', '6', '8'),
    ('staunch-resistance-enhance', 'Reflex', 'Untyped Save Bonus', '2', '4'),
    ('supply-vigor-enhance', 'Dexterity', 'Ignored Existing Ability Damage Drain Penalty', '2', '6'),
    ('harden-weaken-enhance', 'grant DR/adamantine', 'Damage Reduction', '2/adamantine', '7/adamantine'),
])
def test_selected_enhancement_modes_update_and_restore_without_writes(composer, suffix, choice, field, initial, updated):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(4)
    key = 'enhancement:enhance-talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    before = repo._connection.total_changes
    dialog.add_contribution()
    picker = dialog.table.cellWidget(0, 5); picker.setCurrentIndex(picker.findData(choice))
    assert f'{field}: {initial}' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(14)
    assert f'{field}: {updated}' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert f'{field}: {updated}' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == before


def test_alternative_energy_mode_inserts_prices_and_restores_prerequisite(composer):
    from app.marvelous_base_powers import ENERGY_ENHANCEMENT_KEY, ALTERNATIVE_ENERGY_KEY
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(10)
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == ENERGY_ENHANCEMENT_KEY))
    dialog.add_contribution()
    picker = dialog.table.cellWidget(0, 5); picker.setCurrentIndex(picker.findData('weapon: fire'))
    initial = dialog.quotation()[0]; writes = repo._connection.total_changes
    picker.setCurrentIndex(picker.findData('weapon: force'))
    rows = dialog.blueprint()['contributions']
    assert [row['catalog_key'] for row in rows].count(ALTERNATIVE_ENERGY_KEY) == 1
    assert dialog.quotation()[0] == initial + 2
    assert 'Additional Energy Damage: 1d6+5 force' in dialog.item_preview.toPlainText()
    picker.setCurrentIndex(picker.findData('weapon: sonic'))
    assert dialog.table.rowCount() == 2
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


def test_light_speed_inserts_transitive_prerequisites_and_reopens_without_duplicates(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Light'); dialog.cl.setValue(15)
    key = 'light:advanced-talent:light-speed'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution(); dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert {row['catalog_key'] for row in rows} == {key, 'light:advanced-talent:incarnate-glow', 'light:talent:flicker-light'}
    assert len(rows) == 3 and dialog.quotation()[0] == 8
    saved = dialog.blueprint(); writes = repo._connection.total_changes
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved and dialog.table.rowCount() == 3
    assert repo._connection.total_changes == writes


def test_radiation_inserts_paid_irradiance_mode_and_prices_two_total_sp(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Light'); dialog.cl.setValue(10)
    key = 'light:advanced-talent:radiation-light'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution(); assert dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert len(rows) == 2 and sum(row['additional_spell_points'] for row in rows) == 2
    assert rows[1]['effect_choice'] == 'nauseating bright light'
    assert 'Radiation Exposure:' in dialog.item_preview.toPlainText()
    assert dialog.quotation()[0] == 6
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert dialog.add_required_contributions() and dialog.table.rowCount() == 2
    assert repo._connection.total_changes == writes


def test_star_genesis_live_area_updates_and_mode_restores(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Light'); dialog.cl.setValue(10)
    key = 'light:advanced-talent:star-genesis'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution(); dialog.add_required_contributions()
    picker = dialog.table.cellWidget(0, 5); picker.setCurrentIndex(picker.findData('expanded radius'))
    assert 'Bright Light Radius: 105 ft.' in dialog.item_preview.toPlainText()
    assert 'Daylight Equivalent Radius:' not in dialog.item_preview.toPlainText()
    picker.setCurrentIndex(picker.findData('expanded radius with central daylight'))
    assert 'Daylight Equivalent Radius: 55 ft.' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(14)
    assert 'Bright Light Radius: 125 ft.' in dialog.item_preview.toPlainText()
    assert 'Daylight Equivalent Radius: 65 ft.' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); writes = repo._connection.total_changes
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert 'Bright Light Radius: 125 ft.' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == writes


def test_required_irradiance_mode_change_can_cancel_without_mutating_draft(composer, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Light'); dialog.cl.setValue(10)
    for key in ('light:advanced-talent:radiation-light', 'light:talent:irradiance-light'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    picker = dialog.table.cellWidget(1, 5); picker.setCurrentIndex(picker.findData('sicken glowing target'))
    dialog.table.cellWidget(1, 1).setValue(5); dialog.table.cellWidget(1, 4).setValue(3)
    original = dialog.blueprint(); writes = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    assert not dialog.add_required_contributions()
    assert dialog.blueprint() == original and repo._connection.total_changes == writes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    assert dialog.add_required_contributions()
    assert picker.currentData() == 'nauseating bright light'
    assert dialog.table.cellWidget(1, 1).value() == 5
    assert dialog.table.cellWidget(1, 4).value() == 1
    saved = dialog.blueprint()
    saved['contributions'][1]['effect_choice'] = 'sicken glowing target'
    dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'] == saved['contributions']
    assert repo._connection.total_changes == writes


def test_cancel_mode_after_accepting_optional_promotion_is_still_atomic(composer, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Light'); dialog.cl.setValue(10)
    for key in ('light:advanced-talent:radiation-light', 'light:talent:irradiance-light'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    choice = dialog.table.cellWidget(1, 5); choice.setCurrentIndex(choice.findData('sicken glowing target'))
    dialog.table.cellWidget(1, 2).setChecked(True)
    original = dialog.blueprint(); writes = repo._connection.total_changes
    replies = iter([QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No])
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: next(replies))
    assert not dialog.add_required_contributions()
    assert dialog.blueprint() == original
    assert repo._connection.total_changes == writes
    assert list(replies) == []


def test_mode_only_prerequisite_fix_is_available_from_visible_button(composer, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Light'); dialog.cl.setValue(10)
    for key in ('light:advanced-talent:radiation-light', 'light:talent:irradiance-light'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    picker = dialog.table.cellWidget(1, 5); picker.setCurrentIndex(picker.findData('sicken glowing target'))
    original = dialog.blueprint(); writes = repo._connection.total_changes
    assert dialog.add_prerequisites.isEnabled()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    dialog.add_prerequisites.click()
    assert dialog.blueprint() == original and dialog.add_prerequisites.isEnabled()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    dialog.add_prerequisites.click()
    assert picker.currentData() == 'nauseating bright light'
    assert not dialog.add_prerequisites.isEnabled()
    dialog.load_plan(original)
    assert dialog.blueprint()['contributions'] == original['contributions']
    assert dialog.add_prerequisites.isEnabled()
    assert repo._connection.total_changes == writes


def test_add_lens_effect_switches_base_prices_once_and_reopens(composer, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from app.content import magic_entry
    from app.services.crafting import CraftingService
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Light'); dialog.cl.setValue(10)
    entry = magic_entry('light:lens-talent:aiming-scope-lens')
    def choose(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', choose)
    dialog.choose_accessible_effects()
    assert dialog.base_power.currentData() == 'light:lens'
    assert dialog.quotation()[0] == 2
    assert 'Ranged Attack Competence Bonus: 2' in dialog.item_preview.toPlainText()
    assert 'Bright Light Radius:' not in dialog.item_preview.toPlainText()
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Scope', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    try:
        assert reopened.base_power.currentData() == 'light:lens'
        assert reopened.quotation()[0] == 2 and reopened.table.rowCount() == 1
    finally:
        reopened.close()


def test_astral_affixation_inserts_nested_talents_prices_three_total_sp_and_restores(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Telekinesis'); dialog.cl.setValue(15)
    key = 'telekinesis:advanced-talent:astral-affixation'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution(); assert dialog.add_required_contributions()
    rows = dialog.blueprint()['contributions']
    assert {row['catalog_key'] for row in rows} == {key, 'telekinesis:advanced-talent:affix',
        'telekinesis:advanced-talent:effortless-telekinesis', 'telekinesis:talent:idle-concentration'}
    assert len(rows) == 4 and sum(row['additional_spell_points'] for row in rows) == 3
    assert dialog.quotation()[0] == 11
    assert dialog.quotation()[1].market_price_gp == 66000
    saved = dialog.blueprint(); writes = repo._connection.total_changes
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved and dialog.table.rowCount() == 4
    assert repo._connection.total_changes == writes


def test_gravity_modes_update_prerequisite_keep_total_and_cancel_manual_sp_atomically(composer, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Telekinesis'); dialog.cl.setValue(15)
    key = 'telekinesis:advanced-talent:gravity-manipulation'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution(); dialog.add_required_contributions()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    picker = dialog.table.cellWidget(0, 5)
    for mode in ('concentration (2 SP total)', 'Sustained Force (2 SP total)'):
        picker.setCurrentIndex(picker.findData(mode))
        rows = dialog.blueprint()['contributions']
        assert sum(row['additional_spell_points'] for row in rows) == 2
        assert dialog.table.rowCount() == 2 and dialog.quotation()[0] == 6
    dialog.table.cellWidget(0, 4).setValue(7)
    original = dialog.blueprint(); writes = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    picker.setCurrentIndex(picker.findData('concentration (2 SP total)'))
    assert dialog.blueprint() == original
    dialog.load_plan(original)
    assert dialog.blueprint() == original
    assert repo._connection.total_changes == writes


def test_telekinesis_live_movement_and_size_update_and_restore_without_writes(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Telekinesis'); dialog.cl.setValue(5)
    writes = repo._connection.total_changes
    for suffix in ('powerful-telekinesis', 'greater-speed', 'flight'):
        key = 'telekinesis:talent:' + suffix
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    assert 'Maximum Lift Size: Medium' in dialog.item_preview.toPlainText()
    assert 'Granted Fly Speed: 40 ft. (perfect)' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(10)
    assert 'Maximum Lift Size: Large' in dialog.item_preview.toPlainText()
    assert 'Granted Fly Speed: 55 ft. (perfect)' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert 'Granted Fly Speed: 55 ft. (perfect)' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,cost', [('flash-of-excellence-sm', 1),
    ('power-parasitism-alienist-hb', 1), ('ranged-enhancement-range', 0)])
def test_enhancement_modifier_defaults_and_manual_overrides_survive_reopen(composer, suffix, cost):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement')
    key = 'enhancement:talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    saved = dialog.blueprint()
    assert saved['contributions'][0]['additional_spell_points'] == cost
    saved['contributions'][0]['additional_spell_points'] = 4
    saved['contributions'][0]['complexity'] = 5
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


def test_inherent_temporary_mode_preview_and_choices_survive_reopen(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(17)
    saved = dialog.blueprint()
    saved['contributions'] = [dict(catalog_key=key, complexity=1, additional_spell_points=0,
        alternative=False, alternative_group=1, effect_choice='') for key in (
        'enhancement:talent:deep-enhancement', 'enhancement:enhance-talent:mental-enhancement-enhance',
        'enhancement:enhance-talent:physical-enhancement-enhance')]
    saved['contributions'].append(dict(catalog_key='enhancement:advanced-talent:inherent-enhancement-enhance-archmagi-s-hb',
        complexity=3, additional_spell_points=1, alternative=False, alternative_group=1,
        effect_choice='temporary untyped bonus: Dexterity'))
    writes = repo._connection.total_changes
    dialog.load_plan(saved)
    assert 'Ability Untyped Bonus: 6' in dialog.item_preview.toPlainText()
    assert '25,000 gp' in dialog.item_preview.toPlainText()
    restored = dialog.blueprint(); dialog.load_plan(restored)
    assert dialog.blueprint() == restored
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('key', [
    'life:vitality-talent:aggressive-vitality-vitality',
    'life:vitality-talent:calming-vitality-vitality-warden',
    'life:vitality-talent:energizing-vitality-vitality',
    'life:vitality-talent:high-on-vitality-vitality-jester-s-hb',
    'life:vitality-talent:ruin-into-resurgence-vitality-3pp',
    'life:vitality-talent:securing-vitality-vitality-warden',
    'life:vitality-talent:sustaining-vitality-vitality',
])
def test_vitality_default_and_live_description_survive_reopen_without_writes(composer, key):
    from app.marvelous_base_powers import LIFE_VITALITY_EFFECTS
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5)
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    saved = dialog.blueprint()
    assert saved['contributions'][0]['additional_spell_points'] == 0
    assert LIFE_VITALITY_EFFECTS[key] in dialog.item_preview.toPlainText()
    assert 'Only one vitality benefit per target' in dialog.item_preview.toPlainText()
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert LIFE_VITALITY_EFFECTS[key] in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,low,high', [
    ('adrenaline-surge', 'surge one ally', 'surge multiple allies'),
    ('taste-of-victory', 'critical hit, unconscious or zero-HP target', 'ordinary qualifying hit'),
    ('diagnose-utility', 'condition details as standard action', 'condition details as swift action'),
])
def test_conditional_life_mode_updates_price_and_preserves_saved_choice(composer, suffix, low, high):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(10)
    key = 'life:talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    mode = dialog.table.cellWidget(0, 5)
    mode.setCurrentIndex(mode.findData(low))
    before = quote_marvelous_blueprint(dialog.blueprint())[1].market_price_gp
    mode.setCurrentIndex(mode.findData(high))
    saved = dialog.blueprint()
    assert quote_marvelous_blueprint(saved)[1].market_price_gp - before == 4000
    assert saved['contributions'][0]['effect_choice'] == high
    assert high in dialog.cost_formula.toolTip()
    assert 'extra SP' in dialog.cost_formula.toolTip()
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


def test_revitalize_live_preview_replaces_direct_healing_and_preserves_reopen(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('life:cure'))
    key = 'life:talent:revitalize'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    assert 'Fast Healing: 1' in dialog.item_preview.toPlainText()
    assert 'Duration 10 minutes' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint()
    assert saved['contributions'][0]['additional_spell_points'] == 0
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert 'Fast Healing: 1' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix', ['improved-haste', 'improved-slow', 'instill-time-instill',
    'lingering-time-3pp', 'ranged-time-range', 'time-strike-strike', 'time-zone'])
def test_free_time_modifier_defaults_preserve_manual_saved_costs(composer, suffix):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Time'); dialog.cl.setValue(10)
    key = 'time:talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    saved = dialog.blueprint()
    assert saved['contributions'][0]['additional_spell_points'] == 0
    saved['contributions'][0].update(complexity=4, additional_spell_points=2)
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,cost', [('talent:larger-creation', 1),
    ('talent:divided-creation-mass', 0), ('material-talent:expanded-materials-material', 0),
    ('alter-talent:change-material-alter', 1), ('material-talent:acidic-creation-material', 1)])
def test_creation_cost_defaults_update_and_preserve_manual_overrides(composer, suffix, cost):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    key = 'creation:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    saved = dialog.blueprint()
    assert saved['contributions'][0]['additional_spell_points'] == cost
    saved['contributions'][0].update(complexity=5, additional_spell_points=3)
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


def test_creation_capacity_preview_updates_with_level_without_inventory_writes(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('creation:create'))
    key = 'creation:talent:larger-creation'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    assert 'Creation Capacity Small Objects: 20' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(16)
    assert 'Creation Capacity Small Objects: 32' in dialog.item_preview.toPlainText()
    assert 'Maximum Object Size: Colossal' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


def test_transparency_duration_controls_follow_selected_mode_and_reopen(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('creation:alter'))
    key = 'creation:alter-talent:transparency-alter-utility'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    mode = dialog.table.cellWidget(0, 5)
    mode.setCurrentIndex(mode.findData('concentration'))
    assert 'Duration Concentration' in dialog.item_preview.toPlainText()
    mode.setCurrentIndex(mode.findData('minutes per caster level'))
    assert 'Duration 10 minutes' in dialog.item_preview.toPlainText()
    assert 'Larger Object Area Square Feet: 20' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


def test_instill_minimum_live_formula_avoids_double_charge_and_reopens(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('creation:alter'))
    writes = repo._connection.total_changes
    for key in ('creation:talent:instill-alteration-instill', 'creation:alter-talent:forge-alter'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
        if key.endswith('instill'):
            assert '1 instill minimum SP' in dialog.cost_formula.text()
    assert 'instill minimum SP' not in dialog.cost_formula.text()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


def test_instill_alternative_group_shows_discounted_minimum_adjustment(composer):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('creation:alter'))
    saved = dialog.blueprint()
    saved['contributions'] = [
        dict(catalog_key='creation:talent:instill-alteration-instill', complexity=1, additional_spell_points=0,
            alternative=False, alternative_group=1),
        dict(catalog_key='creation:alter-talent:magnify-minimize-alter', complexity=1, additional_spell_points=0,
            alternative=True, alternative_group=1, effect_choice='one size category'),
        dict(catalog_key='creation:alter-talent:forge-alter', complexity=2, additional_spell_points=1,
            alternative=True, alternative_group=1)]
    writes = repo._connection.total_changes
    dialog.load_plan(saved)
    assert quote_marvelous_blueprint(dialog.blueprint())[0] == 5
    assert '1/2 instill minimum SP' in dialog.cost_formula.text()
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


def test_alchemical_preview_updates_value_and_flags_published_cl14_conflict(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('creation:create'))
    key = 'creation:material-talent:alchemical-creation-material'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    assert dialog.blueprint()['contributions'][0]['additional_spell_points'] == 0
    assert 'Maximum Alchemical Value Gp: 750' in dialog.item_preview.toPlainText()
    dialog.cl.setValue(14)
    assert 'Needs rules verification' in dialog.item_preview.toPlainText()
    assert 'Maximum Alchemical Value Gp:' not in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


def test_practiced_creation_live_discount_and_concentration_survive_reopen(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('creation:create'))
    dialog.activation.setCurrentIndex(dialog.activation.findData('full-round'))
    writes = repo._connection.total_changes
    for key in ('creation:talent:practiced-creation', 'creation:talent:larger-creation'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    assert 'Duration Concentration' in dialog.item_preview.toPlainText()
    assert '− 1 Practiced extra-SP reduction' in dialog.cost_formula.text()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


@pytest.mark.parametrize('mode,total_sp', [('unattended non-magical object', 1),
    ('attended, magical or creature target', 3)])
def test_dissolution_mode_automatically_integrates_correct_potent_cost(composer, mode, total_sp):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    dialog.base_power.setCurrentIndex(dialog.base_power.findData('creation:alter'))
    key = 'creation:advanced-talent:dissolution-alter'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    choice = dialog.table.cellWidget(0,5)
    choice.setCurrentIndex(choice.findData(mode))
    saved = dialog.blueprint()
    assert sum(row['additional_spell_points'] for row in saved['contributions']) == total_sp
    assert sum(row['catalog_key'] == 'creation:talent:potent-alteration' for row in saved['contributions']) == 1
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,required', [
    ('create-materials', {'creation:talent:lengthened-creation'}),
    ('create-minds-think-alike-jester-s-hb', {'creation:talent:exquisite-detail-utility',
        'enhancement:enhance-talent:bestow-intelligence-enhance'}),
    ('permanent-change', {'creation:alter-talent:change-material-alter',
        'creation:material-talent:expanded-materials-material', 'creation:alter-talent:forge-alter'}),
])
def test_creation_required_talents_insert_once_and_survive_reopen(composer, suffix, required):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(15)
    key = 'creation:advanced-talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    assert dialog.add_required_contributions()
    saved = dialog.blueprint()
    keys = [row['catalog_key'] for row in saved['contributions']]
    assert set(keys) == required | {key} and len(keys) == len(set(keys))
    assert dialog.add_required_contributions()
    assert dialog.blueprint() == saved
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


def test_costly_creation_choice_inserts_complete_path_or_cancels_without_mutation(composer, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(20)
    key = 'creation:advanced-talent:costly-creation'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    original = dialog.blueprint(); writes = repo._connection.total_changes
    assert original['contributions'][0]['additional_spell_points'] == 5
    assert original['contributions'][0]['complexity'] == 7
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args, **kwargs: ('', False))
    assert not dialog.add_required_contributions()
    assert dialog.blueprint() == original
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args, **kwargs: (next(label for label in args[3] if label == 'Permanent Change'), True))
    assert dialog.add_required_contributions()
    saved = dialog.blueprint()
    assert {'creation:advanced-talent:permanent-change', 'creation:alter-talent:forge-alter',
        'creation:alter-talent:change-material-alter', 'creation:material-talent:expanded-materials-material',
        'creation:talent:lengthened-creation'} <= {row['catalog_key'] for row in saved['contributions']}
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,points', [('fabricate', 1), ('state-shift-alter', 0),
    ('internal-creation-apoc', 0), ('imperfect-recreation-alienist-hb', 0), ('integrate-item-alter-sm', 0)])
def test_advanced_creation_defaults_do_not_replace_manual_costs_on_reopen(composer, suffix, points):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(20)
    key = 'creation:advanced-talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    saved = dialog.blueprint()
    assert saved['contributions'][0]['additional_spell_points'] == points
    saved['contributions'][0].update(complexity=6, additional_spell_points=4)
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved and repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,free,paid', [
    ('advanced-talent:fleshcraft-material', 'create or alter nonliving flesh', 'alter a living creature'),
    ('talent:altering-burst', 'ten-foot radius, half-size objects', 'twenty-foot radius, normal-size objects'),
    ('talent:restrictive-casing', 'non-harmful worn object', 'full-body confinement cage'),
    ('material-talent:plasma-production-material', 'fire or burning object', 'electricity'),
    ('talent:precise-destruction-utility', 'mundane device or lock', 'magical trap'),
    ('alter-talent:magnify-minimize-alter', 'one size category', 'additional size categories'),
    ('alter-talent:transparency-alter-utility', 'concentration', 'minutes per caster level'),
    ('talent:mass-liquid-generation', 'five cubic feet per Small object', '125 cubic feet of non-harmful liquid per Small object'),
    ('talent:potent-alteration', 'enhanced repair or destroy', 'affect magical, attended or construct target'),
])
def test_creation_mode_changes_update_quote_and_keep_saved_choice(composer, suffix, free, paid):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Creation'); dialog.cl.setValue(10)
    key = 'creation:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    mode = dialog.table.cellWidget(0, 5)
    mode.setCurrentIndex(mode.findData(free))
    before = quote_marvelous_blueprint(dialog.blueprint())[1].market_price_gp
    mode.setCurrentIndex(mode.findData(paid))
    saved = dialog.blueprint()
    expected = 8000 if suffix == 'talent:precise-destruction-utility' else 4000
    assert quote_marvelous_blueprint(saved)[1].market_price_gp - before == expected
    if suffix == 'talent:precise-destruction-utility':
        assert sum(row['catalog_key'] == 'creation:talent:potent-alteration' for row in saved['contributions']) == 1
    assert paid in dialog.cost_formula.toolTip()
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('suffix,low,high', [
    ('age-time', 'creature age with concentration', 'creature age for minutes per caster level'),
    ('broken-time-time', 'concentration', 'rounds per caster level'),
    ('rapid-response-time', 'concentration', 'ten minutes per caster level'),
])
def test_time_concentration_mode_costs_update_without_rewriting_saved_inputs(composer, suffix, low, high):
    from app.marvelous_item_rules import quote_marvelous_blueprint
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Time'); dialog.cl.setValue(10)
    key = 'time:talent:' + suffix
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    mode = dialog.table.cellWidget(0, 5)
    mode.setCurrentIndex(mode.findData(low))
    before = quote_marvelous_blueprint(dialog.blueprint())[1].market_price_gp
    mode.setCurrentIndex(mode.findData(high))
    saved = dialog.blueprint()
    assert quote_marvelous_blueprint(saved)[1].market_price_gp - before == 4000
    assert high in dialog.cost_formula.toolTip()
    dialog.load_plan(saved)
    assert dialog.blueprint() == saved
    assert repo._connection.total_changes == writes


def test_cancel_alternative_energy_promotion_preserves_choice_and_manual_cost(composer, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app.marvelous_base_powers import ENERGY_ENHANCEMENT_KEY, ALTERNATIVE_ENERGY_KEY
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(10)
    for key in (ENERGY_ENHANCEMENT_KEY, ALTERNATIVE_ENERGY_KEY):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    picker = dialog.table.cellWidget(0, 5); picker.setCurrentIndex(picker.findData('weapon: fire'))
    dialog.table.cellWidget(0, 4).setValue(3); dialog.table.cellWidget(1, 2).setChecked(True)
    before = dialog.blueprint(); writes = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    picker.setCurrentIndex(picker.findData('weapon: force'))
    assert dialog.blueprint() == before
    assert repo._connection.total_changes == writes


def test_cancel_dual_promotion_restores_previous_ability_choice(composer, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(6)
    for key in ('enhancement:enhance-talent:physical-enhancement-enhance', 'enhancement:talent:dual-enhancement'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    picker = dialog.table.cellWidget(0, 5)
    picker.setCurrentIndex(picker.findData('Dexterity'))
    dialog.table.cellWidget(1, 2).setChecked(True)
    before = dialog.blueprint(); writes = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    picker.setCurrentIndex(picker.findData('Strength + Dexterity'))
    assert dialog.blueprint() == before
    assert repo._connection.total_changes == writes


@pytest.mark.parametrize('kind,choice', [('physical', 'Dexterity'), ('mental', 'Wisdom')])
def test_ability_enhancement_choice_updates_live_and_restores(composer, kind, choice):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(6)
    key = f'enhancement:enhance-talent:{kind}-enhancement-enhance'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    writes = repo._connection.total_changes
    dialog.add_contribution()
    picker = dialog.table.cellWidget(0, 5)
    picker.setCurrentIndex(picker.findData(choice))
    text = dialog.item_preview.toPlainText()
    assert f'Ability Score: {choice}' in text and 'Ability Enhancement Bonus: 2' in text
    assert 'Equipment Enhancement Bonus:' not in text
    dialog.cl.setValue(7)
    assert 'Ability Enhancement Bonus: 4' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and dialog.table.cellWidget(0, 5).currentData() == choice
    assert repo._connection.total_changes == writes


def test_enhance_equipment_preview_updates_bonus_and_restores(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Enhancement'); dialog.cl.setValue(4)
    assert 'Equipment Enhancement Bonus: 2' in dialog.item_preview.toPlainText()
    for key in ('enhancement:talent:greater-enhance-equipment', 'enhancement:talent:mass-enhancement-mass'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    dialog.cl.setValue(20)
    text = dialog.item_preview.toPlainText()
    assert 'Equipment Enhancement Bonus: 6' in text and 'Maximum Targets: 11' in text
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and 'Equipment Enhancement Bonus: 6' in dialog.item_preview.toPlainText()


def test_weather_severity_numbers_update_live_with_item_level(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Weather'); dialog.cl.setValue(10)
    for key in ('weather:talent:severe-weather', 'weather:advanced-talent:cold-lord'):
        dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
        dialog.add_contribution()
    text = dialog.item_preview.toPlainText()
    assert 'Maximum Severity: 5' in text and 'Cold Severity Limit: 6' in text
    dialog.cl.setValue(21)
    text = dialog.item_preview.toPlainText()
    assert 'Cold Severity Limit: 7' in text and 'Cold Excess Severity Bonus: 1' in text
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and 'Cold Excess Severity Bonus: 1' in dialog.item_preview.toPlainText()


def test_climate_add_effects_projects_area_and_required_talent(composer, monkeypatch):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.content import magic_entry
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Weather'); dialog.cl.setValue(10)
    entry = magic_entry('weather:advanced-talent:climate')
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def accept(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', accept)
    dialog.choose_accessible_effects()
    assert dialog.table.rowCount() == 2
    assert '2 miles' in dialog.item_preview.toPlainText() and '20 minutes' in dialog.item_preview.toPlainText()
    assert dialog.quotation()[1].market_price_gp == 20000
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint() == saved and '2 miles' in dialog.item_preview.toPlainText()


def test_greater_invigorate_optional_cost_updates_and_reopens(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(10)
    key = 'life:talent:greater-invigorate'
    dialog.talent.setCurrentIndex(next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key))
    dialog.add_contribution()
    choice = dialog.table.cellWidget(0, 5)
    choice.setCurrentIndex(choice.findData('normal HP limit'))
    initial = dialog.quotation()[1].market_price_gp
    choice.setCurrentIndex(choice.findData('exceed normal HP limit'))
    assert dialog.blueprint()['contributions'][0]['additional_spell_points'] == 1
    assert dialog.quotation()[1].market_price_gp > initial
    assert 'exceed normal HP limit' in dialog.item_preview.toPlainText()
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.blueprint()['contributions'] == saved['contributions']


def test_chain_blast_preview_tracks_item_caster_level(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Destruction'); dialog.cl.setValue(6)
    dialog.description.setPlainText('A branching bolt.')
    for key in ('destruction:blast-type-talent:force-blast-blast-type-force',
                'destruction:blast-shape-talent:chain-blast-blast-shape'):
        index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
        dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    text = dialog.item_preview.toPlainText()
    assert 'A branching bolt.' in text and 'Maximum Targets: 4' in text and '3d6 force' in text
    assert dialog.quotation()[0] == 5
    dialog.cl.setValue(10)
    assert 'Maximum Targets: 6' in dialog.item_preview.toPlainText()
    assert 'Maximum Jump Distance: 20 ft.' in dialog.item_preview.toPlainText()


def test_accessible_effect_picker_reuses_basket_without_learning_rules(composer):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.catalogs import DEFAULT_CATALOG
    dialog, repo, cid = composer
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if e['key'] == 'life:talent:painkiller')
    picker = MarvelousEffectPicker([entry], dialog)
    assert picker._entries == (entry,)
    assert picker._entry_selectable(entry)
    assert picker.selected_entries == ()
    assert not picker.results.selectedItems()
    assert not picker.selection_basket.entries
    picker.reject()
    picker.close()


def test_effect_picker_confirmation_updates_design_without_database_writes(composer, monkeypatch):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from PySide6.QtWidgets import QDialog
    from app.catalogs import DEFAULT_CATALOG
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5)
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if e['key'] == 'life:talent:painkiller')
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def accept(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', accept)
    before = repo._connection.total_changes
    dialog.choose_accessible_effects()
    assert dialog.blueprint()['contributions'][0]['catalog_key'] == entry['key']
    assert dialog.quotation()[1].market_price_gp == 4000
    dialog.choose_accessible_effects()
    assert dialog.table.rowCount() == 1
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', lambda picker: QDialog.DialogCode.Rejected)
    dialog.choose_accessible_effects()
    assert dialog.table.rowCount() == 1 and repo._connection.total_changes == before


@pytest.mark.parametrize('key,unique,price,label', [
    ('crafting:diviner-s-sight', 0, 1800, 'Cheap'),
    ('crafting:evil-artifice', 2, 4000, 'Simple boon'),
    ('crafting:sacred-artifice', 2, 4000, 'Simple boon'),
])
def test_design_tradition_updates_price_without_character_selection(composer, monkeypatch, key, unique, price, label):
    from app.ui.optional_traditions import OptionalTraditionDialog
    from app.optional_traditions import catalog
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    dialog.cl.setValue(5)
    dialog.unique.setValue(unique)
    entry = next(e for e in catalog()['entries'] if e['key'] == key)
    def choose(picker):
        picker.selected_entry = entry
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(OptionalTraditionDialog, 'exec', choose)
    before = repo._connection.total_changes
    dialog.choose_crafting_tradition()
    assert dialog.quotation()[1].market_price_gp == price
    assert dialog.quotation()[2].cost_gp == price / 2
    assert label in dialog.cost_formula.text()
    assert dialog.tradition_button.text() == entry['name']
    assert not repo.list_character_traditions(cid)
    assert repo._connection.total_changes == before
    from app.services.crafting import CraftingService
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Cheap design', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.crafting_tradition['key'] == entry['key']
    assert reopened.crafting_tradition['description'] == entry['description']
    assert reopened.quotation()[1].market_price_gp == price
    reopened.close()
    dialog.remove_crafting_tradition()
    assert dialog.quotation()[1].market_price_gp == 2000 * (1 + unique)


@pytest.mark.parametrize('arcforge', [False, True])
def test_antimagic_picker_selects_ward_and_prices_integrated_prerequisite(composer, monkeypatch, arcforge):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.content import magic_entry
    from PySide6.QtWidgets import QDialog, QInputDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(10)
    entry = magic_entry('protection:advanced-talent:antimagic-aura' + ('-arcforge-addendum-lg' if arcforge else ''))
    if arcforge:
        monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: (args[3][-1], True))
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def accept(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', accept)
    before = repo._connection.total_changes
    dialog.choose_accessible_effects()
    assert dialog.base_power.currentData() == 'protection:ward'
    assert dialog.quotation()[0] == 6
    assert ('Antimagic Aura technological ward' if arcforge else 'Antimagic Aura ward') in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == before
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.base_power.currentData() == 'protection:ward'
    assert dialog.quotation()[0] == 6


def test_add_effects_cancelled_prerequisite_restores_entire_draft(composer, monkeypatch):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.content import magic_entry
    from PySide6.QtWidgets import QDialog, QInputDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(10)
    dialog.name.setText('Existing design')
    dialog.description.setPlainText('Keep my description.')
    entry = magic_entry('protection:advanced-talent:antimagic-aura-arcforge-addendum-lg')
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def accept(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', accept)
    monkeypatch.setattr(QInputDialog, 'getItem', lambda *args: ('', False))
    before = dialog.blueprint()
    price = dialog.quotation()[1].market_price_gp
    writes = repo._connection.total_changes
    dialog.choose_accessible_effects()
    assert dialog.blueprint() == before
    assert dialog.quotation()[1].market_price_gp == price
    assert dialog.name.text() == 'Existing design'
    assert dialog.description.toPlainText() == 'Keep my description.'
    assert repo._connection.total_changes == writes


def test_selectivity_sphere_dialog_cancel_save_reopen_and_live_preview(composer, monkeypatch):
    from PySide6.QtWidgets import QDialog, QListWidget
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(10)
    key = 'protection:advanced-talent:spell-selectivity-dbh'
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution(); dialog.add_required_contributions()
    dialog.table.selectRow(0)
    mode = dialog.table.cellWidget(0, 5); mode.setCurrentIndex(mode.findData('only'))
    assert dialog.effect_options.isEnabled()
    assert not dialog.effect_options.isHidden()
    dialog.table.selectRow(1)
    assert dialog.effect_options.isHidden()
    dialog.table.selectRow(0)
    assert not dialog.effect_options.isHidden()
    before = repo._connection.total_changes
    monkeypatch.setattr(QDialog, 'exec', lambda child: QDialog.DialogCode.Rejected)
    dialog.choose_selectivity_spheres()
    assert 'effect_spheres' not in dialog.blueprint()['contributions'][0]
    def choose(child):
        picker = child.findChild(QListWidget, 'selectivitySpheres')
        for i in range(picker.count()):
            picker.item(i).setSelected(picker.item(i).text() in {'Life', 'Warp'})
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', choose)
    dialog.choose_selectivity_spheres()
    assert 'Affects only Life, Warp' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == before
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Selective device', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.blueprint()['contributions'][0]['effect_spheres'] == ['Life', 'Warp']
    assert 'Affects only Life, Warp' in reopened.item_preview.toPlainText()
    reopened.close()
    invalid = dialog.blueprint(); invalid['contributions'][0]['effect_spheres'] = ['Unknown sphere']
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='unknown magic sphere'):
        CraftingService(repo, cid).save_marvelous_design(invalid, name='Invalid', slot='', description='')
    assert repo._connection.total_changes == before
    dialog.cl.setValue(4)
    assert 'exceed the limit' in dialog.cost_formula.text()
    assert not dialog.save.isEnabled()
    dialog.cl.setValue(10)
    assert 'Affects only Life, Warp' in dialog.item_preview.toPlainText()


def test_custom_drawback_live_price_card_save_reopen_and_remove(composer):
    from app.services.crafting import CraftingService
    from app.marvelous_base_powers import automatic_self_effect
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5); dialog.unique.setValue(2)
    dialog.drawbacks = [dict(source='custom', name='At dawn', description='Sunrise only', reduction=1)]
    dialog.update_preview()
    assert dialog.quotation()[1].market_price_gp == 4000
    assert 'At dawn' in dialog.card_edits['description'].toPlainText()
    assert '− 1 drawbacks' in dialog.cost_formula.text()
    assert automatic_self_effect(dialog.blueprint()) is None
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Limited design', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.drawbacks == dialog.drawbacks
    reopened.drawbacks_list.setCurrentRow(0); reopened.remove_drawback()
    assert reopened.drawbacks == [] and reopened.quotation()[1].market_price_gp == 6000
    reopened.close()


def test_published_drawback_selection_is_draft_only_and_deduplicated(composer, monkeypatch):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.catalogs import DEFAULT_CATALOG
    from PySide6.QtWidgets import QDialog
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5); dialog.unique.setValue(2)
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if 'drawback' in e['category'].casefold())
    def accept(picker):
        assert entry['key'] in picker._entries_by_key
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', accept)
    before = repo._connection.total_changes
    dialog.choose_drawbacks(); dialog.choose_drawbacks()
    assert len(dialog.drawbacks) == 1 and dialog.drawbacks[0]['source'] == 'published'
    assert repo._connection.total_changes == before
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Published limitation', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.drawbacks[0]['catalog_key'] == entry['key']
    reopened.close()


def test_beacon_default_sp_is_included_once_and_saved_values_restore(composer):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(5)
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == 'warp:space-talent:teleport-beacon-space')
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    assert dialog.table.cellWidget(0, 4).value() == 1
    assert dialog.blueprint()['contributions'][0]['complexity'] == 2
    assert dialog.quotation()[1].market_price_gp == 6000
    assert '+ 1 talents + 1 extra SP' in dialog.cost_formula.text()
    assert 'Teleport Beacon' in dialog.card_edits['description'].toPlainText()
    plan = dialog.blueprint(); dialog.load_plan(plan)
    assert dialog.blueprint()['contributions'] == plan['contributions']


def test_choosing_advanced_warp_effect_adds_required_chain(composer, monkeypatch):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.content import magic_entry
    from app.marvelous_item_rules import missing_construction_prerequisites
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(15)
    entry = magic_entry('warp:advanced-talent:portal-network-dbh')
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def choose(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', choose)
    before = repo._connection.total_changes
    dialog.choose_accessible_effects()
    records = dialog.blueprint()['contributions']
    assert len(records) > 1 and not missing_construction_prerequisites(records)
    assert any(row['catalog_key'] == 'warp:space-talent:teleport-beacon-space' and row['additional_spell_points'] == 1 for row in records)
    assert repo._connection.total_changes == before


@pytest.mark.parametrize('theme', ['classic', 'dark'])
@pytest.mark.parametrize('invalid', [False, True])
def test_designer_compact_layout_keeps_card_and_formula_in_window(composer, theme, invalid):
    from app.ui.dialog_theme import dialog_stylesheet
    from PySide6.QtCore import QPoint
    dialog, repo, cid = composer
    dialog.setStyleSheet(dialog_stylesheet(theme))
    if invalid: dialog.unique.setValue(100)
    dialog.resize(1100, 720); dialog.show(); QApplication.instance().processEvents()
    dialog.card_editor_toggle.click(); QApplication.instance().processEvents()
    dialog.card_editor_scroll.ensureWidgetVisible(dialog.card_locks['price'])
    QApplication.instance().processEvents()
    for widget in (dialog.cost_formula, dialog.card_locks['price'], dialog.drawbacks_button, dialog.save):
        corner = widget.mapTo(dialog, QPoint(widget.width() - 1, widget.height() - 1))
        assert dialog.rect().contains(corner)
    assert not dialog.settings_panel.isVisible()
    dialog.settings_toggle.click(); QApplication.instance().processEvents()
    assert dialog.settings_panel.isVisible()
    assert dialog.controls_scroll.verticalScrollBar().maximum() > 0
    corner = dialog.cost_formula.mapTo(dialog, QPoint(dialog.cost_formula.width() - 1, dialog.cost_formula.height() - 1))
    assert dialog.rect().contains(corner)
    dialog.hide()


def test_invalid_design_clears_stale_item_preview(composer):
    dialog, repo, cid = composer
    assert 'Custom Marvelous Item' in dialog.item_preview.toPlainText()
    dialog.unique.setValue(10)
    assert 'valid design' in dialog.item_preview.toPlainText()
    assert 'invalid design' in dialog.cost_formula.text()
    dialog.unique.setValue(0)
    assert 'Custom Marvelous Item' in dialog.item_preview.toPlainText()


def test_drawback_editor_updates_reduction_preserves_locks_and_cancel(composer, monkeypatch):
    from PySide6.QtWidgets import QDialog, QSpinBox, QLineEdit
    dialog, repo, cid = composer
    dialog.cl.setValue(5); dialog.unique.setValue(2)
    dialog.drawbacks = [dict(source='custom', name='Dawn', description='At sunrise', reduction=1)]
    dialog.update_preview(); dialog.drawbacks_list.setCurrentRow(0)
    dialog.card_locks['price'].setChecked(True); dialog.card_edits['price'].setText('Fixed display')
    before = repo._connection.total_changes
    def accept(editor):
        editor.findChild(QSpinBox).setValue(2)
        editor.findChild(QLineEdit).setText('Dawn only')
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', accept)
    dialog.edit_selected_drawback()
    assert dialog.drawbacks[0]['name'] == 'Dawn only' and dialog.drawbacks[0]['reduction'] == 2
    assert dialog.quotation()[1].market_price_gp == 2000
    assert dialog.card_edits['price'].text() == 'Fixed display'
    assert 'Dawn only' in dialog.item_preview.toPlainText()
    assert dialog.drawbacks_list.currentRow() == 0
    monkeypatch.setattr(QDialog, 'exec', lambda editor: QDialog.DialogCode.Rejected)
    previous = dialog.blueprint()
    dialog.edit_selected_drawback()
    assert dialog.blueprint() == previous and repo._connection.total_changes == before


def test_published_drawback_editor_preserves_catalog_text(composer, monkeypatch):
    from PySide6.QtWidgets import QDialog, QSpinBox, QLineEdit, QTextEdit
    from app.catalogs import DEFAULT_CATALOG
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5); dialog.unique.setValue(2)
    entry = next(e for e in DEFAULT_CATALOG.magic_entries('Life') if 'drawback' in e['category'].casefold())
    dialog.drawbacks = [dict(source='published', catalog_key=entry['key'], name=entry['name'], description=entry['description'], reduction=1)]
    dialog.update_preview(); dialog.drawbacks_list.setCurrentRow(0)
    def accept(editor):
        assert editor.findChild(QLineEdit).isReadOnly() and editor.findChild(QTextEdit).isReadOnly()
        editor.findChild(QSpinBox).setValue(0)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog, 'exec', accept)
    dialog.edit_selected_drawback()
    assert dialog.drawbacks[0]['catalog_key'] == entry['key']
    assert dialog.drawbacks[0]['description'] == entry['description']
    assert dialog.drawbacks[0]['reduction'] == 0
    assert dialog.quotation()[1].market_price_gp == 6000


def test_beacon_power_automatically_includes_talent_and_reopens_without_duplicates(composer, monkeypatch):
    from app.services.crafting import CraftingService
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.content import magic_entry
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(5)
    entry = magic_entry('warp:space-talent:teleport-beacon-space')
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def choose(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', choose)
    dialog.choose_accessible_effects()
    assert dialog.table.rowCount() == 1
    assert dialog.quotation()[1].market_price_gp == 6000
    assert dialog.card_edits['range'].text() == 'Touch'
    assert dialog.card_edits['duration'].text() == '5 hours'
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Beacon placer', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.base_power.currentData() == 'warp:beacon'
    assert reopened.table.rowCount() == 1
    assert reopened.quotation()[1].market_price_gp == 6000
    reopened.close()


@pytest.mark.parametrize('sphere,key,points', [
    ('Warp', 'true-teleport', 2), ('Warp', 'planeshift', 2), ('Warp', 'portal', 1), ('Warp', 'enduring-portal', 1),
    ('Weather', 'cacophonic-clap', 1), ('Weather', 'climate', 1), ('Weather', 'climatic-shift', 3),
    ('Weather', 'dehydration-pulse', 2), ('Weather', 'radiation-lord-cata-hb', 2),
    ('Weather', 'rain-bomb', 1), ('Weather', 'volcano-lord', 2), ('Weather', 'boiling-lord', 0),
    ('Enhancement', 'antimagic-aegis', 1), ('Enhancement', 'ascetic-control', 2),
    ('Enhancement', 'bestow-life', 1), ('Enhancement', 'heart-of-hope-and-fear-sm', 1),
    ('Enhancement', 'referential-enhancements', 2), ('Enhancement', 'critical-climax-3pp', 0),
])
def test_advanced_effect_sp_defaults_update_price_and_restore(composer, sphere, key, points):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText(sphere); dialog.cl.setValue(20)
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == sphere.lower() + ':advanced-talent:' + key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    assert dialog.table.cellWidget(0, 4).value() == points
    assert dialog.quotation()[1].market_price_gp == 400 * 20 * (1 + 2 + points)
    plan = dialog.blueprint(); dialog.load_plan(plan)
    assert dialog.blueprint()['contributions'] == plan['contributions']
    # Existing explicit/saved adjustments are not silently overwritten by new defaults.
    plan['contributions'][0]['additional_spell_points'] = 0
    plan['contributions'][0]['complexity'] = 2
    dialog.load_plan(plan)
    assert dialog.table.cellWidget(0, 4).value() == 0


def test_crafting_drawbacks_are_available_and_expensive_updates_materials(composer, monkeypatch):
    from app.optional_traditions import crafting_drawbacks
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from PySide6.QtWidgets import QDialog
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5)
    entries = crafting_drawbacks()
    assert entries and all(entry['key'] not in {'crafting:drawbacks', 'crafting:general-drawbacks'} for entry in entries)
    entry = next(entry for entry in entries if entry['key'] == 'crafting:expensive')
    def choose(picker):
        assert 'crafting:expensive' in picker._entries_by_key
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', choose)
    dialog.choose_drawbacks()
    assert dialog.drawbacks[0]['reduction'] == 0
    assert dialog.quotation()[1].market_price_gp == 2000 and dialog.quotation()[2].cost_gp == 1250
    assert dialog.card_edits['construction_cost'].text() == '1,250.00 gp'
    assert '× 1.25 (Expensive) = 1250 gp' in dialog.cost_formula.text()
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Expensive design', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.drawbacks[0]['description'] == entry['description']
    assert reopened.quotation()[2].cost_gp == 1250
    reopened.close()


@pytest.mark.parametrize('simple', [False, True])
def test_additional_power_custom_text_preview_cl_and_reopen(composer, monkeypatch, simple):
    from PySide6.QtWidgets import QDialog
    from app.services.crafting import CraftingService
    from copy import deepcopy
    dialog, repo, cid = composer
    dialog.cl.setValue(5)
    if simple:
        from app.optional_traditions import catalog
        dialog.crafting_tradition = next(e for e in catalog()['entries'] if e['key'] == 'crafting:sacred-artifice')
    def choose(child):
        child.sphere.setCurrentText('Life')
        child.base_power.setCurrentIndex(child.base_power.findData('life:cure'))
        child.name.setText('Reserve cure'); child.description.setPlainText('A reserve of healing.')
        child.uses.setCurrentIndex(child.uses.findData(50))
        if simple:
            child.unique.setValue(2)
            assert child.quotation()[0] == 2
            assert 'Simple boon' in child.cost_formula.text()
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousCraftingDialog, 'exec', choose)
    before = repo._connection.total_changes
    dialog.edit_extra_effect()
    assert 'Reserve cure' in dialog.item_preview.toPlainText()
    assert '50 total activations' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == before
    saved = deepcopy(dialog.extra_effects)
    assert 'crafting_tradition' not in saved[0]
    def cancel(child):
        assert child.name.text() == 'Reserve cure'
        assert child.description.toPlainText() == 'A reserve of healing.'
        return QDialog.DialogCode.Rejected
    monkeypatch.setattr(MarvelousCraftingDialog, 'exec', cancel)
    dialog.edit_extra_effect(0)
    assert dialog.extra_effects == saved
    dialog.cl.setValue(6)
    assert dialog.extra_effects[0]['caster_level'] == 6
    assert dialog.extra_effects[0]['effect_id'] == saved[0]['effect_id']
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Dual item', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.extra_effects[0]['effect_description'] == 'A reserve of healing.'
    assert 'Reserve cure' in reopened.item_preview.toPlainText()
    reopened.close()


def test_load_does_not_silently_normalize_mismatched_power_levels(composer):
    dialog, repo, cid = composer
    plan = dialog.blueprint()
    plan['caster_level'] = 5
    plan['extra_effects'] = [dict(plan, caster_level=4)]
    dialog.load_plan(plan)
    assert dialog.extra_effects[0]['caster_level'] == 4
    assert 'same caster level' in dialog.result.text()


def test_invalid_additional_power_text_or_lock_performs_no_writes(composer):
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    base = dialog.blueprint()
    for field, value in (('effect_name', 123), ('display_overrides', {'price': {'locked': 'yes', 'value': 'free'}})):
        plan = dict(base, extra_effects=[dict(base, **{field: value})])
        before = repo._connection.total_changes
        with pytest.raises(ValueError):
            CraftingService(repo, cid).save_marvelous_design(plan, name='Invalid', slot='', description='')
        assert repo._connection.total_changes == before


def test_live_price_and_cancel_no_writes(composer):
    dialog, repo, cid = composer
    before = repo._connection.total_changes
    dialog.cl.setValue(5)
    dialog.range_steps.setValue(1)
    assert dialog.quotation()[1].market_price_gp == 4000
    assert '400 gp × 5 (CL) × 2 (complexity)' in dialog.cost_formula.text()
    assert '4000 gp' in dialog.cost_formula.text()
    dialog.uses.setCurrentIndex(4)
    assert dialog.quotation()[1].market_price_gp == 20000
    assert 'unlimited' in dialog.cost_formula.text() and '20000 gp' in dialog.cost_formula.text()
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


@pytest.mark.parametrize('sphere,key', [
    ('Life', 'life:advanced-talent:resurrection-supreme-warden'),
    ('Warp', 'warp:advanced-talent:time-warp-jester-s-hb'),
    ('Weather', 'weather:advanced-talent:radiotherapy-mantle-radiation-cata-hb'),
    ('Weather', 'weather:advanced-talent:fire-tornadoes'),
    ('Weather', 'weather:advanced-talent:volcano-lord'),
    ('Enhancement', 'enhancement:advanced-talent:antimagic-aegis'),
    ('Enhancement', 'enhancement:advanced-talent:heart-of-hope-and-fear-sm'),
    ('Enhancement', 'enhancement:advanced-talent:bestow-life'),
    ('Life', 'life:advanced-talent:soul-consumption-dbh'),
    ('Protection', 'protection:advanced-talent:antimagic-aura'),
    ('Protection', 'protection:advanced-talent:tripped-glyph-3pp'),
])
def test_composer_adds_reviewed_prerequisites_without_duplicates_or_writes(composer, sphere, key):
    from app.marvelous_item_rules import advanced_construction_blockers, missing_construction_prerequisites
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText(sphere); dialog.cl.setValue(20)
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == key)
    dialog.talent.setCurrentIndex(index); dialog.add_contribution()
    before = repo._connection.total_changes
    assert dialog.add_prerequisites.isEnabled() == bool(missing_construction_prerequisites(dialog.blueprint()['contributions']))
    dialog.add_required_contributions()
    contributions = dialog.blueprint()['contributions']
    assert not advanced_construction_blockers(contributions, 20)
    assert len(contributions) == len({row['catalog_key'] for row in contributions})
    if key == 'enhancement:advanced-talent:bestow-life':
        assert sum(row['additional_spell_points'] for row in contributions) == 3
    assert not dialog.add_prerequisites.isEnabled() and repo._connection.total_changes == before
    dialog.add_required_contributions()
    assert dialog.blueprint()['contributions'] == contributions
    if sphere == 'Protection':
        assert contributions[0]['additional_spell_points'] == (2 if 'tripped-glyph' in key else 1)


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


def test_painkiller_activation_button_updates_nonlethal_and_resource(composer):
    from dataclasses import replace
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=19, maximum=20,
                                  nonlethal=12, auto_calculate=False))
    plan = dict(schema_version=1, sphere='Life', base_power='life:temporary-hp', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[dict(catalog_key=key, complexity=1) for key in
                               ('life:talent:painkiller', 'life:talent:deeper-healing')])
    CraftingService(repo, cid).save_marvelous_design(plan, name='Pain relief', slot='', description='')
    book = MarvelousItemUseDialog(repo, cid)
    book.table.cellWidget(0, 3).click()
    assert repo.get_hit_points(cid).nonlethal == 2 and repo.get_hit_points(cid).temporary == 1
    assert not book.table.cellWidget(0, 3).isEnabled()
    assert 'nonlethal healed: 10' in book.result.text()
    book.close()


def test_mixed_effect_button_applies_both_components(composer, monkeypatch):
    from dataclasses import replace
    from app.ui.marvelous_crafting import MarvelousItemUseDialog, effect_detail_lines
    from app.services.crafting import CraftingService
    dialog, repo, cid = composer
    repo.update_hit_points(replace(repo.get_hit_points(cid), current=10, maximum=20, auto_calculate=False))
    base = dict(schema_version=1,caster_level=5,activation='standard',uses=1,range_steps=0,
                duration_steps=0,unique_changes=0,contributions=[])
    plan = {**base,'sphere':'Life','base_power':'life:cure','combination_mode':'mixed',
            'extra_effects':[{**base,'sphere':'Protection','base_power':'protection:aegis'}]}
    CraftingService(repo,cid).save_marvelous_design(plan,name='Mixed',slot='',description='')
    book = MarvelousItemUseDialog(repo,cid)
    assert book.table.cellWidget(0,3).text() == 'Apply mixed effects'
    monkeypatch.setattr('random.randint', lambda a,b:4)
    book.table.cellWidget(0,3).click()
    assert repo.get_hit_points(cid).current == 19 and len(repo.list_ongoing_effects(cid)) == 1
    assert not book.table.cellWidget(0,3).isEnabled() and not book.table.cellWidget(1,3).isEnabled()
    assert '+2 deflection to ac' in book.result.text()
    assert 'Lessen Exhausted to Fatigued' in dict(effect_detail_lines({'restore_changes':[
        dict(condition='Exhausted',operation='replace',replacement='Fatigued')]}))['restore changes']
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

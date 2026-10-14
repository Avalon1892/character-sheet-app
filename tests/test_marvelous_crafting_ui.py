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


def test_antimagic_picker_selects_ward_and_prices_integrated_prerequisite(composer, monkeypatch):
    from app.ui.marvelous_effect_picker import MarvelousEffectPicker
    from app.content import magic_entry
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Protection'); dialog.cl.setValue(10)
    entry = magic_entry('protection:advanced-talent:antimagic-aura')
    monkeypatch.setattr(dialog.service, 'accessible_marvelous_effects', lambda sphere: (entry,))
    def accept(picker):
        picker.selected_entries = (entry,)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(MarvelousEffectPicker, 'exec', accept)
    before = repo._connection.total_changes
    dialog.choose_accessible_effects()
    assert dialog.base_power.currentData() == 'protection:ward'
    assert dialog.quotation()[0] == 6
    assert 'Antimagic Aura ward' in dialog.item_preview.toPlainText()
    assert repo._connection.total_changes == before
    saved = dialog.blueprint(); dialog.load_plan(saved)
    assert dialog.base_power.currentData() == 'protection:ward'
    assert dialog.quotation()[0] == 6


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
def test_designer_compact_layout_keeps_card_and_formula_in_window(composer, theme):
    from app.ui.dialog_theme import dialog_stylesheet
    from PySide6.QtCore import QPoint
    dialog, repo, cid = composer
    dialog.setStyleSheet(dialog_stylesheet(theme))
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


@pytest.mark.parametrize('key,points', [('true-teleport', 2), ('planeshift', 2), ('portal', 1), ('enduring-portal', 1)])
def test_warp_effect_sp_defaults_update_price_and_restore(composer, key, points):
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Warp'); dialog.cl.setValue(20)
    index = next(i for i in range(dialog.talent.count()) if dialog.talent.itemData(i)['key'] == 'warp:advanced-talent:' + key)
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
    ('Protection', 'protection:advanced-talent:antimagic-aura'),
])
def test_composer_adds_reviewed_prerequisites_without_duplicates_or_writes(composer, sphere, key):
    from app.marvelous_item_rules import advanced_construction_blockers
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText(sphere); dialog.cl.setValue(20)
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
    if sphere == 'Protection':
        assert contributions[0]['additional_spell_points'] == 1


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

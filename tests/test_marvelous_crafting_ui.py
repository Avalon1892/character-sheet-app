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


def test_design_tradition_updates_price_without_character_selection(composer, monkeypatch):
    from app.ui.optional_traditions import OptionalTraditionDialog
    from app.optional_traditions import catalog
    from PySide6.QtWidgets import QDialog
    dialog, repo, cid = composer
    dialog.cl.setValue(5)
    entry = next(e for e in catalog()['entries'] if e['key'] == 'crafting:diviner-s-sight')
    def choose(picker):
        picker.selected_entry = entry
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(OptionalTraditionDialog, 'exec', choose)
    before = repo._connection.total_changes
    dialog.choose_crafting_tradition()
    assert dialog.quotation()[1].market_price_gp == 1800
    assert dialog.quotation()[2].cost_gp == 900
    assert 'Cheap' in dialog.cost_formula.text()
    assert dialog.tradition_button.text() == entry['name']
    assert not repo.list_character_traditions(cid)
    assert repo._connection.total_changes == before
    from app.services.crafting import CraftingService
    iid = CraftingService(repo, cid).save_marvelous_design(dialog.blueprint(), name='Cheap design', slot='', description='')
    reopened = MarvelousCraftingDialog(repo, cid, item_id=iid)
    assert reopened.crafting_tradition['key'] == entry['key']
    assert reopened.crafting_tradition['description'] == entry['description']
    assert reopened.quotation()[1].market_price_gp == 1800
    reopened.close()
    dialog.remove_crafting_tradition()
    assert dialog.quotation()[1].market_price_gp == 2000


def test_custom_drawback_live_price_card_save_reopen_and_remove(composer):
    from app.services.crafting import CraftingService
    from app.marvelous_base_powers import automatic_self_effect
    dialog, repo, cid = composer
    dialog.sphere.setCurrentText('Life'); dialog.cl.setValue(5); dialog.unique.setValue(2)
    dialog.drawbacks = [dict(source='custom', name='At dawn', description='Sunrise only', reduction=1)]
    dialog.update_preview()
    assert dialog.quotation()[1].market_price_gp == 4000
    assert 'At dawn' in dialog.card_edits['description'].toPlainText()
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

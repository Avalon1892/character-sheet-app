import json
import pytest
from app.database import CharacterRepository
from app.named_marvelous_items import named_marvelous_effect


def test_named_ring_uses_published_roll_and_atomic_daily_spending(tmp_path, monkeypatch):
    repo = CharacterRepository(tmp_path / 'named.db')
    cid = repo.create_character('User', 'Spheres')
    key = 'spheres:marvelous-items:thunderbolt-ring'
    iid = repo.add_equipment(cid, 'Thunderbolt Ring', 'Gear', 1, .5, False, 0, 'untyped', None, '', catalog_key=key)
    monkeypatch.setattr('random.randint', lambda a, b: 3)
    effect = repo.consume_marvelous_item_use(cid, iid)
    assert effect['damage_rolled'] == 12 and effect['save_dc'] == 12
    assert effect['damage_type'] == 'electricity' and effect['area'] == '5-foot-wide, 140-foot line'
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='No item uses'): repo.consume_marvelous_item_use(cid, iid)
    assert repo._connection.total_changes == before
    metadata = json.loads(repo.list_equipment(cid)[0].automation_json)
    assert 'marvelous_blueprint' not in metadata
    assert repo.reset_marvelous_daily_uses(cid) == 1
    assert repo.consume_marvelous_item_use(cid, iid)['damage_rolled'] == 12
    copy = named_marvelous_effect(key); copy['daily_uses'] = 99
    assert named_marvelous_effect(key)['daily_uses'] == 1
    repo.close()


def test_named_ring_in_activation_window_without_custom_design_controls(tmp_path, monkeypatch):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app.ui.marvelous_crafting import MarvelousItemUseDialog
    app = QApplication.instance() or QApplication([])
    repo = CharacterRepository(tmp_path / 'named-ui.db')
    cid = repo.create_character('User', 'Spheres')
    repo.add_equipment(cid, 'Thunderbolt Ring', 'Gear', 1, .5, False, 0, 'untyped', None, '',
                       catalog_key='spheres:marvelous-items:thunderbolt-ring')
    dialog = MarvelousItemUseDialog(repo, cid)
    assert dialog.table.rowCount() == 1
    dialog.table.selectRow(0)
    assert not dialog.construction.isEnabled()
    dialog.edit_design(0, 0); dialog.open_construction()
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr('random.randint', lambda a, b: 2)
    dialog.table.cellWidget(0, 3).click()
    assert dialog.changed and 'damage rolled: 8' in dialog.result.text()
    assert not dialog.table.cellWidget(0, 3).isEnabled()
    dialog.close(); repo.close()

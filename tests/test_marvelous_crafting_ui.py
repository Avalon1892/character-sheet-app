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

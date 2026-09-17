import os, tempfile, unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.refined.sheet import RefinedSheetWidget
from app.equipment_wearing import effective_item_state


class RefinedCharacterPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = CharacterRepository(Path(self.temp.name) / 'test.db')
        self.cid = self.repo.create_character('Panels', 'Spheres')
        self.repo.add_class_level(self.cid, 'Prodigy', 5, '3/4', 'Good', 'Poor', 'Good', 'prodigy', 8, 30)
        self.sheet = RefinedSheetWidget(self.repo)
        self.sheet.load_character(self.cid)

    def tearDown(self):
        self.sheet.close(); self.sheet.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.repo.close(); self.temp.cleanup()

    def test_combined_grid_keeps_base_and_level_increases_independent(self):
        section = self.sheet.custom_sections['base_abilities']
        self.assertIs(section, self.sheet.ability_score_increase_section)
        self.assertNotIn('ability_score_increases', self.sheet.custom_sections)
        key = next(iter(self.sheet.asi_controls))
        base = self.sheet._ability_controls[key][0]
        allocation = self.sheet.asi_controls[key]
        self.assertTrue(section.isAncestorOf(base))
        self.assertTrue(section.isAncestorOf(allocation))
        base.setValue(14); allocation.setValue(1)
        self.assertEqual(14, self.repo.get_ability_scores(self.cid)[key])
        self.assertEqual(1, self.repo.list_ability_score_increases(self.cid)[key].points)

    def test_focus_actions_and_settings_remain_live(self):
        spend, regain = self.sheet._refined_focus_buttons
        self.sheet._regain_martial_focus()
        self.assertTrue(spend.isEnabled())
        spend.click()
        self.assertEqual(0, self.sheet.martial_focus_current.value())
        self.assertFalse(spend.isEnabled())
        regain.click()
        self.assertEqual(1, self.sheet.martial_focus_current.value())
        self.sheet.martial_focus_setup_toggle.setChecked(True)
        self.assertFalse(self.sheet.martial_focus_setup.isHidden())

    def test_inline_figure_uses_live_inventory_and_resets_character_scope(self):
        item = self.repo.add_equipment(self.cid, 'Boots', 'Gear', 1, 1, False, 0, 'untyped', None, '', slot='Feet')
        panel = self.sheet.refined_equipment_figure
        panel.change_equipment(item, 'Feet')
        self.assertIn('Boots', panel.all_targets['Feet'].toolTip())
        panel.change_equipment(item, '')
        self.assertEqual('stored', effective_item_state(self.repo.list_equipment(self.cid)[0]))
        second = self.repo.create_character('Other', 'Spheres')
        self.sheet.load_character(second)
        self.assertEqual(second, self.sheet.refined_equipment_figure.service.character_id)
        self.assertNotIn('Boots', self.sheet.refined_equipment_figure.all_targets['Feet'].toolTip())


if __name__ == '__main__': unittest.main()

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.class_choice_rules import ClassChoiceOption, class_choice_selection_record, resolve_class_choice_slots
from app.database import CharacterRepository
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.ui.class_choice_dialog import ClassChoiceDialog


class ClassChoiceUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "choices.db")
        self.character = self.repository.create_character("Wizard", "Pathfinder 1e")
        self.repository.add_class_level(
            self.character, "Wizard", 5, "1/2", "Poor", "Poor", "Good",
            "pathfinder-class:wizard", 6, 20,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_searchable_dialog_and_sheet_use_the_same_resolved_slots(self) -> None:
        slots = resolve_class_choice_slots(self.repository, self.character)
        school = next(slot for slot in slots if slot.key == "arcane-school")
        dialog = ClassChoiceDialog(school)
        dialog.search.setText("Evocation")
        self.assertGreater(dialog.results.count(), 0)
        self.assertIn("Evocation School", dialog.results.item(0).text())
        dialog.close()

        evocation = next(option for option in school.options if option.name == "Evocation School")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, school, (evocation.key,))
        )
        sheet = CharacterSheetWidget(self.repository)
        try:
            sheet.load_character(self.character)
            labels = {
                sheet.inquisitor_choice_table.item(row, 1).text()
                for row in range(sheet.inquisitor_choice_table.rowCount())
            }
            self.assertIn("Arcane School", labels)
            self.assertIn("Opposition Schools", labels)
            self.assertIn("Arcane Bond", labels)
        finally:
            sheet.close()

    def test_repeatable_machinehead_choice_count_survives_search_and_uses_slots(self):
        class_id=self.repository.add_class_level(self.character,"Armiger",6,"Full","Good","Poor","Poor","spheres-class:armiger",10,30)
        self.repository.set_class_archetype_keys(self.character,class_id,("spheres-archetype:spheres-class:armiger:machinehead",))
        slot=next(s for s in resolve_class_choice_slots(self.repository,self.character) if s.key=="machinehead-prowesses")
        dialog=ClassChoiceDialog(slot);dialog.search.setText("Custom Graft")
        self.assertEqual(1,dialog.results.count())
        dialog.results.setCurrentRow(0);dialog.repeat_count.setValue(2)
        self.assertEqual(2,len(dialog.selected_keys))
        self.assertTrue(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        dialog.search.setText("Armored Armiger")
        dialog.results.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(2,len(dialog.selected_keys))
        dialog.search.setText("Custom Graft");dialog.results.setCurrentRow(0);dialog.repeat_count.setValue(1)
        self.assertEqual(1,len(dialog.selected_keys))
        self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        record=class_choice_selection_record(self.character,slot,dialog.selected_keys)
        self.repository.save_class_feature_selection(record)
        dialog.close();dialog.deleteLater()

    def test_choice_dependencies_disable_confirmation_until_satisfied(self) -> None:
        base = resolve_class_choice_slots(self.repository, self.character)[0]
        slot = replace(base, minimum=1, maximum=2, selected_keys=(), selected_options=(), options=(
            ClassChoiceOption("intuition", "Intuition"),
            ClassChoiceOption("combat", "Combat Intuition", required_options=("intuition",)),
        ))
        dialog = ClassChoiceDialog(slot)
        try:
            items = {dialog.results.item(i).data(Qt.ItemDataRole.UserRole): dialog.results.item(i)
                     for i in range(dialog.results.count())}
            items["combat"].setCheckState(Qt.CheckState.Checked)
            self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
            self.assertIn("requires Intuition", dialog.selection_status.text())
            items["intuition"].setCheckState(Qt.CheckState.Checked)
            self.assertTrue(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()

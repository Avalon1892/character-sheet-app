from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.class_choice_rules import class_choice_selection_record, resolve_class_choice_slots
from app.database import CharacterRepository
from app.ui.character_sheet import CharacterSheetWidget
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


if __name__ == "__main__":
    unittest.main()

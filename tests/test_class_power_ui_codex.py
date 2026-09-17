from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.catalogs import DEFAULT_CATALOG
from app.codex_index import build_codex_search_records
from app.database import CharacterRepository
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.class_power_dialog import ClassPowerDialog
from app.ui.main_window import CodexDialog


class ClassPowerUiCodexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character = self.repository.create_character("Monk", "Pathfinder 1e")
        self.repository.add_class_level(
            self.character, "Monk (Unchained)", 8, "Full", "Good", "Good", "Good",
            "pathfinder-class:monk-unchained", 10, 50,
        )
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character)

    def tearDown(self) -> None:
        self.sheet.close(); self.repository.close(); self.directory.cleanup()

    def test_sheet_and_dialog_share_the_resolved_power_set(self) -> None:
        self.assertEqual(1, self.sheet.class_power_table.rowCount())
        self.assertEqual("Ki Powers", self.sheet.class_power_table.item(0, 1).text())
        self.sheet.class_power_table.setCurrentCell(0, 0)
        power_set = self.sheet._selected_class_power_set()
        dialog = ClassPowerDialog(power_set)
        try:
            dialog.search.setText("abundant step")
            self.assertEqual(1, dialog.available.count())
            self.assertIn("Abundant Step", dialog.available.item(0).text())
        finally:
            dialog.close()

    def test_catalog_is_browsable_and_in_global_search(self) -> None:
        abundant = DEFAULT_CATALOG.class_power_entry(
            "class-power:ki_power:abundant-step"
        )
        self.assertIsNotNone(abundant)
        rendered = CodexDialog._class_power_html(abundant)
        self.assertIn("Minimum level", rendered)
        record = next(
            item for item in build_codex_search_records(DEFAULT_CATALOG)
            if item["name"] == "Abundant Step" and "Powers" in item["category"]
        )
        self.assertEqual("class-power:class-power:ki_power:abundant-step", record["target"])


if __name__ == "__main__":
    unittest.main()

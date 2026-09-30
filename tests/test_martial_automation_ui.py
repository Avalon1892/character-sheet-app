import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QAbstractItemView, QPushButton

from app.content import martial_entries
from app.database import CharacterRepository
from app.ui.character_sheet import MartialTalentCatalogDialog
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class MartialAutomationUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "characters.db"
        self.repository = CharacterRepository(database_path)
        self.character_id = self.repository.create_character("Practitioner", "Spheres")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temporary_directory.cleanup()

    def test_martial_browser_exposes_reviewed_behavior_filters(self) -> None:
        dialog = MartialTalentCatalogDialog([], self.sheet)
        self.assertEqual(1610, dialog.results.rowCount())
        dialog.automation_filter.setCurrentIndex(
            dialog.automation_filter.findData("automatic")
        )
        self.assertEqual(19, dialog.results.rowCount())
        dialog.automation_filter.setCurrentIndex(
            dialog.automation_filter.findData("toggle")
        )
        self.assertEqual(4, dialog.results.rowCount())
        dialog.close()

    def test_play_picker_requires_an_owned_base_sphere(self) -> None:
        dialog = MartialTalentCatalogDialog([], self.sheet, play_mode=True)
        self.assertEqual(0, dialog.results.rowCount())
        dialog.close()
        entry = next(item for item in martial_entries("Barrage") if item["category"] == "Talent")
        with self.assertRaisesRegex(ValueError, "base sphere on the Character page"):
            self.sheet._add_catalog_martial_entry(entry)
        self.assertEqual([], self.repository.list_martial_talents(self.character_id))
        self.sheet._acquire_martial_sphere("Barrage")
        dialog = MartialTalentCatalogDialog(
            self.repository.list_martial_talents(self.character_id), self.sheet, play_mode=True,
        )
        self.assertGreater(dialog.results.rowCount(), 0)
        self.assertTrue(all(
            item["sphere"] == "Barrage" and item["category"] not in {"Base Sphere", "Drawback"}
            for item in dialog._entries
        ))
        dialog.close()
        self.assertTrue(self.sheet._add_catalog_martial_entry(entry))

    def test_character_page_removes_empty_and_populated_martial_spheres(self) -> None:
        self.sheet._acquire_martial_sphere("Gladiator")
        for with_talent in (False, True):
            self.sheet._acquire_martial_sphere("Barrage")
            if with_talent:
                self.sheet._add_catalog_martial_entry(next(
                    item for item in martial_entries("Barrage") if item["name"] == "Wild Shooter"
                ))
                self.sheet._add_catalog_martial_entry(next(
                    item for item in martial_entries("Barrage") if item["category"] == "Talent"
                ))
            self.sheet._refresh_sphere_build()
            table = self.sheet.martial_sphere_build_table
            table.selectRow(next(row for row in range(table.rowCount()) if table.item(row, 0).text() == "Barrage"))
            button = next(button for button in self.sheet.martial_sphere_build_panel.findChildren(QPushButton)
                          if button.text() == "Remove selected sphere")
            self.assertTrue(button.isEnabled())
            button.click()
            remaining = self.repository.list_martial_talents(self.character_id)
            self.assertFalse(any(item.sphere == "Barrage" for item in remaining))
            self.assertTrue(any(item.sphere == "Gladiator" for item in remaining))

    def test_martial_browser_and_sheet_add_multiple_talents_in_one_batch(self) -> None:
        dialog = MartialTalentCatalogDialog([], self.sheet)
        self.assertEqual(
            QAbstractItemView.SelectionMode.SingleSelection,
            dialog.results.selectionMode(),
        )
        for row in (0, 1):
            dialog.results.setCurrentCell(row, 1)
            dialog._queue_current_entry()
        self.assertEqual("Add Selected (2)", dialog.add_button.text())
        dialog._accept_selected()
        self.assertEqual(2, len(dialog.selected_entries))

        candidates = tuple(
            entry
            for entry in martial_entries("Athletics")
            if entry["category"] == "Talent"
            and not entry.get("automation", {}).get("choice_type")
        )[:2]
        self.assertEqual(2, len(candidates))
        self.sheet._acquire_martial_sphere("Athletics", base_choice="Run")
        added = self.sheet._add_catalog_batch(
            candidates,
            self.sheet._add_catalog_martial_entry,
            self.sheet._martial_talents_changed,
            "martial talents",
        )
        self.assertEqual(2, added)
        stored = self.repository.list_martial_talents(self.character_id)
        self.assertEqual(3, len(stored))  # Base sphere plus both selected talents.

    def test_martial_drawback_changes_matching_saved_attacks(self) -> None:
        self.repository.add_attack(
            self.character_id,
            "Longbow",
            "Ranged",
            "dexterity",
            0,
            "1d8",
            None,
            0,
            0,
            "x3",
            "",
        )
        wild_shooter = next(
            entry
            for entry in martial_entries("Barrage")
            if entry["name"] == "Wild Shooter"
        )
        self.sheet._acquire_martial_sphere("Barrage")
        self.assertTrue(self.sheet._add_catalog_martial_entry(wild_shooter))
        self.sheet._martial_talents_changed()
        self.assertEqual("-1", self.sheet.attack_table.item(0, 2).text())
        self.assertEqual(
            {"Base Sphere", "Drawback"},
            {
                talent.catalog_category
                for talent in self.repository.list_martial_talents(self.character_id)
            },
        )


if __name__ == "__main__":
    unittest.main()

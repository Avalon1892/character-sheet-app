from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.bonded_companion_rules import (
    bonded_companion_progression,
    calculate_familiar_statistics,
    familiar_catalog,
    familiar_entry,
    reconcile_familiar_hit_points,
)
from app.models import BondedCompanion, HitPoints
from app.database import CharacterRepository
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.familiar_dialog import FamiliarCatalogDialog


class FamiliarCatalogRulesTests(unittest.TestCase):
    def test_complete_catalog_contains_requested_fennecs_and_statblocks(self) -> None:
        entries = familiar_catalog()
        self.assertGreaterEqual(len(entries), 90)
        self.assertIsNotNone(familiar_entry("fox-firefoot-fennec"))
        creamfoot = familiar_entry("fox-creamfoot-fennec")
        self.assertIsNotNone(creamfoot)
        self.assertEqual("Third Party", creamfoot["ruleset"])
        for entry in entries:
            self.assertNotIn("parse_warning", entry)
            for field in ("size", "abilities", "armor_class", "speed", "hit_dice"):
                self.assertIn(field, entry, f"{entry['name']} lacks {field}")

    def test_familiar_statistics_follow_master_and_selected_form(self) -> None:
        statistics = calculate_familiar_statistics(
            familiar_entry("fox-firefoot-fennec"),
            bonded_companion_progression("familiar", 5),
            {
                "maximum_hp": 40,
                "bab": 3,
                "character_level": 5,
                "base_saves": {"fortitude": 2, "reflex": 1, "will": 4},
            },
        )
        self.assertEqual(20, statistics.maximum_hp)
        self.assertEqual(8, statistics.abilities["int"])
        self.assertEqual(18, statistics.armor_class)
        self.assertEqual(3, statistics.base_attack_bonus)
        self.assertEqual({"fortitude": 2, "reflex": 5, "will": 5}, statistics.saves)
        self.assertEqual(8, statistics.attacks[0].attack_bonus)

    def test_level_up_reconciliation_preserves_damage_not_old_maximum(self) -> None:
        record = BondedCompanion(
            1,
            "familiar",
            "Ember",
            "Fox, Firefoot Fennec",
            15,
            0,
            json.dumps({"derived_maximum_hp": 20}),
            "",
        )
        updated = reconcile_familiar_hit_points(record, 25)
        self.assertEqual(20, updated.current_hp)
        self.assertEqual(25, json.loads(updated.details_json)["derived_maximum_hp"])


class FamiliarCatalogUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_picker_starts_unselected_and_can_find_firefoot(self) -> None:
        dialog = FamiliarCatalogDialog()
        try:
            self.assertIsNone(dialog.selected_entry)
            self.assertFalse(dialog.choose_button.isEnabled())
            dialog.search.setText("Firefoot Fennec")
            dialog._debounce.flush()
            self.assertEqual(1, dialog.results.rowCount())
            self.assertIn("Firefoot", dialog.results.item(0, 0).text())
            dialog.results.selectRow(0)
            self.application.processEvents()
            self.assertEqual("fox-firefoot-fennec", dialog.selected_entry["key"])
            self.assertTrue(dialog.choose_button.isEnabled())
        finally:
            dialog.close()

    def test_sheet_refresh_updates_familiar_maximum_and_current_hp_after_level_up(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = CharacterRepository(Path(folder) / "characters.db")
            try:
                character = repository.create_character("Master", "Pathfinder 1e")
                class_id = repository.add_class_level(
                    character, "Witch", 1, "1/2", "Poor", "Poor", "Good",
                    "pathfinder-class:witch", 6, 8,
                )
                repository.update_bonded_companion(
                    BondedCompanion(
                        character,
                        "familiar",
                        "Ember",
                        "Fox, Firefoot Fennec",
                        0,
                        0,
                        json.dumps({"familiar_key": "fox-firefoot-fennec"}),
                        "",
                    )
                )
                repository.update_hit_points(
                    HitPoints(character, 0, 0, 0, 0, True)
                )
                sheet = CharacterSheetWidget(repository)
                sheet.load_character(character)
                self.assertEqual("4", sheet.familiar_panel.maximum_hp.text())
                self.assertEqual(4, sheet.familiar_panel.current_hp.value())
                repository.update_class_level(
                    character, class_id, "Witch", 2, "1/2", "Poor", "Poor", "Good",
                    "pathfinder-class:witch", 6, 14,
                )
                sheet.refresh_all()
                self.assertEqual("7", sheet.familiar_panel.maximum_hp.text())
                self.assertEqual(7, sheet.familiar_panel.current_hp.value())
                sheet.close()
            finally:
                repository.close()


if __name__ == "__main__":
    unittest.main()

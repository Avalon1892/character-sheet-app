from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QPushButton

from app.animal_companion_rules import (
    calculate_companion_statistics,
    companion_entry,
    companion_progression,
)
from app.database import CharacterRepository
from app.models import AnimalCompanion
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.ui.dialogs import AnimalCompanionFeatCatalogDialog


class AnimalCompanionEditingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "companion.db")
        self.character_id = self.repository.create_character(
            "Companion editor", "Pathfinder 1e"
        )
        class_level_id = self.repository.add_class_level(
            self.character_id,
            "Inquisitor",
            4,
            "3/4",
            "Good",
            "Poor",
            "Good",
            "pathfinder-class:inquisitor",
            8,
            25,
        )
        self.repository.set_class_archetype_keys(
            self.character_id,
            class_level_id,
            (
                "pathfinder-archetype:pathfinder-class:inquisitor:"
                "sacred-huntsmaster",
            ),
        )
        self.repository.update_animal_companion(
            AnimalCompanion(
                self.character_id,
                name="Lion",
                species_key="cat-big-lion-tiger",
            )
        )
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)
        self.application.processEvents()

    def tearDown(self) -> None:
        self.sheet.dispose()
        self.sheet.deleteLater()
        self.application.processEvents()
        self.repository.close()
        self.directory.cleanup()

    def test_level_four_asi_is_selectable_applied_and_persistent(self) -> None:
        self.assertTrue(self.sheet.companion_asi_fields["str"].isEnabled())
        before = self.sheet._companion_statistics.ability_scores["str"]

        self.sheet.companion_asi_fields["str"].setValue(1)
        self.sheet.companion_asi_fields["str"].editingFinished.emit()
        self.application.processEvents()

        record = self.repository.get_animal_companion(self.character_id)
        details = json.loads(record.details_json)
        self.assertEqual({"str": 1}, details["ability_increases"])
        self.assertEqual(
            before + 1, self.sheet._companion_statistics.ability_scores["str"]
        )
        self.assertIn("1 / 1 assigned", self.sheet.companion_asi_status.text())

        # A second point is rejected at effective companion level 4.
        self.sheet.companion_asi_fields["dex"].setValue(1)
        self.sheet.companion_asi_fields["dex"].editingFinished.emit()
        self.application.processEvents()
        details = json.loads(
            self.repository.get_animal_companion(self.character_id).details_json
        )
        self.assertEqual({"str": 1}, details["ability_increases"])
        self.assertEqual(0, self.sheet.companion_asi_fields["dex"].value())

    def test_explicit_controls_edit_overrides_skills_and_derived_totals(self) -> None:
        self.sheet.companion_ability_override_fields["wis"].setValue(18)
        self.sheet.companion_ability_override_fields["wis"].editingFinished.emit()
        self.application.processEvents()
        self.assertEqual(18, self.sheet._companion_statistics.ability_scores["wis"])

        self.sheet.companion_skill_rank_fields["perception"].setValue(2)
        self.sheet.companion_skill_rank_fields["perception"].editingFinished.emit()
        self.application.processEvents()
        record = self.repository.get_animal_companion(self.character_id)
        self.assertEqual(2, json.loads(record.skill_ranks_json)["perception"])

        old_armor = self.sheet._companion_statistics.natural_armor
        self.sheet.companion_identity_values["natural_armor"].setValue(old_armor + 2)
        self.sheet.companion_identity_values["natural_armor"].editingFinished.emit()
        self.application.processEvents()
        details = json.loads(
            self.repository.get_animal_companion(self.character_id).details_json
        )
        self.assertEqual(2, details["natural_armor_misc"])
        self.assertEqual(
            old_armor + 2, self.sheet._companion_statistics.natural_armor
        )

    def test_rules_engine_ignores_saved_asi_points_until_earned(self) -> None:
        level_three = calculate_companion_statistics(
            companion_entry("cat-big-lion-tiger"),
            companion_progression(3),
            ability_increases={"str": 1},
        )
        level_four = calculate_companion_statistics(
            companion_entry("cat-big-lion-tiger"),
            companion_progression(4),
            ability_increases={"str": 1},
        )
        self.assertEqual({}, level_three.ability_increase_allocations)
        self.assertEqual({"str": 1}, level_four.ability_increase_allocations)
        self.assertEqual(
            level_three.automatic_ability_scores["str"],
            level_three.ability_scores["str"],
        )
        self.assertEqual(
            level_four.automatic_ability_scores["str"] + 1,
            level_four.ability_scores["str"],
        )

    def test_companion_feat_catalog_uses_intelligence_rule_and_readable_ui(self) -> None:
        low_int = AnimalCompanionFeatCatalogDialog((), 2, self.sheet)
        high_int = AnimalCompanionFeatCatalogDialog((), 3, self.sheet)
        try:
            low_names = {entry["name"] for entry in low_int._entries}
            self.assertIn("Improved Natural Attack", low_names)
            self.assertIn("Weapon Focus", low_names)
            self.assertNotIn("Craft Wondrous Item", low_names)
            self.assertGreater(len(high_int._entries), len(low_int._entries))
            self.assertEqual(-1, low_int.results.currentRow())
        finally:
            low_int.close()
            high_int.close()

    def test_special_ability_labels_are_grammatical(self) -> None:
        table = self.sheet.companion_training_tabs["Special abilities"]
        self.assertEqual("Special ability", table.horizontalHeaderItem(0).text())
        labels = {button.text() for button in self.sheet.findChildren(QPushButton)}
        self.assertIn("+ Add special ability", labels)
        self.assertNotIn("+ Add special abilitie", labels)


if __name__ == "__main__":
    unittest.main()

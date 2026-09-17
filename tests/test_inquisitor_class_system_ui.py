from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.content import archetype_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.ui.character_sheet import CharacterSheetWidget


class InquisitorClassSystemUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Judge", "Pathfinder 1e")
        self.class_id = self.repository.add_class_level(
            self.character_id, "Inquisitor", 8, "3/4", "Good", "Poor", "Good",
            "pathfinder-class:inquisitor", 8, 48,
        )
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.directory.cleanup()

    def _row(self, name: str) -> int:
        return next(
            row
            for row in range(self.sheet.inquisitor_resource_table.rowCount())
            if self.sheet.inquisitor_resource_table.item(row, 0).text() == name
        )

    def test_play_table_spends_activates_and_restores_judgment(self) -> None:
        self.repository.save_class_feature_state(
            ClassFeatureState(
                self.character_id, self.class_id, "judgment",
                choices_json=json.dumps(["Justice", "Protection"]),
            )
        )
        self.sheet._refresh_inquisitor_features()
        row = self._row("Judgment")
        self.sheet.inquisitor_resource_table.setCurrentCell(row, 0)
        self.sheet._use_class_feature_resource()
        state = next(
            item for item in self.repository.list_class_feature_states(self.character_id)
            if item.feature_key == "judgment"
        )
        self.assertTrue(state.active)
        self.assertEqual(2, state.current_value)
        self.assertEqual("ACTIVE", self.sheet.inquisitor_resource_table.item(self._row("Judgment"), 3).text())

        self.sheet.inquisitor_resource_table.setCurrentCell(self._row("Judgment"), 0)
        self.sheet._toggle_class_feature_resource()
        state = next(
            item for item in self.repository.list_class_feature_states(self.character_id)
            if item.feature_key == "judgment"
        )
        self.assertFalse(state.active)

    def test_archetype_refresh_removes_replaced_tracker_and_deactivates_it(self) -> None:
        self.repository.save_class_feature_state(
            ClassFeatureState(
                self.character_id, self.class_id, "judgment", 1,
                active=True, choices_json=json.dumps(["Justice"]),
            )
        )
        huntsmaster = archetype_entry(
            "pathfinder-archetype:pathfinder-class:inquisitor:sacred-huntsmaster"
        )
        self.repository.set_class_archetype_keys(
            self.character_id, self.class_id, (str(huntsmaster["key"]),)
        )
        self.sheet._refresh_inquisitor_features()
        names = {
            self.sheet.inquisitor_resource_table.item(row, 0).text()
            for row in range(self.sheet.inquisitor_resource_table.rowCount())
        }
        self.assertNotIn("Judgment", names)
        state = next(
            item for item in self.repository.list_class_feature_states(self.character_id)
            if item.feature_key == "judgment"
        )
        self.assertFalse(state.active)

    def test_declarative_study_transitions_arm_strike_and_end_both(self) -> None:
        investigator = self.repository.create_character("Detective", "Pathfinder 1e")
        investigator_class = self.repository.add_class_level(
            investigator, "Investigator", 8, "3/4", "Good", "Good", "Good",
            "pathfinder-class:investigator", 8, 48,
        )
        self.repository.update_ability_score(investigator, "intelligence", 18)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                investigator,
                investigator_class,
                "studied_combat",
                0,
                choices_json=json.dumps(["Training Dummy"]),
            )
        )
        self.sheet.load_character(investigator)

        self.sheet.inquisitor_resource_table.setCurrentCell(
            self._row("Studied Combat"), 0
        )
        self.sheet._toggle_class_feature_resource()
        states = {
            item.feature_key: item
            for item in self.repository.list_class_feature_states(investigator)
        }
        self.assertTrue(states["studied_combat"].active)
        self.assertEqual(4, states["studied_combat"].current_value)
        self.assertEqual(1, states["studied_strike"].current_value)

        self.sheet.inquisitor_resource_table.setCurrentCell(
            self._row("Studied Strike"), 0
        )
        self.sheet._toggle_class_feature_resource()
        self.sheet.inquisitor_resource_table.setCurrentCell(
            self._row("Studied Strike"), 0
        )
        self.sheet._use_class_feature_resource()
        states = {
            item.feature_key: item
            for item in self.repository.list_class_feature_states(investigator)
        }
        self.assertFalse(states["studied_combat"].active)
        self.assertFalse(states["studied_strike"].active)
        self.assertEqual(0, states["studied_strike"].current_value)

    def test_steady_skill_spends_martial_focus_not_a_false_daily_pool(self) -> None:
        prodigy = self.repository.create_character("Prodigy", "Spheres")
        prodigy_class = self.repository.add_class_level(
            prodigy, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            "prodigy", 8, 30,
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                prodigy,
                prodigy_class,
                "steady_skill",
                choices_json=json.dumps(["Acrobatics"]),
            )
        )
        self.sheet.load_character(prodigy)
        row = self._row("Steady Skill — Take 15")
        self.assertEqual("—", self.sheet.inquisitor_resource_table.item(row, 1).text())
        self.sheet.inquisitor_resource_table.setCurrentCell(row, 0)
        self.sheet._use_class_feature_resource()
        self.assertEqual(0, self.repository.get_martial_focus(prodigy).current)
        state = next(
            item for item in self.repository.list_class_feature_states(prodigy)
            if item.feature_key == "steady_skill"
        )
        self.assertIsNone(state.current_value)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.models import MartialFocus
from app.services.character_calculations import CharacterCalculationService
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class ConditionalAttackAndEffectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Reactive Hero", "Spheres")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.directory.cleanup()

    def _attack(self, condition: str = "") -> int:
        return self.repository.add_attack(
            self.character_id,
            "Focused strike",
            "Melee",
            "strength",
            0,
            "1d6",
            "strength",
            1.0,
            0,
            "20/x2",
            "",
            visibility_condition=condition,
        )

    def test_conditional_attack_visibility_reacts_to_formula_state(self) -> None:
        self._attack("martial_focus.current > 0")
        self.repository.update_martial_focus(
            MartialFocus(self.character_id, current=0, maximum=1)
        )
        self.sheet._refresh_attacks()
        self.assertEqual(0, self.sheet.attack_table.rowCount())

        self.repository.update_martial_focus(
            MartialFocus(self.character_id, current=1, maximum=1)
        )
        self.sheet._refresh_formula_dependents()
        self.assertEqual(1, self.sheet.attack_table.rowCount())
        self.assertEqual("Focused strike", self.sheet.attack_table.item(0, 0).text())

    def test_battered_and_ongoing_effect_share_the_compact_tracker(self) -> None:
        self.repository.add_condition(self.character_id, "Battered")
        effect_id = self.repository.add_ongoing_effect(
            self.character_id,
            "Protective ward",
            "Sphere",
            "5 rounds",
            "ac",
            "deflection",
            2,
            "A temporary ward.",
        )
        self.sheet._refresh_conditions()
        self.assertEqual(2, self.sheet.condition_table.rowCount())
        identities = {
            tuple(self.sheet.condition_table.item(row, 0).data(0x0100))
            for row in range(self.sheet.condition_table.rowCount())
        }
        self.assertIn(("condition", 1), identities)
        self.assertIn(("ongoing_effect", effect_id), identities)

    def test_enabled_ongoing_effect_flows_into_calculations(self) -> None:
        effect_id = self.repository.add_ongoing_effect(
            self.character_id,
            "Protective ward",
            "Spell",
            "10 minutes",
            "ac",
            "deflection",
            2,
            "",
        )
        self.assertEqual(
            12,
            CharacterCalculationService(
                self.repository, self.character_id
            ).combat_results()["ac"].total,
        )
        self.repository.set_ongoing_effect_enabled(
            self.character_id, effect_id, False
        )
        self.assertEqual(
            10,
            CharacterCalculationService(
                self.repository, self.character_id
            ).combat_results()["ac"].total,
        )


if __name__ == "__main__":
    unittest.main()

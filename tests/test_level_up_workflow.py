from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.level_up import (
    LevelUpStepDefinition,
    LevelUpStepRegistry,
    build_level_up_report,
)
from app.services.advancement import character_advancement_budgets
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class LevelUpWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.root.name) / "level-up.db")
        self.character = self.repository.create_character("Advancement", "Pathfinder 1e")
        self.repository.add_class_level(
            self.character,
            "Wizard",
            5,
            "1/2",
            "Poor",
            "Poor",
            "Good",
            preset_key="wizard",
            hit_die=6,
            hp_gained=18,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_shared_projection_drives_report_and_sheet(self) -> None:
        budgets = character_advancement_budgets(self.repository, self.character)
        report = build_level_up_report(self.repository, self.character)
        self.assertEqual(5, report.total_level)
        self.assertEqual(
            {item.key for item in budgets},
            {
                budget.key
                for state in report.steps
                for budget in state.budgets
            },
        )

        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        displayed = {
            sheet.advancement_table.item(row, 0).data(256): int(
                sheet.advancement_table.item(row, 4).text()
            )
            for row in range(sheet.advancement_table.rowCount())
        }
        self.assertEqual(
            {item.key: item.total for item in budgets}, displayed
        )
        sheet.close()

    def test_registry_accepts_future_step_without_dialog_changes(self) -> None:
        registry = LevelUpStepRegistry()
        registry.register(
            LevelUpStepDefinition(
                "future_pool", "Future Pool", "Extension test", action_keys=("future",)
            )
        )
        report = build_level_up_report(self.repository, self.character, registry)
        self.assertEqual(("future_pool",), tuple(item.definition.key for item in report.steps))

    def test_sheet_can_reopen_advancement_review_without_gaining_a_level(self) -> None:
        sheet = CharacterSheetWidget(self.repository)
        sheet.load_character(self.character)
        before = self.repository.list_class_levels(self.character)[0].level
        sheet._review_advancement()
        self.application.processEvents()
        self.assertIsNotNone(sheet._level_up_dialog)
        self.assertTrue(sheet._level_up_dialog.isVisible())
        self.assertGreater(sheet._level_up_dialog.table.rowCount(), 0)
        self.assertEqual(
            before, self.repository.list_class_levels(self.character)[0].level
        )
        sheet._level_up_dialog.close()
        sheet.close()


if __name__ == "__main__":
    unittest.main()

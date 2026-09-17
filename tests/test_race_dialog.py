from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.models import CharacterDetails
from app.ui.race_dialog import RaceCatalogDialog


class RaceCatalogDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_dual_talent_requires_two_distinct_ability_choices(self) -> None:
        dialog = RaceCatalogDialog(CharacterDetails(1, race="Human", race_key="human"))
        dual_row = next(
            row for row in range(dialog.alternates.rowCount())
            if dialog.alternates.item(row, 1).text() == "Dual Talent"
        )
        dialog.alternates.item(dual_row, 0).setCheckState(Qt.CheckState.Checked)
        key = ("race-alt-trait:human:dual-talent", "ability_scores")
        first, second = dialog._choice_widgets[key]
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.assertFalse(dialog.ability.isEnabled())
        self.assertFalse(ok.isEnabled())

        first.setCurrentIndex(first.findData("strength"))
        second.setCurrentIndex(second.findData("strength"))
        self.assertFalse(ok.isEnabled())
        self.assertIn("same selection twice", dialog.validation.text())

        second.setCurrentIndex(second.findData("dexterity"))
        self.assertTrue(ok.isEnabled())
        choice = dialog.selection()["trait_choices"][0]
        self.assertEqual(("strength", "dexterity"), choice.values)
        dialog.close()


if __name__ == "__main__":
    unittest.main()

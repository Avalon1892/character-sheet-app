from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QTableWidget

from app.models import CharacterDetails
from app.ui.race_dialog import RaceCatalogDialog, VariantAbilityPicker


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

    def test_variant_table_selection_and_cancel(self) -> None:
        for race in ("aasimar", "tiefling"):
            dialog = RaceCatalogDialog(CharacterDetails(1, race_key=race))
            row = next(row for row in range(dialog.alternates.rowCount())
                       if dialog.alternates.item(row, 1).text().startswith("Variant "))
            dialog.alternates.item(row, 0).setCheckState(Qt.CheckState.Checked)
            picker = next(widget for widgets in dialog._choice_widgets.values()
                          for widget in widgets if isinstance(widget, VariantAbilityPicker))

            def choose():
                window = picker.findChildren(QDialogButtonBox)[-1].parentWidget()
                table = window.findChild(QTableWidget)
                table.selectRow(11)
                window.accept()

            QTimer.singleShot(0, choose)
            picker.showPopup()
            self.assertEqual("12", picker.currentData())
            QTimer.singleShot(0, lambda: picker.findChildren(QDialogButtonBox)[-1].parentWidget().reject())
            picker.showPopup()
            self.assertEqual("12", picker.currentData())
            dialog.close()


if __name__ == "__main__":
    unittest.main()

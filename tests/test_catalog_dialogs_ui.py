from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QCheckBox, QDialog

from app.class_feature_rules import archetype_optional_features
from app.archetype_rules import archetype_choices
from app.content import archetype_entries, archetype_entry
from app.models import ClassLevel
from app.ui.dialogs import (
    ArchetypeSelectionDialog,
    ClassCatalogDialog,
    ClassLevelDialog,
    TraditionalSpellCatalogDialog,
)


class CatalogDialogsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_class_catalog_is_alphabetical_and_rulesets_are_distinct(self) -> None:
        dialog = ClassCatalogDialog()
        try:
            names = [dialog.results.item(row, 0).text() for row in range(dialog.results.rowCount())]
            self.assertEqual(102, len(names))
            self.assertEqual(sorted(names, key=str.casefold), names)
            dialog.source.setCurrentIndex(dialog.source.findData("Pathfinder"))
            self.assertEqual(44, dialog.results.rowCount())
            self.assertTrue(
                all(dialog.results.item(row, 1).text() == "Pathfinder" for row in range(44))
            )
            dialog.source.setCurrentIndex(dialog.source.findData("Spheres"))
            self.assertEqual(58, dialog.results.rowCount())
            self.assertTrue(
                all(dialog.results.item(row, 1).text() == "Spheres" for row in range(58))
            )
        finally:
            dialog.close()

    def test_traditional_spell_browser_defaults_to_fast_name_search(self) -> None:
        dialog = TraditionalSpellCatalogDialog(("Wizard",))
        try:
            self.assertEqual("name", dialog.search_mode.currentData())
            self.assertEqual("Wizard", dialog.caster_class.currentData())
            dialog.search.setText("Fireball")
            dialog._refresh()
            matching_rows = [
                row
                for row in range(dialog.results.rowCount())
                if dialog.results.item(row, 0).text() == "Fireball"
            ]
            self.assertEqual(1, len(matching_rows))
            self.assertEqual("3", dialog.results.item(matching_rows[0], 1).text())
        finally:
            dialog.close()

    def test_spell_browser_prioritizes_readable_spell_names(self) -> None:
        dialog = TraditionalSpellCatalogDialog(("Wizard",))
        try:
            dialog.resize(1320, 780)
            dialog.show()
            self.application.processEvents()
            self.assertEqual(
                ["Spell name", "Level", "School", "Ruleset"],
                [
                    dialog.results.horizontalHeaderItem(column).text()
                    for column in range(dialog.results.columnCount())
                ],
            )
            self.assertFalse(dialog.results.verticalHeader().isVisible())
            self.assertGreaterEqual(dialog.results.columnWidth(0), 280)
            self.assertTrue(dialog.results.item(0, 0).text())
            self.assertTrue(dialog.results.item(0, 0).font().bold())
            self.assertEqual("Add selected spell", dialog.add_button.text())
            self.assertTrue(dialog.add_button.isEnabled())
        finally:
            dialog.close()

    def test_spell_browser_supports_batch_and_explicit_single_selection_modes(self) -> None:
        dialog = TraditionalSpellCatalogDialog(("Wizard",))
        try:
            self.assertEqual(
                QAbstractItemView.SelectionMode.MultiSelection,
                dialog.results.selectionMode(),
            )
            dialog.results.clearSelection()
            flags = (
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows
            )
            for row in (0, 1):
                dialog.results.selectionModel().select(
                    dialog.results.model().index(row, 0), flags
                )
            self.assertEqual("Add 2 selected spells", dialog.add_button.text())
            dialog._accept()
            self.assertEqual(2, len(dialog.selected_entries))
        finally:
            dialog.close()

        single = TraditionalSpellCatalogDialog(("Wizard",), multi_select=False)
        try:
            self.assertEqual(
                QAbstractItemView.SelectionMode.SingleSelection,
                single.results.selectionMode(),
            )
            single._accept()
            self.assertEqual(1, len(single.selected_entries))
        finally:
            single.close()

    def test_archetype_checkboxes_are_clickable_and_update_selection(self) -> None:
        dialog = ArchetypeSelectionDialog("fighter")
        try:
            dialog.show()
            self.application.processEvents()
            self.assertGreater(dialog.results.rowCount(), 0)
            key = str(
                dialog.results.item(0, 0).data(Qt.ItemDataRole.UserRole)
            )
            checkbox = dialog.results.cellWidget(0, 0).findChild(QCheckBox)
            self.assertIsNotNone(checkbox)
            QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton)
            self.application.processEvents()
            self.assertTrue(checkbox.isChecked())
            self.assertIn(key, dialog.selected_keys)
            QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton)
            self.assertNotIn(key, dialog.selected_keys)
        finally:
            dialog.close()

    def test_incompatible_archetypes_are_disabled_and_grayed_live(self) -> None:
        dialog = ArchetypeSelectionDialog("alchemist")
        try:
            rows = {
                dialog.results.item(row, 1).text(): row
                for row in range(dialog.results.rowCount())
            }
            selected_row = rows["Aerochemist"]
            conflict_row = rows["Alchemical Sapper"]
            selected = dialog.results.cellWidget(selected_row, 0).findChild(QCheckBox)
            conflict = dialog.results.cellWidget(conflict_row, 0).findChild(QCheckBox)

            selected.click()
            self.application.processEvents()

            self.assertTrue(selected.isEnabled())
            self.assertFalse(conflict.isEnabled())
            self.assertIn("mutagen", conflict.toolTip().casefold())
            disabled_color = dialog.results.palette().color(
                dialog.results.palette().ColorGroup.Disabled,
                dialog.results.palette().ColorRole.Text,
            )
            self.assertEqual(
                disabled_color,
                dialog.results.item(conflict_row, 1).foreground().color(),
            )

            selected.click()
            self.application.processEvents()
            self.assertTrue(conflict.isEnabled())
        finally:
            dialog.close()

    def test_new_class_dialog_can_choose_and_retain_archetypes(self) -> None:
        dialog = ClassLevelDialog()
        try:
            dialog.preset.setCurrentIndex(dialog.preset.findData("fighter"))
            available = archetype_entries("fighter")
            self.assertTrue(available)
            self.assertTrue(dialog.choose_archetypes_button.isEnabled())
            self.assertIn(str(len(available)), dialog.choose_archetypes_button.toolTip())
            selected_key = str(available[0]["key"])
            with patch("app.ui.dialogs.ArchetypeSelectionDialog") as chooser:
                chooser.return_value.exec.return_value = QDialog.DialogCode.Accepted
                chooser.return_value.selected_keys = (selected_key,)
                dialog.choose_archetypes_button.click()
            self.assertEqual((selected_key,), dialog.archetype_keys)
            self.assertIn(str(available[0]["name"]), dialog.archetype_summary.text())
        finally:
            dialog.close()

    def test_class_dialog_projects_preselected_optional_archetype_exchange(self) -> None:
        champion_key = (
            "spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor"
        )
        champion = archetype_entry(champion_key)
        option = archetype_optional_features(champion)[0]
        class_level = ClassLevel(
            7, "Inquisitor", 5, "3/4", "Good", "Poor", "Good",
            "inquisitor", 8, 32,
        )
        dialog = ClassLevelDialog(
            class_level=class_level,
            selected_archetype_keys=(champion_key,),
            selected_optional_feature_keys=(option.key,),
        )
        try:
            self.assertIn(option.key, dialog.optional_exchange_checkboxes)
            self.assertTrue(dialog.optional_exchange_checkboxes[option.key].isChecked())
            self.assertEqual((option.key,), dialog.selected_optional_feature_keys)
            self.assertIn("monster lore", dialog.optional_exchange_checkboxes[option.key].toolTip().casefold())
        finally:
            dialog.close()

    def test_class_dialog_requires_and_retains_declarative_archetype_choice(self) -> None:
        exploitant_key = "spheres-archetype:prodigy:exploitant"
        exploitant = archetype_entry(exploitant_key)
        choice = archetype_choices(exploitant)[0]
        class_level = ClassLevel(
            8, "Prodigy", 2, "3/4", "Poor", "Good", "Good",
            "prodigy", 8, 13,
        )
        dialog = ClassLevelDialog(
            class_level=class_level,
            selected_archetype_keys=(exploitant_key,),
        )
        try:
            self.assertIn(choice.key, dialog.archetype_choice_widgets)
            dialog._accept_if_valid()
            self.assertNotEqual(QDialog.DialogCode.Accepted, dialog.result())
            combo = dialog.archetype_choice_widgets[choice.key][0]
            combo.setCurrentIndex(combo.findData("moldable-talents"))
            self.assertEqual(
                ("moldable-talents",), dialog.archetype_choice_values[choice.key]
            )
            dialog._accept_if_valid()
            self.assertEqual(QDialog.DialogCode.Accepted, dialog.result())
        finally:
            dialog.close()

    def test_optional_exchange_is_disabled_when_another_archetype_replaces_its_cost(self) -> None:
        champion_key = (
            "spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor"
        )
        abolisher_key = "pathfinder-archetype:pathfinder-class:inquisitor:abolisher"
        champion = archetype_entry(champion_key)
        option = archetype_optional_features(champion)[0]
        class_level = ClassLevel(
            7, "Inquisitor", 5, "3/4", "Good", "Poor", "Good",
            "inquisitor", 8, 32,
        )
        dialog = ClassLevelDialog(
            class_level=class_level,
            selected_archetype_keys=(champion_key, abolisher_key),
            selected_optional_feature_keys=(option.key,),
        )
        try:
            checkbox = dialog.optional_exchange_checkboxes[option.key]
            self.assertFalse(checkbox.isEnabled())
            self.assertFalse(checkbox.isChecked())
            self.assertEqual((), dialog.selected_optional_feature_keys)
            self.assertIn("abolisher", checkbox.toolTip().casefold())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()

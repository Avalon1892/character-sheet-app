import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QAbstractItemView, QDialog, QMessageBox

from app.content import trait_entry
from app.database import CharacterRepository
from app.ui.character_sheet import CharacterSheetWidget, TraitCatalogDialog
from app.ui.dialogs import FeatChoiceDialog, TraitDialog


class TraitCatalogUiTests(unittest.TestCase):
    def test_save_choice_traits_persist_and_edit_the_selected_saves(self) -> None:
        def choose_two(dialog):
            dialog.selection.setCurrentIndex(dialog.selection.findData("fortitude"))
            dialog.second_selection.setCurrentIndex(dialog.second_selection.findData("will"))
            return QDialog.DialogCode.Accepted

        with patch.object(FeatChoiceDialog, "exec", new=choose_two):
            self.assertTrue(self.sheet._add_catalog_trait(trait_entry("spheres-power:honor-the-fallen")))
        self.sheet._traits_changed()
        self.assertEqual((1, 0, 1), tuple(self.sheet._combat_results()[key].total for key in ("fortitude", "reflex", "will")))
        trait = self.repository.list_traits(self.character_id)[0]
        self.assertEqual("Fortitude / Will", trait.choice)
        editor = TraitDialog(self.sheet, trait)

        def change_two(dialog):
            dialog.selection.setCurrentIndex(dialog.selection.findData("reflex"))
            dialog.second_selection.setCurrentIndex(dialog.second_selection.findData("will"))
            return QDialog.DialogCode.Accepted

        with patch.object(FeatChoiceDialog, "exec", new=change_two):
            editor._choose_saves()
        self.repository.update_trait(self.character_id, trait.id, **editor.values)
        self.sheet._traits_changed()
        self.assertEqual((0, 1, 1), tuple(self.sheet._combat_results()[key].total for key in ("fortitude", "reflex", "will")))
        editor.close()

    def test_single_save_choice_and_cancel(self) -> None:
        entry = trait_entry("aon:soul-searcher-s-strength")
        with patch.object(FeatChoiceDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            self.assertFalse(self.sheet._add_catalog_trait(entry))
        self.assertEqual([], self.repository.list_traits(self.character_id))
        def choose(dialog):
            dialog.selection.setCurrentIndex(dialog.selection.findData("reflex"))
            return QDialog.DialogCode.Accepted
        with patch.object(FeatChoiceDialog, "exec", new=choose):
            self.assertTrue(self.sheet._add_catalog_trait(entry))
        self.sheet._traits_changed()
        self.assertEqual((0, 1, 0), tuple(self.sheet._combat_results()[key].total for key in ("fortitude", "reflex", "will")))

    def test_save_picker_requires_distinct_explicit_choices(self) -> None:
        dialog = FeatChoiceDialog("saving_throws_two", "Saving throws", [], [], self.sheet)
        with patch.object(QMessageBox, "warning") as warning:
            dialog._accept_if_valid()
            self.assertTrue(warning.called)
            for combo in (dialog.selection, dialog.second_selection):
                combo.setCurrentIndex(combo.findData("will"))
            dialog._accept_if_valid()
            self.assertEqual(2, warning.call_count)
        dialog.close()

    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "characters.db"
        self.repository = CharacterRepository(database_path)
        self.character_id = self.repository.create_character("Trait Hero", "Spheres")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temporary_directory.cleanup()

    def test_trait_browser_filters_all_three_sources_and_behavior(self) -> None:
        dialog = TraitCatalogDialog([], self.sheet)
        self.assertEqual(2105, dialog.results.rowCount())

        dialog.source_filter.setCurrentIndex(
            dialog.source_filter.findData("Pathfinder")
        )
        self.assertEqual(1975, dialog.results.rowCount())
        dialog.source_filter.setCurrentIndex(0)
        dialog.automation_filter.setCurrentIndex(
            dialog.automation_filter.findData("automatic")
        )
        self.assertEqual(436, dialog.results.rowCount())  # Three reviewed save-choice traits.
        dialog.automation_filter.setCurrentIndex(
            dialog.automation_filter.findData("toggle")
        )
        self.assertEqual(1, dialog.results.rowCount())
        dialog.close()

    def test_trait_browser_and_sheet_add_multiple_entries_in_one_batch(self) -> None:
        dialog = TraitCatalogDialog([], self.sheet)
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

        entries = (trait_entry("aon:reactionary"), trait_entry("aon:seeker"))
        added = self.sheet._add_catalog_batch(
            tuple(entry for entry in entries if entry is not None),
            self.sheet._add_catalog_trait,
            self.sheet._traits_changed,
            "traits",
        )
        self.assertEqual(2, added)
        self.assertEqual(2, len(self.repository.list_traits(self.character_id)))

    def test_catalog_traits_change_initiative_class_skills_and_toggled_saves(self) -> None:
        reactionary = trait_entry("aon:reactionary")
        self.assertIsNotNone(reactionary)
        self.assertTrue(self.sheet._add_catalog_trait(reactionary))
        self.sheet._traits_changed()
        self.assertEqual(2, self.sheet._combat_results()["initiative"].total)

        seeker = trait_entry("aon:seeker")
        self.assertIsNotNone(seeker)
        self.assertTrue(self.sheet._add_catalog_trait(seeker))
        self.sheet._traits_changed()
        perception_row = next(
            row
            for row in range(self.sheet.skill_table.rowCount())
            if self.sheet.skill_table.item(row, 0).text() == "Perception"
        )
        self.assertEqual("■", self.sheet.skill_table.item(perception_row, 1).text())
        self.assertEqual("+1", self.sheet.skill_table.item(perception_row, 2).text())

        courageous = trait_entry("aon:courageous")
        self.assertIsNotNone(courageous)
        self.assertTrue(self.sheet._add_catalog_trait(courageous))
        stored = next(
            trait
            for trait in self.repository.list_traits(self.character_id)
            if trait.catalog_key == "aon:courageous"
        )
        self.assertFalse(stored.enabled)
        self.assertEqual("toggle", stored.activation)
        self.repository.set_trait_enabled(self.character_id, stored.id, True)
        self.sheet._traits_changed()
        combat = self.sheet._combat_results()
        self.assertEqual(2, combat["fortitude"].total)
        self.assertEqual(2, combat["reflex"].total)
        self.assertEqual(2, combat["will"].total)


if __name__ == "__main__":
    unittest.main()

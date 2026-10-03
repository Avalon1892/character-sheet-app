from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from app.database import CharacterRepository
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.ui.dialogs import (
    FeatCatalogDialog,
    ItemCatalogDialog,
    MagicTalentCatalogDialog,
    MartialTalentCatalogDialog,
    TraitCatalogDialog,
)
from app.ui.theme import THEME_LABELS, style_sheet


class CatalogSelectionBasketUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        # Closing does not destroy parentless Qt dialogs. Dispose of them before
        # Python GC can collect wrapper cycles during the next widget constructor.
        for widget in self.application.topLevelWidgets():
            if isinstance(widget, QDialog):
                widget.close()
                widget.deleteLater()
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def _dialogs(self):
        return (
            FeatCatalogDialog([]),
            TraitCatalogDialog([]),
            MartialTalentCatalogDialog([]),
            MagicTalentCatalogDialog([]),
            ItemCatalogDialog(),
        )

    def test_all_five_catalogs_open_without_an_initial_entry_selection(self) -> None:
        dialogs = self._dialogs()
        try:
            for dialog in dialogs:
                with self.subTest(dialog=type(dialog).__name__):
                    self.assertEqual(-1, dialog.results.currentRow())
                    self.assertEqual(0, dialog.selection_basket.count)
                    self.assertFalse(dialog.add_button.isEnabled())
                    self.assertEqual("Add Selected (0)", dialog.add_button.text())
                    dialog._refresh_results() if hasattr(dialog, "_refresh_results") else dialog._refresh()
                    self.assertEqual(-1, dialog.results.currentRow())
        finally:
            for dialog in dialogs:
                dialog.close()

    def test_single_click_previews_double_click_and_enter_queue_without_duplicates(self) -> None:
        dialog = FeatCatalogDialog([])
        try:
            dialog.show()
            self.application.processEvents()
            dialog.results.setCurrentCell(0, 1)
            self.application.processEvents()
            self.assertEqual(0, dialog.selection_basket.count)
            self.assertEqual(dialog.results.item(0, 1).text(), dialog.detail_name.text())

            dialog.results.itemDoubleClicked.emit(dialog.results.item(0, 1))
            self.assertEqual(1, dialog.selection_basket.count)
            dialog.results.itemDoubleClicked.emit(dialog.results.item(0, 1))
            self.assertEqual(1, dialog.selection_basket.count)

            dialog.results.setFocus()
            QTest.keyClick(dialog.results, Qt.Key.Key_Return)
            self.assertEqual(1, dialog.selection_basket.count)
            self.assertEqual("Add Selected (1)", dialog.add_button.text())
        finally:
            dialog.close()

    def test_queue_persists_across_search_and_supports_remove_delete_and_clear(self) -> None:
        dialog = MartialTalentCatalogDialog([])
        try:
            for row in (0, 1, 2):
                dialog.results.setCurrentCell(row, 1)
                dialog._queue_current_entry()
            self.assertEqual(3, dialog.selection_basket.count)

            dialog.search.setText("no catalog entry can possibly match this phrase")
            dialog.search_debounce.flush()
            self.assertEqual(0, dialog.results.rowCount())
            self.assertEqual(3, dialog.selection_basket.count)

            dialog.selection_basket.list_widget.setCurrentRow(0)
            dialog.selection_basket.remove_button.click()
            self.assertEqual(2, dialog.selection_basket.count)
            dialog.selection_basket.list_widget.setCurrentRow(0)
            QTest.keyClick(
                dialog.selection_basket.list_widget, Qt.Key.Key_Delete
            )
            self.assertEqual(1, dialog.selection_basket.count)
            dialog.selection_basket.clear_button.click()
            self.assertEqual(0, dialog.selection_basket.count)
            self.assertFalse(dialog.selection_basket.remove_button.isEnabled())
            self.assertFalse(dialog.selection_basket.clear_button.isEnabled())
        finally:
            dialog.close()

    def test_escape_rejects_without_confirming_the_queue(self) -> None:
        dialog = TraitCatalogDialog([])
        try:
            dialog.results.setCurrentCell(0, 1)
            dialog._queue_current_entry()
            dialog.show()
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
            self.assertEqual(QDialog.DialogCode.Rejected, dialog.result())
            self.assertEqual((), dialog.selected_entries)
        finally:
            dialog.close()

    def test_item_queue_survives_filtering_and_converts_every_confirmed_entry(self) -> None:
        dialog = ItemCatalogDialog()
        try:
            for row in (0, 1):
                dialog.results.setCurrentCell(row, 0)
                dialog._queue_current_entry()
            queued_keys = tuple(entry["key"] for entry in dialog.selection_basket.entries)
            self.assertEqual(2, len(queued_keys))
            dialog.search.setText("no item has this exact impossible name")
            dialog.search_debounce.flush()
            self.assertEqual(queued_keys, tuple(
                entry["key"] for entry in dialog.selection_basket.entries
            ))
            dialog._accept_selected()
            self.assertEqual(2, len(dialog.selected_entries))
            self.assertTrue(all(dialog.values_for_entry(entry)["name"] for entry in dialog.selected_entries))
        finally:
            dialog.close()

    def test_item_queue_accumulates_and_removes_quantities(self) -> None:
        dialog = ItemCatalogDialog()
        try:
            dialog.results.setCurrentCell(0, 0)
            item = dialog.results.item(0, 0)
            dialog.results.itemDoubleClicked.emit(item)
            dialog.results.itemDoubleClicked.emit(item)
            self.assertEqual(2, dialog.selection_basket.count)
            self.assertEqual(1, len(dialog.selection_basket.entries))

            with patch(
                "app.ui.dialogs.QApplication.keyboardModifiers",
                return_value=Qt.KeyboardModifier.ControlModifier,
            ):
                dialog._queue_from_modified_click()
            self.assertEqual(12, dialog.selection_basket.count)

            with patch(
                "app.ui.dialogs.QApplication.keyboardModifiers",
                return_value=Qt.KeyboardModifier.ShiftModifier,
            ), patch.object(
                dialog.selection_basket, "prompt_quantity", return_value=7
            ):
                dialog._queue_from_modified_click()
            self.assertEqual(19, dialog.selection_basket.count)
            self.assertEqual("Add Selected (19)", dialog.add_button.text())

            dialog.selection_basket.list_widget.setCurrentRow(0)
            queued = dialog.selection_basket.list_widget.currentItem()
            dialog.selection_basket._double_click_remove(queued)
            self.assertEqual(18, dialog.selection_basket.count)
            with patch(
                "app.ui.components.QApplication.keyboardModifiers",
                return_value=Qt.KeyboardModifier.ControlModifier,
            ):
                dialog.selection_basket._modified_remove_click(queued)
            self.assertEqual(8, dialog.selection_basket.count)
            with patch(
                "app.ui.components.QApplication.keyboardModifiers",
                return_value=Qt.KeyboardModifier.ShiftModifier,
            ), patch.object(
                dialog.selection_basket, "prompt_quantity", return_value=3
            ):
                dialog.selection_basket._modified_remove_click(queued)
            self.assertEqual(5, dialog.selection_basket.count)
            selected = dialog.selection_basket.selection_entries[0]
            self.assertEqual(5, dialog.values_for_entry(selected)["quantity"])
            self.assertIn("×5", dialog.selection_basket.list_widget.item(0).text())
        finally:
            dialog.close()

    def test_batch_reports_cancelled_choices_but_keeps_success_and_refreshes_once(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        repository = CharacterRepository(Path(temporary_directory.name) / "characters.db")
        character_id = repository.create_character("Batch Hero", "Pathfinder 1e")
        sheet = CharacterSheetWidget(repository)
        sheet.load_character(character_id)
        try:
            refresh = Mock()
            added_names: list[str] = []

            def add_one(entry: dict) -> bool:
                if entry["name"] == "Needs Choice":
                    return False
                added_names.append(entry["name"])
                return True

            with patch("app.ui.character_sheet.QMessageBox.warning") as warning:
                added = sheet._add_catalog_batch(
                    ({"name": "Valid"}, {"name": "Needs Choice"}),
                    add_one,
                    refresh,
                    "entries",
                )
            self.assertEqual(1, added)
            self.assertEqual(["Valid"], added_names)
            refresh.assert_called_once_with()
            warning.assert_called_once()
            self.assertIn("Needs Choice", warning.call_args.args[2])
        finally:
            sheet.close()
            repository.close()
            temporary_directory.cleanup()

    def test_item_confirmation_inserts_the_whole_batch_with_one_final_refresh(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        repository = CharacterRepository(Path(temporary_directory.name) / "characters.db")
        character_id = repository.create_character("Item Batch Hero", "Pathfinder 1e")
        sheet = CharacterSheetWidget(repository)
        sheet.load_character(character_id)

        class FakeItemCatalog:
            custom_requested = False
            selected_entries = (
                {"key": "test:first", "name": "First item"},
                {"key": "test:second", "name": "Second item"},
            )
            selected_entry = selected_entries[0]

            def __init__(fake_self, _parent):
                pass

            def exec(fake_self):
                return QDialog.DialogCode.Accepted

            @staticmethod
            def values_for_entry(entry: dict) -> dict:
                return {
                    "name": entry["name"], "category": "Gear", "quantity": 1,
                    "weight": 0.0, "equipped": False, "ac_bonus": 0,
                    "bonus_type": "untyped", "max_dex_bonus": None,
                    "armor_check_penalty": 0, "notes": "", "slot": "",
                    "value_gp": 0.0, "catalog_key": entry["key"],
                    "catalog_source": "Test", "state": "stored",
                    "choices_json": "{}", "automation_json": "",
                    "enhancement_bonus": 0, "masterwork": False,
                    "weapon_damage_dice": "", "weapon_damage_type": "",
                    "weapon_critical": "", "weapon_range": "",
                }

        try:
            with patch(
                "app.ui.character_sheet.ItemCatalogDialog", FakeItemCatalog
            ), patch.object(
                sheet, "_refresh_calculation_views"
            ) as refresh:
                sheet._add_equipment()
            self.assertEqual(
                ["First item", "Second item"],
                [item.name for item in repository.list_equipment(character_id)],
            )
            refresh.assert_called_once()
        finally:
            sheet.close()
            repository.close()
            temporary_directory.cleanup()

    def test_selection_basket_layout_is_usable_in_every_theme(self) -> None:
        for theme in THEME_LABELS:
            with self.subTest(theme=theme):
                dialog = FeatCatalogDialog([])
                try:
                    dialog.setStyleSheet(style_sheet(theme))
                    dialog.show()
                    self.application.processEvents()
                    self.assertGreaterEqual(dialog.width(), 1600)
                    self.assertGreaterEqual(dialog.selection_basket.width(), 290)
                    self.assertTrue(dialog.selection_basket.isVisible())
                    self.assertGreater(dialog.results.width(), dialog.selection_basket.width())
                finally:
                    dialog.close()

    def test_single_replacement_mode_cannot_queue_multiple_entries(self) -> None:
        dialog = FeatCatalogDialog([], selection_limit=1)
        try:
            first, second = dialog._entries[:2]
            self.assertTrue(dialog.selection_basket.add_entry(first))
            self.assertFalse(dialog.selection_basket.add_entry(second))
            self.assertEqual(1, dialog.selection_basket.count)
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()

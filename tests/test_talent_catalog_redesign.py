import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractItemView, QLabel, QPushButton

from app.ui.dialogs import MartialTalentCatalogDialog, MagicTalentCatalogDialog
from app.ui.dialog_theme import dialog_stylesheet


class TalentCatalogRedesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_both_catalogs_readable_and_queue_survives_filters(self):
        for factory in (MartialTalentCatalogDialog, MagicTalentCatalogDialog):
            for theme in ("classic", "dark"):
                dialog = factory([])
                try:
                    dialog.setStyleSheet(dialog_stylesheet(theme))
                    dialog.resize(1100, 720)
                    dialog.show()
                    QTest.qWait(100)
                    self.assertLessEqual(dialog.automation_filter.geometry().right(), dialog.width())
                    self.assertLess(dialog.search.geometry().right(), dialog.category.geometry().left())
                    self.assertEqual(-1, dialog.results.currentRow())
                    self.assertEqual("", dialog.detail_description.text())
                    self.assertIsInstance(dialog.detail_description, QLabel)
                    self.assertIs(dialog.details_scroll.widget(), dialog.detail_description.parentWidget())
                    self.assertEqual(QAbstractItemView.EditTrigger.NoEditTriggers, dialog.results.editTriggers())
                    dialog.results.setCurrentCell(0, 1)
                    self.assertTrue(dialog.detail_description.text())
                    self.assertEqual(0, dialog.selection_basket.count)
                    dialog.results.itemDoubleClicked.emit(dialog.results.item(0, 1))
                    QTest.keyClick(dialog.results, Qt.Key.Key_Return)
                    self.assertEqual(1, dialog.selection_basket.count)
                    self.assertIn("Queued", dialog.results.item(0, 1).text())
                    dialog.sphere_list.setCurrentRow(1)
                    dialog.catalog_presentation.refresh()
                    self.assertTrue(dialog.results.isColumnHidden(3))
                    dialog.search.setText("nothing will match this talent name")
                    dialog.search_debounce.flush()
                    self.assertEqual(0, dialog.results.rowCount())
                    self.assertEqual(1, dialog.selection_basket.count)
                    dialog._clear_filters()
                    self.assertFalse(dialog.results.isColumnHidden(3))
                    self.assertEqual(-1, dialog.results.currentRow())
                    queued = dialog.selection_basket.list_widget.item(0)
                    remove = dialog.selection_basket.list_widget.itemWidget(queued).findChild(QPushButton)
                    remove.click()
                    self.assertEqual(0, dialog.selection_basket.count)
                    self.assertFalse(dialog.add_button.isEnabled())
                    dialog.reject()
                    self.assertEqual((), dialog.selected_entries)
                finally:
                    dialog.close()
                    dialog.deleteLater()
                    self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_name_only_search_and_explicit_rules_search(self):
        for factory in (MartialTalentCatalogDialog, MagicTalentCatalogDialog):
            dialog = factory([])
            try:
                dialog.search.setText("you can")
                dialog.search_debounce.flush()
                name_count = dialog.results.rowCount()
                dialog.include_rules.setChecked(True)
                self.assertGreater(dialog.results.rowCount(), name_count)
                dialog.available_only.setChecked(True)
                self.assertTrue(all(
                    dialog._availability(dialog._entries_by_key[dialog.results.item(row, 0).data(Qt.ItemDataRole.UserRole)]).startswith(("No known", "Unknown:"))
                    for row in range(dialog.results.rowCount())))
            finally:
                dialog.close()
                dialog.deleteLater()
                self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

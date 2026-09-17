import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QRect, QEvent
from PySide6.QtGui import QPalette, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QPushButton, QDialog, QTextBrowser, QVBoxLayout
from app.ui.dialog_layout import apply_dialog_layout, ReadableDialogTable
from app.ui.dialog_theme import dialog_stylesheet, style_dialog_links
from app.ui.dialogs import AttackDialog, EquipmentDialog, FeatCatalogDialog, TraditionalSpellCatalogDialog
from app.ui.refined.theme import PALETTES


class DialogLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def polish(self, dialog, theme='classic', width=1440):
        dialog.setStyleSheet(dialog_stylesheet(theme))
        with patch.object(dialog, 'screen', return_value=SimpleNamespace(availableGeometry=lambda: QRect(0, 0, width, 960))):
            apply_dialog_layout(dialog)
        dialog.show()
        QTest.qWait(180)
        self.addCleanup(self.dispose, dialog)
        return dialog

    def dispose(self, dialog):
        dialog.close()
        dialog.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_initial_size_respects_screen_and_later_manual_resize(self):
        dialog = self.polish(AttackDialog(), width=1200)
        self.assertLessEqual(dialog.width(), 1152)
        dialog.resize(1110, 760)
        apply_dialog_layout(dialog)
        self.assertEqual(1110, dialog.width())
        self.assertEqual(760, dialog.height())

    def test_numeric_fields_do_not_stretch_to_fill_their_parent(self):
        dialog = self.polish(AttackDialog())
        self.assertEqual(QSizePolicy.Policy.Fixed, dialog.attack_bonus.sizePolicy().verticalPolicy())
        self.assertLess(dialog.attack_bonus.height(), 60)
        self.assertEqual(0, dialog.attack_bonus.value())

    def test_dense_item_form_remains_accessible_without_clipping_buttons(self):
        dialog = self.polish(EquipmentDialog())
        scroll = dialog.item_editor_splitter.widget(0)
        self.assertIsInstance(scroll, QScrollArea)
        self.assertTrue(scroll.widgetResizable())
        scroll.ensureWidgetVisible(dialog.notes)
        self.app.processEvents()
        self.assertGreater(scroll.verticalScrollBar().value(), 0)
        self.assertIs(dialog.notes.window(), dialog)
        self.assertEqual(1, dialog.quantity.value())

    def test_catalog_names_keep_space_without_auto_selection_or_queue(self):
        dialog = self.polish(FeatCatalogDialog([]), width=1100)
        dialog.catalog_presentation.refresh()
        self.assertGreaterEqual(dialog.results.columnWidth(1), 270)
        self.assertEqual(-1, dialog.results.currentRow())
        self.assertEqual(0, dialog.selection_basket.count)
        self.assertTrue(dialog.catalog_presentation._responsive_hidden)
        QTest.qWait(180)
        self.assertFalse(dialog.catalog_presentation.timer.isActive())

    def test_all_themes_override_the_legacy_dark_catalog_sidebar(self):
        for theme in ('classic', 'light', 'dark'):
            dialog = self.polish(FeatCatalogDialog([]), theme)
            self.assertEqual(QColor(PALETTES[theme].surface), dialog.category_list.palette().color(QPalette.ColorRole.Base))

    def test_read_only_table_wrapping_is_bounded_and_keeps_selection(self):
        dialog = self.polish(TraditionalSpellCatalogDialog())
        table = dialog.results
        table.setCurrentCell(2, 0)
        adapter = dialog._readable_tables[0]
        with patch.object(table, 'resizeRowToContents', wraps=table.resizeRowToContents) as resize:
            adapter.fit()
            self.assertLessEqual(resize.call_count, 45)
        self.assertEqual(2, table.currentRow())
        self.assertTrue(table.wordWrap())
        adapter.schedule()  # Cleanup with a pending callback must remain safe.

    def test_embedded_action_buttons_fit_in_table_rows(self):
        table = QTableWidget(1, 1)
        table.setItem(0, 0, QTableWidgetItem('Resolve'))
        button = QPushButton('Resolve this issue')
        button.setMinimumHeight(48)
        table.setCellWidget(0, 0, button)
        table.show()
        self.app.processEvents()
        adapter = ReadableDialogTable(table)
        adapter.fit()
        self.assertGreaterEqual(table.rowHeight(0), button.minimumSizeHint().height() + 6)
        table.close(); table.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_existing_and_future_description_links_use_theme_color(self):
        dialog = QDialog()
        browser = QTextBrowser()
        QVBoxLayout(dialog).addWidget(browser)
        self.addCleanup(self.dispose, dialog)
        browser.setHtml('<a href="https://example.com">Rules</a>')
        for theme in ('classic', 'light', 'dark'):
            color = PALETTES[theme].accent
            style_dialog_links(dialog, color)
            fragment = browser.document().begin().begin().fragment()
            self.assertEqual(QColor(color), fragment.charFormat().foreground().color())
            self.assertEqual('https://example.com', fragment.charFormat().anchorHref())
            browser.setHtml('<a href="https://example.com">Next rules</a>')
            fragment = browser.document().begin().begin().fragment()
            self.assertEqual(QColor(color), fragment.charFormat().foreground().color())


if __name__ == '__main__':
    unittest.main()

import os
import unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QStyleOptionViewItem
from app.ui.refined.item_colors import RefinedItemDelegate
from app.ui.refined.theme import PALETTES, stylesheet


def luminance(color):
    channels = QColor(color).getRgbF()[:3]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))


class RefinedColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_text_contrast_on_every_semantic_surface(self):
        for theme, p in PALETTES.items():
            for fg in (p.text, p.muted):
                for bg in (p.page, p.surface, p.magic, p.martial, p.selection):
                    bright, dark = sorted((luminance(fg), luminance(bg)), reverse=True)
                    self.assertGreaterEqual((bright + .05) / (dark + .05), 4.5, (theme, fg, bg))

    def test_legacy_roles_are_themed_without_changing_records_or_custom_colors(self):
        table = QTableWidget(3, 1)
        for row, color in enumerate(("#DAE9F8", "#FBE2D5", "#8060AA")):
            item = QTableWidgetItem("Talent")
            item.setBackground(QColor(color))
            item.setForeground(QColor("#252C35"))
            table.setItem(row, 0, item)
        try:
            delegate = RefinedItemDelegate(table, lambda: "dark")
            for row, expected in enumerate((PALETTES["dark"].magic, PALETTES["dark"].martial, "#8060AA")):
                before = table.item(row, 0).background()
                option = QStyleOptionViewItem()
                delegate.initStyleOption(option, table.model().index(row, 0))
                self.assertEqual(expected.lower(), option.backgroundBrush.color().name())
                self.assertEqual(PALETTES["dark"].text.lower(), option.palette.color(QPalette.ColorRole.Text).name())
                self.assertEqual(before, table.item(row, 0).background())
        finally:
            table.deleteLater()
            self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_selection_and_empty_tables_do_not_inherit_legacy_highlights(self):
        for theme, p in PALETTES.items():
            css = stylesheet(theme)
            self.assertIn("QTableWidget::item:selected", css)
            self.assertNotIn('QTableWidget[refinedCategory="martial"] { background:', css)
            self.assertIn("QComboBox QAbstractItemView", css)

    def test_painted_semantic_and_custom_colors_survive_stylesheets(self):
        for theme, p in PALETTES.items():
            table = QTableWidget(3, 1)
            table.setProperty("refinedCategory", "martial")
            table.setStyleSheet(stylesheet(theme))
            table.setItemDelegate(RefinedItemDelegate(table, lambda theme=theme: theme))
            table.setColumnWidth(0, 200)
            table.resize(260, 230)
            for row, color in enumerate(("#DAE9F8", "#FBE2D5", "#8060AA")):
                item = QTableWidgetItem("")
                item.setBackground(QColor(color))
                table.setItem(row, 0, item)
            table.show()
            table.clearSelection()
            table.setCurrentItem(None)
            self.app.processEvents()
            picture = table.viewport().grab().toImage()
            for row, expected in enumerate((p.magic, p.martial, "#8060AA")):
                point = table.visualItemRect(table.item(row, 0)).center()
                self.assertEqual(QColor(expected), picture.pixelColor(point), (theme, row))
            table.close()
            table.deleteLater()
            self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    unittest.main()

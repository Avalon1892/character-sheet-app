import os, unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget, QDialog, QLabel, QVBoxLayout, QTableWidget, QTableWidgetItem, QStyleOptionViewItem
from app.ui.dialog_theme import DialogThemeBoundary, DialogItemDelegate, dialog_stylesheet
from app.ui.refined.theme import PALETTES, stylesheet
from app.ui.sphere_colors import sphere_surface, style_sphere_group
from tests.test_refined_colors import luminance


class DialogColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_child_and_nested_dialogs_have_an_opaque_theme_boundary(self):
        owner=QWidget();sheet=QWidget(owner)
        boundary=DialogThemeBoundary(owner)
        first=QDialog(sheet);nested=QDialog(first)
        label=QLabel('Readable rules',nested);QVBoxLayout(nested).addWidget(label)
        for theme in PALETTES:
            owner.theme=theme;sheet.setStyleSheet(stylesheet(theme))
            boundary.apply(first);boundary.apply(nested)
            nested.resize(240,100);nested.show();self.app.processEvents()
            self.assertIn(dialog_stylesheet(theme),nested.styleSheet())
            color=nested.grab().toImage().pixelColor(2,2)
            self.assertEqual(255,color.alpha())
            self.assertNotEqual('#000000',color.name())
            fg=label.palette().color(QPalette.ColorRole.WindowText)
            bright,dark=sorted((luminance(fg),luminance(color)),reverse=True)
            self.assertGreaterEqual((bright+.05)/(dark+.05),4.5)
        original=nested.styleSheet();boundary.apply(nested)
        self.assertEqual(original,nested.styleSheet())
        owner.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_unrelated_dialogs_are_not_restyled(self):
        owner=QWidget();owner.theme='dark';other=QDialog()
        DialogThemeBoundary(owner).apply(other)
        self.assertEqual('',other.styleSheet())
        owner.deleteLater();other.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_catalog_status_ink_is_readable_and_keeps_data(self):
        table=QTableWidget(3,1)
        for row,color in enumerate(('#008000','#808000','#800000')):
            item=QTableWidgetItem('Status');item.setForeground(QColor(color));table.setItem(row,0,item)
        delegate=DialogItemDelegate(table,lambda:'dark')
        for row in range(3):
            before=table.item(row,0).foreground()
            option=QStyleOptionViewItem();delegate.initStyleOption(option,table.model().index(row,0))
            fg=option.palette.color(QPalette.ColorRole.Text)
            bright,dark=sorted((luminance(fg),luminance('#272c30')),reverse=True)
            self.assertGreaterEqual((bright+.05)/(dark+.05),4.5)
            self.assertEqual(before,table.item(row,0).foreground())
        table.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_sphere_hues_are_stable_distinct_and_readable(self):
        for theme,p in PALETTES.items():
            for kind in ('magic','martial'):
                colors=set()
                for sphere in ('Athletics','Boxing','Equipment','Open Hand','Warp','Weather','Alteration'):
                    color=sphere_surface(kind,sphere,theme,getattr(p,kind));colors.add(color)
                    self.assertEqual(color,sphere_surface(kind,sphere.upper(),theme,getattr(p,kind)))
                    bright,dark=sorted((luminance(p.text),luminance(color)),reverse=True)
                    self.assertGreaterEqual((bright+.05)/(dark+.05),4.5)
                self.assertGreater(len(colors),3)

if __name__=='__main__':unittest.main()

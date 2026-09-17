import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QDialog,QVBoxLayout,QLineEdit,QPushButton
from app.ui.search_navigation import install_search_shortcut


class SearchNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_ctrl_f_focuses_and_selects_search_without_changing_the_query(self):
        dialog=QDialog();layout=QVBoxLayout(dialog)
        search=QLineEdit('existing query');button=QPushButton('Other action')
        layout.addWidget(search);layout.addWidget(button)
        shortcut=install_search_shortcut(dialog,search)
        try:
            dialog.show();dialog.activateWindow();button.setFocus();QTest.qWait(50)
            QTest.keyClick(button,Qt.Key.Key_F,Qt.KeyboardModifier.ControlModifier)
            self.assertTrue(search.hasFocus())
            self.assertEqual('existing query',search.selectedText())
            self.assertEqual(Qt.ShortcutContext.WindowShortcut,shortcut.context())
        finally:
            dialog.close();dialog.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_dynamic_page_lookup_ignores_pages_without_search(self):
        dialog=QDialog();layout=QVBoxLayout(dialog)
        first=QLineEdit('first');second=QLineEdit('second')
        layout.addWidget(first);layout.addWidget(second)
        current=[first];shortcut=install_search_shortcut(dialog,lambda:current[0])
        try:
            dialog.show();self.app.processEvents()
            shortcut.activated.emit();self.assertEqual('first',first.selectedText())
            current[0]=second;shortcut.activated.emit();self.assertEqual('second',second.selectedText())
            current[0]=None;shortcut.activated.emit()
            self.assertEqual('first',first.text());self.assertEqual('second',second.text())
        finally:
            dialog.close();dialog.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

if __name__=='__main__':unittest.main()

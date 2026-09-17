import os, unittest, gc, io
from contextlib import redirect_stderr
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt,QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QSplitter
from app.ui.dialogs import FeatCatalogDialog,TraitCatalogDialog,MartialTalentCatalogDialog,MagicTalentCatalogDialog,ItemCatalogDialog


class CatalogPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def tearDown(self):self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_five_catalogs_have_resizable_panels_and_no_initial_queue(self):
        for factory in (lambda:FeatCatalogDialog([]),lambda:TraitCatalogDialog([]),lambda:MartialTalentCatalogDialog([]),lambda:MagicTalentCatalogDialog([]),ItemCatalogDialog):
            dialog=factory()
            try:
                dialog.resize(1400,900);dialog.show();QTest.qWait(120)
                presentation=dialog.catalog_presentation
                self.assertIsInstance(presentation.splitter,QSplitter)
                self.assertFalse(presentation.splitter.childrenCollapsible())
                self.assertEqual(Qt.TextElideMode.ElideNone,dialog.results.textElideMode())
                self.assertEqual(0,dialog.selection_basket.count)
                self.assertEqual(-1,dialog.results.currentRow())
                self.assertTrue(dialog.results.verticalHeader().isHidden())
                self.assertTrue(dialog.search.isClearButtonEnabled())
                self.assertFalse(presentation.timer.isActive())
                presentation.search_shortcut.activated.emit()
                self.assertTrue(dialog.search.hasFocus())
            finally:dialog.close();dialog.deleteLater()

    def test_preview_hides_empty_metadata_then_restores_real_details(self):
        dialog=FeatCatalogDialog([])
        try:
            dialog.show();QTest.qWait(120)
            self.assertTrue(dialog.detail_automation.isHidden())
            self.assertTrue(dialog.detail_prerequisites.isHidden())
            dialog.results.setCurrentCell(0,1);QTest.qWait(120)
            self.assertFalse(dialog.detail_automation.isHidden())
            self.assertFalse(dialog.detail_meta.isHidden())
            self.assertIn('<style>',dialog.detail_source.text())
            original=dialog.detail_source.text()
            dialog.catalog_presentation.refresh()
            self.assertEqual(original,dialog.detail_source.text())
            dialog.results.itemDoubleClicked.emit(dialog.results.item(0,1))
            dialog.search.setText('nothing-will-match-this-catalog-query');QTest.qWait(120)
            self.assertTrue(dialog.detail_automation.isHidden())
            self.assertEqual(1,dialog.selection_basket.count)
        finally:dialog.close();dialog.deleteLater()

    def test_wrapping_sizes_only_visible_rows_not_the_entire_catalog(self):
        dialog=FeatCatalogDialog([])
        try:
            dialog.resize(1400,900);dialog.show();QTest.qWait(120)
            table=dialog.results
            table.item(0,1).setText('A long feat name that remains fully readable while browsing '+('additional words '*12))
            with patch.object(table,'resizeRowToContents',wraps=table.resizeRowToContents) as resize:
                dialog.catalog_presentation.refresh()
                self.assertLess(resize.call_count,50)
                self.assertGreater(table.rowHeight(0),32)
            self.assertGreater(table.rowCount(),1000)
            QTest.qWait(150)
            self.assertFalse(dialog.catalog_presentation.timer.isActive())
        finally:dialog.close();dialog.deleteLater()

    def test_pending_layout_callbacks_are_safe_during_close_and_cleanup(self):
        errors=io.StringIO()
        with redirect_stderr(errors):
            for _ in range(2):
                dialog=FeatCatalogDialog([]);dialog.show();self.app.processEvents()
                dialog.catalog_presentation.schedule()
                dialog.close();dialog.deleteLater();del dialog
                self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
                gc.collect();self.app.processEvents()
        self.assertEqual('',errors.getvalue())

if __name__=='__main__':unittest.main()

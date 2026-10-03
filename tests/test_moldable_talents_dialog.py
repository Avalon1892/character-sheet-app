import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from PySide6.QtTest import QTest
from app.content import martial_entry, magic_entry, martial_entries
from app.ui.moldable_talents_dialog import MoldableTalentsDialog
from tests import test_exploitant_moldable_talents as fixtures


class MoldableDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.fixture=fixtures.ExploitantMoldableTalentTests()
        self.fixture.setUp()
        self.repo=self.fixture.repository;self.cid=self.fixture.character
        self.dialog=MoldableTalentsDialog(self.repo,self.cid,3)
        self.dialog.show();self.app.processEvents()

    def tearDown(self):
        self.dialog.close();self.dialog.deleteLater()
        self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.fixture.tearDown()

    def record(self,key,kind="martial"):
        return self.fixture._record(martial_entry(key) if kind=="martial" else magic_entry(key),kind)

    def place(self,key):
        entry={**martial_entry(key),"talent_kind":"martial"}
        with patch.object(self.dialog,"_current_entry",return_value=entry):self.dialog._place_current()

    def test_replacement_and_clear_preserve_unrelated_later_slots(self):
        d=self.dialog
        d.selections=[self.record("boxing:base"),self.record("warp:base","magic"),self.record("duelist:base")]
        d._refresh_slots();d.slots.setCurrentCell(0,1)
        self.place("berserker:base")
        self.assertEqual(["berserker:base","warp:base","duelist:base"],[r["catalog_key"] for r in d.selections])
        d.slots.setCurrentCell(1,1);d._clear_slot()
        self.assertEqual(["berserker:base","duelist:base"],[r["catalog_key"] for r in d.selections])

    def test_invalid_dependency_removal_is_atomic(self):
        d=self.dialog
        talent=next(e for e in martial_entries("Boxing") if e["category"] not in ("Base Sphere","Drawback"))
        d.selections=[self.record("boxing:base"),self.fixture._record(talent,"martial"),self.record("warp:base","magic")]
        original=list(d.selections);d._refresh_slots();d.slots.setCurrentCell(0,1)
        with patch.object(QMessageBox,"information") as warning:
            d._clear_slot()
            self.assertTrue(warning.called)
        self.assertEqual(original,d.selections)

    def test_empty_target_maps_to_next_slot_and_cancel_writes_nothing(self):
        d=self.dialog;before=self.repo.sqlite_connection.total_changes
        self.assertEqual(-1,d.results.currentRow())
        self.assertFalse(d.use_button.isEnabled())
        d.slots.setCurrentCell(2,1)
        self.place("boxing:base")
        self.assertEqual(1,len(d.selections))
        self.assertEqual(1,d.slots.currentRow())
        d.reject()
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)

    def test_enter_stages_without_accepting_and_search_is_debounced(self):
        d=self.dialog
        d.search.setText("Boxing");self.assertTrue(d.search_timer.isActive())
        self.assertEqual(400,d.search_timer.interval())
        QTest.qWait(520)
        self.assertEqual(-1,d.results.currentRow())
        row=next(r for r in range(d.results.rowCount()) if d.results.item(r,0).data(Qt.ItemDataRole.UserRole)==("martial","boxing:base"))
        d.results.setCurrentCell(row,0);d.results.setFocus()
        QTest.keyClick(d.results,Qt.Key.Key_Return)
        self.assertEqual(1,len(d.selections))
        self.assertEqual(0,d.result())
        d.search.setText("Warp");QTest.qWait(520)
        self.assertEqual("boxing:base",d.selections[0]["catalog_key"])
        self.assertLessEqual(d.results.rowCount(),350)

    def test_tinker_package_picker_excludes_earlier_staged_packages(self):
        d=self.dialog
        base=self.record("tinker:base");base["choice"]="Augmentation"
        expanded=self.record("tinker:talent:expanded-tinkering");expanded["choice"]="Computation / Modification"
        d.selections=[base,expanded];d._refresh_slots();d.slots.setCurrentCell(2,1)
        before=self.repo.sqlite_connection.total_changes
        entry={**martial_entry("tinker:talent:expanded-tinkering"),"talent_kind":"martial"}
        with patch("app.ui.dialogs.FeatChoiceDialog") as picker:
            picker.return_value.exec.return_value=QDialog.DialogCode.Rejected
            self.assertIsNone(d._selection_record(entry))
            self.assertEqual(frozenset({"Augmentation","Computation","Modification"}),picker.call_args.kwargs["excluded_choices"])
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)

    def test_locked_slots_disable_removal(self):
        d=self.dialog;d.selections=[self.record("boxing:base")];d.locked_count=1
        d._refresh_slots();d.slots.setCurrentCell(0,1)
        self.assertFalse(d.clear_button.isEnabled())
        self.assertFalse(d.clear_all_button.isEnabled())
        d._clear_all();self.assertEqual(1,len(d.selections))


if __name__=="__main__":unittest.main()

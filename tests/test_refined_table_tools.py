import os
import unittest
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
from PySide6.QtCore import Qt, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
from app.ui.refined.components import TablePresentation
from app.ui.refined.table_tools import PageSearchBar, skill_filter_choice


class RefinedTableToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.root=QWidget();layout=QVBoxLayout(self.root)
        self.skills=QTableWidget(3,5)
        self.skills.setHorizontalHeaderLabels(("Skill","Class","Bonus","Ability","Ranks"))
        for row,values in enumerate((("Acrobatics","■","+8","DEX","5"),
                                     ("Climb","□","+2","STR","0"),
                                     ("Craft","■","+3","INT","2"))):
            for column,value in enumerate(values):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row+10)
                self.skills.setItem(row,column,item)
        self.features=QTableWidget(2,1)
        self.features.setHorizontalHeaderLabels(("Ability",))
        for row,value in enumerate(("Spellcasting","Bonus feat")):
            self.features.setItem(row,0,QTableWidgetItem(value))
        self.skill_adapter=TablePresentation(self.skills,self.root)
        self.feature_adapter=TablePresentation(self.features,self.root)
        self.owned=[self.skill_adapter,self.feature_adapter]
        self.bar=PageSearchBar(lambda:self.owned)
        self.choice=skill_filter_choice(self.skill_adapter)
        self.bar.add_filter(self.choice)
        layout.addWidget(self.bar);layout.addWidget(self.skills);layout.addWidget(self.features)
        self.root.resize(900,600);self.root.show();QTest.qWait(150)

    def tearDown(self):
        self.root.close();self.root.deleteLater()
        self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def visible(self,table):
        return [table.item(r,0).text() for r in range(table.rowCount()) if not table.isRowHidden(r)]

    def test_skill_filters_use_live_displayed_values_without_touching_features(self):
        before=[self.skills.item(r,0).data(Qt.ItemDataRole.UserRole) for r in range(3)]
        self.choice.setCurrentText("With ranks");QTest.qWait(150)
        self.assertEqual(["Acrobatics","Craft"],self.visible(self.skills))
        self.assertEqual(["Spellcasting","Bonus feat"],self.visible(self.features))
        self.assertEqual("2 skills",self.bar.feedback.text())
        self.skills.item(1,4).setText("3");QTest.qWait(150)
        self.assertEqual(3,len(self.visible(self.skills)))
        self.choice.setCurrentText("Class skills");QTest.qWait(150)
        self.assertEqual(["Acrobatics","Craft"],self.visible(self.skills))
        self.assertEqual(before,[self.skills.item(r,0).data(Qt.ItemDataRole.UserRole) for r in range(3)])

    def test_search_is_debounced_counts_both_tables_and_enter_applies_now(self):
        self.bar.field.setText("craft")
        QTest.qWait(100)
        self.assertEqual("",self.skill_adapter.query)
        QTest.qWait(480)
        self.assertEqual(["Craft"],self.visible(self.skills))
        self.assertEqual("1 match",self.bar.feedback.text())
        self.bar.field.setText("spell")
        QTest.keyClick(self.bar.field,Qt.Key.Key_Return);QTest.qWait(150)
        self.assertEqual([],self.visible(self.skills))
        self.assertEqual(["Spellcasting"],self.visible(self.features))
        self.assertEqual("1 match",self.bar.feedback.text())

    def test_reset_and_escape_clear_query_and_filters_without_closing(self):
        self.choice.setCurrentText("Class skills")
        self.bar.field.setText("missing");self.bar.apply();QTest.qWait(150)
        self.assertEqual("0 matches",self.bar.feedback.text())
        self.assertEqual("No matching entries",self.skill_adapter.empty_label.text())
        self.bar.clear_button.click();QTest.qWait(150)
        self.assertEqual(3,len(self.visible(self.skills)))
        self.assertFalse(self.bar.clear_button.isVisible())
        self.assertEqual("Ctrl+F",self.bar.feedback.text())
        self.choice.setCurrentText("With ranks");self.bar.field.setText("craft")
        QTest.keyClick(self.bar.field,Qt.Key.Key_Escape);QTest.qWait(150)
        self.assertEqual("",self.bar.field.text())
        self.assertEqual("All skills",self.choice.currentText())
        self.assertTrue(self.root.isVisible())

    def test_filtered_selection_is_not_left_as_hidden_edit_target(self):
        self.skills.setCurrentCell(1,0)
        self.choice.setCurrentText("With ranks");QTest.qWait(150)
        self.assertEqual(-1,self.skills.currentRow())
        self.assertFalse(self.skills.selectedItems())

    def test_search_follows_current_ownership_and_skips_unavailable_tables_in_count(self):
        self.owned=[self.feature_adapter]
        self.bar.field.setText("spell");self.bar.apply();QTest.qWait(150)
        self.assertEqual("",self.skill_adapter.query)
        self.assertFalse(self.choice.isVisible())
        self.assertEqual("1 match",self.bar.feedback.text())
        self.features.hide();self.bar.update_feedback()
        self.assertEqual("0 matches",self.bar.feedback.text())


if __name__=="__main__":unittest.main()

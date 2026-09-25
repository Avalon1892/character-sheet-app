from __future__ import annotations
import os, tempfile, unittest, json, gc
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSettings, QRect, Qt, QEvent, QPoint
from PySide6.QtTest import QTest
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QWidget, QVBoxLayout
from app.database import CharacterRepository
from app.presentation_storage import SheetStyleStore, StyleBlockRepository, MemorySettings
from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.registry import register_builtin_blocks
from app.ui.refined.pages import DEFAULT_TABS
from app.ui.refined.sheet import RefinedSheetWidget
from app.ui.refined.components import ResponsiveRow, TablePresentation, TableDisclosure
from app.ui.table_layout import TableLayoutController
from app.ui.refined.stat_cards import MetricCard
from app.ui.main_window import MainWindow
from app.transfer import export_character, import_character
from app.recovery import FullRestEngine
from app.spellbook import SpellBookService


class RefinedPersistenceTests(unittest.TestCase):
    def test_namespaced_blocks_and_export_are_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            repo=CharacterRepository(Path(folder)/"test.db")
            try:
                cid=repo.create_character("Independent", "Pathfinder 1e")
                legacy=BuildingBlockRepository(repo.database_path,connection=repo.sqlite_connection)
                refined=StyleBlockRepository(repo,"refined",DEFAULT_TABS)
                registry=register_builtin_blocks()
                legacy.ensure_character(cid,registry)
                baseline=legacy.export_character_state(cid)
                refined.ensure_character(cid,registry)
                refined.rename_tab(cid,"core","Adventure")
                instance=refined.list_instances(cid)[0]
                refined.set_instance_visible(instance.id,False)
                store=SheetStyleStore(repo)
                store.save(cid,"refined",{"density":"compact","layout":{"custom":"saved"}})
                store.save(cid,"selection",{"style":"refined"})
                self.assertEqual(baseline,legacy.export_character_state(cid))
                path=Path(folder)/"character.json"
                export_character(repo,cid,path)
                imported=import_character(repo,path)
                self.assertEqual(store.export(cid),store.export(imported))
                self.assertEqual("Adventure",next(t.name for t in refined.list_tabs(imported) if t.key=="core"))
                self.assertEqual(baseline,legacy.export_character_state(cid))
                self.assertEqual("ok",repo.sqlite_connection.execute("PRAGMA integrity_check").fetchone()[0])
            finally:repo.close()


class RefinedTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def test_balanced_spell_summary_filters_only_unavailable_rows(self):
        table=QTableWidget(3,5)
        adapter=TablePresentation(table,table,balanced=True,sortable=False,
            row_visible=RefinedSheetWidget._available_spell_summary_row)
        for row,values in enumerate((("1","14","0","4","—"),("0","18","4th","—","—"),("0","15","1st","3","1"))):
            for column,value in enumerate(values):table.setItem(row,column,QTableWidgetItem(value))
        adapter.fit()
        self.assertEqual([False,True,False],[table.isRowHidden(r) for r in range(3)])
        self.assertTrue(all(table.horizontalHeader().sectionResizeMode(c)==QHeaderView.ResizeMode.Stretch for c in range(5)))
        adapter.sort(2)
        self.assertEqual("0",table.item(0,2).text())
        adapter.filter("1st");adapter.fit()
        self.assertEqual([True,True,False],[table.isRowHidden(r) for r in range(3)])
        adapter.timer.stop();table.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_readable_sort_preserves_identity_and_semantic_tables_opt_out(self):
        table=QTableWidget(2,1)
        for row,name in enumerate(("Zulu","Alpha")):
            item=QTableWidgetItem(name);item.setData(Qt.ItemDataRole.UserRole,row+1);table.setItem(row,0,item)
        adapter=TablePresentation(table,table)
        adapter.sort(0)
        self.assertEqual(("Alpha",2),(table.item(0,0).text(),table.item(0,0).data(Qt.ItemDataRole.UserRole)))
        adapter.sortable=False;adapter.sort(0)
        self.assertEqual("Alpha",table.item(0,0).text())
        adapter.timer.stop();table.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_embedded_editors_have_space_for_their_padding(self):
        table=QTableWidget(1,1)
        editor=QLineEdit("12");table.setCellWidget(0,0,editor)
        adapter=TablePresentation(table,table)
        adapter.fit()
        self.assertGreaterEqual(table.rowHeight(0),editor.sizeHint().height()+22)
        adapter.timer.stop();table.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_reference_preview_search_and_expansion_preserve_all_records(self):
        section=QWidget();layout=QVBoxLayout(section)
        table=QTableWidget(10,1);layout.addWidget(table)
        for row in range(10):
            item=QTableWidgetItem(f"Ability {row}");item.setData(Qt.ItemDataRole.UserRole,row+1)
            table.setItem(row,0,item)
        adapter=TablePresentation(table,section,max_rows=3)
        control=TableDisclosure(adapter,section,preview_rows=4,noun="abilities")
        adapter.fit()
        self.assertEqual(4,sum(not table.isRowHidden(r) for r in range(10)))
        self.assertEqual("+ Show all 10 abilities",control.text())
        control.click();adapter.fit()
        self.assertFalse(any(table.isRowHidden(r) for r in range(10)))
        self.assertGreaterEqual(table.height(),sum(table.rowHeight(r) for r in range(10)))
        control.click();adapter.filter("Ability 9");adapter.fit()
        self.assertFalse(table.isRowHidden(9));self.assertTrue(control.isHidden())
        adapter.filter("not present");adapter.fit()
        self.assertEqual("No matching entries",adapter.empty_label.text())
        self.assertFalse(adapter.empty_label.isHidden())
        adapter.filter("");adapter.fit()
        self.assertTrue(table.isRowHidden(9))
        self.assertEqual(list(range(1,11)),[table.item(r,0).data(Qt.ItemDataRole.UserRole) for r in range(10)])
        adapter.timer.stop();section.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_opt_in_column_order_keeps_saved_customization_and_legacy_defaults(self):
        settings=MemorySettings();controller=TableLayoutController(settings)
        table=QTableWidget(0,3);table.setProperty("defaultColumnOrder",[2,0,1])
        controller.register("refined",table);controller.reload()
        order=lambda:[table.horizontalHeader().logicalIndex(v) for v in range(3)]
        self.assertEqual([2,0,1],order())
        controller._state["refined"]={"user_modified":True,"order":[1,2,0]}
        controller._restore_table("refined")
        self.assertEqual([1,2,0],order())
        controller.reset();self.assertEqual([2,0,1],order())
        legacy=QTableWidget(0,3);controller.register("legacy",legacy);controller.reload()
        self.assertEqual([0,1,2],[legacy.horizontalHeader().logicalIndex(v) for v in range(3)])
        self.app.processEvents();controller.dispose()
        table.deleteLater();legacy.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_metric_card_clicks_labels_keyboard_and_drag_guard(self):
        calls=[]
        card=MetricCard("Armor Class",lambda:calls.append("open"),primary=True)
        card.value.setText("24");card.resize(220,110);card.show();self.app.processEvents()
        QTest.mouseClick(card,Qt.MouseButton.LeftButton,pos=QPoint(4,4))
        QTest.mouseClick(card.title,Qt.MouseButton.LeftButton)
        QTest.mouseClick(card.value,Qt.MouseButton.LeftButton)
        QTest.keyClick(card,Qt.Key.Key_Return)
        QTest.keyClick(card,Qt.Key.Key_Space)
        self.assertEqual(5,len(calls))
        QTest.mousePress(card,Qt.MouseButton.LeftButton,pos=QPoint(4,4))
        QTest.mouseRelease(card,Qt.MouseButton.LeftButton,pos=QPoint(80,50))
        self.assertEqual(5,len(calls))
        self.assertEqual("24",card.value.text())
        self.assertTrue(card.property("primaryMetric"))
        card.deleteLater();self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)


class RefinedUiTests(unittest.TestCase):
    def test_equipment_figure_and_worn_table_share_equipment_state(self):
        self.sheet.session.select_tab("inventory")
        item = self.repo.add_equipment(self.cid, "Boots", "Gear", 1, 1, False, 0,
                                       "untyped", None, "", slot="Feet")
        self.sheet._refresh_equipment()
        self.sheet._open_equipment_figure()
        dialog = self.sheet._equipment_figure_dialog
        self.assertTrue(dialog.isVisible())
        self.assertFalse(dialog.isModal())
        self.sheet.worn_table.equipment_dropped.emit(item, "Feet")
        self.assertIn("Boots", dialog.figure.targets["Feet"].toolTip())
        self.sheet.equipment_table.equipment_dropped.emit(item, "")
        self.assertTrue(dialog.figure.targets["Feet"].icon().isNull())
        other = self.character("Other", "pathfinder-class:fighter")
        self.sheet.load_character(other)
        self.assertIsNone(self.sheet._equipment_figure_dialog)

    def test_skill_reference_click_and_live_refresh(self):
        self.sheet.session.select_tab("skills")
        self.sheet.details_button.setChecked(True)
        QTest.qWait(100)
        table = self.sheet.skill_table
        row = next(r for r in range(table.rowCount())
                   if table.item(r, 0).data(Qt.ItemDataRole.UserRole) == "climb")
        baseline = self.repo.sqlite_connection.total_changes
        table.cellClicked.emit(row, 0)
        text = self.sheet.feature_details.toPlainText()
        self.assertIn("Your check:", text)
        self.assertIn("Climb", text)
        self.assertIn("DC", text)
        self.assertEqual(baseline, self.repo.sqlite_connection.total_changes)
        table.setFocus()
        table.setCurrentCell(row, 0)
        other = next(r for r in range(table.rowCount())
                     if table.item(r, 0).data(Qt.ItemDataRole.UserRole) == "acrobatics")
        table.setCurrentCell(other, 0)
        self.assertIn("Acrobatics", self.sheet.feature_details.toPlainText())
        table.cellClicked.emit(row, 0)
        states = self.repo.list_skill_states(self.cid)
        self.repo.update_skill_state(self.cid, replace(states["climb"], ranks=2))
        self.sheet._refresh_skills()
        self.assertIn("Ranks: 2", self.sheet.feature_details.toPlainText())
        self.sheet.feature_details.setHtml("<h2>Another feature</h2>")
        self.sheet._refresh_skills()
        self.assertEqual("Another feature", self.sheet.feature_details.toPlainText())

    def test_sequence_details_use_complete_reference(self):
        table = self.sheet.sequence_tables["Finisher"]
        self.sheet._refresh_sequence_options()
        row = next(r for r in range(table.rowCount())
                   if table.item(r, 0).text() == "Arcane Apocalypse")
        self.sheet._show_table_row_details(table, row)
        text = self.sheet.feature_details.toPlainText()
        self.assertIn("5 link", text)
        self.assertIn("7 link", text)
        self.assertIn("9 link", text)
        self.assertIn("normal casting time", text)

    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        # Offscreen Qt does not always discover the desktop's installed fonts.
        # Use the actual UI faces when asserting concrete column proportions.
        for name in ("segoeui.ttf","segoeuib.ttf","georgia.ttf","georgiab.ttf"):
            font=Path("C:/Windows/Fonts")/name
            if font.exists():QFontDatabase.addApplicationFont(str(font))

    def setUp(self):
        gc.collect()
        self.app.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.temp=tempfile.TemporaryDirectory()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,self.temp.name)
        self.repo=CharacterRepository(Path(self.temp.name)/"ui.db")
        self.cid=self.character("Fighter", "pathfinder-class:fighter")
        self.window=MainWindow(self.repo)
        self.window.resize(1500,950)
        self.window.refresh_characters(self.cid)
        self.assertIsNotNone(self.window.refined_sheet)  # the requested default
        self.assertIsNone(self.window.original_spheres_sheet)
        self.assertIsNone(self.window.ultra_sheet)
        self.window._set_sheet_type("refined")
        self.sheet=self.window.refined_sheet
        self.window.show()
        QTest.qWait(150)

    def tearDown(self):
        self.window.close(); self.window.deleteLater();self.app.processEvents()
        self.repo.close();self.temp.cleanup()

    def character(self,name,key,kind="Pathfinder 1e"):
        cid=self.repo.create_character(name,kind)
        self.repo.add_class_level(cid,name,6,"3/4","Good","Poor","Good",key,8,36)
        return cid

    def test_skills_first_open_refresh_search_and_resize_fit_the_page(self):
        self.sheet.session.select_tab('skills')
        self.app.processEvents()
        self.assertGreaterEqual(self.sheet.skills_section.height(),self.sheet.skills_section.layout().minimumSize().height())
        QTest.qWait(450)
        for width in (1500, 1100, 1400):
            self.window.resize(width,950)
            self.sheet._refresh_skills()
            QTest.qWait(300)
            table=self.sheet.skill_table
            section=self.sheet.skills_section
            self.assertGreaterEqual(section.height(), section.layout().minimumSize().height(),
                (width,self.sheet.refined_skills_row.size(),self.sheet.refined_skills_row.minimumSizeHint(),
                 self.sheet.refined_pages['skills'][1].size(),self.sheet.refined_pages['skills'][2].minimumSize()))
            self.assertLessEqual(table.geometry().bottom(), section.height())
            self.assertGreater(table.columnWidth(0),250)
            self.assertLessEqual(table.columnWidth(4),70)
        adapter=next(a for a in self.sheet.table_presentations if a.table is table)
        adapter.filter('acrobatics');QTest.qWait(250)
        self.assertEqual(1,sum(not table.isRowHidden(r) for r in range(table.rowCount())))
        adapter.filter('');QTest.qWait(250)
        self.assertEqual(table.rowCount(),sum(not table.isRowHidden(r) for r in range(table.rowCount())))
        self.assertGreaterEqual(section.height(), section.layout().minimumSize().height())
        QTest.qWait(200)
        self.assertFalse(adapter.timer.isActive())
        self.assertFalse(self.sheet._table_reflow_timer.isActive())

    def test_skills_reference_columns_stack_search_and_reset(self):
        sheet=self.sheet
        sheet.session.select_tab("skills");QTest.qWait(300)
        row=sheet.refined_skills_row
        self.assertIs(sheet.skills_section.parentWidget(),row)
        self.assertIs(sheet.special_abilities_section.parentWidget(),row)
        self.assertGreater(sheet.skills_section.width(),sheet.special_abilities_section.width()*1.8,
            (sheet.special_abilities_section.minimumSizeHint(),
             sheet.special_abilities_section.layout().minimumSize(),
             [(type(row.row.itemAt(i).widget()).__name__,row.row.stretch(i)) for i in range(row.row.count())]))
        self.assertEqual(sheet.skills_section.y(),sheet.special_abilities_section.y())
        self.assertGreater(sheet.special_ability_table.columnWidth(1),200)
        self.assertEqual(0,sheet.refined_pages["skills"][0].horizontalScrollBar().maximum())
        search=sheet.refined_pages["skills"][1].findChild(QLineEdit,"refinedPageSearch")
        search.setText("no matching skill or ability");QTest.qWait(550)
        for table in (sheet.skill_table,sheet.special_ability_table):
            self.assertTrue(all(table.isRowHidden(r) for r in range(table.rowCount())))
        search.clear();QTest.qWait(550)
        self.window.resize(1100,950);QTest.qWait(300)
        self.assertGreater(sheet.special_abilities_section.y(),sheet.skills_section.geometry().bottom())
        self.assertGreaterEqual(row.height(),row.layout().minimumSize().height())
        self.assertEqual(0,sheet.refined_pages["skills"][0].horizontalScrollBar().maximum())
        self.window.resize(1500,950);QTest.qWait(300)
        sheet.session.reset(confirm=False)
        sheet.session.select_tab("skills");QTest.qWait(300)
        self.assertEqual((2,1),tuple(row.row.stretch(i) for i in range(2)))
        self.assertGreater(sheet.skills_section.width(),sheet.special_abilities_section.width()*1.8)

    def test_custom_special_ability_destination_survives_reload(self):
        session=self.sheet.session
        section=self.sheet.special_abilities_section
        instance=int(section.property("blockInstanceId"))
        session.runtime.move(instance,"inventory")
        session.save();session.load(self.cid)
        self.assertIs(session.controller.section_canvases[section],session.tabs.canvases["inventory"])
        session.reset(confirm=False)
        self.assertIs(section.parentWidget(),self.sheet.refined_skills_row)

    def test_quick_filters_are_presentation_only_and_reset_between_characters(self):
        sheet=self.sheet
        sheet.session.select_tab("skills");QTest.qWait(200)
        states=self.repo.list_skill_states(self.cid)
        self.repo.update_skill_state(self.cid,replace(states["climb"],ranks=2))
        sheet._refresh_skills();QTest.qWait(200)
        before=self.repo.sqlite_connection.total_changes
        sheet.refined_skill_filter.setCurrentText("With ranks");QTest.qWait(200)
        table=sheet.skill_table
        shown=[table.item(r,0).data(Qt.ItemDataRole.UserRole) for r in range(table.rowCount())
               if not table.isRowHidden(r)]
        self.assertIn("climb",shown)
        self.assertTrue(all(float(table.item(r,4).text())>0 for r in range(table.rowCount())
                            if not table.isRowHidden(r)))
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)
        search=sheet.refined_page_searches["skills"]
        search.field.setText("climb");search.apply();QTest.qWait(200)
        self.assertIn("match",search.feedback.text())
        other=self.character("Rogue","pathfinder-class:rogue")
        sheet.load_character(other);QTest.qWait(200)
        self.assertEqual("",search.field.text())
        self.assertEqual("All skills",sheet.refined_skill_filter.currentText())
        self.assertFalse(any(sheet.skill_table.isRowHidden(r) for r in range(sheet.skill_table.rowCount())))

    def test_category_columns_are_readable_but_user_widths_still_win(self):
        sheet=self.sheet
        sheet.session.select_tab("skills");QTest.qWait(200)
        canvas=sheet.refined_pages["skills"][1]
        for key in ("skills", "special_abilities", "feats", "traits"):
            self.assertTrue(canvas.isAncestorOf(sheet.custom_sections[key]))
        self.assertLess(sheet.refined_skills_row.y(),sheet.feats_section.parentWidget().y())
        self.assertEqual(180,sheet.feat_table.columnWidth(1))
        self.assertEqual(180,sheet.trait_table.columnWidth(1))
        row=sheet.feats_section.parentWidget()
        self.assertEqual((2,1),tuple(row.row.stretch(i) for i in range(2)))
        controller=sheet.session.controller.table_layout
        key=sheet.feat_table.property("tableLayoutId")
        controller._state[key]={"user_modified":True,"widths":{"builtin:1":77}}
        controller._restore_table(key)
        sheet._refresh_feats();QTest.qWait(200)
        self.assertEqual(77,sheet.feat_table.columnWidth(1))

    def test_feats_traits_old_defaults_migrate_but_custom_destination_stays(self):
        from app.ui.refined.layout_migrations import migrate_feats_traits_skills_page
        session=self.sheet.session
        presentation=session.presentation
        instances={i.template_snapshot.get("section_key"):i
                   for i in presentation.list_instances(self.cid)}
        for key, destination in (("feats", "abilities"), ("traits", "inventory")):
            instance=instances[key]
            snapshot={**instance.template_snapshot,"default_tab":"abilities"}
            presentation.connection.execute(
                "UPDATE sheet_block_instances SET tab_key=?,template_snapshot_json=? WHERE id=?",
                (destination,json.dumps(snapshot),instance.id))
        presentation.connection.execute(
            "DELETE FROM sheet_presentation_migrations WHERE character_id=? AND migration_key=?",
            (self.cid,"feats-traits-skills-page-v1"))
        presentation.connection.commit()
        migrate_feats_traits_skills_page(presentation,self.cid,{})
        updated={i.template_snapshot.get("section_key"):i for i in presentation.list_instances(self.cid)}
        self.assertEqual("skills",updated["feats"].tab_key)
        self.assertEqual("inventory",updated["traits"].tab_key)
        migrate_feats_traits_skills_page(presentation,self.cid,{})
        self.assertEqual("skills",next(i for i in presentation.list_instances(self.cid)
                                     if i.id==instances["feats"].id).tab_key)

    def test_legacy_customized_skills_keep_the_old_ability_page_until_reset(self):
        session=self.sheet.session
        skills=self.sheet.skills_section
        ability=self.sheet.special_abilities_section
        instance=next(i for i in session.presentation.list_instances(self.cid)
                      if i.id==int(ability.property("blockInstanceId")))
        snapshot={**instance.template_snapshot,"default_tab":"abilities"}
        session.presentation.connection.execute(
            "UPDATE sheet_block_instances SET tab_key='abilities',template_snapshot_json=? WHERE id=?",
            (json.dumps(snapshot),instance.id))
        session.presentation.connection.execute("DELETE FROM sheet_presentation_migrations WHERE character_id=?",(self.cid,))
        session.presentation.connection.commit()
        session.controller.place_section_freeform(skills,session.tabs.canvases["skills"],QRect(30,50,800,900))
        session.controller._save_geometry(skills)
        session.save();original=session.controller.capture_state()["freeform"]
        session.load(self.cid);QTest.qWait(200)
        self.assertEqual(original,session.controller.capture_state()["freeform"])
        self.assertIs(ability.parentWidget(),self.sheet.refined_pages["abilities"][1])
        self.assertFalse(ability.property("freeformManaged"))
        self.assertEqual(1,self.sheet.refined_pages["abilities"][2].indexOf(ability))
        session.select_tab("abilities")
        search=self.sheet.refined_pages["abilities"][1].findChild(QLineEdit,"refinedPageSearch")
        search.setText("no matching ability");QTest.qWait(550)
        self.assertTrue(all(self.sheet.special_ability_table.isRowHidden(r)
                            for r in range(self.sheet.special_ability_table.rowCount())))
        search.clear();QTest.qWait(550)
        session.reset(confirm=False)
        self.assertIs(ability.parentWidget(),self.sheet.refined_skills_row)
        self.assertIs(skills.parentWidget(),self.sheet.refined_skills_row)
        self.assertTrue(session.history.undo(self.cid))
        self.assertIs(ability.parentWidget(),self.sheet.refined_pages["abilities"][1])
        self.assertEqual(original,session.controller.capture_state()["freeform"])

    def test_style_isolation_reset_undo_switch_and_character_preferences(self):
        s=self.sheet.session
        original=self.window.customization.capture_state()
        blocks=self.window.block_repository.export_character_state(self.cid)
        s.history.record("Move attacks",lambda:(s.controller.place_section_freeform(self.sheet.attacks_section,s.tabs.canvases["core"],QRect(30,420,700,260)),s.controller._save_geometry(self.sheet.attacks_section)))
        changed=s.controller.capture_state()
        self.assertIn("freeform",changed)
        self.assertTrue(s.history.can_undo(self.cid))
        s.reset(confirm=False)
        self.assertNotIn("freeform",s.controller.capture_state())
        self.assertTrue(s.history.undo(self.cid))
        self.assertEqual(changed,s.controller.capture_state())
        self.assertEqual(original,self.window.customization.capture_state())
        self.assertEqual(blocks,self.window.block_repository.export_character_state(self.cid))
        s.select_tab("skills");s.save()
        other=self.character("Rogue","pathfinder-class:rogue")
        self.window.style_store.save(other,"selection",{"style":"customizable"})
        self.window.refresh_characters(other)
        self.assertNotEqual("refined",self.window.sheet_type)
        self.window.refresh_characters(self.cid)
        self.assertEqual("refined",self.window.sheet_type)
        self.assertEqual("skills",s.tabs.current_key())
        self.assertEqual(changed,s.controller.capture_state())
        self.window.build_mode_action.setChecked(True)
        self.assertTrue(self.sheet.customize_button.isChecked())
        self.assertTrue(s.controller.build_mode)
        self.window.build_mode_action.setChecked(False)

    def test_health_formula_details_and_existing_actions(self):
        hp=replace(self.repo.get_hit_points(self.cid),maximum=40,current=30,temporary=3,nonlethal=5,auto_calculate=False)
        self.repo.update_hit_points(hp);self.sheet.refresh_all()
        self.sheet.classic_hp_adjustment.setValue(8)
        self.sheet.classic_hp_damage_button.click()
        current=self.repo.get_hit_points(self.cid)
        self.assertEqual((25,0),(current.current,current.temporary))
        self.sheet.classic_hp_adjustment.setValue(4);self.sheet.classic_hp_heal_button.click()
        current=self.repo.get_hit_points(self.cid)
        self.assertEqual((29,1),(current.current,current.nonlethal))
        field=self.sheet.movement_controls["land_speed"]
        field.set_expression("=30+5")
        self.sheet._save_movement()
        self.assertIn("35",self.sheet.movement_totals["land_speed"].text())
        self.assertTrue(field.preview.text().startswith("ƒ"))
        self.assertEqual("=30+5",field.expression)
        self.sheet._show_ability_breakdown("strength","Strength")
        self.assertTrue(self.sheet.details_button.isChecked())
        self.assertIn("Strength",self.sheet.feature_details.toPlainText())
        self.assertEqual(1,self.sheet.refined_detail_actions.count())
        self.sheet.feature_details.setHtml("<h2>Selected feat</h2><p>Description first.</p>")
        self.assertEqual(0,self.sheet.refined_detail_actions.count())
        for method in ("_open_spell_book","_open_martial_book","_open_inventory","_add_attack","_edit_skill"):
            self.assertTrue(callable(getattr(self.sheet,method,None)),method)
        self.assertTrue(any("inventory" in b.text().casefold() for b in self.sheet.findChildren(QPushButton)))

    def test_capability_pages_and_shared_spell_resources(self):
        cases=(("Wizard","pathfinder-class:wizard",True,False),
               ("Sorcerer","pathfinder-class:sorcerer",True,False),
               ("Incanter","spheres-class:incanter",True,True),
               ("Conscript","spheres-class:conscript",False,False),
               ("Prodigy","prodigy",True,True),
               ("Hunter","pathfinder-class:hunter",True,False),
               ("Witch","pathfinder-class:witch",True,False))
        for name,key,magic,spheres in cases:
            with self.subTest(name=name):
                cid=self.character(name,key,"Spheres" if spheres or name=="Conscript" else "Pathfinder 1e")
                self.sheet.load_character(cid)
                self.assertEqual(magic,self.sheet.is_sheet_tab_available("magic"))
                self.assertEqual(spheres,not self.sheet.spells_section.isHidden())
                if name=="Witch":self.assertTrue(self.sheet.is_sheet_tab_available("familiar"))
                if name=="Hunter":self.assertTrue(self.sheet.is_sheet_tab_available("companion"))
                if name=="Prodigy":self.assertFalse(self.sheet.prodigy_section.isHidden())
        wizard=self.character("Wizard","pathfinder-class:wizard")
        class_id=self.repo.list_class_levels(wizard)[0].id
        spell=self.repo.add_spell(wizard,"Fireball",system="Prepared",level=3,school_or_sphere="Evocation",notes="Description")
        self.repo.add_prepared_spell(wizard,class_id,spell,prepared_count=2)
        self.sheet.load_character(wizard)
        service=SpellBookService(self.repo,wizard)
        self.assertTrue(service.cast_traditional(f"traditional:spell:{spell}").changed)
        self.sheet.refresh_all()
        self.assertEqual(1,self.repo.list_prepared_spells(wizard)[0].remaining)
        FullRestEngine(self.repo,wizard).perform({"prepared_spells":True})
        self.sheet.refresh_all()
        self.assertEqual(2,self.repo.list_prepared_spells(wizard)[0].remaining)
        champion=self.character("Inquisitor","pathfinder-class:inquisitor")
        cls=self.repo.list_class_levels(champion)[0]
        self.repo.set_class_archetype_keys(champion,cls.id,["spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor"])
        self.repo.add_class_level(champion,"Fighter",2,"Full","Good","Poor","Poor","pathfinder-class:fighter",10,12)
        self.sheet.load_character(champion)
        self.assertTrue(self.sheet._class_capabilities.magic)
        self.assertFalse(self.sheet._class_capabilities.traditional_spells)

    def test_responsive_rows_columns_and_all_themes(self):
        before=self.sheet.session.controller.capture_state()
        self.sheet.customize_button.setChecked(True)
        self.sheet.customize_button.setChecked(False)
        self.assertEqual(before,self.sheet.session.controller.capture_state())
        self.sheet.details_button.setChecked(True)
        QTest.qWait(150)
        self.assertLessEqual(self.sheet.classic_statistics_section.width(),self.sheet.core_scroll.viewport().width())
        self.sheet.details_button.setChecked(False)
        for theme in ("classic","light","dark"):
            self.window._set_theme(theme)
            for width in (1500,1100):
                self.window.resize(width,950);QTest.qWait(130)
                for row in self.sheet.classic_statistics_section.findChildren(ResponsiveRow):
                    self.assertGreater(row.height(),100)
                    self.assertLessEqual(row.geometry().right(),self.sheet.core_canvas.width())
                self.assertEqual(0,self.sheet.core_scroll.horizontalScrollBar().maximum())
        equipment=self.sheet.equipment_table
        defaults=equipment.property("defaultHiddenColumns")
        self.assertTrue(defaults)
        self.sheet.session.controller.table_layout.reload()
        for key in defaults:self.assertTrue(equipment.isColumnHidden(int(key.split(":")[1])))
        for control in self.sheet.table_presentations:
            self.assertEqual(Qt.TextElideMode.ElideNone,control.table.textElideMode())
        self.assertEqual("Overview",self.sheet.page_tabs.tabText(0))
        self.assertEqual("4   ANIMAL COMPANION",self.window.sheet.page_tabs.tabText(self.window.sheet.page_tabs.indexOf(self.window.sheet.companion_scroll)))

    def test_polished_layout_and_disclosure_preferences_do_not_modify_gameplay(self):
        sheet=self.sheet
        sheet.session.select_tab("skills");QTest.qWait(150)
        baseline=self.repo.sqlite_connection.total_changes
        disclosure=sheet.refined_disclosures["special_abilities"]
        disclosure.set_expanded(True);disclosure.adapter.fit()
        QTest.qWait(120)
        self.assertGreaterEqual(sheet.special_abilities_section.height(),
                                sheet.special_abilities_section.layout().minimumSize().height())
        self.assertEqual(baseline,self.repo.sqlite_connection.total_changes)
        sheet.session.save()
        self.assertEqual(["special_abilities"],sheet.session.store.get(self.cid,"refined")["expanded_sections"])
        sheet.session.load(self.cid)
        self.assertTrue(disclosure.adapter.expanded)
        # Short and long panels stay aligned after saved-layout restoration.
        for row in sheet.findChildren(ResponsiveRow):
            for index in range(row.row.count()):
                if row.row.itemAt(index).widget():
                    self.assertTrue(row.row.itemAt(index).alignment() & Qt.AlignmentFlag.AlignTop)
        self.assertEqual(2,sheet.skill_table.horizontalHeader().logicalIndex(0))
        self.assertIsNone(self.window.sheet.skill_table.property("defaultColumnOrder"))
        # A detached movement card must not be reinserted by a live update.
        sheet.session.select_tab("core")
        card=sheet.refined_movement_cards["land_speed"]
        sheet.refined_movement_grid.removeWidget(card)
        card.move(230,50);before=card.geometry()
        sheet._refresh_refined_visibility()
        self.assertEqual(-1,sheet.refined_movement_grid.indexOf(card))
        self.assertEqual(before,card.geometry())
        sheet.refined_movement_grid.addWidget(card,0,0)

    def test_grouped_stat_cards_share_live_values_details_and_eligibility(self):
        sheet=self.sheet
        self.assertTrue(sheet.refined_magic_maneuvers.isHidden())
        for key,result in sheet._combat_results().items():
            self.assertIn(key,sheet.refined_stat_cards)
            self.assertEqual(result.total,int(sheet.refined_stat_cards[key].value.text()))
        sheet.refined_stat_cards["ac"]._metric_interaction.callback()
        self.assertIn("Total AC",sheet.feature_details.toPlainText())
        self.assertIn("Current total",sheet.feature_details.toPlainText())
        sheet.refined_movement_cards["land_speed"]._metric_interaction.callback()
        self.assertIn("movement",sheet.feature_details.toPlainText())
        self.assertEqual("Edit movement…",sheet.refined_detail_actions.itemAt(0).widget().text())
        sheet.refined_detail_actions.itemAt(0).widget().click()
        self.assertTrue(sheet.movement_edit_toggle.isChecked())
        cid=self.character("Incanter","spheres-class:incanter","Spheres")
        sheet.load_character(cid)
        self.assertFalse(sheet.refined_magic_maneuvers.isHidden())
        sheet._show_magic_metric("msb")
        self.assertIn("Casting class levels",sheet.feature_details.toPlainText())
        sheet._show_magic_metric("msd")
        self.assertIn("11 + MSB",sheet.feature_details.toPlainText())
        sheet.load_character(self.cid)
        self.assertTrue(sheet.refined_magic_maneuvers.isHidden())
        self.assertEqual("attr:refined_movement_cards.land_speed",
            sheet.session.cells._cell_key(sheet.refined_movement_cards["land_speed"],sheet.custom_sections["movement"]))
        self.assertTrue(sheet.refined_movement_cards["land_speed"].findChildren(QLineEdit)==[])
        original=sheet.feature_details.toPlainText()
        sheet.session.controller.build_mode=True
        try:
            sheet._show_combat_breakdown("ac","Armor Class")
            sheet._show_movement_metric("land_speed")
            sheet._show_magic_metric("msb")
            self.assertEqual(original,sheet.feature_details.toPlainText())
        finally:sheet.session.controller.build_mode=False


if __name__=="__main__":unittest.main()

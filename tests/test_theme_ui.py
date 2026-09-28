import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, QSettings, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QMessageBox, QSpinBox, QStyle, QStyleOptionSpinBox,
)

from app.database import CharacterRepository
from app.ui.main_window import CodexDialog, MainWindow


class ThemeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary_directory.name) / "characters.db"
        )
        QSettings("Georg", "Character Sheet App").remove("appearance/theme")
        QSettings("Georg", "Character Sheet App").remove("customization")
        QSettings("Georg", "Character Sheet App").remove("files")
        self.window = MainWindow(self.repository)

    def tearDown(self) -> None:
        self.window.close()
        self.repository.close()
        QSettings("Georg", "Character Sheet App").remove("appearance/theme")
        QSettings("Georg", "Character Sheet App").remove("customization")
        QSettings("Georg", "Character Sheet App").remove("files")
        self.temporary_directory.cleanup()

    def test_two_themes_switch_and_persist(self) -> None:
        menus = [action.text().replace("&", "") for action in self.window.menuBar().actions()]
        self.assertEqual(
            ["File", "Edit", "Build Mode", "Theme", "Color", "Rest", "Codex", "Building Blocks"],
            menus[:8],
        )
        self.assertEqual("Ctrl+Z", self.window.undo_action.shortcut().toString())
        self.assertIn(
            "Ctrl+Y",
            [shortcut.toString() for shortcut in self.window.redo_action.shortcuts()],
        )
        self.assertEqual("classic", self.window.theme)
        classic = self.window.styleSheet()
        self.window._set_theme("dark")
        dark = self.window.styleSheet()
        self.assertNotEqual(classic, dark)
        self.assertEqual(
            "dark", QSettings("Georg", "Character Sheet App").value("appearance/theme")
        )

    def test_closing_window_releases_application_event_filters(self) -> None:
        self.assertIsNotNone(self.window.sheet._event_filter_application)
        self.assertIsNotNone(self.window.customization._event_filter_application)

        self.window.close()

        self.assertIsNone(self.window.sheet._event_filter_application)
        self.assertIsNone(self.window.customization._event_filter_application)

    def test_character_sidebar_is_replaced_by_file_menu_navigation_and_saves(self) -> None:
        first = self.repository.create_character("First", "Spheres")
        second = self.repository.create_character("Second", "Pathfinder 1e")
        self.window.refresh_characters(first)
        self.assertTrue(self.window.character_list.isHidden())
        self.assertEqual(
            ["First", "Second"],
            sorted(action.text() for action in self.window.switch_character_menu.actions()),
        )
        file_actions = [action.text().replace("&", "") for action in self.window.file_menu.actions()]
        self.assertIn("Save character", file_actions)
        self.assertIn("Save character as…", file_actions)
        self.assertIn("Save sheet arrangement to this character", file_actions)

        self.window.customization._paint(
            self.window.sheet.conditions_section, QColor("#123456")
        )
        self.assertTrue(self.window.save_sheet_arrangement(notify=False))
        saved = self.window.style_store.get(first, "refined")["layout"]
        self.assertEqual("#123456", saved["colors/conditions"])

        export_path = Path(self.temporary_directory.name) / "first.character.json"
        QSettings("Georg", "Character Sheet App").setValue(
            "files/characterPaths", json.dumps({str(first): str(export_path)})
        )
        self.window.save_character()
        self.assertTrue(export_path.exists())
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertEqual("#123456", payload["character"]["sheet_styles"]["refined"]["layout"]["colors/conditions"])

        self.window._select_character(second)
        self.assertEqual(second, self.window._selected_character().id)

    def test_save_as_starts_in_app_folder_then_remembers_last_folder(self) -> None:
        first = self.repository.create_character("First", "Pathfinder 1e")
        self.window.refresh_characters(first)
        saved_folder = Path(self.temporary_directory.name) / "My Character Files"
        saved_folder.mkdir()
        first_path = saved_folder / "First.character.json"

        with patch(
            "app.ui.main_window.QFileDialog.getSaveFileName",
            return_value=(str(first_path), "Character files (*.character.json)"),
        ) as dialog:
            self.window.save_character_as()
        self.assertEqual(
            str(self.window._application_folder() / "First.character.json"),
            dialog.call_args.args[2],
        )
        self.assertTrue(first_path.exists())
        self.assertEqual(
            str(saved_folder.resolve()),
            str(QSettings("Georg", "Character Sheet App").value("files/lastSaveDirectory")),
        )

        second = self.repository.create_character("Second", "Pathfinder 1e")
        self.window.refresh_characters(second)
        with patch(
            "app.ui.main_window.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ) as dialog:
            self.window.save_character_as()
        self.assertEqual(
            str(saved_folder.resolve() / "Second.character.json"),
            dialog.call_args.args[2],
        )

    def test_deleting_active_character_selects_the_next_and_last_delete_clears_state(self) -> None:
        first = self.repository.create_character("First", "Spheres")
        second = self.repository.create_character("Second", "Pathfinder 1e")
        self.window.refresh_characters(first)
        QSettings("Georg", "Character Sheet App").setValue(
            "files/characterPaths",
            json.dumps({str(first): "first.character.json", str(second): "second.character.json"}),
        )

        with patch(
            "app.ui.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window.delete_selected()

        self.assertFalse(self.repository.character_exists(first))
        self.assertEqual(second, self.window.active_character_id)
        self.assertEqual(second, self.window._selected_character().id)
        self.assertEqual(1, len(self.window.switch_character_menu.actions()))
        self.assertNotIn(
            str(first), self.window._character_save_paths()
        )

        with patch(
            "app.ui.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            self.window.delete_selected()

        self.assertEqual([], self.repository.list_characters())
        self.assertIsNone(self.window.active_character_id)
        self.assertIsNone(self.window._selected_character())
        self.assertEqual(0, self.window.pages.currentIndex())

    def test_customization_controller_keeps_layout_and_rules_separate(self) -> None:
        self.repository.create_character("Layout Test", "Spheres")
        self.window.refresh_characters()
        self.window.character_list.setCurrentRow(0)
        self.window.show()
        self.application.processEvents()
        controller = self.window.customization
        self.assertIn("conditions", controller.sections)
        self.assertIn("core_main", controller.layouts)
        controller.set_build_mode(True)
        self.assertTrue(controller.build_mode)
        for page, key, canvas in (
            (5, "overview", self.window.sheet.builder_canvas),
            (0, "conditions", self.window.sheet.core_canvas),
            (1, "feats", self.window.sheet.refined_pages["skills"][1]),
            (3, "magic_talents", self.window.sheet.magic_canvas),
        ):
            self.window.sheet.page_tabs.setCurrentIndex(page)
            self.application.processEvents()
            self.application.processEvents()
            self.assertIs(controller.sections[key].parentWidget(), canvas)
        self.assertIs(controller.sections["conditions"].parentWidget(), self.window.sheet.core_canvas)
        self.assertNotEqual(
            controller.sections["equipment"].geometry().topLeft(),
            controller.sections["feats"].geometry().topLeft(),
        )
        original = controller.sections["conditions"].geometry()
        controller.sections["conditions"].move(original.x() + 25, original.y() + 15)
        controller._save_geometry(controller.sections["conditions"])
        saved = str(controller.settings.value("customization/freeform", ""))
        self.assertIn('"conditions"', saved)
        controller._paint(controller.sections["conditions"], QColor("#123456"))
        self.assertIn("#123456", controller.sections["conditions"].styleSheet())
        controller.clear_colors()
        self.assertEqual("", controller.sections["conditions"].styleSheet())

    def test_build_mode_resizes_tables_and_persists_column_widths_and_order(self) -> None:
        character_id = self.repository.create_character("Flexible Tables", "Spheres")
        self.repository.add_class_level(
            character_id, "Prodigy", 1, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=8,
        )
        self.window.refresh_characters()
        self.window.character_list.setCurrentRow(0)
        self.window.show()
        controller = self.window.customization
        controller.set_build_mode(True)
        self.window.sheet.page_tabs.setCurrentIndex(2)
        self.application.processEvents()
        self.application.processEvents()

        section = self.window.sheet.martial_talents_section
        table = self.window.sheet.martial_talent_table
        table_id = "martial_talents/martial_talent_table"
        self.assertIn(table_id, controller.table_layout.tables)
        self.assertTrue(table.horizontalHeader().sectionsMovable())

        header = table.horizontalHeader()
        header.resizeSection(0, 321)
        header.moveSection(header.visualIndex(0), 2)
        controller.table_layout._capture_table(table_id)
        controller.table_layout._save()
        saved = json.loads(
            str(controller.settings.value(
                "customization/tableLayouts", "{}"
            ))
        )
        self.assertEqual(321, saved[table_id]["widths"]["0"])
        self.assertEqual(0, saved[table_id]["order"][2])

    def test_build_mode_can_scale_a_box_contents_proportionally(self) -> None:
        self.repository.create_character("Scaled Sheet", "Spheres")
        self.window.refresh_characters()
        self.window.character_list.setCurrentRow(0)
        self.window.show()
        self.application.processEvents()
        controller = self.window.customization
        controller.set_build_mode(True)
        self.window.sheet.page_tabs.setCurrentIndex(1)
        self.application.processEvents()
        self.application.processEvents()
        section = controller.sections["combat_defense"]
        field = self.window.sheet.hp_maximum
        original_font = field.font().pointSizeF()
        original_geometry = section.geometry()
        controller.set_content_scale_mode(True)
        controller.content_scale.begin("combat_defense", original_geometry)
        enlarged = QRect(original_geometry)
        enlarged.setWidth(round(original_geometry.width() * 1.5))
        enlarged.setHeight(round(original_geometry.height() * 1.5))
        controller.content_scale.preview(enlarged)
        controller.content_scale.finish()
        self.assertGreater(field.font().pointSizeF(), original_font)
        saved = json.loads(str(controller.settings.value(
            "customization/contentScales", "{}"
        )))
        self.assertGreater(saved["combat_defense"], 1.0)

    def test_codex_contains_class_hierarchy_and_prodigy_rules(self) -> None:
        dialog = CodexDialog("prodigy", self.window)
        self.assertEqual("Codex Home", dialog.tree.topLevelItem(0).text(0))
        self.assertEqual("Classes", dialog.tree.topLevelItem(1).text(0))
        spheres = dialog.tree.topLevelItem(1).child(1)
        self.assertEqual("Spheres", spheres.text(0))
        prodigy_nodes = dialog.tree.findItems(
            "Prodigy", Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive, 0
        )
        self.assertEqual(1, len(prodigy_nodes))
        text = dialog.browser.toPlainText()
        self.assertIn("Swift Heal", text)
        self.assertIn("Steel Mind", text)
        self.assertIn("Regenerate", text)
        self.assertIn("Step Between", text)
        dialog.close()

    def test_codex_search_can_target_name_description_or_both(self) -> None:
        dialog = CodexDialog("prodigy", self.window)
        pathfinder = dialog.tree.topLevelItem(1).child(0)
        self.assertEqual("Core Classes", pathfinder.child(0).text(0))
        self.assertGreater(pathfinder.childCount(), 5)
        self.assertEqual(3, dialog.codex_search_mode.count())
        dialog.codex_search_mode.setCurrentIndex(dialog.codex_search_mode.findData("name"))
        dialog.codex_search.setText("Arcanist")
        dialog._search_codex()
        self.assertIn("Arcanist", dialog.browser.toPlainText())
        dialog.codex_search_mode.setCurrentIndex(dialog.codex_search_mode.findData("description"))
        dialog.codex_search.setText("arcane reservoir")
        dialog._search_codex()
        self.assertIn("results", dialog.browser.toPlainText())
        dialog.codex_search_mode.setCurrentIndex(dialog.codex_search_mode.findData("both"))
        dialog.close()

    def test_codex_name_search_prioritizes_parent_and_opens_local_feature(self) -> None:
        dialog = CodexDialog("home", self.window)
        dialog.codex_search_mode.setCurrentIndex(
            dialog.codex_search_mode.findData("name")
        )
        dialog.codex_search.setText("Alteration")
        dialog._search_codex()
        result_text = dialog.browser.toPlainText()
        self.assertLess(
            result_text.find("Alteration Sphere"),
            result_text.find("Mass Alteration"),
        )
        self.assertLess(
            result_text.find("Mass Alteration"),
            result_text.find("Aura Alteration"),
        )
        self.assertIn("Open complete Codex entry", result_text)
        self.assertIn("codex:feature:magic:", dialog.browser.toHtml())

        dialog._open_codex_link(
            QUrl("codex:feature:magic:alteration%3Abase")
        )
        opened = dialog.browser.toPlainText()
        self.assertIn("Alteration Sphere", opened)
        self.assertIn("Base Sphere", opened)
        dialog.close()

    def test_codex_contains_talents_feats_and_traits_from_shared_catalogs(self) -> None:
        dialog = CodexDialog("prodigy", self.window)
        sections = {
            dialog.tree.topLevelItem(index).text(0): dialog.tree.topLevelItem(index)
            for index in range(dialog.tree.topLevelItemCount())
        }
        self.assertEqual(dialog.tree.topLevelItemCount(), len(sections))
        self.assertTrue(
            {"Codex Home", "Classes", "Races", "Spells", "Equipment & Items",
             "Enchantments", "Talents", "Feats", "Traits", "Traditions", "Sheet Tools",
             "Skills", "Gizmos & Tinker Rules", "Item Creation Rules"} <= sections.keys()
        )
        for title, family in (
            ("Skills", "skills"),
            ("Gizmos & Tinker Rules", "gizmos"),
            ("Item Creation Rules", "crafting"),
        ):
            self.assertGreater(sections[title].childCount(), 0)
            self.assertEqual(
                "reference-index:" + family,
                sections[title].data(0, Qt.ItemDataRole.UserRole),
            )
        talents = sections["Talents"]
        self.assertEqual("Martial Talents", talents.child(0).text(0))
        self.assertEqual("Magical Talents", talents.child(1).text(0))
        traditions = sections["Traditions"]
        self.assertEqual("Casting Traditions", traditions.child(0).text(0))
        self.assertEqual("Martial Traditions", traditions.child(1).text(0))
        dialog.codex_search_mode.setCurrentIndex(dialog.codex_search_mode.findData("name"))
        for query in ("Power Attack", "Reactionary", "Warp Sphere"):
            dialog.codex_search.setText(query)
            dialog._search_codex()
            self.assertIn(query, dialog.browser.toPlainText())
        dialog.close()

        home = CodexDialog(parent=self.window)
        self.assertEqual("Codex Home", home.tree.currentItem().text(0))
        self.assertIn("Pathfinder 1e & Spheres Codex", home.browser.toPlainText())
        home.close()

        formulas = CodexDialog("formulas", self.window)
        self.assertIn("Sheet Formula Language", formulas.browser.toPlainText())
        self.assertIn("trackers.ki_pool.maximum", formulas.browser.toPlainText())
        formulas.codex_search.setText("floor division")
        formulas._search_codex()
        self.assertIn("Formula Language", formulas.browser.toPlainText())
        formulas.close()

    def test_codex_spell_search_opens_the_complete_local_entry(self) -> None:
        dialog = CodexDialog("prodigy", self.window)
        dialog._open_codex_link(QUrl("codex:spell:pathfinder-spell%3A6oq1wcryviik9ice"))
        text = dialog.browser.toPlainText()
        self.assertIn("Fireball", text)
        self.assertIn("Description", text)
        self.assertIn("Class levels", text)
        dialog.close()

    def test_spinbox_arrow_hit_area_matches_right_hand_visual(self) -> None:
        spin = QSpinBox()
        spin.setStyleSheet(self.window._style_sheet("classic"))
        spin.resize(120, 32)
        spin.show()
        self.application.processEvents()
        option = QStyleOptionSpinBox()
        spin.initStyleOption(option)
        up = spin.style().subControlRect(
            QStyle.ComplexControl.CC_SpinBox,
            option,
            QStyle.SubControl.SC_SpinBoxUp,
            spin,
        )
        self.assertGreaterEqual(up.width(), 20)
        self.assertGreaterEqual(up.left(), spin.width() - 26)

    def test_character_header_remains_visible_above_refined_pages(self) -> None:
        character_id = self.repository.create_character("Header Hero", "Spheres")
        self.window.refresh_characters(character_id)
        self.assertEqual("Header Hero", self.window.sheet.refined_name.text())
        self.window.sheet.page_tabs.setCurrentIndex(1)
        self.window.show()
        self.application.processEvents()
        self.assertTrue(self.window.sheet.refined_name.isVisibleTo(self.window))


if __name__ == "__main__":
    unittest.main()

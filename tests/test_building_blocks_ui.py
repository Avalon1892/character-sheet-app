from __future__ import annotations

import os
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QRect, QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QSizePolicy, QWidget
from PySide6.QtWidgets import QHeaderView

from app.building_blocks.catalog import BuildingBlocksDialog
from app.building_blocks.designer import BlockDesignerDialog
from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.registry import CELL_TYPE_REGISTRY, CellTypeDescriptor, register_builtin_blocks
from app.building_blocks.schemas import BlockDefinition, CellDefinition, CellOverride
from app.database import CharacterRepository
from app.ui.main_window import MainWindow


class BuildingBlocksUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat,
            QSettings.Scope.UserScope,
            self.root.name,
        )
        QSettings("Georg", "Character Sheet App").clear()
        self.path = Path(self.root.name) / "characters.db"
        self.repository = CharacterRepository(self.path)
        self.first = self.repository.create_character("First", "Pathfinder 1e")
        self.second = self.repository.create_character("Second", "Pathfinder 1e")
        self.window = MainWindow(self.repository)
        self.window.refresh_characters(self.first)
        self.window.show()
        self.application.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.repository.close()
        self.root.cleanup()

    def test_catalog_contains_every_registered_builtin_and_destination_tabs(self) -> None:
        dialog = BuildingBlocksDialog(
            self.repository,
            self.window.block_repository,
            self.window.block_registry,
            self.first,
            self.window.block_repository.list_tabs(self.first),
            self.window.block_runtime.add_block,
            self.window,
        )
        self.assertEqual(len(self.window.block_registry.all()), dialog.results.count())
        self.assertEqual(len(self.window.sheet.session.presentation.default_tabs), dialog.destination.count())
        dialog.close()

    def test_catalog_removes_placed_block_from_page_but_keeps_template(self) -> None:
        definition = BlockDefinition(
            "user:removable", "Removable", "Custom", width=260, height=130,
            cells=(CellDefinition("value", "label", "Value", 20, 50, 120, 30),),
        )
        self.window.block_repository.save_user_template(definition)
        instance_id = self.window.block_runtime.add_block(definition, "core")
        dialog = BuildingBlocksDialog(
            self.repository,
            self.window.block_repository,
            self.window.block_registry,
            self.first,
            self.window.block_repository.list_tabs(self.first),
            self.window.block_runtime.add_block,
            self.window,
            remove_block=self.window.block_runtime.remove_block,
            current_tab_key="core",
        )
        dialog.search.setText("Removable")
        self.application.processEvents()

        self.assertEqual("core", dialog.destination.currentData())
        self.assertTrue(dialog.remove_from_page.isEnabled())
        dialog._remove_from_page()

        placed = next(
            item
            for item in self.window.block_repository.list_instances(self.first)
            if item.id == instance_id
        )
        self.assertFalse(placed.visible)
        self.assertIn(
            "user:removable",
            {item.key for item in self.window.block_repository.list_user_templates()},
        )
        self.assertFalse(dialog.remove_from_page.isEnabled())
        dialog.close()

    def test_saved_block_visibility_cannot_override_class_rule_availability(self) -> None:
        magic_index = self.window.sheet.page_tabs.indexOf(
            self.window.sheet.magic_scroll
        )
        self.assertFalse(self.window.sheet.page_tabs.isTabVisible(magic_index))

        self.repository.add_class_level(
            self.first,
            "Incanter",
            6,
            "1/2",
            "Poor",
            "Poor",
            "Good",
            preset_key="spheres-class:incanter",
            hit_die=6,
            hp_gained=26,
        )
        self.window.sheet.refresh_all()
        self.window.block_runtime.refresh()
        self.application.processEvents()

        magic_index = self.window.sheet.page_tabs.indexOf(
            self.window.sheet.magic_scroll
        )
        self.assertTrue(self.window.sheet.page_tabs.isTabVisible(magic_index))
        self.assertFalse(self.window.sheet.casting_profile_section.isHidden())
        self.assertTrue(self.window.sheet.traditional_casting_section.isHidden())
        self.assertTrue(self.window.sheet.martial_talents_section.isHidden())
        self.assertTrue(self.window.sheet.prodigy_section.isHidden())

        # A second saved-layout projection must preserve the same rule gates.
        self.window.tab_manager.reload()
        self.window.sheet.session._reload_tabs()
        self.window.block_runtime.refresh()
        self.application.processEvents()
        magic_index = self.window.sheet.page_tabs.indexOf(
            self.window.sheet.magic_scroll
        )
        self.assertTrue(self.window.sheet.page_tabs.isTabVisible(magic_index))
        self.assertTrue(self.window.sheet.martial_talents_section.isHidden())
        self.assertTrue(self.window.sheet.prodigy_section.isHidden())

    def test_traditional_magic_page_name_excludes_spheres(self) -> None:
        self.repository.add_class_level(
            self.first, "Wizard", 3, "1/2", "Poor", "Poor", "Good",
            preset_key="pathfinder-class:wizard", hit_die=6, hp_gained=12,
        )
        self.window.sheet.refresh_all()
        self.window.tab_manager.reload()
        index = self.window.sheet.page_tabs.indexOf(self.window.sheet.magic_scroll)
        self.assertEqual("Magic", self.window.sheet.page_tabs.tabText(index))

    def test_build_mode_does_not_persist_untouched_table_widths(self) -> None:
        settings = self.window.customization.settings
        self.window.customization.table_layout.reload()
        self.application.processEvents()
        before = self.window.customization.table_layout._state.copy()
        self.window.customization.set_build_mode(True)
        self.application.processEvents()
        self.window.customization.set_build_mode(False)
        self.application.processEvents()
        self.assertEqual(before, self.window.customization.table_layout._state)

    def test_legacy_width_only_spell_columns_return_to_responsive_modes(self) -> None:
        controller = self.window.customization.table_layout
        table_id = "magic_talents/spell_table"
        settings = self.window.customization.settings
        settings.setValue(
            "customization/tableLayouts",
            json.dumps({table_id: {
                "order": list(range(self.window.sheet.spell_table.columnCount())),
                "widths": {str(index): 900 for index in range(self.window.sheet.spell_table.columnCount())},
                "hidden": [], "custom": [],
            }}),
        )
        controller.reload()
        self.assertEqual(
            QHeaderView.ResizeMode.Stretch,
            self.window.sheet.spell_table.horizontalHeader().sectionResizeMode(0),
        )
        self.assertNotIn("widths", controller._state.get(table_id, {}))

    def test_designer_supports_all_cell_types_and_template_round_trip(self) -> None:
        dialog = BlockDesignerDialog(self.repository, self.first, parent=self.window)
        for descriptor in dialog.canvas.cells.values():
            self.assertIsNotNone(descriptor)
        for cell_type in ("label", "text", "number", "formula", "checkbox", "dropdown", "button", "table"):
            dialog.canvas.add_cell(cell_type)
        definition = dialog.definition("user:all_cells")
        self.assertEqual(8, len(definition.cells))
        self.window.block_repository.save_user_template(definition)
        self.assertEqual("user:all_cells", self.window.block_repository.list_user_templates()[0].key)
        dialog.close()

    def test_custom_block_renders_and_tabs_are_character_specific(self) -> None:
        definition = BlockDefinition(
            "user:pool_card", "Pool Card", "Custom", width=360, height=180,
            cells=(
                CellDefinition("title", "label", "POOL", 10, 32, 330, 28),
                CellDefinition("hp", "number", "HP", 20, 76, 120, 32, binding="hit_points.current"),
                CellDefinition("level", "formula", "Level", 170, 76, 120, 32, formula="character.level + 1"),
            ),
        )
        self.window.block_repository.save_user_template(definition)
        instance_id = self.window.block_runtime.add_block(definition, "build")
        self.application.processEvents()
        self.assertIn(instance_id, self.window.block_runtime.widgets)
        custom_tab = self.window.tab_manager.add_tab("First Only")
        self.window.sheet.session._reload_tabs()
        self.assertEqual(len(self.window.block_repository.default_tabs) + 1, self.window.sheet.page_tabs.count())
        self.assertIn(custom_tab, [tab.key for tab in self.window.block_repository.list_tabs(self.first)])
        self.window.refresh_characters(self.second)
        self.application.processEvents()
        self.assertNotIn(custom_tab, [tab.key for tab in self.window.block_repository.list_tabs(self.second)])

    def test_parent_scaling_respects_anchored_and_independent_cells(self) -> None:
        definition = BlockDefinition(
            "user:scale", "Scale", "Custom", width=300, height=160,
            cells=(
                CellDefinition("anchored", "label", "Anchored", 20, 40, 100, 30, anchored=True),
                CellDefinition("independent", "label", "Independent", 160, 40, 100, 30, anchored=False),
            ),
        )
        instance_id = self.window.block_runtime.add_block(definition, "core")
        self.window.sheet.page_tabs.setCurrentWidget(self.window.sheet.core_scroll)
        self.application.processEvents()
        widget = self.window.block_runtime.widgets[instance_id]
        independent_before = widget.cells["independent"].geometry()
        widget.resize(600, 320)
        self.application.processEvents()
        self.assertEqual((40, 80, 200, 60), (
            widget.cells["anchored"].x(), widget.cells["anchored"].y(),
            widget.cells["anchored"].width(), widget.cells["anchored"].height(),
        ))
        self.assertEqual(independent_before, widget.cells["independent"].geometry())
        self.window.block_runtime.save_widget_geometry(widget)
        self.window.block_runtime.refresh()
        restored = self.window.block_runtime.widgets[instance_id]
        self.assertEqual((40, 80, 200, 60), (
            restored.cells["anchored"].x(), restored.cells["anchored"].y(),
            restored.cells["anchored"].width(), restored.cells["anchored"].height(),
        ))

    def test_builtin_anchored_cells_follow_parent_resize(self) -> None:
        self.repository.add_class_level(
            self.first, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.window.sheet.refresh_all()
        self.application.processEvents()
        editor = self.window.nested_cell_editor
        block = self.window.sheet.prodigy_section
        anchored = self.window.sheet.prodigy_class_summary
        independent = self.window.sheet.prodigy_feature_summary

        editor._select(anchored, block, False)
        editor._persist_selected()
        editor.clear_selection()
        editor._select(independent, block, False)
        independent.resize(independent.width(), 30)
        editor._persist_selected()
        editor.set_anchored(False)
        editor.clear_selection()
        anchored_before = anchored.geometry()
        independent_before = independent.geometry()
        block_before = block.size()

        editor.begin_parent_resize(block)
        block.resize(
            round(block_before.width() * 1.5),
            round(block_before.height() * 1.5),
        )
        editor.preview_parent_resize(block)
        scale_x = block.width() / block_before.width()
        scale_y = block.height() / block_before.height()
        self.assertEqual(
            (
                round(anchored_before.x() * scale_x),
                round(anchored_before.y() * scale_y),
                max(20, round(anchored_before.width() * scale_x)),
                max(18, round(anchored_before.height() * scale_y)),
            ),
            (
                anchored.x(), anchored.y(),
                anchored.width(), anchored.height(),
            ),
        )
        self.assertEqual(independent_before, independent.geometry())
        editor.persist_block_cells(block)
        editor.finish_parent_resize()

        anchored_after = anchored.geometry()
        editor.apply_overrides()
        self.application.processEvents()
        self.assertEqual(anchored_after, anchored.geometry())
        self.assertEqual(independent_before, independent.geometry())

    def test_nested_editor_groups_and_reparents_cells_without_touching_data(self) -> None:
        source = BlockDefinition(
            "user:source", "Source", "Custom", width=320, height=180,
            cells=(
                CellDefinition("one", "number", "One", 20, 50, 90, 30, binding="hit_points.current"),
                CellDefinition("two", "label", "Two", 130, 50, 90, 30),
            ),
        )
        target = BlockDefinition(
            "user:target", "Target", "Custom", width=320, height=180,
            cells=(CellDefinition("label", "label", "Target", 20, 50, 90, 30),),
        )
        source_id = self.window.block_runtime.add_block(source, "core")
        target_id = self.window.block_runtime.add_block(target, "core")
        source_widget = self.window.block_runtime.widgets[source_id]
        target_widget = self.window.block_runtime.widgets[target_id]
        editor = self.window.nested_cell_editor
        editor._select(source_widget.cells["one"], source_widget, False)
        editor._select(source_widget.cells["two"], source_widget, True)
        editor.group_selected()
        editor.clear_selection()
        editor._select(source_widget.cells["one"], source_widget, False)
        self.assertEqual(2, len(editor.selected))
        editor._reparent_selected(target_widget)
        overrides = self.window.block_repository.list_cell_overrides(source_id)
        self.assertTrue(all(item.config.get("parent_instance_key") for item in overrides))
        self.assertEqual(0, self.repository.get_hit_points(self.first).current)

    def test_layout_managed_builtin_cell_keeps_resized_geometry(self) -> None:
        self.window.build_mode_action.setChecked(True)
        self.repository.add_class_level(
            self.first, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.window.sheet.refresh_all()
        self.application.processEvents()

        block = self.window.sheet.prodigy_section
        cell = self.window.sheet.prodigy_class_summary
        neighbor = self.window.sheet.prodigy_feature_summary
        layout = block.layout()
        QTest.qWait(100)
        self.assertGreaterEqual(layout.indexOf(cell), 0)

        neighbor_before = neighbor.geometry()
        instance_before = next(
            item.id
            for item in self.window.block_repository.list_instances(self.first)
            if item.template_key == "builtin:prodigy_sequence"
        )

        editor = self.window.nested_cell_editor
        def resize_cell() -> None:
            editor._select(cell, block, False)
            self.application.processEvents()
            self.assertEqual(-1, layout.indexOf(cell))
            self.assertEqual(neighbor_before, neighbor.geometry())
            placeholder = editor._layout_placeholders[cell]
            self.assertEqual(0, placeholder.minimumWidth())
            self.assertEqual(0, placeholder.minimumHeight())
            self.assertFalse(placeholder.autoFillBackground())
            self.assertNotEqual(
                QSizePolicy.Policy.Fixed,
                placeholder.sizePolicy().horizontalPolicy(),
            )
            self.assertNotEqual(
                QSizePolicy.Policy.Fixed,
                placeholder.sizePolicy().verticalPolicy(),
            )
            cell.resize(max(20, cell.width() // 2), 34)
            editor._persist_selected()

        self.window.presentation_history.record("Resize Prodigy summary", resize_cell)
        resized = cell.geometry()

        editor.apply_overrides()
        self.application.processEvents()
        self.assertEqual(-1, layout.indexOf(cell))
        self.assertEqual(resized, cell.geometry())

        with (
            patch.object(self.window.tab_manager, "load_character") as reload_tabs,
            patch.object(self.window.block_runtime, "load_character") as reload_blocks,
        ):
            self.window.undo()
        reload_tabs.assert_not_called()
        reload_blocks.assert_not_called()
        self.application.processEvents()
        self.assertGreaterEqual(layout.indexOf(cell), 0)
        self.assertEqual(
            instance_before,
            next(
                item.id
                for item in self.window.block_repository.list_instances(self.first)
                if item.template_key == "builtin:prodigy_sequence"
            ),
        )
        self.window.redo()
        self.application.processEvents()
        self.assertEqual(-1, layout.indexOf(cell))
        self.assertEqual(resized, cell.geometry())

        self.window.block_repository.reset_character_presentation(
            self.first, self.window.block_registry
        )
        self.window.block_runtime.load_character(self.first)
        editor.load_character(self.first)
        self.application.processEvents()
        self.assertGreaterEqual(layout.indexOf(cell), 0)

    def test_delete_key_removes_selected_visual_cell_and_is_undoable(self) -> None:
        self.window.build_mode_action.setChecked(True)
        self.repository.add_class_level(
            self.first, "Prodigy", 1, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=8,
        )
        self.window.sheet.refresh_all()
        self.application.processEvents()
        editor = self.window.nested_cell_editor
        editor.set_enabled(True)
        block = self.window.sheet.prodigy_section
        cell = self.window.sheet.prodigy_class_summary
        editor._select(cell, block, False)
        placeholder = editor._layout_placeholders[cell]
        layout = block.layout()
        layout_count_with_placeholder = layout.count()

        event = QKeyEvent(
            QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier
        )
        self.assertTrue(self.window.customization.eventFilter(self.window, event))
        self.assertTrue(cell.isHidden())
        override = next(
            item
            for instance in self.window.block_repository.list_instances(self.first)
            if instance.template_key == "builtin:prodigy_sequence"
            for item in self.window.block_repository.list_cell_overrides(instance.id)
            if item.cell_key == "attr:prodigy_class_summary"
        )
        self.assertFalse(override.visible)
        self.application.processEvents()
        self.assertNotIn(cell, editor._layout_placeholders)
        self.assertEqual(-1, layout.indexOf(placeholder))
        self.assertEqual(layout_count_with_placeholder - 1, layout.count())

        self.window.undo()
        self.application.processEvents()
        self.assertFalse(cell.isHidden())
        self.assertGreaterEqual(block.layout().indexOf(cell), 0)

    def test_anchor_to_parent_restores_builtin_cell_to_native_layout(self) -> None:
        self.repository.add_class_level(
            self.first, "Prodigy", 1, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=8,
        )
        self.window.sheet.refresh_all()
        self.application.processEvents()
        editor = self.window.nested_cell_editor
        block = self.window.sheet.prodigy_section
        cell = self.window.sheet.prodigy_class_summary
        layout = block.layout()

        editor._select(cell, block, False)
        cell.move(cell.x() + 40, cell.y() + 20)
        editor._persist_selected()
        self.assertEqual(-1, layout.indexOf(cell))
        self.assertTrue(
            any(
                item.cell_key == "attr:prodigy_class_summary"
                for instance in self.window.block_repository.list_instances(self.first)
                if instance.template_key == "builtin:prodigy_sequence"
                for item in self.window.block_repository.list_cell_overrides(instance.id)
            )
        )

        editor.set_anchored(True)
        self.application.processEvents()

        self.assertGreaterEqual(layout.indexOf(cell), 0)
        self.assertNotIn(cell, editor._layout_placeholders)
        self.assertFalse(
            any(
                item.cell_key == "attr:prodigy_class_summary"
                for instance in self.window.block_repository.list_instances(self.first)
                if instance.template_key == "builtin:prodigy_sequence"
                for item in self.window.block_repository.list_cell_overrides(instance.id)
            )
        )

        self.window.undo()
        self.application.processEvents()
        self.assertEqual(-1, layout.indexOf(cell))

    def test_future_registered_cell_type_renders_without_catalogue_changes(self) -> None:
        descriptor = CellTypeDescriptor(
            "sample.badge", "Sample Badge", 60, 24,
            runtime_factory=lambda parent, cell, context: QLabel(
                f"Badge: {cell.label}", parent
            ),
        )
        CELL_TYPE_REGISTRY.register(descriptor)
        try:
            definition = BlockDefinition(
                "sample:block", "Future Block", "Sample", width=260, height=130,
                cells=(CellDefinition("badge", "sample.badge", "Ready", 20, 50, 180, 30),),
            )
            instance_id = self.window.block_runtime.add_block(definition, "core")
            rendered = self.window.block_runtime.widgets[instance_id].cells["badge"]
            self.assertIsInstance(rendered, QLabel)
            self.assertEqual("Badge: Ready", rendered.text())
        finally:
            CELL_TYPE_REGISTRY.unregister("sample.badge")

    def test_cell_context_menu_receives_clicks_executes_and_closes(self) -> None:
        definition = BlockDefinition(
            "user:menu", "Menu", "Custom", width=260, height=130,
            cells=(CellDefinition("value", "label", "Value", 20, 50, 120, 30),),
        )
        instance_id = self.window.block_runtime.add_block(definition, "core")
        block = self.window.block_runtime.widgets[instance_id]
        cell = block.cells["value"]
        editor = self.window.nested_cell_editor
        editor.set_enabled(True)

        popup = QMenu(block)
        popup_child = QWidget(popup)
        event = QEvent(QEvent.Type.MouseButtonPress)
        self.assertFalse(editor.handle(popup_child, event))
        self.assertFalse(self.window.customization.eventFilter(popup_child, event))

        menu = editor._build_context_menu(block, cell)
        self.assertIs(menu.parentWidget(), self.window.sheet)
        menu.actions()[0].trigger()
        override = self.window.block_repository.list_cell_overrides(instance_id)[0]
        self.assertFalse(override.visible)
        self.assertFalse(editor.popup_active)

    def test_scrolling_is_ready_after_loading_without_toggling_build_mode(self) -> None:
        tab_key = self.window.tab_manager.add_tab("Long Page")
        self.window.sheet.session._reload_tabs()
        definition = BlockDefinition(
            "user:low_block", "Low Block", "Custom", width=320, height=180,
            cells=(CellDefinition("label", "label", "At the bottom", 20, 50, 180, 30),),
        )
        self.window.block_repository.add_instance(
            self.first, definition, tab_key, x=30, y=1450
        )
        self.window.block_runtime.refresh()
        self.window.customization.refresh_canvas_sizes()
        scroll, canvas, _layout = self.window.tab_manager.custom_pages[tab_key]
        self.assertGreaterEqual(canvas.minimumHeight(), 1650)
        self.window.sheet.page_tabs.setCurrentWidget(scroll)
        self.application.processEvents()
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        self.assertFalse(self.window.customization.build_mode)


    def test_restore_default_sheet_preserves_rules_and_global_templates(self) -> None:
        self.repository.update_hit_points(
            replace(self.repository.get_hit_points(self.first), current=25)
        )
        definition = BlockDefinition(
            "user:kept_template", "Kept Template", "Custom", width=260, height=130,
            cells=(CellDefinition("value", "number", "HP", 20, 50, 100, 30, binding="hit_points.current"),),
        )
        self.window.block_repository.save_user_template(definition)
        custom_tab = self.window.tab_manager.add_tab("Temporary Page")
        self.window.sheet.session._reload_tabs()
        self.window.block_runtime.add_block(definition, custom_tab)
        self.window.block_repository.rename_tab(self.first, "core", "My Core")
        builtin = next(
            item for item in self.window.block_repository.list_instances(self.first)
            if item.template_key == "builtin:abilities"
        )
        self.window.block_repository.save_cell_override(CellOverride(
            0, builtin.id, "attr:ability_total_labels.strength",
            70, 70, 120, 40, False, False, "", "", "", "", {}, {},
        ))
        self.window.customization.settings.setValue("customization/colors/test", "#123456")

        self.assertTrue(self.window.restore_default_sheet(confirm=False))
        self.application.processEvents()
        self.assertEqual(
            [key for key, _ in self.window.block_repository.default_tabs],
            [tab.key for tab in self.window.block_repository.list_tabs(self.first)],
        )
        instances = self.window.block_repository.list_instances(self.first)
        self.assertEqual(len(self.window.block_registry.all()), len(instances))
        self.assertTrue(all(item.template_key.startswith("builtin:") for item in instances))
        self.assertTrue(all(
            not self.window.block_repository.list_cell_overrides(item.id)
            for item in instances
        ))
        self.assertEqual(25, self.repository.get_hit_points(self.first).current)
        self.assertIn(
            "user:kept_template",
            [item.key for item in self.window.block_repository.list_user_templates()],
        )
        self.assertNotIn("colors/test", self.window.customization.capture_state())
        self.assertEqual(len(self.window.block_repository.default_tabs), self.window.sheet.page_tabs.count())
        self.window.undo()
        self.application.processEvents()
        self.assertIn(
            "Temporary Page",
            [tab.name for tab in self.window.block_repository.list_tabs(self.first)],
        )
        self.assertEqual(25, self.repository.get_hit_points(self.first).current)
        self.window.redo()
        self.application.processEvents()
        self.assertEqual(len(self.window.block_repository.default_tabs), self.window.sheet.page_tabs.count())

    def test_table_columns_can_be_added_removed_moved_and_undone(self) -> None:
        controller = self.window.customization.table_layout
        table = self.window.sheet.skill_table
        table_id = str(table.property("tableLayoutId"))
        original_count = table.columnCount()
        self.window.customization.set_build_mode(True)

        custom_key = controller.add_custom_column(table_id, "Campaign Note")
        self.assertEqual(original_count + 1, table.columnCount())
        custom_logical = controller._logical_for_key(table, custom_key)
        self.assertGreaterEqual(custom_logical, 0)
        table.horizontalHeader().moveSection(
            table.horizontalHeader().visualIndex(custom_logical), 1
        )
        controller.flush()

        controller.remove_column(table_id, "builtin:2")
        self.assertTrue(table.isColumnHidden(2))
        self.window.undo()
        self.application.processEvents()
        self.assertFalse(table.isColumnHidden(2))
        self.window.undo()
        self.application.processEvents()
        self.assertEqual(original_count, table.columnCount())
        self.window.redo()
        self.application.processEvents()
        self.assertEqual(original_count + 1, table.columnCount())
        self.window.redo()
        self.application.processEvents()
        self.assertTrue(table.isColumnHidden(2))

        controller.restore_column(table_id, "builtin:2")
        self.assertFalse(table.isColumnHidden(2))
        controller.rename_custom_column(table_id, custom_key, "Session Note")
        custom_logical = controller._logical_for_key(table, custom_key)
        self.assertEqual(
            "Session Note", table.horizontalHeaderItem(custom_logical).text()
        )


if __name__ == "__main__":
    unittest.main()

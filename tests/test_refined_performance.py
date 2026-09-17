"""Regression guards for bounded UI work and atomic presentation setup."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
from PySide6.QtCore import QEvent
from app.database import CharacterRepository
from app.presentation_storage import SheetStyleStore, StyleBlockRepository
from app.building_blocks.registry import register_builtin_blocks
from app.ui.refined.pages import DEFAULT_TABS
from app.ui.refined.components import TablePresentation, TableDisclosure
from app.ui.customization import SheetCustomizationController
from app.class_feature_rules import feature_token, _text_token


class RefinedStoragePerformanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repo = CharacterRepository(Path(self.folder.name) / "character.db")
        self.cid = self.repo.create_character("Performance", "Pathfinder 1e")
        self.blocks = StyleBlockRepository(self.repo, "refined", DEFAULT_TABS)
        self.registry = register_builtin_blocks()

    def tearDown(self):
        self.repo.close()
        self.folder.cleanup()

    def test_initial_layout_is_one_transaction_and_second_load_writes_nothing(self):
        statements = []
        self.repo.sqlite_connection.set_trace_callback(statements.append)
        self.blocks.ensure_character(self.cid, self.registry)
        self.assertEqual(1, sum(s.startswith("RELEASE SAVEPOINT") for s in statements))
        self.assertFalse(any(s == "COMMIT" for s in statements))
        before = self.repo.sqlite_connection.total_changes
        self.blocks.ensure_character(self.cid, self.registry)
        self.assertEqual(before, self.repo.sqlite_connection.total_changes)
        self.repo.sqlite_connection.set_trace_callback(None)

    def test_failed_initialization_rolls_back_every_new_block_and_tab(self):
        original = self.blocks.add_instance
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise ValueError("test failure")
        with patch.object(self.blocks, "add_instance", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "test failure"):
                self.blocks.ensure_character(self.cid, self.registry)
        self.assertFalse(self.blocks.list_instances(self.cid))
        self.assertFalse(self.blocks.list_tabs(self.cid))
        self.blocks.ensure_character(self.cid, self.registry)
        self.assertTrue(self.blocks.list_instances(self.cid))

    def test_unchanged_preferences_do_not_write(self):
        store = SheetStyleStore(self.repo)
        state = {"page": "core", "expanded_sections": ["special_abilities"]}
        store.save(self.cid, "refined", state)
        before = self.repo.sqlite_connection.total_changes
        store.save(self.cid, "refined", state)
        self.assertEqual(before, self.repo.sqlite_connection.total_changes)


class RefinedDisclosurePerformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.section = QWidget()
        layout = QVBoxLayout(self.section)
        self.table = QTableWidget(18, 2)
        layout.addWidget(self.table)
        for row in range(18):
            self.table.setItem(row, 0, QTableWidgetItem(str(row)))
            self.table.setItem(row, 1, QTableWidgetItem(f"Ability {row}"))
        self.adapter = TablePresentation(self.table, self.section)
        self.disclosure = TableDisclosure(self.adapter, self.section, preview_rows=6)

    def tearDown(self):
        self.section.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_show_all_is_immediate_even_with_custom_geometry(self):
        for property_name in ("freeformManaged", "fillAvailableHeight"):
            with self.subTest(property_name=property_name):
                self.table.setProperty(property_name, True)
                self.table.setFixedHeight(240)
                self.disclosure.set_expanded(False)
                self.assertEqual(6, sum(not self.table.isRowHidden(r) for r in range(18)))
                self.disclosure.click()
                self.assertEqual(18, sum(not self.table.isRowHidden(r) for r in range(18)))
                self.assertEqual(240, self.table.maximumHeight())
                self.assertIn("fewer", self.disclosure.text())
                self.table.setProperty(property_name, False)

    def test_hidden_table_does_not_measure_rows_on_background_refresh(self):
        with patch.object(self.adapter, "fit") as fit:
            self.adapter._fit_visible()
            fit.assert_not_called()

    def test_fitting_does_not_schedule_itself_forever(self):
        self.adapter.fit()
        self.assertFalse(self.adapter.timer.isActive())
        self.assertFalse(self.adapter._fitting)

    def test_idle_editor_does_not_walk_the_widget_tree(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        controller = SimpleNamespace(build_mode=False, paint_color=None,
                                     nested_editor=SimpleNamespace(enabled=False))
        controller._section_for = Mock(side_effect=AssertionError("idle hierarchy walk"))
        self.assertFalse(SheetCustomizationController.eventFilter(
            controller, self.table, QEvent(QEvent.Type.Paint)))
        controller._section_for.assert_not_called()

    def test_feature_normalization_cache_is_pure_and_bounded(self):
        _text_token.cache_clear()
        first = feature_token("Judgment 1/day")
        self.assertEqual(first, feature_token("Judgment 1/day"))
        self.assertEqual(1, _text_token.cache_info().hits)
        self.assertEqual(8192, _text_token.cache_info().maxsize)
        self.assertEqual("domain", feature_token("Domains"))
        self.assertNotEqual(first, feature_token("Bardic performance"))


if __name__ == "__main__":
    unittest.main()

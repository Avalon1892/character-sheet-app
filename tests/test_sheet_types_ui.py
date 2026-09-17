from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.services.sheet_presentation import build_character_sheet_snapshot
from app.ui.main_window import MainWindow
from app.ui.sheet_types import (
    DEFAULT_SHEET_TYPE,
    SHEET_TYPE_REGISTRY,
    normalize_sheet_type,
)


class SheetTypeTests(unittest.TestCase):
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
        self.repository = CharacterRepository(Path(self.root.name) / "characters.db")
        self.character_id = self.repository.create_character("Spheres Test", "Spheres")

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_registry_is_extensible_and_unknown_values_fall_back(self) -> None:
        self.assertEqual(
            ["customizable", "original_spheres", "ultra", "refined"],
            list(SHEET_TYPE_REGISTRY),
        )
        self.assertEqual(DEFAULT_SHEET_TYPE, normalize_sheet_type("unknown"))
        self.assertTrue(SHEET_TYPE_REGISTRY["customizable"].supports_customization)
        self.assertFalse(
            SHEET_TYPE_REGISTRY["original_spheres"].supports_customization
        )
        self.assertFalse(SHEET_TYPE_REGISTRY["ultra"].supports_customization)

    def test_original_sheet_uses_the_shared_character_projection(self) -> None:
        snapshot = build_character_sheet_snapshot(self.repository, self.character_id)
        self.assertEqual("Spheres Test", snapshot.summary.name)
        self.assertEqual(6, len(snapshot.abilities))
        self.assertEqual(35, len(snapshot.skills))

    def test_menu_switches_and_persists_the_selected_sheet_type(self) -> None:
        window = MainWindow(self.repository)
        try:
            self.assertEqual("refined", window.sheet_type)
            self.assertFalse(window.build_menu.isEnabled())
            window.refresh_characters(self.character_id)
            self.application.processEvents()
            menu_names = [action.text().replace("&", "") for action in window.menuBar().actions()]
            self.assertLess(menu_names.index("Theme"), menu_names.index("Sheet Types"))
            self.assertEqual("refined", window.sheet_type)
            self.assertIsNone(window.original_spheres_sheet)

            window._set_sheet_type("original_spheres")
            self.assertEqual(4, window.original_spheres_sheet.page_tabs.count())
            self.assertIs(
                window.sheet_stack.currentWidget(), window.original_spheres_sheet
            )
            self.assertFalse(window.build_menu.isEnabled())
            self.assertFalse(window.color_menu.isEnabled())
            self.assertEqual(
                "original_spheres",
                QSettings("Georg", "Character Sheet App").value(
                    "appearance/sheetType"
                ),
            )

            window._set_sheet_type("customizable")
            self.assertIs(window.sheet_stack.currentWidget(), window.sheet)
            self.assertTrue(window.build_menu.isEnabled())
            self.assertTrue(window.color_menu.isEnabled())
        finally:
            window.close()

    def test_original_pages_match_the_source_page_geometry(self) -> None:
        widget = SHEET_TYPE_REGISTRY["original_spheres"].create(self.repository)
        try:
            self.assertEqual((1208, 1575), (widget.core_page.width(), widget.core_page.height()))
            self.assertEqual(
                (1575, 1208),
                (widget.companion_page.width(), widget.companion_page.height()),
            )
            widget.load_character(self.character_id)
            self.assertTrue(
                any(item.text == "Spheres Test" for item in widget.core_page._items)
            )
        finally:
            widget.close()


if __name__ == "__main__":
    unittest.main()

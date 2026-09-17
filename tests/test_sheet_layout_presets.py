from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.ui.main_window import MainWindow
from app.ui.sheet_layout_presets import (
    DEFAULT_SPHERES_PLACEMENTS,
    layout_preset_for_character_type,
)


class DefaultSpheresLayoutTests(unittest.TestCase):
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
        self.repository = CharacterRepository(Path(self.root.name) / "characters.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_preset_resolver_is_character_type_specific(self) -> None:
        spheres = layout_preset_for_character_type("Spheres")
        pathfinder = layout_preset_for_character_type("Pathfinder 1e")
        self.assertEqual("default_spheres", spheres.key)
        self.assertEqual("factory", pathfinder.key)
        self.assertTrue(spheres.presentation_state())
        self.assertEqual({}, pathfinder.presentation_state())

    def test_default_spheres_uses_responsive_layout_not_fixed_coordinates(self) -> None:
        self.assertEqual({}, DEFAULT_SPHERES_PLACEMENTS)
        self.assertNotIn(
            "freeform",
            layout_preset_for_character_type("Spheres").presentation_state(),
        )

    def test_new_spheres_character_receives_default_spheres_arrangement(self) -> None:
        character_id = self.repository.create_character("New Sphere Hero", "Spheres")
        window = MainWindow(self.repository)
        try:
            window.refresh_characters(character_id)
            window.show()
            self.application.processEvents()
            state = self.repository.get_character_sheet_layout(character_id)
            self.assertEqual("default_spheres", state["preset"])
            self.assertNotIn("freeform", state)
            self.assertIs(window.sheet.ability_summary_section.parent(), window.sheet.core_canvas)
            self.assertFalse(bool(window.sheet.ability_summary_section.property("freeformManaged")))
            self.assertTrue(window.sheet.ability_summary_section.isHidden())
            self.assertFalse(window.sheet.classic_statistics_section.isHidden())
            window.resize(1440, 900)
            self.application.processEvents()
            for index, scroll in enumerate(
                (
                    window.sheet.core_scroll,
                    window.sheet.inventory_scroll,
                    window.sheet.magic_scroll,
                ),
                start=1,
            ):
                window.sheet.page_tabs.setCurrentIndex(index)
                self.application.processEvents()
                self.assertEqual(0, scroll.horizontalScrollBar().maximum())
            self.assertIn("Default Spheres", window.reset_layout_action.text())
        finally:
            window.close()

    def test_reset_restores_default_spheres_without_removing_rules_data(self) -> None:
        character_id = self.repository.create_character("Rearranged", "Spheres")
        self.repository.add_feat(character_id, "Layout-Safe Feat", notes="Must survive")
        window = MainWindow(self.repository)
        try:
            window.refresh_characters(character_id)
            window.show()
            self.application.processEvents()
            window.sheet.ability_summary_section.setGeometry(200, 200, 700, 700)
            self.assertTrue(window.restore_default_sheet(confirm=False))
            self.application.processEvents()
            self.assertTrue(window.sheet.ability_summary_section.isHidden())
            self.assertFalse(window.sheet.classic_statistics_section.isHidden())
            self.assertFalse(bool(window.sheet.ability_summary_section.property("freeformManaged")))
            self.assertEqual(
                ["Layout-Safe Feat"],
                [feat.name for feat in self.repository.list_feats(character_id)],
            )
            self.assertEqual(
                "default_spheres",
                self.repository.get_character_sheet_layout(character_id)["preset"],
            )
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()

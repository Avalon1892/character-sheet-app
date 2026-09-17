from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QPushButton

from app.database import CharacterRepository
from app.ui.main_window import MainWindow


class CharacterLibraryUiTests(unittest.TestCase):
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
        self.first = self.repository.create_character("Ari", "Spheres")
        self.repository.add_class_level(
            self.first,
            "Prodigy",
            3,
            "3/4",
            "Poor",
            "Good",
            "Good",
            preset_key="prodigy",
            hit_die=8,
            hp_gained=18,
        )
        self.repository.add_class_level(
            self.first,
            "Fighter",
            2,
            "Full",
            "Good",
            "Poor",
            "Poor",
            preset_key="fighter",
            hit_die=10,
            hp_gained=12,
        )
        self.second = self.repository.create_character("Bex", "Pathfinder 1e")
        self.window = MainWindow(self.repository)

    def tearDown(self) -> None:
        self.window.close()
        self.repository.close()
        self.root.cleanup()

    def test_startup_opens_library_with_class_and_total_level_cards(self) -> None:
        self.assertIs(self.window.pages.currentWidget(), self.window.character_library)
        self.assertIsNone(self.window.active_character_id)
        cards = self.window.character_library.character_cards()
        self.assertEqual(2, len(cards))
        ari = next(card for card in cards if card.property("characterId") == self.first)
        self.assertIn("Ari", ari.text())
        self.assertIn("Prodigy / Fighter", ari.text())
        self.assertIn("Level 5", ari.text())
        bex = next(card for card in cards if card.property("characterId") == self.second)
        self.assertIn("No class selected", bex.text())
        self.assertIsNotNone(
            self.window.character_library.findChild(QPushButton, "createCharacterCard")
        )

    def test_opening_a_card_transitions_to_the_existing_sheet(self) -> None:
        card = next(
            card
            for card in self.window.character_library.character_cards()
            if card.property("characterId") == self.first
        )
        card.click()
        self.application.processEvents()
        self.assertEqual(self.first, self.window.active_character_id)
        self.assertEqual(self.first, self.window._selected_character().id)
        self.assertIs(self.window.pages.currentWidget(), self.window.pages.widget(1))

        self.window.show_character_library()
        self.assertIs(self.window.pages.currentWidget(), self.window.character_library)
        self.window._select_character(self.first)
        self.assertIs(self.window.pages.currentWidget(), self.window.pages.widget(1))

    def test_explicit_refresh_still_opens_a_character_for_existing_callers(self) -> None:
        self.window.refresh_characters(self.second)
        self.assertEqual(self.second, self.window.active_character_id)
        self.assertEqual(self.second, self.window._selected_character().id)
        self.assertEqual(1, self.window.pages.currentIndex())


if __name__ == "__main__":
    unittest.main()


from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.character_advancement_codex import character_advancement_codex_html
from app.ui.main_window import CodexDialog


class CharacterAdvancementCodexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_page_contains_progression_table_and_core_advancement_rules(self) -> None:
        html = character_advancement_codex_html()
        for text in (
            "Character Advancement",
            "5,350,000",
            "3,600,000",
            "2,400,000",
            "Multiclassing",
            "Favored class",
            "Prestige classes",
        ):
            self.assertIn(text, html)

    def test_codex_tree_and_search_open_character_advancement(self) -> None:
        dialog = CodexDialog("character_advancement")
        try:
            self.assertEqual("Character Advancement", dialog.tree.currentItem().text(0))
            self.assertIn("Advancement and level-dependent bonuses", dialog.browser.toPlainText())
            dialog.codex_search.setText("favored class")
            dialog._search_codex()
            self.assertIn("Character Advancement", dialog.browser.toPlainText())
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()

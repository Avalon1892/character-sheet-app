from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.archetype_presentation import (
    archetype_change_labels,
    archetype_collection_row_html,
    archetype_rule_sections,
    archetype_rules_html,
)
from app.content import archetype_entries
from app.ui.dialogs import ArchetypeSelectionDialog


class ArchetypePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    @staticmethod
    def abolisher() -> dict:
        return next(
            entry for entry in archetype_entries("pathfinder-class:inquisitor")
            if entry["name"] == "Abolisher"
        )

    @staticmethod
    def captain() -> dict:
        return next(
            entry for entry in archetype_entries("spheres-class:advisor")
            if entry["name"] == "Captain"
        )

    def test_feature_changes_are_concise_and_rules_are_split_by_feature(self) -> None:
        entry = self.abolisher()
        self.assertIn("Domains", archetype_change_labels(entry))
        sections = archetype_rule_sections(entry)
        purity = next(section for section in sections if section.title == "Sworn to Purity")
        self.assertTrue(any("alters domains" in claim.casefold() for claim in purity.changes))
        self.assertNotIn("This ability alters domains", purity.body)

    def test_shared_html_prioritizes_replacements_and_feature_cards(self) -> None:
        entry = self.abolisher()
        rendered = archetype_rules_html(entry)
        self.assertIn("Class feature changes", rendered)
        self.assertIn("Archetype features", rendered)
        self.assertIn("Sworn to Purity", rendered)
        self.assertIn("Class-feature interaction", rendered)
        self.assertIn("codex:archetype:", archetype_collection_row_html(entry))

    def test_picker_shows_replacement_summary_as_its_own_column(self) -> None:
        dialog = ArchetypeSelectionDialog("pathfinder-class:inquisitor")
        self.assertEqual(4, dialog.results.columnCount())
        self.assertEqual("Replaces / alters", dialog.results.horizontalHeaderItem(2).text())
        self.assertTrue(dialog.results.item(0, 2).text())
        dialog.close()

    def test_spheres_line_based_rules_become_readable_feature_sections(self) -> None:
        entry = self.captain()
        sections = archetype_rule_sections(entry)
        titles = [section.title for section in sections]
        self.assertIn("Deadly Acumen", titles)
        self.assertIn("Combat Strategy", titles)
        self.assertIn("Improved Strategies", titles)
        self.assertGreaterEqual(titles.count("Class-feature interaction"), 4)
        rendered = archetype_rules_html(entry)
        self.assertGreaterEqual(rendered.count("<h3>"), 8)
        self.assertIn("This replaces factotum", rendered)
        self.assertNotIn("Deadly Acumen At 2nd level", rendered)


if __name__ == "__main__":
    unittest.main()

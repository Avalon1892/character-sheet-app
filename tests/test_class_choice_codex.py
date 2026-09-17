from __future__ import annotations

import unittest

from app.catalogs import DEFAULT_CATALOG
from app.codex_index import build_codex_search_records
from app.ui.main_window import CodexDialog


class ClassChoiceCodexTests(unittest.TestCase):
    def test_all_choice_families_are_searchable_and_renderable(self) -> None:
        choices = DEFAULT_CATALOG.class_choice_entries()
        self.assertGreaterEqual(len(choices), 610)
        self.assertEqual(
            {
                "arcane_school", "bloodline", "domain", "inquisition",
                "kineticist_element", "mystery", "oracle_curse", "order",
                "occultist_implement", "occultist_panoply", "phantom_focus",
                "psychic_discipline", "shaman_spirit", "shifter_aspect",
                "warpriest_blessing", "witch_patron",
            },
            {str(entry["family"]) for entry in choices},
        )
        records = build_codex_search_records(DEFAULT_CATALOG)
        fire = next(
            record for record in records
            if record["name"] == "Fire Domain"
            and "Feature Choices" in record["category"]
        )
        self.assertTrue(fire["target"].startswith("class-choice:"))
        html = CodexDialog._class_choice_html(
            DEFAULT_CATALOG.class_choice_entry(
                "class-choice:arcane_school:evocation-school"
            )
        )
        self.assertIn("Evocation School", html)
        self.assertIn("Granted features", html)


if __name__ == "__main__":
    unittest.main()

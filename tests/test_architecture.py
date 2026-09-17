import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QTableWidget

from app.catalogs import RulesCatalog
from app.database import CharacterRepository
from app.feature_registry import FEATURE_CATEGORIES, FeatureKind
from app.models import Feat
from app.presentation import feature_details_html, feature_summary_text, readable_tooltip
from app.services.character_calculations import CharacterCalculationService
from app.services.character_state import CharacterStateSnapshot
from app.ui.components import fit_table_rows, numeric_field
from app.ui.theme import THEME_LABELS, normalize_theme, style_sheet


class ArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_feature_registry_covers_every_rules_bearing_family(self) -> None:
        self.assertEqual(
            {
                FeatureKind.MARTIAL_TALENT,
                FeatureKind.MAGIC_TALENT,
                FeatureKind.FEAT,
                FeatureKind.TRAIT,
                FeatureKind.SPELL,
                FeatureKind.SPECIAL_ABILITY,
                FeatureKind.PRODIGY_OPENER,
                FeatureKind.PRODIGY_LINK,
                FeatureKind.PRODIGY_FINISHER,
                FeatureKind.EQUIPMENT,
            },
            set(FEATURE_CATEGORIES),
        )

    def test_theme_selection_and_styles_are_centralized(self) -> None:
        self.assertEqual(("classic", "light", "dark"), tuple(THEME_LABELS))
        self.assertEqual("classic", normalize_theme("unknown"))
        self.assertEqual(3, len({style_sheet(theme) for theme in THEME_LABELS}))

    def test_shared_presentation_formats_hover_and_details(self) -> None:
        feat = Feat(
            1,
            "Architectural Example",
            notes="Complete rules description.",
            prerequisites="Base attack bonus +1",
            source_url="https://example.invalid/rule",
        )
        summary = feature_summary_text("Feat", feat)
        self.assertIn("Complete rules description.", summary)
        self.assertIn("Prerequisites", summary)
        self.assertIn("Architectural Example", readable_tooltip(feat.name, summary))
        self.assertIn("Open rules page", feature_details_html("Feat", feat))

    def test_state_and_calculation_services_are_independent_of_widgets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = CharacterRepository(Path(directory) / "characters.db")
            try:
                character_id = repository.create_character("Service Test", "Pathfinder 1e")
                state = CharacterStateSnapshot.load(repository, character_id)
                calculations = CharacterCalculationService(repository, character_id)
                self.assertEqual(character_id, state.character_id)
                self.assertEqual(6, len(calculations.ability_results()))
                self.assertIn("ac", calculations.combat_results())
            finally:
                repository.close()

    def test_catalog_gateway_and_reusable_numeric_table_components(self) -> None:
        catalog = RulesCatalog()
        self.assertEqual("Fighter", catalog.entry_by_key("classes", "fighter")["name"])
        number = numeric_field(-5, 10)
        self.assertEqual((-5, 10), (number.minimum(), number.maximum()))
        table = QTableWidget(0, 1)
        fit_table_rows(table, 2, 2, 3)
        compact_height = table.height()
        fit_table_rows(table, 5, 2, 3)
        self.assertGreater(table.height(), compact_height)


if __name__ == "__main__":
    unittest.main()

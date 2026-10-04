import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QAbstractItemView

from app.content import feat_entry
from app.database import CharacterRepository
from app.models import HitPoints
from app.ui.character_sheet import FeatCatalogDialog
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class FeatCatalogUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "characters.db"
        self.repository = CharacterRepository(database_path)
        self.character_id = self.repository.create_character("Feat Hero", "Pathfinder 1e")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temporary_directory.cleanup()

    def test_feat_browser_filters_sources_and_automatic_behavior(self) -> None:
        dialog = FeatCatalogDialog([], self.sheet)
        self.assertEqual(4672, dialog.results.rowCount())  # Includes Forge Construct and the two Tech graft-crafting feats.

        dialog.source_filter.setCurrentIndex(
            dialog.source_filter.findData("Pathfinder")
        )
        self.assertEqual(3442, dialog.results.rowCount())
        dialog.automation_filter.setCurrentIndex(
            dialog.automation_filter.findData("automatic")
        )
        self.assertEqual(33, dialog.results.rowCount())
        dialog.automation_filter.setCurrentIndex(
            dialog.automation_filter.findData("toggle")
        )
        self.assertEqual(5, dialog.results.rowCount())

        dialog.automation_filter.setCurrentIndex(0)
        dialog.source_filter.setCurrentIndex(dialog.source_filter.findData("Spheres"))
        dialog.search.setText("Extra Magic Talent")
        self.assertIn(
            "Extra Magic Talent",
            [
                dialog.results.item(row, 1).text()
                for row in range(dialog.results.rowCount())
            ],
        )
        dialog.close()

    def test_feat_browser_and_sheet_add_multiple_entries_in_one_batch(self) -> None:
        dialog = FeatCatalogDialog([], self.sheet)
        self.assertEqual(
            QAbstractItemView.SelectionMode.SingleSelection,
            dialog.results.selectionMode(),
        )
        for row in (0, 1):
            dialog.results.setCurrentCell(row, 1)
            dialog._queue_current_entry()
        self.assertEqual("Add Selected (2)", dialog.add_button.text())
        dialog._accept_selected()
        self.assertEqual(2, len(dialog.selected_entries))

        entries = (
            feat_entry("aon:improved-initiative"),
            feat_entry("aon:toughness"),
        )
        added = self.sheet._add_catalog_batch(
            tuple(entry for entry in entries if entry is not None),
            self.sheet._add_catalog_feat,
            self.sheet._feats_changed,
            "feats",
        )
        self.assertEqual(2, added)
        self.assertEqual(2, len(self.repository.list_feats(self.character_id)))

    def test_catalog_feats_change_initiative_and_manual_maximum_hp(self) -> None:
        initiative = feat_entry("aon:improved-initiative")
        self.assertIsNotNone(initiative)
        self.assertTrue(self.sheet._add_catalog_feat(initiative))
        self.sheet._feats_changed()
        self.assertEqual(4, self.sheet._combat_results()["initiative"].total)

        self.repository.update_hit_points(
            HitPoints(self.character_id, maximum=10, current=10, auto_calculate=False)
        )
        toughness = feat_entry("aon:toughness")
        self.assertIsNotNone(toughness)
        self.assertTrue(self.sheet._add_catalog_feat(toughness))
        self.sheet._feats_changed()
        self.assertEqual(13, self.sheet.hp_maximum.value())
        self.assertEqual(10, self.repository.get_hit_points(self.character_id).maximum)

        power_attack = feat_entry("aon:power-attack")
        self.assertIsNotNone(power_attack)
        self.assertTrue(self.sheet._add_catalog_feat(power_attack))
        power_attack_row = next(
            feat
            for feat in self.repository.list_feats(self.character_id)
            if feat.catalog_key == "aon:power-attack"
        )
        self.assertFalse(power_attack_row.enabled)
        self.assertEqual("toggle", power_attack_row.activation)


if __name__ == "__main__":
    unittest.main()

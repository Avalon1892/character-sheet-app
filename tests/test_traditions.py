import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog

from app.catalogs import DEFAULT_CATALOG
from app.codex_index import build_codex_search_records
from app.database import CharacterRepository
from app.models import CastingProfile
from app.services.character_calculations import CharacterCalculationService
from app.services.sheet_presentation import build_character_sheet_snapshot
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.ui.dialogs import TraditionChoiceDialog
from app.tradition_rules import resolved_tradition_definition, spell_point_rule_for_unused_drawbacks


class TraditionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Traditionalist", "Spheres")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_complete_catalog_and_codex_projection(self) -> None:
        self.assertEqual(89, len(DEFAULT_CATALOG.tradition_entries("Casting")))
        self.assertEqual(66, len(DEFAULT_CATALOG.tradition_entries("Martial")))
        records = build_codex_search_records(DEFAULT_CATALOG)
        self.assertTrue(any(record["name"] == "Traditional Magic" and record["category"] == "Traditions · Casting" for record in records))
        self.assertTrue(any(record["name"] == "Ace" and record["category"] == "Traditions · Martial" for record in records))

    def test_drawbacks_and_boons_have_distinct_codex_categories(self) -> None:
        rules = DEFAULT_CATALOG.tradition_rule_entries()
        self.assertGreater(len(rules), 400)
        categories = {
            (entry.get("kind"), entry.get("category")) for entry in rules
        }
        self.assertIn(("Casting", "General Drawback"), categories)
        self.assertIn(("Casting", "Sphere-Specific Drawback"), categories)
        self.assertIn(("Casting", "Dual Sphere Drawback"), categories)
        self.assertIn(("Casting", "Boon"), categories)
        self.assertIn(("Martial", "Sphere-Specific Drawback"), categories)
        records = build_codex_search_records(DEFAULT_CATALOG)
        limited_warp = next(
            record for record in records
            if record["name"] == "Limited Warp"
            and "Sphere-Specific Drawback" in record["category"]
        )
        self.assertIn("Warp", limited_warp["category"])

    def test_character_tradition_round_trip_and_dynamic_spell_points(self) -> None:
        entry = next(item for item in DEFAULT_CATALOG.tradition_entries("Casting") if item["name"] == "Traditional Magic")
        self.repository.update_casting_profile(CastingProfile(
            character_id=self.character_id,
            casting_ability="intelligence",
            casting_class_levels=5,
            auto_spell_points=True,
            tradition_name=entry["name"],
        ))
        tradition_id = self.repository.add_character_tradition(
            self.character_id, entry["key"], entry["name"], "Casting",
            json.dumps({}), json.dumps([]),
        )
        stored = self.repository.list_character_traditions(self.character_id)
        self.assertEqual([tradition_id], [item.id for item in stored])
        contribution = next(
            item for item in CharacterCalculationService(self.repository, self.character_id).spell_point_contributions()
            if item.source == "Tradition: Traditional Magic"
        )
        self.assertEqual(5, contribution.value)

    def test_incompatible_energies_automatically_reduces_msd_only(self) -> None:
        entry = next(
            item for item in DEFAULT_CATALOG.tradition_entries("Casting")
            if "Incompatible Energies" in str(item.get("drawbacks", ""))
        )
        self.repository.update_casting_profile(CastingProfile(
            character_id=self.character_id,
            casting_ability="intelligence",
            casting_class_levels=5,
            caster_level=5,
        ))
        tradition_id = self.repository.add_character_tradition(
            self.character_id, entry["key"], entry["name"], "Casting"
        )
        calculator = CharacterCalculationService(self.repository, self.character_id)
        self.assertEqual(-3, calculator.automatic_total("magic_skill_defense"))
        self.assertEqual(0, calculator.automatic_total("magic_skill_bonus"))
        self.assertEqual(0, calculator.automatic_total("caster_level"))
        presented = build_character_sheet_snapshot(
            self.repository, self.character_id
        ).casting
        self.assertEqual(5, presented.magic_skill_bonus)
        self.assertEqual(13, presented.magic_skill_defense)
        self.assertEqual(5, presented.caster_level)

        self.repository.delete_character_tradition(self.character_id, tradition_id)
        refreshed = CharacterCalculationService(self.repository, self.character_id)
        self.assertEqual(0, refreshed.automatic_total("magic_skill_defense"))

    def test_choice_dialog_builds_catalog_driven_options(self) -> None:
        entry = next(item for item in DEFAULT_CATALOG.tradition_entries("Martial") if item["name"] == "Animal Trainer")
        dialog = TraditionChoiceDialog(entry)
        try:
            self.assertEqual(1, len(dialog._groups))
            group, picker = dialog._groups[0]
            self.assertEqual(2, group["count"])
            self.assertGreater(picker.count(), 20)
        finally:
            dialog.close()

    def test_sheet_lists_saved_traditions(self) -> None:
        entry = next(item for item in DEFAULT_CATALOG.tradition_entries("Martial") if item["name"] == "Barbarian")
        self.repository.add_character_tradition(
            self.character_id, entry["key"], entry["name"], "Martial",
            json.dumps({"choice-1": ["Barroom Sphere"]}), json.dumps([]),
        )
        sheet = CharacterSheetWidget(self.repository)
        try:
            sheet.load_character(self.character_id)
            self.assertEqual(1, sheet.tradition_table.rowCount())
            self.assertEqual("Barbarian", sheet.tradition_table.item(0, 1).text())
        finally:
            sheet.close()

    def test_martial_tradition_applies_fixed_and_selected_grants(self) -> None:
        entry = next(item for item in DEFAULT_CATALOG.tradition_entries("Martial") if item["name"] == "Barbarian")
        selected = next(option for option in entry["choice_groups"][0]["options"] if option["label"] == "Barroom Sphere")
        catalog_dialog = SimpleNamespace(
            selected_entry=entry,
            exec=lambda: QDialog.DialogCode.Accepted,
        )
        choice_dialog = SimpleNamespace(
            choices={"choice-1": ["Barroom Sphere"]},
            grants=tuple(entry["fixed_grants"]) + tuple(selected["grants"]),
            exec=lambda: QDialog.DialogCode.Accepted,
        )
        sheet = CharacterSheetWidget(self.repository)
        try:
            sheet.load_character(self.character_id)
            with patch("app.ui.character_sheet.TraditionCatalogDialog", return_value=catalog_dialog), patch(
                "app.ui.character_sheet.TraditionChoiceDialog", return_value=choice_dialog
            ):
                sheet._add_tradition("Martial")
            names = {item.name for item in self.repository.list_martial_talents(self.character_id)}
            self.assertIn("Berserker Sphere", names)
            self.assertIn("Scout Sphere", names)
            self.assertIn("Barroom Sphere", names)
            self.assertEqual("Barbarian", self.repository.list_character_traditions(self.character_id)[0].name)
        finally:
            sheet.close()

    def test_custom_casting_tradition_grants_magic_and_spell_points(self) -> None:
        base = next(
            entry for entry in DEFAULT_CATALOG.magic_entries("Warp")
            if entry["category"] == "Base Sphere"
        )
        talent = next(
            entry for entry in DEFAULT_CATALOG.magic_entries("Warp")
            if entry["category"] == "Talent" and not entry.get("prerequisites")
        )
        custom = {
            "key": "custom-tradition:wayfarer",
            "name": "Wayfarer",
            "kind": "Casting",
            "custom": True,
            "description": "A custom test tradition.",
            "casting_ability_options": ["wisdom"],
            "drawbacks": "Somatic Casting, Verbal Casting",
            "boons": "",
            "spell_point_rule": spell_point_rule_for_unused_drawbacks(2),
            "fixed_grants": [
                {"kind": "magic", "catalog_key": base["key"], "name": base["name"], "sphere": "Warp", "category": "Base Sphere"},
                {"kind": "magic", "catalog_key": talent["key"], "name": talent["name"], "sphere": "Warp", "category": talent["category"]},
            ],
            "choice_groups": [],
        }
        self.repository.update_casting_profile(CastingProfile(
            character_id=self.character_id,
            casting_class_levels=6,
            auto_spell_points=True,
        ))
        catalog_dialog = SimpleNamespace(
            selected_entry=custom,
            exec=lambda: QDialog.DialogCode.Accepted,
        )
        sheet = CharacterSheetWidget(self.repository)
        try:
            sheet.load_character(self.character_id)
            with patch(
                "app.ui.character_sheet.TraditionCatalogDialog",
                return_value=catalog_dialog,
            ):
                sheet._add_tradition("Casting")
            saved = self.repository.list_character_traditions(self.character_id)[0]
            self.assertEqual(custom, resolved_tradition_definition(saved))
            keys = {spell.catalog_key for spell in self.repository.list_spells(self.character_id)}
            self.assertIn(base["key"], keys)
            self.assertIn(talent["key"], keys)
            contribution = next(
                item for item in CharacterCalculationService(
                    self.repository, self.character_id
                ).spell_point_contributions()
                if item.source == "Tradition: Wayfarer"
            )
            self.assertEqual(3, contribution.value)
        finally:
            sheet.close()


if __name__ == "__main__":
    unittest.main()

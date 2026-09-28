from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from app.database import CharacterRepository
from app.models import SKILLS, SkillState
from app.ui.character_sheet import (
    _FormulaStatBreakdownDialog,
    _sphere_stat_formula_keys,
)


ACCEPTED = QDialog.DialogCode.Accepted
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class SheetDialogFormulaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary_directory.name) / "dialog-formulas.db"
        )
        self.character_id = self.repository.create_character(
            "Formula Editor", "Spheres"
        )
        self.repository.add_class_level(
            self.character_id,
            "Fighter",
            4,
            "Full",
            "Good",
            "Poor",
            "Poor",
            preset_key="pathfinder-class:fighter",
            hit_die=10,
            hp_gained=34,
        )
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temporary_directory.cleanup()

    @staticmethod
    def _select_record(table, record_id) -> None:
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if (
                item is not None
                and item.data(Qt.ItemDataRole.UserRole) == record_id
            ):
                table.setCurrentCell(row, 0)
                return
        raise AssertionError(f"Record {record_id!r} was not displayed")

    def test_skill_editor_uses_stable_index_and_round_trips_formula(self) -> None:
        entity_id = next(
            index
            for index, definition in enumerate(SKILLS, start=1)
            if definition.key == "acrobatics"
        )
        self.repository.set_numeric_formula(
            self.character_id, "skill", entity_id, "misc_bonus", "=bab"
        )
        captured = {}

        class FakeSkillDialog:
            def __init__(fake_self, _name, state, _parent, **options):
                captured.update(options)
                fake_self.state = SkillState(
                    state.skill_key,
                    state.ranks,
                    state.class_skill,
                    5,
                    state.notes,
                    state.ability_override,
                )
                fake_self.numeric_formulas = {"misc_bonus": "=bab + 1"}

            def exec(fake_self):
                return ACCEPTED

        self._select_record(self.sheet.skill_table, "acrobatics")
        with patch("app.ui.character_sheet.SkillDialog", FakeSkillDialog):
            self.sheet._edit_skill()

        self.assertEqual({"misc_bonus": "=bab"}, captured["formulas"])
        self.assertEqual(4, captured["formula_evaluator"]("bab"))
        self.assertTrue(captured["formula_suggestions"]())
        self.assertEqual(
            "=bab + 1",
            self.repository.numeric_formulas(
                self.character_id, "skill", entity_id
            )[("skill", entity_id, "misc_bonus")],
        )

    def test_sphere_editor_translates_dialog_fields_and_clears_only_its_keys(self) -> None:
        self.repository.add_spell(
            self.character_id,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            catalog_category="Base Sphere",
        )
        keys = _sphere_stat_formula_keys("Warp")
        self.repository.set_numeric_formula(
            self.character_id, "sphere_stat", 0, keys["caster_level_bonus"], "=bab"
        )
        self.repository.set_numeric_formula(
            self.character_id, "sphere_stat", 0, keys["dc_bonus"], "=1"
        )
        self.sheet._refresh_sphere_statistics()
        captured = {}

        class FakeSphereDialog:
            values = {
                "caster_level_bonus": 5,
                "dc_bonus": 0,
                "notes": "formula test",
            }
            numeric_formulas = {
                "caster_level_bonus": "=bab + 1",
                "dc_bonus": "",
            }

            def __init__(fake_self, _statistic, _parent, **options):
                captured.update(options)

            def exec(fake_self):
                return ACCEPTED

        self._select_record(self.sheet.sphere_stats_table, "Warp")
        with patch("app.ui.character_sheet.SphereStatisticDialog", FakeSphereDialog):
            self.sheet._edit_sphere_statistic()

        self.assertEqual(
            {"caster_level_bonus": "=bab", "dc_bonus": "=1"},
            captured["formulas"],
        )
        stored = self.repository.numeric_formulas(
            self.character_id, "sphere_stat", 0
        )
        self.assertEqual(
            "=bab + 1",
            stored[("sphere_stat", 0, keys["caster_level_bonus"])],
        )
        self.assertNotIn(("sphere_stat", 0, keys["dc_bonus"]), stored)

        self._select_record(self.sheet.sphere_stats_table, "Warp")
        self.sheet._clear_sphere_statistic()
        self.assertFalse(
            self.repository.numeric_formulas(self.character_id, "sphere_stat", 0)
        )

    def test_custom_equipment_formula_is_saved_and_removed_with_item(self) -> None:
        class FakeCatalog:
            custom_requested = True

            def __init__(fake_self, _parent):
                pass

            def exec(fake_self):
                return ACCEPTED

        class FakeEquipmentDialog:
            values = {
                "name": "Formula Pack",
                "category": "Gear",
                "quantity": 1,
                "weight": 4.0,
                "equipped": False,
                "ac_bonus": 0,
                "bonus_type": "untyped",
                "max_dex_bonus": None,
                "notes": "",
                "armor_check_penalty": 0,
                "slot": "",
                "value_gp": 10.0,
                "state": "stored",
                "choices_json": "{}",
                "automation_json": "",
                "enhancement_bonus": 0,
                "masterwork": False,
                "weapon_damage_dice": "",
                "weapon_damage_type": "",
                "weapon_critical": "",
                "weapon_range": "",
            }
            numeric_formulas = {
                "weight": "=bab",
                "value_gp": "",
                "ac_bonus": "",
                "max_dex_bonus": "",
                "armor_check_penalty": "",
                "enhancement_bonus": "",
            }

            def __init__(fake_self, _parent, **options):
                self.assertEqual({}, options["formulas"])
                self.assertEqual(4, options["formula_evaluator"]("bab"))

            def exec(fake_self):
                return ACCEPTED

        with patch("app.ui.character_sheet.ItemCatalogDialog", FakeCatalog), patch(
            "app.ui.character_sheet.EquipmentDialog", FakeEquipmentDialog
        ):
            self.sheet._add_equipment()

        item = self.repository.list_equipment(self.character_id)[0]
        self.assertEqual(
            "=bab",
            self.repository.numeric_formulas(
                self.character_id, "equipment", item.id
            )[("equipment", item.id, "weight")],
        )
        edit_options = {}

        class FakeEquipmentEditDialog:
            values = dict(FakeEquipmentDialog.values, weight=5.0)
            numeric_formulas = dict(
                FakeEquipmentDialog.numeric_formulas, weight="=bab + 1"
            )

            def __init__(fake_self, _parent, _item, **options):
                edit_options.update(options)

            def exec(fake_self):
                return ACCEPTED

        self._select_record(self.sheet.equipment_table, item.id)
        with patch(
            "app.ui.character_sheet.EquipmentDialog", FakeEquipmentEditDialog
        ):
            self.sheet._edit_equipment()
        self.assertEqual("=bab", edit_options["formulas"]["weight"])
        self.assertEqual(
            "=bab + 1",
            self.repository.numeric_formulas(
                self.character_id, "equipment", item.id
            )[("equipment", item.id, "weight")],
        )
        self._select_record(self.sheet.equipment_table, item.id)
        self.sheet._remove_equipment()
        self.assertFalse(
            self.repository.numeric_formulas(
                self.character_id, "equipment", item.id
            )
        )

    def test_custom_feat_and_trait_editors_round_trip_and_cleanup_formulas(self) -> None:
        captured_feat = []

        class FakeFeatDialog:
            values = {
                "name": "Scaling Feat",
                "target": "initiative",
                "bonus_type": "untyped",
                "value": 4,
                "notes": "",
            }
            numeric_formulas = {"value": "=bab"}

            def __init__(fake_self, _parent, feat=None, **options):
                captured_feat.append(options)

            def exec(fake_self):
                return ACCEPTED

        with patch("app.ui.character_sheet.FeatDialog", FakeFeatDialog):
            self.sheet._add_custom_feat()
            feat = self.repository.list_feats(self.character_id)[0]
            self._select_record(self.sheet.feat_table, feat.id)
            self.sheet._edit_feat()
        self.assertEqual({}, captured_feat[0]["formulas"])
        self.assertEqual({"value": "=bab"}, captured_feat[1]["formulas"])
        self.assertIn(
            ("feat", feat.id, "value"),
            self.repository.numeric_formulas(self.character_id, "feat", feat.id),
        )
        self._select_record(self.sheet.feat_table, feat.id)
        self.sheet._remove_feat()
        self.assertFalse(
            self.repository.numeric_formulas(self.character_id, "feat", feat.id)
        )

        captured_trait = []

        class FakeTraitDialog:
            values = {
                "name": "Scaling Trait",
                "target": "initiative",
                "bonus_type": "trait",
                "value": 4,
                "notes": "",
            }
            numeric_formulas = {"value": "=bab"}

            def __init__(fake_self, _parent, trait=None, **options):
                captured_trait.append(options)

            def exec(fake_self):
                return ACCEPTED

        with patch("app.ui.character_sheet.TraitDialog", FakeTraitDialog):
            self.sheet._add_custom_trait()
            trait = self.repository.list_traits(self.character_id)[0]
            self._select_record(self.sheet.trait_table, trait.id)
            self.sheet._edit_trait()
        self.assertEqual({}, captured_trait[0]["formulas"])
        self.assertEqual({"value": "=bab"}, captured_trait[1]["formulas"])
        self._select_record(self.sheet.trait_table, trait.id)
        self.sheet._remove_trait()
        self.assertFalse(
            self.repository.numeric_formulas(self.character_id, "trait", trait.id)
        )

    def test_modifier_breakdown_saves_and_cleans_formula_by_database_id(self) -> None:
        class FakeModifierDialog:
            source = "Formula source"
            bonus_type = "untyped"
            value = 4
            numeric_formulas = {"value": "=bab"}

            def __init__(fake_self, _title, _default, _parent, **options):
                self.assertEqual({}, options["formulas"])
                self.assertEqual(4, options["formula_evaluator"]("bab"))

            def exec(fake_self):
                return ACCEPTED

        dialog = _FormulaStatBreakdownDialog(
            self.repository,
            self.character_id,
            "initiative",
            "Initiative",
            lambda: self.sheet._combat_results()["initiative"],
            self.sheet._evaluate_character_formula,
            self.sheet._character_formula_suggestions,
            self.sheet,
        )
        with patch("app.ui.character_sheet.ModifierDialog", FakeModifierDialog):
            dialog._add_modifier()
        modifier = self.repository.list_modifiers(
            self.character_id, "initiative"
        )[0]
        self.assertEqual(
            "=bab",
            self.repository.numeric_formulas(
                self.character_id, "modifier", modifier.id
            )[("modifier", modifier.id, "value")],
        )
        self._select_record(dialog.table, modifier.id)
        dialog._remove_modifier()
        self.assertFalse(
            self.repository.numeric_formulas(
                self.character_id, "modifier", modifier.id
            )
        )
        dialog.close()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QSpinBox

from app.formulas import DEFAULT_FORMULA_ENGINE
from app.models import SkillState, SphereStatistic
from app.ui.dialogs import (
    EquipmentDialog,
    FeatDialog,
    ModifierDialog,
    SkillDialog,
    SphereStatisticDialog,
    TraitDialog,
)


class DialogFormulaFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    @staticmethod
    def evaluator(expression: str) -> float:
        return DEFAULT_FORMULA_ENGINE.evaluate(
            expression,
            {
                "bab": 6,
                "character.level": 8,
                "abilities.dexterity.modifier": 4,
            },
        )

    def test_skill_misc_bonus_accepts_formula_and_keeps_ranks_literal(self) -> None:
        dialog = SkillDialog(
            "Acrobatics",
            SkillState("acrobatics", ranks=3, misc_bonus=1),
            formulas={"misc_bonus": "=bab / 2"},
            formula_evaluator=self.evaluator,
        )
        self.addCleanup(dialog.close)

        self.assertIsInstance(dialog.ranks, QSpinBox)
        self.assertEqual(3, dialog.state.misc_bonus)
        self.assertEqual({"misc_bonus": "=bab / 2"}, dialog.numeric_formulas)

    def test_sphere_statistics_expose_both_formula_fields(self) -> None:
        dialog = SphereStatisticDialog(
            SphereStatistic(1, "Warp", caster_level_bonus=1, dc_bonus=0),
            formulas={
                "caster_level_bonus": "=character.level / 2",
                "dc_bonus": "=abilities.dexterity.modifier - 2",
            },
            formula_evaluator=self.evaluator,
        )
        self.addCleanup(dialog.close)

        self.assertEqual(4, dialog.values["caster_level_bonus"])
        self.assertEqual(2, dialog.values["dc_bonus"])
        self.assertEqual(
            {
                "caster_level_bonus": "=character.level / 2",
                "dc_bonus": "=abilities.dexterity.modifier - 2",
            },
            dialog.numeric_formulas,
        )

    def test_equipment_rules_fields_accept_formulas_but_quantity_stays_literal(self) -> None:
        formulas = {
            "weight": "=bab / 4",
            "value_gp": "=character.level * 100.5",
            "ac_bonus": "=abilities.dexterity.modifier",
            "max_dex_bonus": "=-1",
            "armor_check_penalty": "=bab / 3",
            "enhancement_bonus": "=character.level // 4",
        }
        dialog = EquipmentDialog(
            formulas=formulas,
            formula_evaluator=self.evaluator,
        )
        self.addCleanup(dialog.close)
        dialog.name.setText("Formula armor")

        self.assertIsInstance(dialog.quantity, QSpinBox)
        self.assertAlmostEqual(1.5, dialog.values["weight"])
        self.assertAlmostEqual(804.0, dialog.values["value_gp"])
        self.assertEqual(4, dialog.values["ac_bonus"])
        self.assertIsNone(dialog.values["max_dex_bonus"])
        self.assertEqual(2, dialog.values["armor_check_penalty"])
        self.assertEqual(2, dialog.values["enhancement_bonus"])
        self.assertEqual(formulas, dialog.numeric_formulas)
        self.assertNotIn("quantity", dialog.numeric_formulas)

    def test_modifier_feat_and_trait_share_formula_value_contract(self) -> None:
        modifier = ModifierDialog(
            "Armor Class",
            formulas={"value": "=bab / 2"},
            formula_evaluator=self.evaluator,
        )
        feat = FeatDialog(
            formulas={"value": "=abilities.dexterity.modifier"},
            formula_evaluator=self.evaluator,
        )
        trait = TraitDialog(
            formulas={"value": "=bab - character.level"},
            formula_evaluator=self.evaluator,
        )
        for dialog in (modifier, feat, trait):
            self.addCleanup(dialog.close)

        modifier.source_input.setText("Formula source")
        self.assertEqual(3, modifier.value)
        self.assertEqual({"value": "=bab / 2"}, modifier.numeric_formulas)

        for dialog, target, expected in (
            (feat, "attack", 4),
            (trait, "reflex", -2),
        ):
            dialog.name.setText("Formula feature")
            dialog.target.setCurrentIndex(dialog.target.findData(target))
            self.assertEqual(expected, dialog.values["value"])
            self.assertTrue(dialog.numeric_formulas["value"].startswith("="))

    def test_old_positional_constructor_calls_remain_valid(self) -> None:
        skill = SkillDialog("Acrobatics", SkillState("acrobatics"), None)
        sphere = SphereStatisticDialog(SphereStatistic(1, "Warp"), None)
        equipment = EquipmentDialog(None, None)
        modifier = ModifierDialog("AC", "armor", None)
        feat = FeatDialog(None, None, "Feat")
        trait = TraitDialog(None, None)
        for dialog in (skill, sphere, equipment, modifier, feat, trait):
            self.addCleanup(dialog.close)

        self.assertEqual(0, skill.state.misc_bonus)
        self.assertEqual(0, sphere.values["dc_bonus"])
        self.assertEqual(1, equipment.values["quantity"])
        self.assertEqual(1, modifier.value)


if __name__ == "__main__":
    unittest.main()

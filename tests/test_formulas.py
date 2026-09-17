from __future__ import annotations

import unittest

from app.formulas import DEFAULT_FORMULA_ENGINE, FormulaEngine, FormulaError, UnknownReferenceError, formula_references


class FormulaEngineTests(unittest.TestCase):
    def test_named_values_functions_and_excel_prefix_are_supported(self) -> None:
        values = {
            "classes.monk.level": 8,
            "abilities.wisdom.modifier": 3,
        }
        self.assertEqual(
            5,
            DEFAULT_FORMULA_ENGINE.evaluate(
                "= floor(classes.monk.level / 3) + abilities.wisdom.modifier", values
            ),
        )
        self.assertEqual(4, DEFAULT_FORMULA_ENGINE.evaluate("clamp(9, 1, 4)"))

    def test_references_are_reported_without_function_names(self) -> None:
        self.assertEqual(
            ("classes.monk.level", "trackers.reserve.maximum"),
            formula_references("floor(classes.monk.level / 3) + trackers.reserve.maximum"),
        )

    def test_excel_if_is_lazy_and_validates_its_three_arguments(self) -> None:
        self.assertEqual(7, DEFAULT_FORMULA_ENGINE.evaluate("IF(1, 7, 1 / 0)"))
        self.assertEqual(4, DEFAULT_FORMULA_ENGINE.evaluate("IF(0, unknown.value, 4)"))
        self.assertEqual(
            -2,
            DEFAULT_FORMULA_ENGINE.evaluate(
                "IF(feats.power_attack, -2, 0)",
                {"feats.power_attack": True},
            ),
        )
        with self.assertRaisesRegex(FormulaError, "requires a condition"):
            DEFAULT_FORMULA_ENGINE.evaluate("IF(1, 2)")

    def test_ampersand_is_the_same_lazy_boolean_operator_as_and(self) -> None:
        values = {"martial_focus": True, "sphere.brute": True}
        self.assertEqual(
            DEFAULT_FORMULA_ENGINE.evaluate(
                "IF(martial_focus and sphere.brute, 3, 0)", values
            ),
            DEFAULT_FORMULA_ENGINE.evaluate(
                "IF(martial_focus & sphere.brute, 3, 0)", values
            ),
        )

    def test_dice_notation_and_function_are_safe_composable_rolls(self) -> None:
        engine = FormulaEngine(randint=lambda _minimum, maximum: maximum)
        self.assertEqual(6, engine.evaluate("1d6"))
        self.assertEqual(24, engine.evaluate("3d8 * floor(5 / 3)"))
        self.assertEqual(8, engine.evaluate("dice(2, 4)"))
        self.assertEqual((), formula_references("3d8 + floor(5 / 3)"))
        for invalid in ("0d6", "1d1", "1001d6", "dice(2.5, 6)"):
            with self.subTest(invalid=invalid), self.assertRaises(FormulaError):
                engine.evaluate(invalid)

    def test_symbolic_damage_formulas_preserve_dice_until_roll_time(self) -> None:
        result = DEFAULT_FORMULA_ENGINE.evaluate_symbolic_dice("=1d6 + 1d4 + 6")
        self.assertEqual("1d6+1d4+6", result.format())
        scaled = DEFAULT_FORMULA_ENGINE.evaluate_symbolic_dice(
            "=3d8 * floor(5 / 3)"
        )
        self.assertEqual("3d8", scaled.format())
        localized = DEFAULT_FORMULA_ENGINE.evaluate_symbolic_dice(
            "=IF(1; 2d6; 1d4)"
        )
        self.assertEqual("2d6", localized.format())

    def test_unknown_unsafe_and_invalid_expressions_fail_cleanly(self) -> None:
        with self.assertRaises(UnknownReferenceError):
            DEFAULT_FORMULA_ENGINE.evaluate("unknown.value + 1")
        for expression in (
            "__import__('os').system('dir')",
            "character.__class__",
            "[1, 2, 3][0]",
            "1 / 0",
            "2 ** 100",
        ):
            with self.subTest(expression=expression), self.assertRaises(FormulaError):
                DEFAULT_FORMULA_ENGINE.evaluate(expression)


if __name__ == "__main__":
    unittest.main()

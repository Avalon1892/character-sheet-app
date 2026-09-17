from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.class_feature_systems import resolve_class_feature_modules
from app.database import CharacterRepository
from app.models import Attack, ClassFeatureState
from app.recovery import FullRestEngine
from app.services.character_calculations import CharacterCalculationService


class MonkBarbarianResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")

    def tearDown(self) -> None:
        self.repository.close(); self.directory.cleanup()

    def character_with_class(self, name: str, key: str, level: int) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, "Full", "Good", "Good", "Good", key, 10, 50
        )
        return character, class_id

    def test_monk_ki_pool_scales_with_wisdom_and_full_rest(self) -> None:
        character, class_id = self.character_with_class("Monk", "pathfinder-class:monk", 8)
        self.repository.update_ability_score(character, "wisdom", 18)
        module = resolve_class_feature_modules(self.repository, character, {"wisdom": 4})[0]
        ki = module.resources[0]
        self.assertEqual(8, ki.maximum)
        self.repository.save_class_feature_state(ClassFeatureState(character, class_id, "ki_pool", 1))
        FullRestEngine(self.repository, character).perform()
        saved = next(item for item in self.repository.list_class_feature_states(character) if item.feature_key == "ki_pool")
        self.assertEqual(8, saved.current_value)

    def test_classic_rage_automates_abilities_saves_ac_and_formula_state(self) -> None:
        character, class_id = self.character_with_class("Barbarian", "pathfinder-class:barbarian", 12)
        self.repository.update_ability_score(character, "strength", 14)
        self.repository.update_ability_score(character, "constitution", 14)
        self.repository.save_class_feature_state(ClassFeatureState(character, class_id, "rage", 20, active=True))
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(20, calculator.ability_result("strength").total)
        self.assertEqual(20, calculator.ability_result("constitution").total)
        calculator.combat_results()
        self.assertEqual(3, calculator.automatic_total("will"))
        self.assertEqual(-2, calculator.automatic_total("armor_class"))
        context = calculator.formula_context()
        self.assertTrue(context.evaluate("class_feature.barbarian.rage.active"))

    def test_unchained_rage_only_adds_attack_to_melee_and_damage_to_thrown(self) -> None:
        character, class_id = self.character_with_class(
            "Barbarian (Unchained)", "pathfinder-class:barbarian-unchained", 12
        )
        self.repository.save_class_feature_state(ClassFeatureState(character, class_id, "rage", 20, active=True))
        calculator = CharacterCalculationService(self.repository, character)
        melee = Attack(0, "Sword", "Melee", "strength", 0, "1d8", "strength", 1, 0, "20/x2")
        ranged = Attack(0, "Bow", "Ranged", "dexterity", 0, "1d8", "strength", 1, 0, "20/x3")
        thrown = Attack(0, "Axe", "Thrown", "strength", 0, "1d6", "strength", 1, 0, "20/x2")
        self.assertEqual(([3], [3]), tuple([[item.value for item in values] for values in calculator.attack_effects(melee, 12)]))
        self.assertEqual(([], []), calculator.attack_effects(ranged, 12))
        self.assertEqual(([], [3]), tuple([[item.value for item in values] for values in calculator.attack_effects(thrown, 12)]))


if __name__ == "__main__":
    unittest.main()

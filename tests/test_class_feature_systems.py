from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_feature_systems import resolve_class_feature_modules
from app.content import archetype_entry
from app.database import CharacterRepository
from app.models import Attack, ClassFeatureState
from app.recovery import FullRestEngine
from app.rules import calculate_attack, total_bab
from app.services.character_calculations import CharacterCalculationService


class ClassFeatureSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Judge", "Pathfinder 1e")
        self.class_id = self.repository.add_class_level(
            self.character_id,
            "Inquisitor",
            12,
            "3/4",
            "Good",
            "Poor",
            "Good",
            "pathfinder-class:inquisitor",
            8,
            70,
        )
        self.repository.update_ability_score(self.character_id, "wisdom", 18)

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_inquisitor_resources_scale_and_expose_formula_references(self) -> None:
        modules = resolve_class_feature_modules(
            self.repository, self.character_id, {"wisdom": 4}
        )
        self.assertEqual(1, len(modules))
        resources = {item.key: item for item in modules[0].resources}
        self.assertEqual(4, resources["judgment"].maximum)
        self.assertEqual(12, resources["bane"].maximum)
        self.assertEqual(12, resources["discern_lies"].maximum)
        self.assertEqual(4, resources["teamwork_swaps"].maximum)
        self.assertEqual(2, resources["judgment"].maximum_choices)

        context = CharacterCalculationService(
            self.repository, self.character_id
        ).formula_context()
        self.assertEqual(4, context.evaluate("class_feature.inquisitor.judgment.maximum"))
        self.assertEqual(12, context.evaluate("class_feature.inquisitor.bane.current"))

    def test_true_judgment_is_a_once_daily_level_twenty_resource(self) -> None:
        character = self.repository.create_character("Final Judge", "Pathfinder 1e")
        self.repository.add_class_level(
            character,
            "Inquisitor",
            20,
            "3/4",
            "Good",
            "Poor",
            "Good",
            "pathfinder-class:inquisitor",
            8,
            120,
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(1, resources["true_judgment"].maximum)
        self.assertEqual(1, resources["true_judgment"].current)

    def test_active_judgment_and_bane_automate_combat_and_damage(self) -> None:
        self.repository.save_class_feature_state(
            ClassFeatureState(
                self.character_id,
                self.class_id,
                "judgment",
                3,
                active=True,
                choices_json=json.dumps(["Destruction", "Justice"]),
            )
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                self.character_id,
                self.class_id,
                "bane",
                11,
                active=True,
                choices_json=json.dumps(["Undead"]),
            )
        )
        calculator = CharacterCalculationService(self.repository, self.character_id)
        combat = calculator.combat_results()
        # Cunning Initiative adds the retained Inquisitor governing ability.
        self.assertEqual(8, combat["initiative"].total)
        self.assertEqual(6, calculator.skill_result("intimidate").total)

        attack = Attack(0, "Test", "Melee", "strength", 0, "1d8", "strength", 1.0, 0, "20/x2")
        profile = calculator.resolve_attack_profile(attack)
        attack_modifiers, damage_modifiers = calculator.attack_effects(attack, total_bab(self.repository.list_class_levels(self.character_id)))
        result = calculate_attack(
            profile.attack,
            9,
            calculator.ability_results(),
            "Medium",
            calculator.automatic_modifier_map().get("attack", []) + attack_modifiers,
            calculator.automatic_modifier_map().get("damage", []) + damage_modifiers,
            profile.extra_damage,
        )
        self.assertEqual(14, result.attack_bonus)
        self.assertEqual(7, result.damage_bonus)
        self.assertIn("4d6", result.damage_display)

    def test_archetype_replacement_removes_only_replaced_systems(self) -> None:
        huntsmaster = archetype_entry(
            "pathfinder-archetype:pathfinder-class:inquisitor:sacred-huntsmaster"
        )
        self.assertIsNotNone(huntsmaster)
        self.repository.set_class_archetype_keys(
            self.character_id, self.class_id, (str(huntsmaster["key"]),)
        )
        module = resolve_class_feature_modules(
            self.repository, self.character_id, {"wisdom": 4}
        )[0]
        resource_keys = {item.key for item in module.resources}
        self.assertNotIn("judgment", resource_keys)
        self.assertIn("bane", resource_keys)
        self.assertFalse(module.solo_tactics)

    def test_full_rest_restores_resources_and_ends_effects(self) -> None:
        state = ClassFeatureState(
            self.character_id,
            self.class_id,
            "judgment",
            0,
            active=True,
            choices_json=json.dumps(["Justice"]),
        )
        self.repository.save_class_feature_state(state)
        results = FullRestEngine(self.repository, self.character_id).perform()
        saved = next(
            item
            for item in self.repository.list_class_feature_states(self.character_id)
            if item.feature_key == "judgment"
        )
        self.assertEqual(4, saved.current_value)
        self.assertFalse(saved.active)
        self.assertTrue(any(item.key == "class_feature_resources" for item in results))


if __name__ == "__main__":
    unittest.main()

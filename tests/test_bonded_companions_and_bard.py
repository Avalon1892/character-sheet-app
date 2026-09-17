from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.bonded_companion_rules import (
    bonded_companion_levels,
    bonded_companion_progression,
)
from app.character_creation import CharacterCreationDraft, apply_character_creation_draft
from app.class_feature_systems import resolve_class_feature_modules
from app.database import CharacterRepository
from app.models import BondedCompanion, ClassFeatureState
from app.models import Attack
from app.rules import calculate_attack
from app.services.character_calculations import CharacterCalculationService


class BondedCompanionAndBardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.temp.name) / "characters.db")

    def tearDown(self) -> None:
        self.repository.close(); self.temp.cleanup()

    def test_witch_and_necros_get_independent_progression_pages(self) -> None:
        witch = self.repository.create_character("Witch", "Pathfinder 1e")
        self.repository.add_class_level(
            witch, "Witch", 5, "1/2", "Poor", "Poor", "Good",
            "pathfinder-class:witch", 6, 20,
        )
        self.assertEqual(5, bonded_companion_levels(self.repository, witch)["familiar"])
        familiar = bonded_companion_progression("familiar", 5)
        self.assertEqual(3, familiar.natural_armor)
        self.assertIn("Speak with Master", familiar.specials)

        necros = self.repository.create_character("Necros", "Spheres")
        self.repository.add_class_level(
            necros, "Necros", 6, "3/4", "Poor", "Poor", "Good",
            "spheres-class:necros", 8, 30,
        )
        self.assertEqual(6, bonded_companion_levels(self.repository, necros)["corpse_puppet"])
        puppet = bonded_companion_progression("corpse_puppet", 6)
        self.assertEqual("6d8", puppet.hit_dice)
        self.assertEqual("4", puppet.bab)
        self.assertIn("Undead Evolution", puppet.specials)

    def test_bonded_companion_record_round_trips(self) -> None:
        character = self.repository.create_character("Master", "Pathfinder 1e")
        record = BondedCompanion(
            character, "familiar", "Ink", "Raven", 12, 2,
            json.dumps({"abilities": {"intelligence": 8}}), "Scout",
        )
        self.repository.update_bonded_companion(record)
        self.assertEqual(record, self.repository.get_bonded_companion(character, "familiar"))

    def test_bardic_performance_pool_choices_and_inspire_courage_are_live(self) -> None:
        character = self.repository.create_character("Singer", "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, "Bard", 5, "3/4", "Poor", "Good", "Good",
            "pathfinder-class:bard", 8, 30,
        )
        self.repository.update_ability_score(character, "charisma", 16)
        module = resolve_class_feature_modules(
            self.repository, character, {"charisma": 3}
        )[0]
        performance = module.resources[0]
        self.assertEqual(15, performance.maximum)
        self.assertIn("Inspire Courage", performance.choice_options)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "bardic_performance", 10,
                active=True, choices_json=json.dumps(["Inspire Courage"]),
            )
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(2, calculator.automatic_total("attack"))
        self.assertEqual(2, calculator.automatic_total("damage"))

    def test_guided_creation_draft_is_optional_and_applies_through_service(self) -> None:
        character = self.repository.create_character("Guide", "Pathfinder 1e")
        draft = CharacterCreationDraft(
            "Guide", "Pathfinder 1e", race="Human", alignment="NG",
            abilities={"strength": 14, "dexterity": 12, "constitution": 10,
                       "intelligence": 13, "wisdom": 8, "charisma": 16},
            class_values={
                "class_name": "Bard", "level": 1, "bab_progression": "3/4",
                "fort_progression": "Poor", "reflex_progression": "Good",
                "will_progression": "Good", "preset_key": "pathfinder-class:bard",
                "hit_die": 8, "hp_gained": 8,
            },
        )
        apply_character_creation_draft(self.repository, character, draft)
        self.assertEqual("Human", self.repository.get_character_details(character).race)
        self.assertEqual(14, self.repository.get_ability_scores(character)["strength"])
        self.assertEqual("Bard", self.repository.list_class_levels(character)[0].class_name)

    def test_attack_damage_formula_keeps_each_die_in_the_live_profile(self) -> None:
        character = self.repository.create_character("Dice", "Pathfinder 1e")
        self.repository.update_ability_score(character, "strength", 22)
        attack_id = self.repository.add_attack(
            character, name="Strike", attack_type="Melee", ability="strength",
            attack_bonus=0, damage_dice="1d6", damage_ability="strength",
            damage_multiplier=1.0, damage_bonus=0, critical="20/x2", notes="",
            equipment_id=None, profile_key="", damage_ability_mode="manual",
            visibility_condition="",
        )
        self.repository.set_numeric_formula(
            character, "attack", attack_id, "damage_bonus", "=1d6+1d4"
        )
        calculator = CharacterCalculationService(self.repository, character)
        profile = calculator.resolve_attack_profile(
            self.repository.list_attacks(character)[0]
        )
        result = calculate_attack(
            profile.attack, 0, calculator.ability_results(), "Medium",
            extra_damage=profile.extra_damage,
        )
        self.assertEqual("1d6+6+1d6+1d4", result.damage_display)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_power_rules import class_power_selection_record, resolve_class_power_sets
from app.class_feature_systems import resolve_class_feature_modules
from app.database import CharacterRepository
from app.models import Attack, ClassFeatureState
from app.services.character_calculations import CharacterCalculationService
from app.services.sheet_presentation import build_character_sheet_snapshot


class ClassCombatWave3BTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _character(self, class_key: str, level: int, **scores: int) -> tuple[int, int]:
        character = self.repository.create_character(class_key, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character,
            class_key.rsplit(":", 1)[-1].replace("-", " ").title(),
            level,
            "3/4",
            "Good",
            "Good",
            "Good",
            class_key,
            8,
            40,
        )
        for ability, score in scores.items():
            self.repository.update_ability_score(character, ability, score)
        return character, class_id

    @staticmethod
    def _attack(name: str, attack_type: str) -> Attack:
        return Attack(
            0, name, attack_type, "strength", 0, "1d8", "strength", 1.0, 0, "20/x2"
        )

    def test_studied_combat_and_strike_are_melee_target_bound_profiles(self) -> None:
        character, class_id = self._character(
            "pathfinder-class:investigator", 10, intelligence=18, strength=14
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character,
                class_id,
                "studied_combat",
                4,
                active=True,
                choices_json=json.dumps(["Clockwork Assassin"]),
            )
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "studied_strike", 1, active=True)
        )
        calculator = CharacterCalculationService(self.repository, character)
        melee = self._attack("Rapier", "Melee")
        ranged = self._attack("Bow", "Ranged")
        melee_attack, melee_damage = calculator.attack_effects(melee, 7)
        ranged_attack, ranged_damage = calculator.attack_effects(ranged, 7)
        self.assertEqual(5, sum(item.value for item in melee_attack))
        self.assertEqual(5, sum(item.value for item in melee_damage))
        self.assertEqual([], ranged_attack)
        self.assertEqual([], ranged_damage)
        profile = calculator.resolve_attack_profile(melee)
        self.assertEqual("4d6", profile.extra_damage[-1].dice)
        self.assertEqual("precision", profile.extra_damage[-1].damage_type)
        self.assertIn("Clockwork Assassin", profile.extra_damage[-1].source)
        self.assertFalse(calculator.resolve_attack_profile(ranged).extra_damage)

    def test_replacing_investigator_features_removes_state_and_automation(self) -> None:
        character, class_id = self._character(
            "pathfinder-class:investigator", 8, intelligence=16
        )
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:investigator:cryptid-scholar",),
        )
        calculator = CharacterCalculationService(self.repository, character)
        module = next(
            item
            for item in resolve_class_feature_modules(
                self.repository,
                character,
                {
                    key: value.ability_modifier
                    for key, value in calculator.ability_results().items()
                },
            )
            if item.key == "investigator"
        )
        self.assertNotIn("studied_combat", {item.key for item in module.resources})
        self.assertNotIn("studied_strike", {item.key for item in module.resources})

    def test_alchemist_bomb_is_generated_with_live_scaling(self) -> None:
        character, _class_id = self._character(
            "pathfinder-class:alchemist", 5, intelligence=18, dexterity=14
        )
        calculator = CharacterCalculationService(self.repository, character)
        bomb = next(item for item in calculator.attacks() if item.name == "Bomb")
        self.assertLess(bomb.id, 0)
        self.assertEqual("3d6", bomb.damage_dice)
        self.assertEqual(4, bomb.damage_bonus)
        self.assertEqual("Ranged", bomb.attack_type)
        self.assertIn("Reflex DC 16", bomb.notes)
        self.assertIn("Bombs remaining: 9/9", bomb.notes)
        self.assertEqual("Bomb", build_character_sheet_snapshot(self.repository, character).attacks[0].record.name)

    def test_selected_bomb_discovery_adds_only_its_derived_variant(self) -> None:
        character, _class_id = self._character(
            "pathfinder-class:alchemist", 8, intelligence=16
        )
        power_set = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "alchemist-discoveries"
        )
        force_bomb = next(item for item in power_set.options if item.name == "Force Bomb")
        early = [
            item for item in power_set.options
            if item.minimum_level <= 2
            and not item.prerequisite_names
            and not item.repeatable
            and item.key != force_bomb.key
        ][:3]
        self.repository.save_class_feature_selection(
            class_power_selection_record(
                character, power_set, (*[item.key for item in early], force_bomb.key)
            )
        )
        attacks = CharacterCalculationService(self.repository, character).attacks()
        variant = next(item for item in attacks if item.name == "Force Bomb")
        self.assertEqual("4d4", variant.damage_dice)
        self.assertIn("force", variant.notes.casefold())

    def test_bomb_replacing_archetype_removes_generated_attack(self) -> None:
        character, class_id = self._character(
            "pathfinder-class:alchemist", 5, intelligence=18
        )
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:alchemist:vivisectionist",),
        )
        self.assertFalse(CharacterCalculationService(self.repository, character).attacks())


if __name__ == "__main__":
    unittest.main()

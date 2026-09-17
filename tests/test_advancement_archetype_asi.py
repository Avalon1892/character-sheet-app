from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.advancement_rules import calculate_advancement_budgets
from app.class_feature_rules import (
    archetype_optional_features,
    resolve_class_features,
)
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import (
    AbilityScoreIncreaseAllocation,
    ClassFeatureSelection,
    ClassLevel,
)
from app.services.character_calculations import CharacterCalculationService
from app.transfer import export_character, import_character


CHAMPION_OPTION_ARCHETYPES = (
    "spheres-archetype:pathfinder-class:alchemist:champion-alchemist",
    "spheres-archetype:pathfinder-class:bard:champion-bard",
    "spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor",
    "spheres-archetype:pathfinder-class:mesmerist:champion-mesmerist",
    "spheres-archetype:pathfinder-class:ranger:adventurer",
    "spheres-archetype:pathfinder-class:warpriest:champion-warpriest",
)


class AdvancementArchetypeAndAsiTests(unittest.TestCase):
    def _budget_inputs(self, class_level: ClassLevel) -> dict:
        return {
            "classes": (class_level,),
            "class_lookup": class_entry,
            "intelligence_modifier": 0,
            "race": "",
            "skill_ranks": 0,
            "favored_skill_points": 0,
            "feats": (),
            "martial_talents": (),
            "spells": (),
            "traditions": (),
            "adjustments": {},
        }

    def test_level_ability_increases_are_separate_saved_calculation_sources(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = CharacterRepository(Path(folder) / "characters.db")
            character = repository.create_character("Level Eight", "Pathfinder 1e")
            repository.add_class_level(
                character, "Fighter", 8, "Full", "Good", "Poor", "Poor",
                preset_key="pathfinder-class:fighter", hit_die=10, hp_gained=64,
            )
            repository.update_ability_score(character, "strength", 10)
            repository.update_ability_score_increase(
                AbilityScoreIncreaseAllocation(character, "strength", 2)
            )

            result = CharacterCalculationService(repository, character).ability_result("strength")
            self.assertEqual(12, result.total)
            self.assertEqual(10, repository.get_ability_scores(character)["strength"])
            self.assertIn(
                "Level ability-score increases",
                {item.source for item in result.contributions if item.applied},
            )

            class_level = repository.list_class_levels(character)[0]
            budgets = calculate_advancement_budgets(
                **self._budget_inputs(class_level),
                ability_score_increases=repository.list_ability_score_increases(character),
            )
            asi = next(item for item in budgets if item.key == "ability_score_increases")
            self.assertEqual((2, 2, 0), (asi.automatic, asi.used, asi.remaining))

            export_path = Path(folder) / "asi.character.json"
            export_character(repository, character, export_path)
            imported = import_character(repository, export_path)
            self.assertEqual(
                2,
                repository.list_ability_score_increases(imported)["strength"].points,
            )
            self.assertEqual(
                12,
                CharacterCalculationService(repository, imported).ability_result("strength").total,
            )
            repository.close()

    def test_champion_inquisitor_budget_uses_archetype_and_greater_training_choice(self) -> None:
        archetype_key = CHAMPION_OPTION_ARCHETYPES[2]
        archetype = archetype_entry(archetype_key)
        self.assertIsNotNone(archetype)
        option = archetype_optional_features(archetype)[0]
        class_level = ClassLevel(
            41, "Inquisitor", 5, "3/4", "Good", "Poor", "Good",
            "pathfinder-class:inquisitor", 8, 40,
        )
        inputs = {
            **self._budget_inputs(class_level),
            "archetype_keys_by_class_level": {41: (archetype_key,)},
            "archetype_lookup": archetype_entry,
        }

        normal = calculate_advancement_budgets(**inputs)
        self.assertNotIn("spells", {item.key for item in normal})
        self.assertEqual(5, next(item for item in normal if item.key == "talents").automatic)

        greater = calculate_advancement_budgets(
            **inputs,
            feature_selections=(
                ClassFeatureSelection(
                    1, 41, option.key, "Optional Exchange", "enabled",
                    option.name, option.description,
                ),
            ),
        )
        self.assertEqual(7, next(item for item in greater if item.key == "talents").automatic)

        resolved = resolve_class_features(
            class_entry("pathfinder-class:inquisitor")["features"],
            (archetype,),
            5,
            "Inquisitor",
            (option.key,),
        )
        names = {item.name for item in resolved}
        self.assertIn("Greater Training", names)
        self.assertNotIn("Monster Lore", names)
        self.assertNotIn("Stern Gaze", names)

    def test_all_known_greater_training_exchanges_use_the_generic_contract(self) -> None:
        for key in CHAMPION_OPTION_ARCHETYPES:
            with self.subTest(key=key):
                archetype = archetype_entry(key)
                self.assertIsNotNone(archetype)
                options = archetype_optional_features(archetype)
                greater = [item for item in options if item.name == "Greater Training"]
                self.assertEqual(1, len(greater))
                self.assertTrue(greater[0].replaces)
                self.assertIn("every class level", greater[0].description.casefold())

    def test_adventurer_only_replaces_ranger_spells_when_greater_training_is_selected(self) -> None:
        archetype_key = CHAMPION_OPTION_ARCHETYPES[4]
        archetype = archetype_entry(archetype_key)
        option = archetype_optional_features(archetype)[0]
        class_level = ClassLevel(
            9, "Ranger", 5, "Full", "Good", "Good", "Poor",
            "pathfinder-class:ranger", 10, 45,
        )
        inputs = {
            **self._budget_inputs(class_level),
            "archetype_keys_by_class_level": {9: (archetype_key,)},
            "archetype_lookup": archetype_entry,
        }
        standard = calculate_advancement_budgets(**inputs)
        self.assertIn("spells", {item.key for item in standard})
        self.assertEqual(3, next(item for item in standard if item.key == "talents").automatic)

        greater = calculate_advancement_budgets(
            **inputs,
            feature_selections=(
                ClassFeatureSelection(
                    1, 9, option.key, "Optional Exchange", "enabled",
                    option.name, option.description,
                ),
            ),
        )
        self.assertNotIn("spells", {item.key for item in greater})
        self.assertEqual(7, next(item for item in greater if item.key == "talents").automatic)

    def test_import_without_asi_data_remains_backward_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = CharacterRepository(Path(folder) / "characters.db")
            character = repository.create_character("Legacy", "Pathfinder 1e")
            self.assertEqual({}, repository.list_ability_score_increases(character))
            repository.close()


if __name__ == "__main__":
    unittest.main()

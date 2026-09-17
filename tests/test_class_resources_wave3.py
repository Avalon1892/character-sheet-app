from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_feature_systems import resolve_class_feature_modules
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.recovery import FullRestEngine
from app.services.character_calculations import CharacterCalculationService


class ClassResourcesWave3Tests(unittest.TestCase):
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
            "Poor",
            "Good",
            class_key,
            8,
            40,
        )
        for ability, score in scores.items():
            self.repository.update_ability_score(character, ability, score)
        return character, class_id

    def _module(self, character: int, key: str):
        calculations = CharacterCalculationService(self.repository, character)
        modifiers = {
            ability: result.ability_modifier
            for ability, result in calculations.ability_results().items()
        }
        return next(
            module
            for module in resolve_class_feature_modules(
                self.repository, character, modifiers
            )
            if module.key == key
        )

    def test_daily_pool_progressions_and_arcanist_capacity_are_distinct(self) -> None:
        cases = (
            ("pathfinder-class:alchemist", 10, {"intelligence": 18}, "alchemist", "bombs", 14),
            ("pathfinder-class:investigator", 10, {"intelligence": 18}, "investigator", "inspiration", 9),
            ("pathfinder-class:magus", 10, {"intelligence": 18}, "magus", "arcane_pool", 9),
            ("pathfinder-class:ninja", 10, {"charisma": 16}, "ninja", "ki_pool", 8),
            ("pathfinder-class:gunslinger", 5, {"wisdom": 14}, "gunslinger", "grit", 2),
            ("pathfinder-class:swashbuckler", 5, {"charisma": 16}, "swashbuckler", "panache", 3),
        )
        for class_key, level, scores, module_key, resource_key, expected in cases:
            with self.subTest(class_key=class_key):
                character, _class_id = self._character(class_key, level, **scores)
                resource = next(
                    item for item in self._module(character, module_key).resources
                    if item.key == resource_key
                )
                self.assertEqual(expected, resource.maximum)
                self.assertEqual(expected, resource.recovery_value)

        arcanist, class_id = self._character("pathfinder-class:arcanist", 10, intelligence=18)
        reservoir = self._module(arcanist, "arcanist").resources[0]
        self.assertEqual(13, reservoir.maximum)
        self.assertEqual(8, reservoir.current)
        self.assertEqual(8, reservoir.recovery_value)
        self.repository.save_class_feature_state(
            ClassFeatureState(arcanist, class_id, "arcane_reservoir", 1)
        )
        FullRestEngine(self.repository, arcanist).perform({"class_feature_resources": True})
        restored = self._module(arcanist, "arcanist").resources[0]
        self.assertEqual(8, restored.current)
        self.assertEqual(13, restored.maximum)

    def test_mutagen_and_bloodrage_feed_live_ability_and_defense_modifiers(self) -> None:
        alchemist, alchemist_class = self._character(
            "pathfinder-class:alchemist", 6, strength=10, intelligence=18
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                alchemist,
                alchemist_class,
                "mutagen",
                0,
                active=True,
                choices_json=json.dumps(["Strength"]),
            )
        )
        calculations = CharacterCalculationService(self.repository, alchemist)
        self.assertEqual(14, calculations.ability_result("strength").total)
        self.assertEqual(16, calculations.ability_result("intelligence").total)
        modifiers = calculations.automatic_modifier_map()
        self.assertTrue(
            any(item.value == 2 and item.bonus_type == "natural armor"
                for item in modifiers["armor_class"])
        )
        FullRestEngine(self.repository, alchemist).perform(
            {"class_feature_resources": True}
        )
        mutagen = self._module(alchemist, "alchemist").resources[1]
        self.assertEqual(0, mutagen.current)
        self.assertFalse(mutagen.active)

        bloodrager, bloodrager_class = self._character(
            "pathfinder-class:bloodrager", 11, constitution=18
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(bloodrager, bloodrager_class, "bloodrage", 20, active=True)
        )
        active = CharacterCalculationService(self.repository, bloodrager)
        self.assertEqual(24, active.ability_result("constitution").total)
        resource = self._module(bloodrager, "bloodrager").resources[0]
        self.assertEqual(28, resource.maximum)
        context = active.formula_context()
        self.assertEqual(1, context.evaluate("class_feature.bloodrager.bloodrage.active"))

    def test_grit_and_panache_combine_into_one_shared_pool(self) -> None:
        character, _gunslinger = self._character(
            "pathfinder-class:gunslinger", 3, wisdom=14, charisma=16
        )
        self.repository.add_class_level(
            character, "Swashbuckler", 2, "Full", "Good", "Good", "Poor",
            "pathfinder-class:swashbuckler", 10, 20,
        )
        module = self._module(character, "heroic_pool")
        self.assertEqual(("grit_panache",), tuple(item.key for item in module.resources))
        self.assertEqual(5, module.resources[0].maximum)
        context = CharacterCalculationService(self.repository, character).formula_context()
        self.assertEqual(5, context.evaluate("class_feature.heroic_pool.grit_panache.maximum"))
        self.assertEqual(5, context.evaluate("class_feature.gunslinger.grit.maximum"))
        self.assertEqual(5, context.evaluate("class_feature.swashbuckler.panache.maximum"))

    def test_resource_altering_and_replacing_archetypes_are_respected(self) -> None:
        gunslinger, gunslinger_class = self._character(
            "pathfinder-class:gunslinger", 3, wisdom=12, charisma=16
        )
        self.repository.set_class_archetype_keys(
            gunslinger,
            gunslinger_class,
            ("pathfinder-archetype:pathfinder-class:gunslinger:mysterious-stranger",),
        )
        self.assertEqual(
            3, self._module(gunslinger, "gunslinger").resources[0].maximum
        )

        swashbuckler, swashbuckler_class = self._character(
            "pathfinder-class:swashbuckler", 3, charisma=14, intelligence=16
        )
        self.repository.set_class_archetype_keys(
            swashbuckler,
            swashbuckler_class,
            ("pathfinder-archetype:pathfinder-class:swashbuckler:inspired-blade",),
        )
        self.assertEqual(
            5, self._module(swashbuckler, "swashbuckler").resources[0].maximum
        )

        alchemist, alchemist_class = self._character(
            "pathfinder-class:alchemist", 5, intelligence=16
        )
        self.repository.set_class_archetype_keys(
            alchemist,
            alchemist_class,
            ("pathfinder-archetype:pathfinder-class:alchemist:vivisectionist",),
        )
        resource_keys = {
            resource.key for resource in self._module(alchemist, "alchemist").resources
        }
        self.assertNotIn("bombs", resource_keys)
        self.assertIn("mutagen", resource_keys)


if __name__ == "__main__":
    unittest.main()

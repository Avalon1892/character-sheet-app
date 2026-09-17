from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.animal_companion_rules import resolve_companion_grant
from app.class_feature_context import resolved_class_features_for_level
from app.class_feature_systems import resolve_class_feature_modules
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.character_calculations import CharacterCalculationService


class AlchemistBarbarianCavalierPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "classes.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def add_class(self, name: str, key: str, level: int) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, "3/4", "Good", "Poor", "Poor",
            key, 8, level * 6,
        )
        return character, class_id

    def test_base_packages_and_generated_archetypes_are_available(self) -> None:
        for key in ("alchemist", "barbarian", "cavalier"):
            self.assertIsNotNone(class_package(key))
        for key in (
            "pathfinder-archetype:pathfinder-class:alchemist:construct-rider",
            "pathfinder-archetype:pathfinder-class:barbarian:savage-technologist",
            "spheres-archetype:pathfinder-class:cavalier:blooded-knight",
        ):
            entry = archetype_entry(key)
            self.assertIsNotNone(entry)
            self.assertTrue(entry["features"])
            self.assertEqual(entry["key"], key)

    def test_alchemist_resources_scale_and_mutagen_remains_live(self) -> None:
        character, class_id = self.add_class(
            "Alchemist", "pathfinder-class:alchemist", 12
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"intelligence": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(16, resources["bombs"].maximum)
        self.assertIn("mutagen", resources)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "mutagen", 0,
                active=True, choices_json='["Dexterity"]',
            )
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.automatic_total("dexterity"))
        self.assertEqual(-2, calculator.automatic_total("wisdom"))

    def test_savage_technologist_rage_uses_dexterity_not_constitution(self) -> None:
        character, class_id = self.add_class(
            "Barbarian", "pathfinder-class:barbarian", 8
        )
        key = (
            "pathfinder-archetype:pathfinder-class:barbarian:"
            "savage-technologist"
        )
        self.repository.set_class_archetype_keys(character, class_id, (key,))
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "rage", 10, active=True)
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.automatic_total("strength"))
        self.assertEqual(4, calculator.automatic_total("dexterity"))
        self.assertEqual(0, calculator.automatic_total("constitution"))
        self.assertEqual(2, calculator.automatic_total("will"))

    def test_cavalier_tactician_charge_and_mount_are_resolved(self) -> None:
        character, class_id = self.add_class(
            "Cavalier", "pathfinder-class:cavalier", 10
        )
        modules = resolve_class_feature_modules(self.repository, character)
        resources = {
            resource.key: resource
            for module in modules
            for resource in module.resources
        }
        self.assertEqual(3, resources["tactician"].maximum)
        self.assertIn("mounted_charge", resources)
        self.assertIn("banner_charge", resources)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "mounted_charge", 1, active=True
            )
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "banner_charge", 1, active=True
            )
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.automatic_total("attack"))
        self.assertEqual(2, calculator.automatic_total("armor_class"))

        classes = self.repository.list_class_levels(character)
        features = {
            row.id: resolved_class_features_for_level(
                self.repository, character, row
            )
            for row in classes
        }
        grant = resolve_companion_grant(
            classes, features, (), self.repository.list_skill_states(character)
        )
        self.assertTrue(grant.available)
        self.assertEqual(10, grant.effective_level)
        self.assertTrue(any("Mount" in source for source in grant.sources))

    def test_spheres_archetype_profiles_convert_advancement(self) -> None:
        alchemist = class_entry("pathfinder-class:alchemist")
        cavalier = class_entry("pathfinder-class:cavalier")
        champion = resolve_class_profile(
            alchemist,
            (
            archetype_entry(
                "spheres-archetype:pathfinder-class:alchemist:champion-alchemist"
            ),
            ),
        )
        self.assertFalse(champion.casting["traditional"])
        self.assertEqual("Mid", champion.casting["sphere_progression"])
        self.assertEqual(
            {"magic", "martial"}, set(champion.advancement["talent_kinds"])
        )

        blooded = resolve_class_profile(
            cavalier,
            (
            archetype_entry(
                "spheres-archetype:pathfinder-class:cavalier:blooded-knight"
            ),
            ),
        )
        self.assertEqual("Expert", blooded.advancement["talent_progression"])
        self.assertIn("martial", blooded.capabilities)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import resolve_class_choice_slots
from app.class_feature_systems import (
    class_feature_extra_damage,
    resolve_class_feature_modules,
)
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState


class AntipaladinUnchainedBarbarianBrawlerPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "antipaladin-unchained-barbarian-brawler.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self,
        name: str,
        key: str,
        level: int,
        *,
        charisma: int = 10,
        constitution: int = 10,
        strength: int = 10,
        dexterity: int = 10,
    ) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, "Full", "Good", "Poor", "Poor",
            key, 10, level * 6,
        )
        for ability, value in {
            "charisma": charisma,
            "constitution": constitution,
            "strength": strength,
            "dexterity": dexterity,
        }.items():
            self.repository.update_ability_score(character, ability, value)
        return character, class_id

    def resources(self, character: int) -> dict[str, object]:
        return {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }

    def test_packages_and_all_archetypes_are_reviewed(self) -> None:
        expected = {
            "antipaladin": 19,
            "barbarian-unchained": 4,
            "brawler": 22,
        }
        root = (
            Path(__file__).resolve().parent.parent
            / "app" / "class_packages" / "definitions" / "archetypes"
        )
        for slug, count in expected.items():
            self.assertIsNotNone(class_package(slug))
            document = json.loads((root / f"{slug}.json").read_text("utf-8"))
            self.assertEqual(count, len(document["entries"]))
            self.assertTrue(all(entry["features"] for entry in document["entries"]))

        audit = json.loads(
            (
                Path(__file__).resolve().parent.parent
                / "data" / "pf1e" / "class_automation_audit.json"
            ).read_text("utf-8")
        )
        keys = {
            "pathfinder-class:antipaladin",
            "pathfinder-class:barbarian-unchained",
            "pathfinder-class:brawler",
        }
        entries = [
            entry for entry in audit["archetypes"]
            if entry.get("class_key") in keys
        ]
        self.assertEqual(45, len(entries))
        self.assertEqual({"fully_automated"}, {entry["status"] for entry in entries})

    def test_base_resource_progressions_are_live(self) -> None:
        antipaladin, _ = self.add_class(
            "Antipaladin", "pathfinder-class:antipaladin", 10, charisma=18
        )
        antipaladin_resources = self.resources(antipaladin)
        self.assertEqual(4, antipaladin_resources["smite"].maximum)
        self.assertEqual(9, antipaladin_resources["touch_of_corruption"].maximum)
        self.assertEqual(3, antipaladin_resources["cruelties"].maximum_choices)

        barbarian, _ = self.add_class(
            "Barbarian (Unchained)", "pathfinder-class:barbarian-unchained", 12,
            constitution=16,
        )
        self.assertEqual(29, self.resources(barbarian)["rage"].maximum)

        brawler, _ = self.add_class(
            "Brawler", "pathfinder-class:brawler", 10, strength=18
        )
        flexibility = self.resources(brawler)["martial_flexibility"]
        self.assertEqual(8, flexibility.maximum)
        self.assertEqual(3, flexibility.maximum_choices)

    def test_spheres_profiles_preserve_exact_progressions(self) -> None:
        cases = (
            (
                "pathfinder-class:antipaladin",
                "spheres-archetype:pathfinder-class:antipaladin:champion-of-the-cause",
                "Low", "High", {"magic", "martial"},
            ),
            (
                "pathfinder-class:barbarian-unchained",
                "spheres-archetype:pathfinder-class:barbarian-unchained:painted-savage",
                "", "Proficient", {"martial"},
            ),
            (
                "pathfinder-class:brawler",
                "spheres-archetype:pathfinder-class:brawler:prescient-pugilist",
                "Low", "High", {"magic", "martial"},
            ),
        )
        for class_key, archetype_key, caster, talents, capabilities in cases:
            profile = resolve_class_profile(
                class_entry(class_key), (archetype_entry(archetype_key),)
            )
            self.assertEqual(caster, profile.casting.get("sphere_progression", ""))
            self.assertEqual(talents, profile.advancement["talent_progression"])
            self.assertTrue(capabilities <= profile.capabilities)

    def test_archetype_specific_choices_and_resources_are_focused(self) -> None:
        antimage, class_id = self.add_class(
            "Antipaladin", "pathfinder-class:antipaladin", 12, charisma=14
        )
        self.repository.update_ability_score(antimage, "intelligence", 18)
        self.repository.set_class_archetype_keys(
            antimage, class_id,
            ("spheres-archetype:pathfinder-class:antipaladin:antimage",),
        )
        self.assertEqual(10, self.resources(antimage)["nullmagic"].maximum)
        choices = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, antimage)}
        self.assertEqual(4, choices["antimage-nullshaping"].maximum)

        winding, class_id = self.add_class(
            "Brawler", "pathfinder-class:brawler", 8
        )
        self.repository.set_class_archetype_keys(
            winding, class_id,
            ("pathfinder-archetype:pathfinder-class:brawler:winding-path-renegade",),
        )
        school = next(
            slot for slot in resolve_class_choice_slots(self.repository, winding)
            if slot.key == "winding-path-school"
        )
        self.assertEqual(
            {"Mystery of Unblinking Flame", "Mystery of Unfolding Wind", "Mystery of Untwisting Iron"},
            {option.name for option in school.options},
        )

    def test_archetype_precision_damage_uses_declared_level_tables(self) -> None:
        character, class_id = self.add_class(
            "Brawler", "pathfinder-class:brawler", 12, dexterity=18
        )
        self.repository.set_class_archetype_keys(
            character, class_id,
            ("pathfinder-archetype:pathfinder-class:brawler:snakebite-striker",),
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "sneak_attack", 1, active=True)
        )
        damage = class_feature_extra_damage(self.repository, character)
        self.assertEqual("4d6", damage[0].dice)

        strangler, class_id = self.add_class(
            "Brawler", "pathfinder-class:brawler", 15, strength=18
        )
        self.repository.set_class_archetype_keys(
            strangler, class_id,
            ("pathfinder-archetype:pathfinder-class:brawler:strangler",),
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(strangler, class_id, "sneak_attack", 1, active=True)
        )
        damage = class_feature_extra_damage(self.repository, strangler)
        self.assertEqual("4d6", damage[0].dice)


if __name__ == "__main__":
    unittest.main()

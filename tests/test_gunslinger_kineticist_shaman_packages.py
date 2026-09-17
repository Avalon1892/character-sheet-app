from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import resolve_class_choice_slots
from app.class_feature_systems import resolve_class_feature_modules
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.class_power_rules import resolve_class_power_sets
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.character_calculations import CharacterCalculationService


class GunslingerKineticistShamanPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "gunslinger-kineticist-shaman.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self, name: str, key: str, level: int, wisdom: int = 10,
        charisma: int = 10, constitution: int = 10, dexterity: int = 10,
    ) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, "3/4", "Poor", "Poor", "Good",
            key, 8, level * 6,
        )
        for ability, value in {
            "wisdom": wisdom,
            "charisma": charisma,
            "constitution": constitution,
            "dexterity": dexterity,
        }.items():
            self.repository.update_ability_score(character, ability, value)
        return character, class_id

    def resources(self, character: int) -> dict[str, object]:
        calculations = CharacterCalculationService(self.repository, character)
        modifiers = {
            ability: result.ability_modifier
            for ability, result in calculations.ability_results().items()
        }
        return {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, modifiers
            )
            for resource in module.resources
        }

    def test_packages_and_all_reviewed_archetypes_are_complete(self) -> None:
        expected = {"gunslinger": 32, "kineticist": 20, "shaman": 19}
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
            "pathfinder-class:gunslinger",
            "pathfinder-class:kineticist",
            "pathfinder-class:shaman",
        }
        entries = [
            entry for entry in audit["archetypes"]
            if entry.get("class_key") in keys
        ]
        self.assertEqual(71, len(entries))
        self.assertEqual({"fully_automated"}, {entry["status"] for entry in entries})

    def test_base_signature_resources_and_choices_use_published_rules(self) -> None:
        gunslinger, _ = self.add_class(
            "Gunslinger", "pathfinder-class:gunslinger", 10,
            wisdom=16, dexterity=18,
        )
        gunslinger_resources = self.resources(gunslinger)
        self.assertEqual(3, gunslinger_resources["grit"].maximum)
        self.assertEqual(3, gunslinger_resources["nimble_applies"].maximum)

        kineticist, _ = self.add_class(
            "Kineticist", "pathfinder-class:kineticist", 10, constitution=18
        )
        self.assertEqual(7, self.resources(kineticist)["burn"].maximum)
        choices = {
            slot.key for slot in resolve_class_choice_slots(
                self.repository, kineticist
            )
        }
        self.assertIn("kineticist-elements", choices)

        shaman, _ = self.add_class(
            "Shaman", "pathfinder-class:shaman", 12, wisdom=18
        )
        choices = {
            slot.key for slot in resolve_class_choice_slots(
                self.repository, shaman
            )
        }
        self.assertIn("shaman-spirit", choices)
        hexes = next(
            power_set for power_set in resolve_class_power_sets(
                self.repository, shaman
            )
            if power_set.key == "shaman-hexes"
        )
        self.assertEqual(6, hexes.maximum)

    def test_nimble_and_gun_training_only_apply_when_enabled(self) -> None:
        character, class_id = self.add_class(
            "Gunslinger", "pathfinder-class:gunslinger", 10,
            wisdom=16, dexterity=18,
        )
        calculations = CharacterCalculationService(self.repository, character)
        self.assertEqual(0, calculations.automatic_total("armor_class"))
        self.assertEqual(0, calculations.automatic_total("damage"))

        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "nimble_applies", 3, active=True
            )
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "gun_training_applies", 1,
                active=True, choices_json='["Pistol"]',
            )
        )
        calculations = CharacterCalculationService(self.repository, character)
        self.assertEqual(3, calculations.automatic_total("armor_class"))
        self.assertEqual(3, calculations.automatic_total("touch_ac"))
        self.assertEqual(4, calculations.automatic_total("damage"))

    def test_spheres_profiles_keep_exact_caster_and_talent_progressions(self) -> None:
        cases = (
            ("pathfinder-class:gunslinger", "spheres-archetype:pathfinder-class:gunslinger:spellshot-engineer", "Low", "High", {"magic", "martial"}),
            ("pathfinder-class:kineticist", "spheres-archetype:pathfinder-class:kineticist:scion", "Mid", "Low", {"magic"}),
            ("pathfinder-class:shaman", "spheres-archetype:pathfinder-class:shaman:sphere-shaman", "High", "High", {"magic"}),
        )
        for class_key, archetype_key, caster, talents, capabilities in cases:
            profile = resolve_class_profile(
                class_entry(class_key), (archetype_entry(archetype_key),)
            )
            self.assertEqual(caster, profile.casting["sphere_progression"])
            self.assertEqual(talents, profile.advancement["talent_progression"])
            self.assertTrue(capabilities <= profile.capabilities)

        glass_eye = resolve_class_profile(
            class_entry("pathfinder-class:gunslinger"),
            (archetype_entry(
                "spheres-archetype:pathfinder-class:gunslinger:glass-eye-gunmage"
            ),),
        )
        self.assertEqual("Quarter", glass_eye.advancement["talent_progression"])

    def test_archetype_resources_and_restricted_choices_are_live(self) -> None:
        firebrand, class_id = self.add_class(
            "Gunslinger", "pathfinder-class:gunslinger", 10,
            wisdom=10, charisma=18,
        )
        self.repository.set_class_archetype_keys(
            firebrand, class_id,
            ("pathfinder-archetype:pathfinder-class:gunslinger:firebrand",),
        )
        resources = self.resources(firebrand)
        self.assertEqual(4, resources["grit"].maximum)
        self.assertEqual(10, resources["bombs"].maximum)

        gun_tank, class_id = self.add_class(
            "Gunslinger", "pathfinder-class:gunslinger", 16, wisdom=16
        )
        self.repository.set_class_archetype_keys(
            gun_tank, class_id,
            ("pathfinder-archetype:pathfinder-class:gunslinger:gun-tank",),
        )
        self.assertEqual(4, self.resources(gun_tank)["armor_training"].maximum)

        cinderlands, class_id = self.add_class(
            "Kineticist", "pathfinder-class:kineticist", 15,
            constitution=18,
        )
        self.repository.set_class_archetype_keys(
            cinderlands, class_id,
            ("pathfinder-archetype:pathfinder-class:kineticist:cinderlands-adept",),
        )
        elements = next(
            slot for slot in resolve_class_choice_slots(
                self.repository, cinderlands
            )
            if slot.key == "kineticist-elements"
        )
        self.assertEqual((3, 3), (elements.minimum, elements.maximum))
        self.assertEqual({"Fire Element"}, {option.name for option in elements.options})

    def test_speaker_for_the_past_offers_only_ancestor_and_time_revelations(self) -> None:
        character, class_id = self.add_class(
            "Shaman", "pathfinder-class:shaman", 14, wisdom=18
        )
        self.repository.set_class_archetype_keys(
            character, class_id,
            ("pathfinder-archetype:pathfinder-class:shaman:speaker-for-the-past",),
        )
        revelations = next(
            power_set for power_set in resolve_class_power_sets(
                self.repository, character
            )
            if power_set.key == "speaker-past-revelations"
        )
        self.assertEqual((4, 6, 12, 14), revelations.slot_levels)
        self.assertTrue(revelations.options)
        self.assertTrue(
            {option.category for option in revelations.options}
            <= {"Ancestor", "Time"}
        )


if __name__ == "__main__":
    unittest.main()

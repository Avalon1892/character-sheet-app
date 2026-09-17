from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import resolve_class_choice_slots
from app.class_feature_systems import resolve_class_feature_modules
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.character_calculations import CharacterCalculationService


class ArcanistInvestigatorMagusPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "three-class-wave.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self, name: str, key: str, level: int, intelligence: int = 18,
        charisma: int = 10,
    ) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, "3/4", "Poor", "Poor", "Good",
            key, 8, level * 6,
        )
        self.repository.update_ability_score(character, "intelligence", intelligence)
        self.repository.update_ability_score(character, "charisma", charisma)
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

    def test_packages_and_every_generated_archetype_are_present(self) -> None:
        expected = {"arcanist": 17, "investigator": 46, "magus": 36}
        root = (
            Path(__file__).resolve().parent.parent
            / "app" / "class_packages" / "definitions" / "archetypes"
        )
        for slug, count in expected.items():
            self.assertIsNotNone(class_package(slug))
            document = json.loads(
                (root / f"{slug}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(count, len(document["entries"]))
            self.assertTrue(all(entry["features"] for entry in document["entries"]))

        audit = json.loads(
            (
                Path(__file__).resolve().parent.parent
                / "data" / "pf1e" / "class_automation_audit.json"
            ).read_text(encoding="utf-8")
        )
        keys = {
            "pathfinder-class:arcanist",
            "pathfinder-class:investigator",
            "pathfinder-class:magus",
        }
        entries = [
            entry for entry in audit["archetypes"]
            if entry.get("class_key") in keys
        ]
        self.assertEqual(99, len(entries))
        self.assertEqual({"fully_automated"}, {entry["status"] for entry in entries})

    def test_base_signature_resources_use_the_published_progressions(self) -> None:
        arcanist, _ = self.add_class(
            "Arcanist", "pathfinder-class:arcanist", 10
        )
        reservoir = self.resources(arcanist)["arcane_reservoir"]
        self.assertEqual(13, reservoir.maximum)
        self.assertEqual(8, reservoir.recovery_value)

        investigator, _ = self.add_class(
            "Investigator", "pathfinder-class:investigator", 10
        )
        investigator_resources = self.resources(investigator)
        self.assertEqual(9, investigator_resources["inspiration"].maximum)
        self.assertEqual(4, investigator_resources["studied_combat"].maximum)
        self.assertIn("studied_strike", investigator_resources)

        magus, _ = self.add_class("Magus", "pathfinder-class:magus", 10)
        self.assertEqual(9, self.resources(magus)["arcane_pool"].maximum)

    def test_spheres_profiles_replace_only_the_correct_casting_systems(self) -> None:
        arcanist = resolve_class_profile(
            class_entry("pathfinder-class:arcanist"),
            (archetype_entry(
                "spheres-archetype:pathfinder-class:arcanist:sphere-arcanist"
            ),),
        )
        self.assertFalse(arcanist.casting["traditional"])
        self.assertEqual("High", arcanist.casting["sphere_progression"])
        self.assertEqual("High", arcanist.advancement["talent_progression"])

        acupuncturist = resolve_class_profile(
            class_entry("pathfinder-class:investigator"),
            (archetype_entry(
                "spheres-archetype:pathfinder-class:investigator:acupuncturist"
            ),),
        )
        self.assertFalse(acupuncturist.casting["traditional"])
        self.assertEqual("Expert", acupuncturist.advancement["talent_progression"])
        self.assertIn("martial", acupuncturist.capabilities)

        sphere_magus = resolve_class_profile(
            class_entry("pathfinder-class:magus"),
            (archetype_entry(
                "spheres-archetype:pathfinder-class:magus:sphere-magus"
            ),),
        )
        self.assertFalse(sphere_magus.casting["traditional"])
        self.assertEqual("Mid", sphere_magus.casting["sphere_progression"])
        self.assertEqual("Mid", sphere_magus.advancement["talent_progression"])

    def test_spellcasting_conversion_archetypes_select_the_right_mode(self) -> None:
        psychic = resolve_class_profile(
            class_entry("pathfinder-class:investigator"),
            (archetype_entry(
                "pathfinder-archetype:pathfinder-class:investigator:psychic-detective"
            ),),
        )
        self.assertEqual("spontaneous", psychic.casting["type"])
        self.assertEqual("intelligence", psychic.casting["ability"])
        self.assertEqual("Psychic", psychic.casting["spells"])

        scion = resolve_class_profile(
            class_entry("pathfinder-class:magus"),
            (archetype_entry(
                "pathfinder-archetype:pathfinder-class:magus:eldritch-scion"
            ),),
        )
        self.assertEqual("spontaneous", scion.casting["type"])
        self.assertEqual("charisma", scion.casting["ability"])

        myrmidarch = resolve_class_profile(
            class_entry("pathfinder-class:magus"),
            (archetype_entry(
                "pathfinder-archetype:pathfinder-class:magus:myrmidarch"
            ),),
        )
        self.assertEqual(-1, myrmidarch.casting["daily_slot_adjustment"])

    def test_archetype_choices_are_exact_and_contextual(self) -> None:
        arcanist, class_id = self.add_class(
            "Arcanist", "pathfinder-class:arcanist", 8
        )
        self.repository.set_class_archetype_keys(
            arcanist, class_id,
            ("pathfinder-archetype:pathfinder-class:arcanist:elemental-master",),
        )
        focus = next(
            slot for slot in resolve_class_choice_slots(self.repository, arcanist)
            if slot.key == "elemental-master-focus"
        )
        self.assertEqual(
            {"Air", "Earth", "Fire", "Water"},
            {option.name for option in focus.options},
        )

        self.repository.set_class_archetype_keys(
            arcanist, class_id,
            ("pathfinder-archetype:pathfinder-class:arcanist:blood-arcanist",),
        )
        bloodline = next(
            slot for slot in resolve_class_choice_slots(self.repository, arcanist)
            if slot.key == "blood-arcanist-bloodline"
        )
        self.assertTrue(bloodline.options)
        self.assertEqual((1, 1), (bloodline.minimum, bloodline.maximum))

    def test_investigator_and_magus_archetype_resources_feed_live_rules(self) -> None:
        jinyiwei, class_id = self.add_class(
            "Investigator", "pathfinder-class:investigator", 10
        )
        self.repository.set_class_archetype_keys(
            jinyiwei, class_id,
            ("pathfinder-archetype:pathfinder-class:investigator:jinyiwei",),
        )
        self.assertEqual(3, self.resources(jinyiwei)["judgment"].maximum)

        magus, class_id = self.add_class("Magus", "pathfinder-class:magus", 12)
        self.repository.set_class_archetype_keys(
            magus, class_id,
            ("pathfinder-archetype:pathfinder-class:magus:myrmidarch",),
        )
        myrmidarch = self.resources(magus)
        self.assertEqual(2, myrmidarch["weapon_training_applies"].maximum)
        self.assertEqual(1, myrmidarch["armor_training"].maximum)
        self.repository.save_class_feature_state(
            ClassFeatureState(
                magus, class_id, "weapon_training_applies", 2,
                active=True,
            )
        )
        calculations = CharacterCalculationService(self.repository, magus)
        self.assertEqual(2, calculations.automatic_total("attack"))
        self.assertEqual(2, calculations.automatic_total("damage"))


if __name__ == "__main__":
    unittest.main()

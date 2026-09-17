from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
)
from app.class_feature_systems import resolve_class_feature_modules
from app.class_granted_spells import synchronize_class_granted_spells
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.class_power_rules import resolve_class_power_sets
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.character_calculations import CharacterCalculationService


class WitchWarpriestBloodragerPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(
            Path(self.temporary.name) / "witch-warpriest-bloodrager.db"
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(
        self, name: str, key: str, level: int, wisdom: int = 10,
        charisma: int = 10, intelligence: int = 10, constitution: int = 10,
    ) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, "3/4", "Poor", "Poor", "Good",
            key, 8, level * 6,
        )
        for ability, value in {
            "wisdom": wisdom,
            "charisma": charisma,
            "intelligence": intelligence,
            "constitution": constitution,
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
        expected = {"witch": 45, "warpriest": 24, "bloodrager": 23}
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
            "pathfinder-class:witch",
            "pathfinder-class:warpriest",
            "pathfinder-class:bloodrager",
        }
        entries = [
            entry for entry in audit["archetypes"]
            if entry.get("class_key") in keys
        ]
        self.assertEqual(92, len(entries))
        self.assertEqual({"fully_automated"}, {entry["status"] for entry in entries})

    def test_base_class_choices_powers_and_resources_use_published_scaling(self) -> None:
        witch, _ = self.add_class(
            "Witch", "pathfinder-class:witch", 12, intelligence=18
        )
        choices = {slot.key for slot in resolve_class_choice_slots(self.repository, witch)}
        self.assertIn("witch-patron", choices)
        hexes = next(
            power_set for power_set in resolve_class_power_sets(self.repository, witch)
            if power_set.key == "witch-hexes"
        )
        self.assertEqual(7, len(hexes.slot_levels))

        warpriest, _ = self.add_class(
            "Warpriest", "pathfinder-class:warpriest", 10, wisdom=18
        )
        resources = self.resources(warpriest)
        self.assertEqual(8, resources["blessing_uses"].maximum)
        self.assertEqual(9, resources["fervor"].maximum)
        blessings = next(
            slot for slot in resolve_class_choice_slots(self.repository, warpriest)
            if slot.key == "warpriest-blessings"
        )
        self.assertEqual((2, 2), (blessings.minimum, blessings.maximum))

        bloodrager, _ = self.add_class(
            "Bloodrager", "pathfinder-class:bloodrager", 10,
            charisma=18, constitution=16,
        )
        self.assertEqual(25, self.resources(bloodrager)["bloodrage"].maximum)
        choices = {
            slot.key for slot in resolve_class_choice_slots(
                self.repository, bloodrager
            )
        }
        self.assertIn("bloodrager-bloodline", choices)

    def test_spheres_archetypes_replace_traditional_casting_and_budget(self) -> None:
        cases = (
            ("pathfinder-class:witch", "spheres-archetype:pathfinder-class:witch:sphere-witch", "High", "High", {"magic"}),
            ("pathfinder-class:warpriest", "spheres-archetype:pathfinder-class:warpriest:champion-warpriest", "Mid", "Mid", {"magic", "martial"}),
            ("pathfinder-class:bloodrager", "spheres-archetype:pathfinder-class:bloodrager:hemophage", "Low", "High", {"magic", "martial"}),
        )
        for class_key, archetype_key, caster, talents, capabilities in cases:
            profile = resolve_class_profile(
                class_entry(class_key), (archetype_entry(archetype_key),)
            )
            self.assertFalse(profile.casting["traditional"])
            self.assertEqual(caster, profile.casting["sphere_progression"])
            self.assertEqual(talents, profile.advancement["talent_progression"])
            self.assertTrue(capabilities <= profile.capabilities)

    def test_wyrm_witch_draconic_patron_grants_exact_spells(self) -> None:
        character, class_id = self.add_class(
            "Witch", "pathfinder-class:witch", 10, intelligence=18
        )
        self.repository.set_class_archetype_keys(
            character, class_id,
            ("pathfinder-archetype:pathfinder-class:witch:wyrm-witch",),
        )
        patron = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "witch-patron"
        )
        self.assertEqual(
            {"Chromatic", "Esoteric", "Imperial", "Metallic", "Outer", "Primal"},
            {option.name for option in patron.options},
        )
        metallic = next(option for option in patron.options if option.name == "Metallic")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, patron, (metallic.key,))
        )
        self.assertTrue(synchronize_class_granted_spells(self.repository, character))
        granted = {
            spell.name for spell in self.repository.list_spells(character)
            if spell.catalog_category == "Class Granted"
        }
        self.assertEqual(
            {"Protection from Evil", "Weapon of Awe", "Heroism", "Dispel Evil", "Commune"},
            granted,
        )

    def test_archetype_resources_feed_live_rules(self) -> None:
        steelblood, class_id = self.add_class(
            "Bloodrager", "pathfinder-class:bloodrager", 13, constitution=16
        )
        self.repository.set_class_archetype_keys(
            steelblood, class_id,
            ("pathfinder-archetype:pathfinder-class:bloodrager:steelblood",),
        )
        self.assertEqual(3, self.resources(steelblood)["armor_training"].maximum)

        feral, class_id = self.add_class(
            "Warpriest", "pathfinder-class:warpriest", 15, wisdom=18
        )
        self.repository.set_class_archetype_keys(
            feral, class_id,
            ("pathfinder-archetype:pathfinder-class:warpriest:feral-champion",),
        )
        self.assertEqual(3, self.resources(feral)["wild_shape"].maximum)

        arsenal, class_id = self.add_class(
            "Warpriest", "pathfinder-class:warpriest", 13, wisdom=18
        )
        self.repository.set_class_archetype_keys(
            arsenal, class_id,
            ("pathfinder-archetype:pathfinder-class:warpriest:molthuni-arsenal-chaplain",),
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                arsenal, class_id, "weapon_training_applies", 3, active=True
            )
        )
        calculations = CharacterCalculationService(self.repository, arsenal)
        self.assertEqual(3, calculations.automatic_total("attack"))
        self.assertEqual(3, calculations.automatic_total("damage"))


if __name__ == "__main__":
    unittest.main()

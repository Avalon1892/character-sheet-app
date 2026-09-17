from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import audit_archetype, audit_class
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.services.advancement import character_advancement_budgets


TARGETS = {
    "thaumaturge": ("spheres-class:thaumaturge", 15),
    "fey-adept": ("spheres-class:fey-adept", 12),
    "symbiat": ("spheres-class:symbiat", 17),
}


class ThaumaturgeFeyAdeptSymbiatPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "classes.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def character_with_class(self, family: str, level: int = 20) -> int:
        key = TARGETS[family][0]
        entry = class_entry(key)
        character = self.repository.create_character(family.title(), "Spheres")
        self.repository.add_class_level(
            character, str(entry["name"]), level, str(entry["bab"]),
            str(entry["fort"]), str(entry["reflex"]), str(entry["will"]),
            key, int(entry["hit_die"]), level * int(entry["hit_die"]),
        )
        return character

    def test_all_three_classes_and_all_44_archetypes_are_fully_automated(self) -> None:
        root = Path(__file__).resolve().parent.parent
        total = 0
        for family, (key, expected_count) in TARGETS.items():
            self.assertIsNotNone(class_package(key))
            self.assertEqual("fully_automated", audit_class(class_entry(key))["status"])
            document = json.loads((root / "app" / "class_packages" / "definitions" / "archetypes" / f"{family}.json").read_text(encoding="utf-8"))
            self.assertEqual(expected_count, len(document["entries"]))
            total += expected_count
            for declared in document["entries"]:
                self.assertEqual("fully_automated", audit_archetype(archetype_entry(declared["key"]))["status"], declared["key"])
        self.assertEqual(44, total)

    def test_thaumaturge_resources_advancement_and_master_invoker(self) -> None:
        character = self.character_with_class("thaumaturge")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"casting": 5}) for resource in module.resources}
        self.assertEqual(15, resources["invocations"].maximum)
        self.assertEqual(6, resources["forbidden_lore"].maximum)
        self.assertEqual(25, resources["invocation_dc"].maximum)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(12, talents.automatic)

    def test_fey_adept_shadow_resources_and_talents(self) -> None:
        character = self.character_with_class("fey-adept")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"charisma": 5}) for resource in module.resources}
        self.assertEqual(15, resources["shadow_points"].maximum)
        self.assertEqual(10, resources["shadowmark_damage"].maximum)
        self.assertEqual(4, resources["shadowmark_penalty"].maximum)
        self.assertEqual(5, resources["truesight"].maximum)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(23, talents.automatic)

    def test_symbiat_psionics_and_mental_power_talents(self) -> None:
        character = self.character_with_class("symbiat")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"intelligence": 5}) for resource in module.resources}
        self.assertEqual(47, resources["psionics"].maximum)
        self.assertEqual(25, resources["psionic_dc"].maximum)
        self.assertIn("Telekinetic Colossus", resources["psionics"].choice_options)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(19, talents.automatic)

    def test_reviewed_archetype_profiles_apply_conversions_and_choices(self) -> None:
        champion_entry = archetype_entry("spheres-archetype:spheres-class:symbiat:champion-symbiat")
        choice_key = "archetype-choice:spheres-archetype:spheres-class:symbiat:champion-symbiat:champion-symbiat-training"
        champion = resolve_class_profile(class_entry("spheres-class:symbiat"), (champion_entry,), {choice_key: ("greater-training",)})
        self.assertEqual("High", champion.advancement["talent_progression"])
        self.assertEqual({"magic", "martial"}, set(champion.advancement["talent_kinds"]))
        self.assertIn("Bucklers", champion.proficiencies["armor"])
        solipsist = resolve_class_profile(class_entry("spheres-class:fey-adept"), (archetype_entry("spheres-archetype:spheres-class:fey-adept:solipsist"),))
        self.assertEqual("intelligence", solipsist.casting["ability"])
        genius = resolve_class_profile(class_entry("spheres-class:thaumaturge"), (archetype_entry("spheres-archetype:spheres-class:thaumaturge:genius"),))
        self.assertNotIn("magic", genius.capabilities)
        self.assertEqual(8, genius.skill_points)


if __name__ == "__main__":
    unittest.main()

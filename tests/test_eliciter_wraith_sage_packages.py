from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import audit_archetype, audit_class
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, archetype_entries, class_entry
from app.database import CharacterRepository
from app.services.advancement import character_advancement_budgets


TARGETS = {
    "eliciter": ("spheres-class:eliciter", 8),
    "wraith": ("spheres-class:wraith", 7),
    "sage": ("spheres-class:sage", 5),
}


class EliciterWraithSagePackageTests(unittest.TestCase):
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

    def test_all_three_classes_and_all_twenty_archetypes_are_fully_automated(self) -> None:
        root = Path(__file__).resolve().parent.parent
        total = 0
        for family, (key, expected_count) in TARGETS.items():
            self.assertIsNotNone(class_package(key))
            self.assertEqual("fully_automated", audit_class(class_entry(key))["status"])
            document = json.loads((root / "app" / "class_packages" / "definitions" / "archetypes" / f"{family}.json").read_text(encoding="utf-8"))
            self.assertEqual(expected_count, len(document["entries"]))
            self.assertEqual(expected_count, len(archetype_entries(key)))
            total += expected_count
            for declared in document["entries"]:
                self.assertEqual("fully_automated", audit_archetype(archetype_entry(declared["key"]))["status"], declared["key"])
        self.assertEqual(20, total)

    def test_eliciter_hypnotism_persuasive_emotions_and_advancement(self) -> None:
        character = self.character_with_class("eliciter")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"charisma": 5}) for resource in module.resources}
        self.assertEqual(13, resources["hypnotism"].maximum)
        self.assertEqual(30, resources["hypnotism_dc"].maximum)
        self.assertEqual(3, resources["convincing"].maximum)
        self.assertIn("Domination", resources["hypnotism"].choice_options)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(18, talents.automatic)

    def test_wraith_mid_casting_form_possession_and_haunts(self) -> None:
        character = self.character_with_class("wraith")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"casting": 5}) for resource in module.resources}
        self.assertEqual(25, resources["wraith_form"].maximum)
        self.assertEqual(25, resources["possession_dc"].maximum)
        profile = resolve_class_profile(class_entry("spheres-class:wraith"), ())
        self.assertEqual("Mid", profile.casting["sphere_progression"])

    def test_sage_ki_meditation_chi_gong_and_mixed_talents(self) -> None:
        character = self.character_with_class("sage")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"wisdom": 5}) for resource in module.resources}
        self.assertEqual(25, resources["ki_pool"].maximum)
        self.assertEqual(10, resources["meditation_dice"].maximum)
        self.assertEqual(10, resources["chi_gong_dice"].maximum)
        self.assertEqual(25, resources["esotery_dc"].maximum)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(22, talents.automatic)

    def test_reviewed_archetype_profile_conversions(self) -> None:
        empathic = resolve_class_profile(class_entry("spheres-class:eliciter"), (archetype_entry("spheres-archetype:spheres-class:eliciter:empathic-duelist"),))
        self.assertEqual({"magic", "martial"}, set(empathic.advancement["talent_kinds"]))
        matagot = resolve_class_profile(class_entry("spheres-class:wraith"), (archetype_entry("spheres-archetype:spheres-class:wraith:matagot"),))
        self.assertEqual("High", matagot.advancement["talent_progression"])
        wand_master = resolve_class_profile(class_entry("spheres-class:sage"), (archetype_entry("spheres-archetype:spheres-class:sage:wand-master"),))
        self.assertIn("spellcraft", wand_master.class_skills)
        self.assertNotIn("diplomacy", wand_master.class_skills)


if __name__ == "__main__":
    unittest.main()

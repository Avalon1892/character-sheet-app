from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import class_choice_selection_record, resolve_class_choice_slots
from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import audit_archetype, audit_class
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.services.advancement import character_advancement_budgets


TARGETS = {
    "hedgewitch": ("spheres-class:hedgewitch", 7),
    "shifter": ("spheres-class:shifter", 17),
    "soul-weaver": ("spheres-class:soul-weaver", 9),
}


class HedgewitchShifterSoulWeaverPackageTests(unittest.TestCase):
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

    def test_all_three_classes_and_all_33_archetypes_are_fully_automated(self) -> None:
        total = 0
        root = Path(__file__).resolve().parent.parent
        for family, (key, expected_count) in TARGETS.items():
            self.assertIsNotNone(class_package(key))
            self.assertEqual("fully_automated", audit_class(class_entry(key))["status"])
            document = json.loads((root / "app" / "class_packages" / "definitions" / "archetypes" / f"{family}.json").read_text(encoding="utf-8"))
            self.assertEqual(expected_count, len(document["entries"]))
            total += expected_count
            for declared in document["entries"]:
                self.assertEqual("fully_automated", audit_archetype(archetype_entry(declared["key"]))["status"], declared["key"])
        self.assertEqual(33, total)

    def test_hedgewitch_paths_secrets_and_magic_budget_are_live(self) -> None:
        character = self.character_with_class("hedgewitch")
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(2, slots["hedgewitch-paths"].minimum)
        self.assertEqual(2, slots["hedgewitch-paths"].maximum)
        self.assertEqual(10, slots["hedgewitch-secrets"].maximum)
        self.assertIn("Familiar", {option.name for option in slots["hedgewitch-secrets"].options})
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(17, talents.automatic)

    def test_shifter_form_bestial_traits_and_magic_budget_are_live(self) -> None:
        character = self.character_with_class("shifter")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"wisdom": 4}) for resource in module.resources}
        self.assertEqual(1, resources["self_shapeshift"].maximum)
        self.assertEqual(3, resources["enhanced_physicality"].maximum)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(10, slots["shifter-bestial-traits"].maximum)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(18, talents.automatic)

    def test_soul_weaver_souls_channel_and_blessings_are_live(self) -> None:
        character = self.character_with_class("soul-weaver")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"charisma": 5}) for resource in module.resources}
        self.assertEqual(8, resources["souls"].maximum)
        self.assertEqual(8, resources["channel_energy"].maximum)
        self.assertEqual(10, resources["channel_energy_dice"].maximum)
        self.assertEqual(25, resources["nexus_save_dc"].maximum)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(1, slots["soul-weaver-channel"].maximum)
        self.assertNotIn("soul-weaver-blessings", slots)
        self.assertNotIn("soul-weaver-blights", slots)
        channel = slots["soul-weaver-channel"]
        positive = next(option.key for option in channel.options if option.name.startswith("Positive"))
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, channel, (positive,))
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(5, slots["soul-weaver-blessings"].maximum)
        self.assertNotIn("soul-weaver-blights", slots)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(23, talents.automatic)

    def test_reviewed_archetype_profiles_apply_real_conversions(self) -> None:
        champion = resolve_class_profile(class_entry("spheres-class:shifter"), (archetype_entry("spheres-archetype:spheres-class:shifter:champion-shifter"),))
        self.assertEqual({"magic", "martial"}, set(champion.advancement["talent_kinds"]))
        self.assertIn("Bucklers", champion.proficiencies["armor"])
        martial = resolve_class_profile(class_entry("spheres-class:hedgewitch"), (archetype_entry("spheres-archetype:spheres-class:hedgewitch:martial-hedgewitch"),))
        self.assertEqual("Five-Fourths", martial.advancement["talent_progression"])
        self.assertIn("acrobatics", martial.class_skills)
        banshee = resolve_class_profile(class_entry("spheres-class:soul-weaver"), (archetype_entry("spheres-archetype:spheres-class:soul-weaver:banshee"),))
        self.assertIn("bluff", banshee.class_skills)
        self.assertNotIn("heal", banshee.class_skills)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import resolve_class_choice_slots
from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import audit_archetype, audit_class
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, archetype_entries, class_entry
from app.database import CharacterRepository
from app.services.advancement import character_advancement_budgets


TARGETS = {
    "necros": ("spheres-class:necros", 2),
    "troubadour": ("spheres-class:troubadour", 5),
    "warden": ("spheres-class:warden", 4),
}


class NecrosTroubadourWardenPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "classes.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def character_with_class(self, family: str, level: int = 20) -> tuple[int, int]:
        key = TARGETS[family][0]
        entry = class_entry(key)
        character = self.repository.create_character(family.title(), "Spheres")
        class_id = self.repository.add_class_level(
            character, str(entry["name"]), level, str(entry["bab"]),
            str(entry["fort"]), str(entry["reflex"]), str(entry["will"]),
            key, int(entry["hit_die"]), level * int(entry["hit_die"]),
        )
        return character, class_id

    def select_archetype(self, character_id: int, class_id: int, key: str) -> None:
        self.repository.set_class_archetype_keys(character_id, class_id, (key,))

    def test_classes_and_all_eleven_archetypes_are_fully_automated(self) -> None:
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
        self.assertEqual(11, total)

    def test_necros_resources_choices_and_advancement(self) -> None:
        character, _ = self.character_with_class("necros")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"intelligence": 5}) for resource in module.resources}
        self.assertEqual(8, resources["channel_energy"].maximum)
        self.assertEqual(10, resources["channel_energy_dice"].maximum)
        self.assertEqual(50, resources["necrotic_shield"].maximum)
        self.assertEqual(4, resources["decaying_form"].maximum)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(17, talents.automatic)

    def test_necrotech_replaces_necros_trackers_and_adds_its_own(self) -> None:
        character, class_id = self.character_with_class("necros")
        self.select_archetype(character, class_id, "spheres-archetype:spheres-class:necros:necrotech-savant")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"intelligence": 5, "casting": 5}) for resource in module.resources}
        self.assertNotIn("channel_energy", resources)
        self.assertEqual(8, resources["gadgets"].maximum)
        self.assertEqual(5, resources["necrograft_capacity"].maximum)
        self.assertEqual(50, resources["necrograft_shield"].maximum)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(5, slots["necrotech-technical-insights"].maximum)
        self.assertEqual(5, slots["necrotech-necrografts"].maximum)

    def test_troubadour_persona_resources_and_scaling(self) -> None:
        character, _ = self.character_with_class("troubadour")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"charisma": 5}) for resource in module.resources}
        self.assertEqual(5, resources["quick_change"].maximum)
        self.assertEqual(25, resources["flexible_truth_dc"].maximum)
        self.assertIn("base_persona", resources)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(16, talents.automatic)

    def test_ringmaster_clone_polymath_and_keeper_profiles(self) -> None:
        troubadour = class_entry("spheres-class:troubadour")
        polymath = resolve_class_profile(troubadour, (archetype_entry("spheres-archetype:spheres-class:troubadour:polymath"),))
        self.assertEqual("Journeyman", polymath.advancement["talent_progression"])
        self.assertEqual({"magic", "martial", "skill"}, set(polymath.advancement["talent_kinds"]))

        for archetype_name in ("clone", "ringmaster"):
            character, class_id = self.character_with_class("troubadour")
            self.select_archetype(character, class_id, f"spheres-archetype:spheres-class:troubadour:{archetype_name}")
            personas = next(slot for slot in resolve_class_choice_slots(self.repository, character) if slot.key == "troubadour-personas")
            self.assertEqual(1, personas.maximum)

        warden = class_entry("spheres-class:warden")
        keeper = resolve_class_profile(warden, (archetype_entry("spheres-archetype:spheres-class:warden:keeper"),))
        self.assertEqual(["magic"], list(keeper.advancement["talent_kinds"]))
        self.assertNotIn("martial", keeper.capabilities)

    def test_warden_guard_reinforcements_and_archetype_trackers(self) -> None:
        character, _ = self.character_with_class("warden")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"charisma": 5, "casting": 5}) for resource in module.resources}
        self.assertEqual(5, resources["guard"].maximum_choices)
        self.assertEqual(5, resources["guard_bonus"].maximum)
        self.assertEqual(25, resources["reinforcement_dc"].maximum)
        self.assertEqual(5, resources["steadfast"].maximum)
        self.assertEqual(10000, resources["projected_empathy"].maximum)
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(24, talents.automatic)

        jailer, class_id = self.character_with_class("warden")
        self.select_archetype(jailer, class_id, "spheres-archetype:spheres-class:warden:jailer")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, jailer, {"charisma": 5, "casting": 5}) for resource in module.resources}
        self.assertEqual(25, resources["detain_dc"].maximum)
        self.assertEqual(1, resources["detained_targets"].maximum_choices)


if __name__ == "__main__":
    unittest.main()

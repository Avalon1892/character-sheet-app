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
from app.services.character_calculations import CharacterCalculationService


TARGETS = {
    "striker": ("spheres-class:striker", 9),
    "technician": ("spheres-class:technician", 6),
    "mageknight": ("spheres-class:mageknight", 19),
}


class StrikerTechnicianMageknightPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "classes.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _character_with_class(self, family: str, level: int = 20) -> tuple[int, int]:
        key = TARGETS[family][0]
        entry = class_entry(key)
        character = self.repository.create_character(family.title(), "Spheres")
        class_level = self.repository.add_class_level(
            character, str(entry["name"]), level, str(entry["bab"]),
            str(entry["fort"]), str(entry["reflex"]), str(entry["will"]),
            key, int(entry["hit_die"]), level * int(entry["hit_die"]),
        )
        return character, class_level

    def test_families_and_all_34_archetypes_are_fully_automated(self) -> None:
        total = 0
        for family, (key, expected_count) in TARGETS.items():
            self.assertIsNotNone(class_package(key))
            self.assertEqual("fully_automated", audit_class(class_entry(key))["status"])
            path = Path(__file__).resolve().parent.parent / "app" / "class_packages" / "definitions" / "archetypes" / f"{family}.json"
            entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
            self.assertEqual(expected_count, len(entries))
            total += len(entries)
            for declared in entries:
                catalog = archetype_entry(declared["key"])
                self.assertEqual("fully_automated", audit_archetype(catalog)["status"], declared["key"])
        self.assertEqual(34, total)

    def test_striker_tension_techniques_choices_and_ac_are_live(self) -> None:
        character, _class_level = self._character_with_class("striker")
        self.repository.update_ability_score(character, "constitution", 18)
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"constitution": 4}) for resource in module.resources}
        self.assertEqual(10, resources["tension"].maximum)
        self.assertEqual(7, resources["opening_tension"].maximum)
        self.assertEqual(7, resources["drill_knuckle"].maximum)
        self.assertEqual(3, resources["rapid_pummel"].use_cost)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(1, slots["striker-bare-knuckles"].maximum)
        self.assertEqual(7, slots["striker-arts"].maximum)
        self.assertEqual(3, slots["striker-tension-training"].maximum)
        self.assertEqual(4, CharacterCalculationService(self.repository, character).automatic_total("armor_class"))
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(21, talents.automatic)

    def test_technician_engineering_capacity_and_trapfinding_are_live(self) -> None:
        character, _class_level = self._character_with_class("technician")
        self.repository.update_ability_score(character, "intelligence", 20)
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"intelligence": 5}) for resource in module.resources}
        self.assertEqual(15, resources["gadgets"].maximum)
        self.assertEqual(25, resources["gadget_save_dc"].maximum)
        self.assertEqual(6, resources["inventions"].maximum)
        self.assertEqual(6, resources["danger_sense"].maximum)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(10, slots["technician-technical-insights"].maximum)
        calculator = CharacterCalculationService(self.repository, character)
        # Trapfinding's Perception bonus only applies when searching for traps.
        self.assertEqual(0, calculator.automatic_total("skill:perception"))
        self.assertEqual(10, calculator.automatic_total("skill:disable_device"))
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(16, talents.automatic)

    def test_mageknight_mystic_combat_spellsword_and_magic_progression_are_live(self) -> None:
        character, _class_level = self._character_with_class("mageknight")
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"casting": 4}) for resource in module.resources}
        self.assertEqual(5, resources["resist_magic"].maximum)
        self.assertEqual(10, resources["mystic_defense"].maximum)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        mystic = slots["mageknight-mystic-combat"]
        self.assertEqual(10, mystic.maximum)
        choices = tuple(option.key for option in mystic.options[:2])
        self.repository.save_class_feature_selection(class_choice_selection_record(character, mystic, choices))
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(2, slots["mageknight-spellsword"].maximum)
        self.assertEqual(set(choices), {option.key for option in slots["mageknight-spellsword"].options})
        talents = next(item for item in character_advancement_budgets(self.repository, character) if item.key == "talents")
        self.assertEqual(13, talents.automatic)

    def test_reviewed_archetype_profiles_apply_real_conversions(self) -> None:
        knight = resolve_class_profile(
            class_entry("spheres-class:mageknight"),
            (archetype_entry("spheres-archetype:spheres-class:mageknight:knightknight"),),
        )
        self.assertFalse(bool(knight.casting.get("sphere_progression")))
        self.assertEqual("Adept", knight.advancement["talent_progression"])
        self.assertEqual({"martial"}, set(knight.advancement["talent_kinds"]))
        self.assertEqual("Good", knight.reflex_progression)
        self.assertEqual("Poor", knight.will_progression)
        self.assertIn("intimidate", knight.class_skills)
        self.assertNotIn("spellcraft", knight.class_skills)

        character, class_level = self._character_with_class("striker")
        self.repository.set_class_archetype_keys(character, class_level, ("spheres-archetype:spheres-class:striker:black-powder-brawler",))
        resources = {resource.key: resource for module in resolve_class_feature_modules(self.repository, character, {"constitution": 1, "wisdom": 5}) for resource in module.resources}
        self.assertEqual(11, resources["tension"].maximum)


if __name__ == "__main__":
    unittest.main()

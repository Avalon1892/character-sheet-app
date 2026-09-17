from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.catalogs import DEFAULT_CATALOG
from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
)
from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import audit_archetype, audit_class
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.services.advancement import character_advancement_budgets


TARGETS = {
    "armiger": ("spheres-class:armiger", 9),
    "armorist": ("spheres-class:armorist", 18),
    "incanter": ("spheres-class:incanter", 3),
}


class ArmigerArmoristIncanterPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "classes.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _character_with_class(self, family: str, level: int) -> tuple[int, int]:
        key = TARGETS[family][0]
        entry = class_entry(key)
        character = self.repository.create_character(family.title(), "Spheres")
        class_level = self.repository.add_class_level(
            character,
            str(entry["name"]),
            level,
            str(entry["bab"]),
            str(entry["fort"]),
            str(entry["reflex"]),
            str(entry["will"]),
            key,
            int(entry["hit_die"]),
            level * int(entry["hit_die"]),
        )
        return character, class_level

    def test_three_classes_and_every_owned_archetype_are_fully_automated(self) -> None:
        for family, (key, expected_count) in TARGETS.items():
            package = class_package(key)
            entry = class_entry(key)
            self.assertIsNotNone(package)
            self.assertEqual("fully_automated", audit_class(entry)["status"])
            path = (
                Path(__file__).resolve().parent.parent
                / "app" / "class_packages" / "definitions" / "archetypes"
                / f"{family}.json"
            )
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(expected_count, len(document["entries"]))
            for declared in document["entries"]:
                catalog = archetype_entry(declared["key"])
                self.assertIsNotNone(catalog, declared["key"])
                self.assertEqual(
                    "fully_automated",
                    audit_archetype(catalog)["status"],
                    declared["key"],
                )

    def test_armiger_scaling_and_choices_are_live(self) -> None:
        character, _class_level = self._character_with_class("armiger", 19)
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"wisdom": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(5, resources["customized_weapons"].maximum)
        self.assertEqual(4, resources["enhanced_customization"].maximum)
        choices = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, character)
        }
        self.assertEqual((1, 1), (
            choices["armiger-practitioner-ability"].minimum,
            choices["armiger-practitioner-ability"].maximum,
        ))
        self.assertEqual(9, choices["armiger-prowesses"].maximum)

    def test_armorist_bound_equipment_and_arsenal_progressions_are_live(self) -> None:
        character, _class_level = self._character_with_class("armorist", 19)
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"wisdom": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(4, resources["bound_equipment"].maximum)
        self.assertEqual(10, resources["bound_enhancement"].maximum)
        self.assertEqual(5, resources["armor_training"].maximum)
        arsenal = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "armorist-arsenal-tricks"
        )
        self.assertEqual(9, arsenal.maximum)

    def test_incanter_specializations_enforce_the_five_point_budget(self) -> None:
        character, _class_level = self._character_with_class("incanter", 20)
        slot = next(
            choice for choice in resolve_class_choice_slots(self.repository, character)
            if choice.key == "incanter-specializations"
        )
        self.assertEqual(5, slot.point_budget)
        expensive = tuple(option.key for option in slot.options if option.cost == 3)
        record = class_choice_selection_record(character, slot, expensive)
        self.repository.save_class_feature_selection(record)
        resolved = next(
            choice for choice in resolve_class_choice_slots(self.repository, character)
            if choice.key == "incanter-specializations"
        )
        self.assertEqual(1, len(resolved.selected_options))
        self.assertLessEqual(sum(option.cost for option in resolved.selected_options), 5)
        talents = next(
            budget for budget in character_advancement_budgets(
                self.repository, character
            )
            if budget.key == "talents"
        )
        self.assertEqual(32, talents.automatic)

    def test_frostweaver_replaces_incanter_talent_schedule_and_exposes_choice(self) -> None:
        character, class_level = self._character_with_class("incanter", 20)
        key = "spheres-archetype:spheres-class:incanter:frostweaver"
        self.repository.set_class_archetype_keys(character, class_level, (key,))
        slots = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, character)
        }
        self.assertIn("frostweaver-variant", slots)
        self.assertEqual(6, len(slots["frostweaver-variant"].options))
        talents = next(
            budget for budget in character_advancement_budgets(
                self.repository, character
            )
            if budget.key == "talents"
        )
        self.assertEqual(4, talents.automatic)


if __name__ == "__main__":
    unittest.main()

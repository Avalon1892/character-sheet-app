from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.bonded_companion_rules import bonded_companion_grants
from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
)
from app.class_feature_systems import resolve_class_feature_modules
from app.class_mechanics_audit import audit_archetype, audit_class
from app.class_modifications import resolve_class_profile
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.advancement import character_advancement_budgets
from app.services.character_calculations import CharacterCalculationService


TARGETS = {
    "commander": ("spheres-class:commander", 10),
    "scholar": ("spheres-class:scholar", 9),
    "sentinel": ("spheres-class:sentinel", 9),
}


class CommanderScholarSentinelPackageTests(unittest.TestCase):
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

    def test_three_classes_and_all_archetypes_are_fully_automated(self) -> None:
        for family, (key, expected_count) in TARGETS.items():
            self.assertIsNotNone(class_package(key))
            self.assertEqual("fully_automated", audit_class(class_entry(key))["status"])
            path = (
                Path(__file__).resolve().parent.parent
                / "app" / "class_packages" / "definitions" / "archetypes"
                / f"{family}.json"
            )
            entries = json.loads(path.read_text(encoding="utf-8"))["entries"]
            self.assertEqual(expected_count, len(entries))
            for declared in entries:
                catalog = archetype_entry(declared["key"])
                self.assertIsNotNone(catalog, declared["key"])
                self.assertEqual(
                    "fully_automated", audit_archetype(catalog)["status"],
                    declared["key"],
                )

    def test_commander_uses_higher_mental_modifier_and_exact_choice_schedules(self) -> None:
        character, _class_level = self._character_with_class("commander")
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"charisma": 2, "intelligence": 5}
            )
            for resource in module.resources
        }
        self.assertEqual(5, resources["lingering_commands"].maximum)
        self.assertEqual(3, resources["active_enhanced_tactics"].maximum)
        self.assertEqual(3, resources["group_focus"].maximum)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(10, slots["commander-enhanced-tactics"].maximum)
        self.assertEqual(3, slots["commander-battlefield-specialists"].maximum)
        self.assertEqual(3, slots["commander-logistic-specialties"].maximum)
        talents = next(
            budget for budget in character_advancement_budgets(self.repository, character)
            if budget.key == "talents"
        )
        self.assertEqual(16, talents.automatic)

    def test_scholar_knacks_impositions_and_familiar_grant_are_live(self) -> None:
        character, _class_level = self._character_with_class("scholar")
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"intelligence": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(4, resources["medical_training_attempts"].maximum)
        self.assertEqual(24, resources["flashbang_save_dc"].maximum)
        self.assertEqual(230, resources["flashbang_range"].maximum)
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(10, slots["scholar-knacks"].maximum)
        self.assertEqual(9, slots["scholar-material-impositions"].maximum)
        imposition = slots["scholar-material-impositions"].options[0].key
        self.repository.save_class_feature_selection(
            class_choice_selection_record(
                character, slots["scholar-material-impositions"], (imposition,)
            )
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(1, slots["scholar-mastered-imposition"].maximum)
        self.assertEqual(
            {imposition},
            {option.key for option in slots["scholar-mastered-imposition"].options},
        )
        animal = next(
            option.key for option in slots["scholar-knacks"].options
            if option.name == "Animal Training, Small"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(
                character, slots["scholar-knacks"], (animal,)
            )
        )
        grant = bonded_companion_grants(self.repository, character)
        self.assertIn("familiar", grant)
        self.assertEqual(20, grant["familiar"].level)
        talents = next(
            budget for budget in character_advancement_budgets(self.repository, character)
            if budget.key == "talents"
        )
        self.assertEqual(14, talents.automatic)

    def test_sentinel_resources_substitution_and_challenge_are_live(self) -> None:
        character, class_level = self._character_with_class("sentinel")
        self.repository.update_ability_score(character, "wisdom", 22)
        self.repository.update_ability_score(character, "dexterity", 12)
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"wisdom": 6, "dexterity": 1}
            )
            for resource in module.resources
        }
        self.assertEqual(16, resources["sentinel_reserve"].maximum)
        self.assertEqual(5, resources["dedicated_defense"].maximum)
        self.assertEqual(5, resources["guardian_challenge"].maximum)
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_level, "guardian_challenge", active=True)
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_level, "guard_wall", active=True)
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(5, calculator.automatic_total("attack"))
        self.assertEqual(5, calculator.automatic_total("damage"))
        self.assertEqual(5, calculator.automatic_total("initiative"))
        self.assertEqual(5, calculator.automatic_total("reflex"))
        self.assertEqual(4, calculator.automatic_total("cmd"))
        talents = next(
            budget for budget in character_advancement_budgets(self.repository, character)
            if budget.key == "talents"
        )
        self.assertEqual(21, talents.automatic)

    def test_reviewed_archetype_profile_and_choice_changes_are_applied(self) -> None:
        dreadlord = resolve_class_profile(
            class_entry("spheres-class:commander"),
            (archetype_entry("spheres-archetype:spheres-class:commander:dreadlord"),),
        )
        self.assertIn("knowledge_arcana", dreadlord.class_skills)
        self.assertNotIn("climb", dreadlord.class_skills)
        self.assertEqual({"martial", "magic"}, set(dreadlord.advancement["talent_kinds"]))

        character, class_level = self._character_with_class("sentinel")
        self.repository.set_class_archetype_keys(
            character, class_level,
            ("spheres-archetype:spheres-class:sentinel:paragon",),
        )
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertEqual(
            {"Chaotic", "Evil", "Good", "Lawful"},
            {option.name for option in slots["chosen-alignment"].options},
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
    selected_character_class_skill_names,
)
from app.class_feature_systems import (
    class_feature_extra_damage,
    resolve_class_feature_modules,
)
from app.class_mechanics_audit import audit_archetype, audit_class
from app.class_packages import class_package
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.advancement import character_advancement_budgets


TARGETS = {
    "blacksmith": ("spheres-class:blacksmith", 10),
    "conscript": ("spheres-class:conscript", 0),
    "elementalist": ("spheres-class:elementalist", 17),
}


class BlacksmithConscriptElementalistPackageTests(unittest.TestCase):
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
                    "fully_automated", audit_archetype(catalog)["status"], declared["key"]
                )

    def test_blacksmith_scaling_insights_and_thunderous_damage_are_live(self) -> None:
        character, class_level = self._character_with_class("blacksmith")
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"constitution": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(5, resources["maintenance_allies"].maximum)
        self.assertEqual(4, resources["maintenance"].maximum)
        insights = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "blacksmith-insights"
        )
        self.assertEqual(10, insights.maximum)
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_level, "thunderous_blows", active=True)
        )
        damage = class_feature_extra_damage(self.repository, character)
        self.assertTrue(any(item.dice == "10d6" for item in damage))

    def test_conscript_weighted_specializations_ability_and_skills_are_live(self) -> None:
        character, _class_level = self._character_with_class("conscript")
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        ability = slots["conscript-practitioner-ability"]
        intelligence = next(option.key for option in ability.options if option.name == "Intelligence")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, ability, (intelligence,))
        )
        skills = slots["conscript-extra-class-skills"]
        selected_skills = tuple(option.key for option in skills.options[:3])
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, skills, selected_skills)
        )
        specialization = slots["conscript-specializations"]
        ki = next(option.key for option in specialization.options if option.name == "Ki Cultivator")
        heavy = next(option.key for option in specialization.options if option.cost == 3)
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, specialization, (ki, heavy))
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"wisdom": 0, "intelligence": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(14, resources["ki_pool"].maximum)
        self.assertEqual(3, len(selected_character_class_skill_names(self.repository, character)))
        feats = next(
            budget for budget in character_advancement_budgets(self.repository, character)
            if budget.key == "feats"
        )
        self.assertEqual(10, feats.automatic)

    def test_elementalist_progressions_and_reviewed_archetype_choices_are_live(self) -> None:
        character, class_level = self._character_with_class("elementalist")
        talents = next(
            budget for budget in character_advancement_budgets(self.repository, character)
            if budget.key == "talents"
        )
        self.assertEqual(18, talents.automatic)
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"intelligence": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(20, resources["elemental_resistance"].maximum)
        self.assertEqual(3, resources["elemental_movement"].maximum_choices)

        twinsoul = "spheres-archetype:spheres-class:elementalist:twinsoul-elementalist"
        self.repository.set_class_archetype_keys(character, class_level, (twinsoul,))
        slots = {slot.key: slot for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertIn("twinsoul-elemental-conduit", slots)
        talents = next(
            budget for budget in character_advancement_budgets(self.repository, character)
            if budget.key == "talents"
        )
        self.assertEqual(19, talents.automatic)


if __name__ == "__main__":
    unittest.main()

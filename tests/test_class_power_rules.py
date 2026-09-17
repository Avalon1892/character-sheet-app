from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.class_choice_rules import class_choice_selection_record, resolve_class_choice_slots
from app.class_power_rules import (
    class_power_reference_values,
    class_power_selection_record,
    projected_class_power_features,
    resolve_class_power_sets,
)
from app.database import CharacterRepository


class ClassPowerRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character = self.repository.create_character("Powers", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close(); self.directory.cleanup()

    def add_class(self, name: str, key: str, level: int) -> int:
        return self.repository.add_class_level(
            self.character, name, level, "Full", "Good", "Good", "Good", key, 10, 50
        )

    def test_unchained_monk_uses_level_gated_ordered_ki_slots(self) -> None:
        self.add_class("Monk (Unchained)", "pathfinder-class:monk-unchained", 8)
        power_set = resolve_class_power_sets(self.repository, self.character)[0]
        self.assertEqual("unchained-monk-ki-powers", power_set.key)
        self.assertEqual((4, 6, 8), power_set.slot_levels)
        abundant = next(option for option in power_set.options if option.name == "Abundant Step")
        diamond_mind = next(option for option in power_set.options if option.name == "Diamond Mind")
        high_jump = next(option for option in power_set.options if option.name == "High Jump")
        self.assertIn(abundant.key, power_set.unavailable_reasons)
        self.assertEqual(6, diamond_mind.minimum_level)
        self.repository.save_class_feature_selection(
            class_power_selection_record(
                self.character, power_set,
                (high_jump.key, diamond_mind.key, abundant.key),
            )
        )
        resolved = resolve_class_power_sets(self.repository, self.character)[0]
        self.assertEqual((high_jump.key, diamond_mind.key, abundant.key), resolved.selected_keys)
        self.assertEqual([4, 6, 8], [row[1] for row in projected_class_power_features((resolved,))])

    def test_barbarian_archetype_removes_only_exchanged_rage_power_slots(self) -> None:
        class_id = self.add_class("Barbarian", "pathfinder-class:barbarian", 12)
        self.repository.set_class_archetype_keys(
            self.character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:barbarian:beastkin-berserker",),
        )
        power_set = resolve_class_power_sets(self.repository, self.character)[0]
        self.assertEqual((2, 6, 10), power_set.slot_levels)

    def test_oracle_revelations_follow_the_selected_mystery(self) -> None:
        self.add_class("Oracle", "pathfinder-class:oracle", 7)
        self.assertEqual((), resolve_class_power_sets(self.repository, self.character))
        mystery = next(
            slot for slot in resolve_class_choice_slots(self.repository, self.character)
            if slot.key == "oracle-mystery"
        )
        flame = next(option for option in mystery.options if option.name == "Flame Mystery")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(self.character, mystery, (flame.key,))
        )
        power_set = resolve_class_power_sets(self.repository, self.character)[0]
        self.assertEqual((1, 3, 7), power_set.slot_levels)
        self.assertEqual({"Flame"}, {option.category for option in power_set.options})
        touch = next(option for option in power_set.options if option.name == "Touch of Flame")
        self.repository.save_class_feature_selection(
            class_power_selection_record(self.character, power_set, (touch.key,))
        )
        resolved = resolve_class_power_sets(self.repository, self.character)[0]
        references = class_power_reference_values((resolved,))
        prefix = "class_power.oracle.oracle_revelations"
        self.assertEqual(1, references[f"{prefix}.count"])
        self.assertTrue(references[f"{prefix}.touch_of_flame"])

    def test_occultist_and_vigilante_catalogs_are_complete_and_use_native_slots(self) -> None:
        occultist = self.repository.create_character("Occultist", "Pathfinder 1e")
        self.repository.add_class_level(
            occultist, "Occultist", 19, "3/4", "Good", "Poor", "Good",
            "pathfinder-class:occultist", 8, 100,
        )
        focus = next(
            item for item in resolve_class_power_sets(self.repository, occultist)
            if item.key == "occultist-focus-powers"
        )
        self.assertEqual(53, len(focus.options))
        self.assertEqual((1, *tuple(range(3, 20, 2))), focus.slot_levels)
        self.assertIn("Aegis", {option.name for option in focus.options})

        vigilante = self.repository.create_character("Vigilante", "Pathfinder 1e")
        self.repository.add_class_level(
            vigilante, "Vigilante", 20, "3/4", "Poor", "Good", "Good",
            "pathfinder-class:vigilante", 8, 120,
        )
        sets = {
            item.key: item for item in resolve_class_power_sets(self.repository, vigilante)
        }
        self.assertEqual(tuple(range(2, 21, 2)), sets["vigilante-talents"].slot_levels)
        self.assertEqual(tuple(range(1, 20, 2)), sets["vigilante-social-talents"].slot_levels)
        self.assertEqual(82, len(sets["vigilante-talents"].options))
        self.assertEqual(46, len(sets["vigilante-social-talents"].options))
        self.assertIn("Swamp Concoctions", {option.name for option in sets["vigilante-talents"].options})
        self.assertIn("Renown", {option.name for option in sets["vigilante-social-talents"].options})


if __name__ == "__main__":
    unittest.main()

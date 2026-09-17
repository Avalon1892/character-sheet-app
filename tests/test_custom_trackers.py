from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.custom_trackers import CustomTrackerResolver
from app.database import CharacterRepository
from app.transfer import export_character, import_character


class CustomTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.root.name) / "characters.db")
        self.character_id = self.repository.create_character("Formula Monk", "Pathfinder 1e")
        self.repository.add_class_level(
            self.character_id, "Monk", 8, "3/4", "Good", "Good", "Good",
            preset_key="monk", hit_die=8, hp_gained=43,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_pool_counter_and_calculated_values_persist_and_resolve(self) -> None:
        pool_id = self.repository.add_custom_tracker(
            self.character_id,
            "spell_points",
            "Spell Points",
            "pool",
            formula="floor(classes.monk.level / 3)",
            current_value=1,
            unit="SP",
            recovery_event="full_rest",
            recovery_operation="set_to_max",
        )
        self.repository.add_custom_tracker(
            self.character_id,
            "reserve",
            "Reserve",
            "calculated",
            formula="trackers.spell_points.maximum + abilities.wisdom.modifier",
        )
        resolved = {item.tracker.key: item for item in CustomTrackerResolver(
            self.repository, self.character_id
        ).resolve_all()}
        self.assertEqual(2, resolved["spell_points"].maximum)
        self.assertEqual(1, resolved["spell_points"].value)
        self.assertEqual(2, resolved["reserve"].value)
        self.repository.update_custom_tracker(
            self.character_id, pool_id, "spell_points", "Spell Points", "pool",
            "floor(classes.monk.level / 2)", 0, 3, 0, "SP", "House-rule pool",
            "full_rest", "set_to_max",
        )
        self.assertEqual(4, CustomTrackerResolver(
            self.repository, self.character_id
        ).resolve_all()[0].maximum)

    def test_cycles_and_unknown_references_are_visible_errors(self) -> None:
        self.repository.add_custom_tracker(
            self.character_id, "first", "First", "calculated",
            formula="trackers.second.value + 1",
        )
        self.repository.add_custom_tracker(
            self.character_id, "second", "Second", "calculated",
            formula="trackers.first.value + 1",
        )
        self.repository.add_custom_tracker(
            self.character_id, "unknown", "Unknown", "calculated",
            formula="campaign.mythic_rank + 1",
        )
        resolved = CustomTrackerResolver(self.repository, self.character_id).resolve_all()
        self.assertTrue(all(item.error for item in resolved))
        self.assertTrue(any("Circular" in item.error for item in resolved))
        self.assertTrue(any("Unknown value" in item.error for item in resolved))

    def test_invalid_keys_duplicate_keys_and_unsafe_formulas_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.add_custom_tracker(
                self.character_id, "bad key", "Bad", "counter", manual_maximum=3
            )
        self.repository.add_custom_tracker(
            self.character_id, "uses", "Uses", "counter", manual_maximum=3
        )
        with self.assertRaises(ValueError):
            self.repository.add_custom_tracker(
                self.character_id, "uses", "Again", "counter", manual_maximum=3
            )
        with self.assertRaises(ValueError):
            self.repository.add_custom_tracker(
                self.character_id, "unsafe", "Unsafe", "calculated",
                formula="__import__('os')",
            )

    def test_trackers_round_trip_with_character_exports(self) -> None:
        self.repository.add_custom_tracker(
            self.character_id, "spell_points", "Spell Points", "pool",
            formula="floor(classes.monk.level / 3)", current_value=2,
            recovery_event="full_rest", recovery_operation="set_to_max",
        )
        self.repository.save_rest_preferences(
            self.character_id, {"tracker.spell_points": True, "martial_focus": False}
        )
        path = Path(self.root.name) / "monk.character.json"
        export_character(self.repository, self.character_id, path)
        imported_id = import_character(self.repository, path)
        imported = self.repository.list_custom_trackers(imported_id)
        self.assertEqual(1, len(imported))
        self.assertEqual("spell_points", imported[0].key)
        self.assertEqual("full_rest", imported[0].recovery_event)
        self.assertEqual(
            {"tracker.spell_points": True, "martial_focus": False},
            self.repository.get_rest_preferences(imported_id),
        )


if __name__ == "__main__":
    unittest.main()

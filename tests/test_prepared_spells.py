from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.database import CharacterRepository
from app.prepared_spell_rules import (
    bonus_spell_slots,
    prepared_spell_slots,
    validate_preparation_capacity,
)


class PreparedSpellTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "prepared.db")
        self.character_id = self.repository.create_character("Prepared", "Pathfinder 1e")
        self.class_id = self.repository.add_class_level(
            self.character_id, "Wizard", 5, "1/2", "Poor", "Poor", "Good",
            preset_key="wizard", hit_die=6, hp_gained=18,
        )
        self.fireball_id = self.repository.add_spell(
            self.character_id, "Fireball", system="Prepared", level=3,
            school_or_sphere="Evocation",
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_known_and_custom_preparations_persist_and_reset(self) -> None:
        known_id = self.repository.add_prepared_spell(
            self.character_id, self.class_id, self.fireball_id, prepared_count=2
        )
        self.repository.update_prepared_spell_counts(
            self.character_id, known_id, 2, 1
        )
        self.repository.add_prepared_spell(
            self.character_id, self.class_id, name="Special Fire Spell", level=3,
            prepared_count=1, catalog_key="custom:fire", custom=True,
        )
        rows = self.repository.list_prepared_spells(self.character_id)
        self.assertEqual(2, len(rows))
        self.assertEqual(1, rows[0].remaining)
        self.assertTrue(rows[1].custom)
        self.assertEqual(1, self.repository.reset_prepared_spell_uses(self.character_id))
        self.assertTrue(all(row.used_count == 0 for row in self.repository.list_prepared_spells(self.character_id)))

    def test_non_custom_preparation_must_reference_known_spell(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.add_prepared_spell(
                self.character_id, self.class_id, None, name="Not known", level=1
            )

    def test_deleting_known_spell_removes_its_preparation(self) -> None:
        self.repository.add_prepared_spell(
            self.character_id, self.class_id, self.fireball_id
        )
        self.repository.delete_spell(self.character_id, self.fireball_id)
        self.assertEqual([], self.repository.list_prepared_spells(self.character_id))

    def test_slot_progressions_include_ability_bonus(self) -> None:
        self.assertEqual(1, bonus_spell_slots(4, 3))
        wizard = prepared_spell_slots("wizard", "Wizard", 5, "high", 4)
        self.assertEqual((4, 4, 3, 2), wizard)
        alchemist = prepared_spell_slots("alchemist", "Alchemist", 4, "med", 3)
        self.assertEqual((0, 4, 2), alchemist)
        paladin = prepared_spell_slots("paladin", "Paladin", 4, "low", 3)
        self.assertEqual((0, 1), paladin)

    def test_capacity_validation_blocks_over_preparation(self) -> None:
        with self.assertRaises(ValueError):
            validate_preparation_capacity((3, 2), {1: 3})


if __name__ == "__main__":
    unittest.main()

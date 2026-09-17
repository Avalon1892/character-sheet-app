from __future__ import annotations

import unittest

from app.spontaneous_spell_rules import spontaneous_spell_slots


class SpontaneousSpellRulesTests(unittest.TestCase):
    def test_sixth_level_high_caster_with_ability_modifier_four(self) -> None:
        base, bonus, total = spontaneous_spell_slots(6, "high", 4)
        self.assertEqual((0, 6, 5, 3), base)
        self.assertEqual((0, 1, 1, 1), bonus)
        self.assertEqual((0, 7, 6, 4), total)

    def test_zero_entries_allow_bonus_slots_but_locked_levels_do_not(self) -> None:
        base, bonus, total = spontaneous_spell_slots(4, "low", 4)
        self.assertEqual((0, 0), base)
        self.assertEqual((0, 1), bonus)
        self.assertEqual((0, 1), total)

    def test_cantrips_never_consume_daily_slots(self) -> None:
        for progression in ("high", "med", "low"):
            base, bonus, total = spontaneous_spell_slots(20, progression, 12)
            self.assertEqual((0, 0, 0), (base[0], bonus[0], total[0]))


if __name__ == "__main__":
    unittest.main()

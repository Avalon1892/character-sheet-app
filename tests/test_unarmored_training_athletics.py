from __future__ import annotations

import unittest

from app.models import MartialTalent, SheetEffect, SkillState
from app.rules import martial_talent_modifiers


class UnarmoredTrainingAthleticsTests(unittest.TestCase):
    def test_athletics_allows_higher_acrobatics_ranks_to_replace_bab(self) -> None:
        unarmored = MartialTalent(
            1, "Unarmored Training", "Equipment", enabled=True,
            effects=(SheetEffect("ac", "armor", 3, "unarmored_bab_thirds"),),
        )
        athletics = MartialTalent(2, "Athletics", "Athletics", "Base Sphere")
        skills = {"acrobatics": SkillState("acrobatics", ranks=12)}
        without = martial_talent_modifiers([unarmored], skills, 12, 6, [])
        with_sphere = martial_talent_modifiers(
            [unarmored, athletics], skills, 12, 6, []
        )
        self.assertEqual(5, without["ac"][0].value)
        self.assertEqual(7, with_sphere["ac"][0].value)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.talent_sorting import talent_category_rank, talent_entry_sort_key


class TalentSortingTests(unittest.TestCase):
    def test_logical_category_hierarchy(self) -> None:
        self.assertLess(talent_category_rank("Base Sphere"), talent_category_rank("Talent"))
        self.assertLess(talent_category_rank("Talent"), talent_category_rank("Form Talent"))
        self.assertLess(talent_category_rank("Form Talent"), talent_category_rank("Advanced Talent"))
        self.assertLess(talent_category_rank("Advanced Talent"), talent_category_rank("Drawback"))
        self.assertEqual(talent_category_rank("Advanced Talent"), talent_category_rank("Legendary Talent"))

    def test_entries_are_ordered_by_group_then_sphere_and_name(self) -> None:
        entries = [
            {"name": "Drawback", "sphere": "Warp", "category": "Drawback"},
            {"name": "Advanced", "sphere": "Warp", "category": "Advanced Talent"},
            {"name": "Special", "sphere": "Warp", "category": "Space Talent"},
            {"name": "Regular", "sphere": "Warp", "category": "Talent"},
            {"name": "Warp Sphere", "sphere": "Warp", "category": "Base Sphere"},
        ]
        self.assertEqual(
            ["Warp Sphere", "Regular", "Special", "Advanced", "Drawback"],
            [item["name"] for item in sorted(entries, key=talent_entry_sort_key)],
        )


if __name__ == "__main__":
    unittest.main()

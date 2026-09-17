from __future__ import annotations

import unittest

from app.catalogs import DEFAULT_CATALOG


class PathfinderClassCatalogTests(unittest.TestCase):
    def test_all_playable_class_families_are_present(self) -> None:
        self.assertEqual(44, len(DEFAULT_CATALOG.pathfinder_class_entries()))
        self.assertEqual(
            ("Core Classes", "Base Classes", "Alternate Classes", "Hybrid Classes", "Occult Classes", "Unchained Classes", "Later Classes"),
            DEFAULT_CATALOG.pathfinder_class_categories(),
        )

    def test_npc_classes_are_not_in_playable_catalog(self) -> None:
        names = {entry["name"] for entry in DEFAULT_CATALOG.pathfinder_class_entries()}
        self.assertFalse({"Adept", "Aristocrat", "Commoner", "Expert", "Warrior"} & names)

    def test_class_records_have_rules_and_selection_statistics(self) -> None:
        for entry in DEFAULT_CATALOG.pathfinder_class_entries():
            self.assertTrue(entry["description"])
            self.assertTrue(entry["features"])
            self.assertIn(entry["bab"], {"Full", "3/4", "1/2"})
            self.assertIn(entry["fort"], {"Good", "Poor"})
            self.assertIn(entry["reflex"], {"Good", "Poor"})
            self.assertIn(entry["will"], {"Good", "Poor"})

    def test_class_picker_uses_complete_pathfinder_and_spheres_catalogs(self) -> None:
        selectable = DEFAULT_CATALOG.entries("classes")
        self.assertEqual(102, len(selectable))
        self.assertIn("arcanist", {entry["key"] for entry in selectable})
        self.assertIn("prodigy", {entry["key"] for entry in selectable})

    def test_spheres_class_families_and_rules_are_complete(self) -> None:
        self.assertEqual(58, len(DEFAULT_CATALOG.spheres_class_entries()))
        self.assertEqual(
            (
                "Spherecasters",
                "Practitioners",
                "Operatives",
                "Champions",
                "Prestige Classes",
            ),
            DEFAULT_CATALOG.spheres_class_categories(),
        )
        for entry in DEFAULT_CATALOG.spheres_class_entries():
            self.assertTrue(entry["description"], entry["name"])
            self.assertTrue(entry["rules_text"], entry["name"])
            self.assertTrue(entry["source_url"], entry["name"])
            self.assertIn(entry["bab"], {"Full", "3/4", "1/2"})


if __name__ == "__main__":
    unittest.main()

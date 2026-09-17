from __future__ import annotations

import unittest

from app.catalogs import DEFAULT_CATALOG


class ItemCatalogTests(unittest.TestCase):
    def test_catalog_keeps_pathfinder_and_spheres_separate(self) -> None:
        self.assertEqual(("Pathfinder", "Spheres"), DEFAULT_CATALOG.item_sources())
        self.assertGreater(len(DEFAULT_CATALOG.item_entries("Pathfinder")), 1500)
        self.assertGreater(len(DEFAULT_CATALOG.item_entries("Spheres")), 500)

    def test_catalog_has_expected_ruleset_specific_families(self) -> None:
        pathfinder = set(DEFAULT_CATALOG.item_families("Pathfinder"))
        spheres = set(DEFAULT_CATALOG.item_families("Spheres"))
        self.assertTrue({"Armor & Shields", "Weapons & Ammunition", "Technology"} <= pathfinder)
        self.assertTrue({"Implements", "Apparatuses", "Spell Engines", "Talent Crystals"} <= spheres)

    def test_every_item_has_stable_identity_and_codex_categories(self) -> None:
        entries = DEFAULT_CATALOG.item_entries()
        keys = [entry["key"] for entry in entries]
        self.assertEqual(len(keys), len(set(keys)))
        for entry in entries:
            self.assertTrue(entry["name"])
            self.assertTrue(entry["source_group"])
            self.assertTrue(entry["family"])
            self.assertTrue(entry["category"])


if __name__ == "__main__":
    unittest.main()

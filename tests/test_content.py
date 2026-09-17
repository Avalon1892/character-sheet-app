import unittest

from app.content import (
    entries,
    entry_by_key,
    feat_categories,
    feat_entries,
    feat_entry,
    magic_entries,
    magic_sphere,
    magic_spheres,
    martial_entries,
    martial_sphere,
    martial_spheres,
    trait_categories,
    trait_entries,
    trait_entry,
    trait_sources,
)


class ContentCatalogTests(unittest.TestCase):
    def test_core_catalog_counts_and_keys(self) -> None:
        self.assertEqual(77, len(entries("races")))
        self.assertEqual(102, len(entries("classes")))
        self.assertGreaterEqual(len(entries("armor")), 18)
        self.assertGreaterEqual(len(entries("weapons")), 12)
        self.assertEqual(10, entry_by_key("classes", "fighter")["hit_die"])
        prodigy = entry_by_key("classes", "prodigy")
        self.assertEqual((8, "3/4", "Poor", "Good", "Good"), (
            prodigy["hit_die"], prodigy["bab"], prodigy["fort"],
            prodigy["reflex"], prodigy["will"],
        ))
        self.assertEqual(9, entry_by_key("armor", "full_plate")["ac_bonus"])

    def test_martial_catalog_contains_spheres_talents_and_drawbacks(self) -> None:
        self.assertEqual(26, len(martial_spheres()))
        self.assertGreaterEqual(len(martial_entries()), 1600)
        self.assertEqual(155, sum(entry["category"] == "Drawback" for entry in martial_entries()))
        self.assertIsNotNone(martial_sphere("Equipment"))
        athletics = martial_entries("Athletics")
        self.assertTrue(any(entry["category"] == "Base Sphere" for entry in athletics))
        self.assertTrue(any(entry["category"] == "Legendary Talent" for entry in athletics))
        self.assertTrue(all(entry["description"] for entry in athletics))

    def test_magic_catalog_contains_spheres_talents_and_casting_drawbacks(self) -> None:
        self.assertEqual(23, len(magic_spheres()))
        self.assertEqual(1696, len(magic_entries()))
        self.assertEqual(
            158,
            sum(entry["category"] == "Drawback" for entry in magic_entries()),
        )
        self.assertEqual(
            388,
            sum(entry["category"] == "Advanced Talent" for entry in magic_entries()),
        )
        self.assertIsNotNone(magic_sphere("Destruction"))
        destruction = magic_entries("Destruction")
        self.assertTrue(any(entry["category"] == "Base Sphere" for entry in destruction))
        self.assertTrue(any(entry["category"] == "Drawback" for entry in destruction))
        self.assertTrue(any(entry["category"] == "Blast Type Talent" for entry in destruction))
        self.assertTrue(all(entry["description"] for entry in destruction))
        self.assertEqual(
            {
                "Atmospheric Brew", "Limited Weather", "Localized Weather",
                "Personal Mantle", "Small Weather",
            },
            {
                entry["name"] for entry in magic_entries("Weather")
                if entry["category"] == "Drawback"
            },
        )

    def test_feat_catalog_contains_pathfinder_spheres_and_automation(self) -> None:
        self.assertEqual(4669, len(feat_entries()))
        self.assertEqual(3442, len(feat_entries("Pathfinder")))
        self.assertEqual(1227, len(feat_entries("Spheres")))
        self.assertGreaterEqual(len(feat_categories()), 60)
        self.assertEqual(len(feat_entries()), len({entry["key"] for entry in feat_entries()}))
        initiative = feat_entry("aon:improved-initiative")
        self.assertIsNotNone(initiative)
        self.assertEqual(4, initiative["automation"]["effects"][0]["value"])
        self.assertEqual("initiative", initiative["automation"]["effects"][0]["target"])
        extra_talent = feat_entry("spheres:extra-magic-talent")
        self.assertIsNotNone(extra_talent)
        self.assertTrue(extra_talent["full_rules"])
        self.assertTrue(extra_talent["repeatable"])
        self.assertTrue(all(entry["description"] for entry in feat_entries()))

    def test_trait_catalog_contains_pathfinder_and_both_spheres_collections(self) -> None:
        self.assertEqual(2105, len(trait_entries()))
        self.assertEqual(1975, len(trait_entries("Pathfinder")))
        self.assertEqual(110, len(trait_entries("Spheres of Power")))
        self.assertEqual(20, len(trait_entries("Spheres of Might")))
        self.assertEqual(
            ("Pathfinder", "Spheres of Might", "Spheres of Power"),
            trait_sources(),
        )
        self.assertGreaterEqual(len(trait_categories()), 15)
        self.assertEqual(len(trait_entries()), len({entry["key"] for entry in trait_entries()}))
        self.assertEqual(
            433,
            sum(bool(entry["automation"].get("effects")) for entry in trait_entries()),
        )
        reactionary = trait_entry("aon:reactionary")
        self.assertIsNotNone(reactionary)
        self.assertEqual("initiative", reactionary["automation"]["effects"][0]["target"])
        self.assertEqual(2, reactionary["automation"]["effects"][0]["value"])
        self.assertTrue(all(entry["description"] for entry in trait_entries()))

    def test_all_rules_catalogs_report_reviewed_sheet_behavior(self) -> None:
        self.assertEqual(38, sum(bool(entry["automation"].get("effects")) for entry in feat_entries()))
        self.assertEqual(8, sum(bool(entry["automation"].get("effects")) for entry in martial_entries()))
        self.assertEqual(4, sum(bool(entry["automation"].get("effects")) for entry in magic_entries()))


if __name__ == "__main__":
    unittest.main()

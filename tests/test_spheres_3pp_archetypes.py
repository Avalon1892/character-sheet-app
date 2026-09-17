from __future__ import annotations

import unittest

from app.archetype_rules import validate_archetype_selection
from app.catalogs import DEFAULT_CATALOG
from app.class_feature_rules import resolve_class_features


class ThirdPartySpheresArchetypeTests(unittest.TestCase):
    def test_link_only_third_party_archetype_families_are_complete(self) -> None:
        expected = {
            "Dragoon": {"Mech Dragoon", "Spellscale", "Violent Brute"},
            "Kingking": {"Martial Emperor", "Paragon", "Revolutionary", "Traditionalist"},
            "Mountebank": {"Back Alley Grifter", "Mental Manipulator", "Phantom Thief"},
            "Necros": {"Brutal Necromancer", "Necrotech Savant"},
            "Reaper": {
                "Chem Dog", "Disciple of the Monstrous Arts", "Flagellant",
                "Hunt Master", "Machine Cultist", "Magekiller", "Mythos Hunter",
                "Partisan",
            },
        }
        for class_name, names in expected.items():
            with self.subTest(class_name=class_name):
                entries = {
                    entry["name"]: entry
                    for entry in DEFAULT_CATALOG.archetype_entries(source_group="Spheres")
                    if entry["class_name"] == class_name
                }
                self.assertEqual(names, set(entries))
                self.assertTrue(all(entry["description"] for entry in entries.values()))
                self.assertTrue(all(not entry.get("import_warning") for entry in entries.values()))

    def test_necros_replacements_and_alterations_resolve_separately(self) -> None:
        necros = next(
            entry for entry in DEFAULT_CATALOG.class_entries()
            if entry["name"] == "Necros"
        )
        archetypes = {
            entry["name"]: entry
            for entry in DEFAULT_CATALOG.archetype_entries("spheres-class:necros")
        }

        brutal = resolve_class_features(
            necros["features"], (archetypes["Brutal Necromancer"],), 20, "Necros"
        )
        brutal_names = {feature.name.casefold() for feature in brutal}
        self.assertIn("casting", brutal_names)  # altered, not removed
        self.assertIn("fleshcraft", brutal_names)
        self.assertIn("hardened warrior", brutal_names)
        self.assertIn("reduced casting", brutal_names)

        savant = resolve_class_features(
            necros["features"], (archetypes["Necrotech Savant"],), 20, "Necros"
        )
        base_names = {
            feature.name.casefold() for feature in savant if not feature.archetype
        }
        granted_names = {
            feature.name.casefold() for feature in savant if feature.archetype
        }
        self.assertNotIn("channel energy", base_names)
        self.assertNotIn("rebuke undead", base_names)
        self.assertNotIn("fleshcraft", base_names)
        self.assertIn("corpse puppet", base_names)  # only its evolution is altered
        self.assertIn("deathbound", base_names)
        self.assertIn("advanced fleshcraft", base_names)
        self.assertIn("dark gadgets", granted_names)
        self.assertIn("necrograft", granted_names)
        self.assertIn("inventor’s evolution", granted_names)

    def test_necros_archetypes_conflict_when_they_affect_fleshcraft(self) -> None:
        definitions = {
            entry["key"]: entry
            for entry in DEFAULT_CATALOG.archetype_entries("spheres-class:necros")
        }
        result = validate_archetype_selection(definitions, definitions)
        self.assertFalse(result.compatible)
        self.assertTrue(result.conflicts)


if __name__ == "__main__":
    unittest.main()

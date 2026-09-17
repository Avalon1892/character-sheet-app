from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.catalogs import DEFAULT_CATALOG
from app.class_capabilities import resolve_sphere_capabilities
from app.database import CharacterRepository


class ArchetypeCatalogTests(unittest.TestCase):
    def test_complete_catalog_is_grouped_by_parent_class_and_rules_family(self) -> None:
        entries = DEFAULT_CATALOG.archetype_entries()
        self.assertEqual(1830, len(entries))
        self.assertEqual(1275, len(DEFAULT_CATALOG.archetype_entries(source_group="Pathfinder")))
        self.assertEqual(555, len(DEFAULT_CATALOG.archetype_entries(source_group="Spheres")))
        self.assertEqual(8, len(DEFAULT_CATALOG.archetype_entries("prodigy")))
        self.assertEqual(len(entries), len({entry["key"] for entry in entries}))
        self.assertTrue(all(entry["description"] for entry in entries))
        self.assertTrue(all(entry["source_url"] for entry in entries))

    def test_spheres_capabilities_are_structured_for_runtime_resolution(self) -> None:
        runesinger = next(
            entry
            for entry in DEFAULT_CATALOG.archetype_entries("fighter", "Spheres")
            if entry["name"] == "Runesinger"
        )
        self.assertEqual(["martial"], runesinger["sphere_capabilities"]["grants"])
        battle_born = next(
            entry
            for entry in DEFAULT_CATALOG.archetype_entries("prodigy")
            if entry["name"] == "Battle-Born"
        )
        self.assertIn("magic", battle_born["sphere_capabilities"]["removes"])


class ArchetypePersistenceAndResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.root.name) / "characters.db")
        self.character_id = self.repository.create_character("Archetype Hero", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close()
        self.root.cleanup()

    def test_selections_persist_per_class_and_cascade_on_delete(self) -> None:
        class_id = self.repository.add_class_level(
            self.character_id, "Fighter", 5, "Full", "Good", "Poor", "Poor",
            preset_key="fighter", hit_die=10, hp_gained=35,
        )
        keys = (
            "spheres-archetype:pathfinder-class:fighter:runesinger",
            "pathfinder-archetype:pathfinder-class:fighter:archer",
        )
        self.repository.set_class_archetype_keys(self.character_id, class_id, keys)
        self.assertEqual(
            keys, self.repository.list_class_archetype_keys(self.character_id)[class_id]
        )
        self.repository.delete_class_level(self.character_id, class_id)
        self.assertEqual({}, self.repository.list_class_archetype_keys(self.character_id))

    def test_resolver_applies_grants_and_explicit_removals(self) -> None:
        class_id = self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=28,
        )
        battle_born = next(
            entry
            for entry in DEFAULT_CATALOG.archetype_entries("prodigy")
            if entry["name"] == "Battle-Born"
        )
        resolved = resolve_sphere_capabilities(
            self.repository.list_class_levels(self.character_id),
            {class_id: (battle_born["key"],)},
            {battle_born["key"]: battle_born},
        )
        self.assertFalse(resolved.magic)
        self.assertTrue(resolved.martial)
        self.assertTrue(resolved.sequence)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path

from app.database import CharacterRepository
from app.services.class_progression import character_progressions, reference_tables


class ClassProgressionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.repo = CharacterRepository(Path(self.folder.name) / "test.db")
        self.cid = self.repo.create_character("Progression", "Pathfinder 1e")

    def tearDown(self):
        self.repo.close()
        self.folder.cleanup()

    def add(self, key, name):
        return self.repo.add_class_level(self.cid, name, 5, "3/4", "Poor", "Good", "Good", key, 8, 25)

    def test_reference_tables_are_rectangular_and_ordered(self):
        self.assertEqual(102, len(reference_tables()))
        for key, table in reference_tables().items():
            with self.subTest(key=key):
                self.assertTrue(table["source_url"].startswith("https://"))
                self.assertTrue(all(len(row) == len(table["headers"]) for row in table["rows"]))

    def test_multiclass_is_read_only_and_preserves_published_columns(self):
        self.add("pathfinder-class:cleric", "Cleric")
        self.add("prodigy", "Prodigy")
        before = self.repo.sqlite_connection.total_changes
        cleric, prodigy = character_progressions(self.repo, self.cid)
        self.assertEqual(before, self.repo.sqlite_connection.total_changes)
        self.assertEqual(20, len(cleric.rows))
        self.assertEqual("1+1", cleric.rows[0][7])
        self.assertEqual(("Blended Training Talents", "Caster Level"), prodigy.headers[-2:])
        self.assertEqual(("1 (+2 magic)", "0 (1)"), prodigy.rows[0][-2:])

    def test_archetype_removes_original_features_and_casting_columns(self):
        cid = self.add("pathfinder-class:bard", "Bard")
        self.repo.set_class_archetype_keys(self.cid, cid, (
            "spheres-archetype:pathfinder-class:bard:sphere-bard",
            "pathfinder-archetype:pathfinder-class:bard:arcane-duelist"))
        projection = character_progressions(self.repo, self.cid)[0]
        self.assertFalse(any("Spells Per Day" in h for h in projection.headers))
        special = " ".join(r[5] for r in projection.rows)
        self.assertNotIn("Bardic Knowledge", special)
        self.assertNotIn("Bard Spells", special)
        self.assertNotIn("Cantrips", special)
        self.assertIn("Arcane Strike", special)
        self.assertEqual(("Magic Talents", "Caster Level"), projection.headers[-2:])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.catalogs import DEFAULT_CATALOG
from app.class_mechanics_audit import (
    AUTOMATED,
    MISSING,
    audit_archetype,
    audit_class,
    build_audit,
)


class ClassMechanicsAuditTests(unittest.TestCase):
    def test_original_class_and_archetype_catalogs_are_both_complete(self) -> None:
        audit = build_audit(
            DEFAULT_CATALOG.class_entries(), DEFAULT_CATALOG.archetype_entries()
        )
        self.assertEqual(102, audit["summary"]["classes"]["total"])
        self.assertEqual(1830, audit["summary"]["archetypes"]["total"])
        self.assertEqual(
            {"Pathfinder": 44, "Spheres": 58},
            audit["summary"]["classes"]["by_source_group"],
        )

    def test_class_axes_do_not_confuse_documentation_with_runtime_systems(self) -> None:
        row = audit_class(
            {
                "key": "pathfinder-class:test",
                "name": "Test",
                "hit_die": 8,
                "bab": "3/4",
                "fort": "Poor",
                "reflex": "Poor",
                "will": "Good",
                "skill_points": 4,
                "features": [
                    {"level": 1, "name": "Ki Pool", "description": "A pool of ki points."}
                ],
                "weapon_proficiencies": ["simple"],
                "armor_proficiencies": ["lgt"],
                "casting": {"traditional": False},
            }
        )
        axes = {axis["key"]: axis for axis in row["coverage"]}
        self.assertEqual(AUTOMATED, axes["statistics"]["status"])
        self.assertEqual(MISSING, axes["interactive_systems"]["status"])
        self.assertIn("ki_pool", row["missing_interactive_mechanics"])

    def test_declarative_archetype_choices_and_profile_changes_are_automated(self) -> None:
        row = audit_archetype(
            {
                "key": "test-archetype",
                "name": "Test Archetype",
                "class_key": "test-class",
                "class_name": "Test",
                "description": "Complete rules.",
                "removed_features": ["Feature A"],
                "class_modifications": {"statistics": {"hit_die": 10}},
                "choices": [{"key": "path", "options": [{"key": "a", "name": "A"}]}],
                "features": [{"level": 1, "name": "New Feature", "description": "Rules"}],
                "compatibility": {"incompatible_keys": ["other"]},
            }
        )
        axes = {axis["key"]: axis for axis in row["coverage"]}
        self.assertEqual(AUTOMATED, axes["feature_replacements"]["status"])
        self.assertEqual(AUTOMATED, axes["class_profile"]["status"])
        self.assertEqual(AUTOMATED, axes["choices"]["status"])

    def test_audit_rows_keep_stable_keys_and_actionable_gaps(self) -> None:
        row = audit_archetype(
            {
                "key": "test",
                "name": "Choice Archetype",
                "class_key": "base",
                "class_name": "Base",
                "description": "At 1st level, the character must choose one of the following paths.",
            }
        )
        self.assertEqual("test", row["key"])
        self.assertTrue(row["gaps"])
        self.assertEqual(MISSING, {axis["key"]: axis["status"] for axis in row["coverage"]}["choices"])


if __name__ == "__main__":
    unittest.main()

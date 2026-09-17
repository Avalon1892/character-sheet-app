from __future__ import annotations

import unittest

from app.archetype_rules import (
    ArchetypeCompatibilityIndex,
    archetype_compatibility_metadata,
    replaced_features,
    validate_archetype_selection,
)
from app.catalogs import DEFAULT_CATALOG


class ArchetypeCompatibilityTests(unittest.TestCase):
    def test_overlapping_replaced_features_block_stacking(self) -> None:
        entries = {
            entry["key"]: entry
            for entry in DEFAULT_CATALOG.archetype_entries("alchemist")
            if entry["name"] in {"Aerochemist", "Alchemical Sapper"}
        }
        result = validate_archetype_selection(entries, entries)
        self.assertFalse(result.compatible)
        self.assertTrue(result.conflicts)
        self.assertIn("mutagen", set.intersection(*(set(replaced_features(entry)) for entry in entries.values())))

    def test_non_overlapping_archetypes_can_stack(self) -> None:
        definitions = {
            "one": {"name": "One", "replaces": "Bravery"},
            "two": {"name": "Two", "replaces": "Armor Training"},
        }
        self.assertTrue(validate_archetype_selection(definitions, definitions).compatible)

    def test_reusable_index_matches_shared_validator(self) -> None:
        definitions = {
            "one": {"name": "One", "replaces": "Bravery"},
            "two": {"name": "Two", "replaces": "Bravery"},
        }
        indexed = ArchetypeCompatibilityIndex(definitions).validate(("one", "two"))
        direct = validate_archetype_selection(("one", "two"), definitions)
        self.assertEqual(direct, indexed)

    def test_explicit_compatibility_overrides_normal_overlap(self) -> None:
        definitions = {
            "one": {
                "name": "One",
                "replaces": "Bravery",
                "compatibility": {"explicitly_compatible": ["two"]},
            },
            "two": {"name": "Two", "replaces": "Bravery"},
        }
        self.assertTrue(validate_archetype_selection(definitions, definitions).compatible)

    def test_explicit_incompatibility_and_requirements_are_enforced(self) -> None:
        definitions = {
            "one": {
                "name": "One",
                "compatibility": {
                    "explicitly_incompatible": ["two"],
                    "requires": ["three"],
                },
            },
            "two": {"name": "Two"},
            "three": {"name": "Three"},
        }
        result = validate_archetype_selection(("one", "two"), definitions)
        self.assertFalse(result.compatible)
        self.assertTrue(result.conflicts)
        self.assertEqual((("one", "three"),), result.missing_requirements)

    def test_spheres_prose_requirements_support_either_base_archetype(self) -> None:
        definitions = {
            "sphere": {
                "key": "sphere",
                "name": "Sphere Alchemist",
                "description": "This ability replaces alchemy.",
            },
            "champion": {
                "key": "champion",
                "name": "Champion Alchemist",
                "description": "This ability replaces alchemy.",
            },
            "engineer": {
                "key": "engineer",
                "name": "Combat Engineer",
                "description": (
                    "This archetype requires sphere alchemist or champion alchemist. "
                    "This ability replaces alchemy."
                ),
            },
        }
        metadata = archetype_compatibility_metadata(definitions["engineer"], definitions)
        self.assertEqual((("champion", "sphere"),), metadata["requires_any"])
        self.assertFalse(
            validate_archetype_selection(("engineer",), definitions).compatible
        )
        # A required base archetype is an intentional stacking relationship, so
        # its shared replacement does not create a false conflict.
        self.assertTrue(
            validate_archetype_selection(("engineer", "sphere"), definitions).compatible
        )

    def test_spheres_prose_incompatibility_is_enforced(self) -> None:
        definitions = {
            "one": {
                "key": "one",
                "name": "One",
                "description": "This archetype is not compatible with Two.",
            },
            "two": {"key": "two", "name": "Two"},
        }
        result = validate_archetype_selection(("one", "two"), definitions)
        self.assertFalse(result.compatible)
        self.assertTrue(result.conflicts)


if __name__ == "__main__":
    unittest.main()

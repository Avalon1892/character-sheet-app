from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.adaptation_rules import (
    ADAPTATION_SOURCE_KEY,
    adaptation_action_text,
    adaptation_change_cost,
    adaptation_profile,
    projected_adaptation_martial_talents,
    validate_adaptation_entries,
)
from app.class_feature_systems import resolve_class_feature_modules
from app.content import martial_entries, martial_entry
from app.database import CharacterRepository
from app.recovery import FullRestEngine


class ProdigyAdaptationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.folder.name) / "characters.db")
        self.character = self.repository.create_character("Adaptive", "Spheres")
        self.class_id = self.repository.add_class_level(
            self.character,
            "Prodigy",
            5,
            "3/4",
            "Poor",
            "Good",
            "Good",
            preset_key="prodigy",
            hit_die=8,
            hp_gained=30,
        )
        base = martial_entry("boxing:base")
        self.repository.add_martial_talent(
            self.character,
            base["name"],
            base["sphere"],
            "Base Sphere",
            base.get("description", ""),
            catalog_key=base["key"],
            catalog_category="Base Sphere",
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.folder.cleanup()

    @staticmethod
    def _record(entry: dict, kind: str = "martial") -> dict:
        return {
            "talent_kind": kind,
            "catalog_key": entry["key"],
            "name": entry["name"],
            "sphere": entry["sphere"],
            "category": entry["category"],
            "description": entry.get("description", ""),
            "choice": "",
            "choice_key": "",
        }

    def _boxing_talent(self) -> dict:
        return next(
            entry
            for entry in martial_entries("Boxing")
            if entry["category"] not in {"Base Sphere", "Drawback"}
            and "drawback" not in entry["category"].casefold()
        )

    def test_capacity_access_projection_and_action_tiers(self) -> None:
        profile = adaptation_profile(self.repository, self.character)
        self.assertEqual((True, 2, ("martial", "magic")), (
            profile.available, profile.capacity, profile.allowed_kinds
        ))
        talent = self._boxing_talent()
        selections = validate_adaptation_entries(
            self.repository, self.character, (self._record(talent),)
        )
        self.repository.replace_flexible_talent_selections(
            self.character, ADAPTATION_SOURCE_KEY, selections
        )
        projected = projected_adaptation_martial_talents(
            self.repository, self.character
        )
        self.assertEqual([talent["name"]], [item.name for item in projected])
        self.assertEqual("Move action", adaptation_action_text(5, 1))
        self.assertEqual("Standard action", adaptation_action_text(5, 2))

    def test_requires_owned_base_and_cannot_grant_a_base_sphere(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot grant"):
            validate_adaptation_entries(
                self.repository,
                self.character,
                (self._record(martial_entry("athletics:base")),),
            )
        athletics_talent = next(
            entry
            for entry in martial_entries("Athletics")
            if entry["category"] not in {"Base Sphere", "Drawback"}
            and "drawback" not in entry["category"].casefold()
        )
        with self.assertRaisesRegex(ValueError, "Possess the Athletics base sphere"):
            validate_adaptation_entries(
                self.repository, self.character, (self._record(athletics_talent),)
            )

    def test_change_cost_counts_new_or_replaced_slots_but_not_clearing(self) -> None:
        talent = self._boxing_talent()
        selections = validate_adaptation_entries(
            self.repository, self.character, (self._record(talent),)
        )
        self.repository.replace_flexible_talent_selections(
            self.character, ADAPTATION_SOURCE_KEY, selections
        )
        existing = self.repository.list_flexible_talent_selections(
            self.character, ADAPTATION_SOURCE_KEY
        )
        self.assertEqual(0, adaptation_change_cost(existing, selections))
        self.assertEqual(0, adaptation_change_cost(existing, ()))
        another = next(
            entry for entry in martial_entries("Boxing")
            if entry["category"] not in {"Base Sphere", "Drawback"}
            and entry["key"] != talent["key"]
            and "drawback" not in entry["category"].casefold()
        )
        self.assertEqual(1, adaptation_change_cost(existing, (self._record(another),)))

    def test_archetype_access_profiles_and_resource_aliases(self) -> None:
        cases = (
            ("spheres-archetype:prodigy:battle-born", ("martial",), True),
            ("spheres-archetype:prodigy:chromamancer", ("magic",), True),
            ("spheres-archetype:prodigy:mimic", (), False),
        )
        for key, kinds, available in cases:
            with self.subTest(key=key):
                self.repository.set_class_archetype_keys(
                    self.character, self.class_id, (key,)
                )
                profile = adaptation_profile(self.repository, self.character)
                self.assertEqual((available, kinds), (profile.available, profile.allowed_kinds))
                resource_keys = {
                    resource.key
                    for module in resolve_class_feature_modules(
                        self.repository, self.character
                    )
                    for resource in module.resources
                }
                self.assertEqual(available, "adaptation" in resource_keys)

    def test_full_rest_ends_active_adaptation(self) -> None:
        talent = self._boxing_talent()
        selections = validate_adaptation_entries(
            self.repository, self.character, (self._record(talent),)
        )
        self.repository.replace_flexible_talent_selections(
            self.character, ADAPTATION_SOURCE_KEY, selections
        )
        FullRestEngine(self.repository, self.character).perform({
            "class_feature_resources": True
        })
        self.assertEqual([], self.repository.list_flexible_talent_selections(
            self.character, ADAPTATION_SOURCE_KEY
        ))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from app.class_feature_rules import (
    archetype_granted_features,
    base_feature_is_replaced,
    resolve_class_features,
)
from app.content import archetype_entries, class_entry


class ClassFeatureRulesTests(unittest.TestCase):
    def test_complete_replacement_removes_base_and_adds_archetype_feature(self) -> None:
        archetype = next(
            entry for entry in archetype_entries("wizard") if entry["name"] == "Arcane Bomber"
        )
        wizard = class_entry("wizard")
        resolved = resolve_class_features(wizard["features"], (archetype,), 1, "Wizard")
        names = {feature.name for feature in resolved}
        self.assertNotIn("Arcane Bond", names)
        self.assertNotIn("Cantrips", names)
        self.assertIn("Bomb", names)
        self.assertIn("Spellblast Bombs", names)
        self.assertIn("School of the Bomb", names)

    def test_level_scoped_replacement_preserves_overarching_feature(self) -> None:
        feature = {"level": 1, "name": "Bonus Feats (FGT)"}
        archetype = {"replaces": "2nd, 12th-level Bonus Feat"}
        self.assertFalse(base_feature_is_replaced(feature, (archetype,)))

    def test_real_archetype_features_obey_character_level(self) -> None:
        archetype = next(
            entry for entry in archetype_entries("fighter") if entry["name"] == "Aerial Assaulter"
        )
        level_two = archetype_granted_features(archetype, 2)
        names = {feature.name for feature in level_two}
        self.assertIn("Aerial Expertise", names)
        self.assertIn("Take the High Ground", names)
        self.assertNotIn("Aerial Dodge", names)


if __name__ == "__main__":
    unittest.main()

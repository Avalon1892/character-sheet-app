from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.class_feature_rules import (
    archetype_optional_features,
    resolve_class_features,
    resolved_feature_key,
)
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureSelection, SpecialAbilityAdjustment
from app.services.sheet_presentation import build_character_sheet_snapshot


class SheetPresentationFeatureTests(unittest.TestCase):
    def test_projection_applies_optional_choices_and_manual_feature_overlays(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            repository = CharacterRepository(Path(folder) / "characters.db")
            character = repository.create_character("Champion", "Spheres")
            class_level_id = repository.add_class_level(
                character,
                "Inquisitor",
                5,
                "3/4",
                "Good",
                "Poor",
                "Good",
                preset_key="inquisitor",
                hit_die=8,
                hp_gained=32,
            )
            archetype_key = (
                "spheres-archetype:pathfinder-class:inquisitor:champion-inquisitor"
            )
            archetype = archetype_entry(archetype_key)
            option = archetype_optional_features(archetype)[0]
            repository.set_class_archetype_keys(
                character, class_level_id, (archetype_key,)
            )
            repository.save_class_feature_selection(
                ClassFeatureSelection(
                    character,
                    class_level_id,
                    option.key,
                    "Optional Exchange",
                    "enabled",
                    option.name,
                    option.description,
                )
            )
            repository.save_class_feature_selection(
                ClassFeatureSelection(
                    character,
                    class_level_id,
                    "domain",
                    "Domain",
                    "fire",
                    "Fire",
                    "Fire domain rules",
                )
            )

            resolved = resolve_class_features(
                class_entry("inquisitor")["features"],
                (archetype,),
                5,
                "Inquisitor",
                (option.key,),
            )
            greater = next(item for item in resolved if item.name == "Greater Training")
            judgment = next(item for item in resolved if item.name == "Judgment")
            repository.save_special_ability_adjustment(
                SpecialAbilityAdjustment(
                    0,
                    character,
                    resolved_feature_key(class_level_id, greater),
                    2,
                    "Personal Greater Training",
                    "Campaign-adjusted rules",
                )
            )
            repository.save_special_ability_adjustment(
                SpecialAbilityAdjustment(
                    0,
                    character,
                    resolved_feature_key(class_level_id, judgment),
                    1,
                    judgment.name,
                    judgment.description,
                    hidden=True,
                )
            )
            repository.save_special_ability_adjustment(
                SpecialAbilityAdjustment(
                    0,
                    character,
                    "custom:champion:test",
                    3,
                    "Campaign Gift",
                    "A manually added feature",
                    custom=True,
                )
            )

            snapshot = build_character_sheet_snapshot(repository, character)
            by_name = {item.name: item for item in snapshot.class_features}
            self.assertNotIn("Monster Lore", by_name)
            self.assertNotIn("Stern Gaze", by_name)
            self.assertNotIn("Judgment", by_name)
            self.assertNotIn("Greater Training", by_name)
            self.assertNotIn("Optional Exchange — Greater Training", by_name)
            self.assertEqual(
                (2, "Campaign-adjusted rules"),
                (
                    by_name["Personal Greater Training"].level,
                    by_name["Personal Greater Training"].description,
                ),
            )
            self.assertIn("Domain — Fire", by_name)
            self.assertEqual("Custom", by_name["Campaign Gift"].class_name)
            repository.close()


if __name__ == "__main__":
    unittest.main()

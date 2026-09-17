import json
import tempfile
import unittest
from pathlib import Path

from app.database import CharacterRepository
from app.tradition_rules import (
    boon_cost,
    casting_drawback_names,
    casting_tradition_automation,
    drawback_value,
    resolved_tradition_definition,
    spell_point_bonus,
    spell_point_rule_for_unused_drawbacks,
)


class TraditionRulesTests(unittest.TestCase):
    def test_incompatible_energies_replaces_only_msd_level_component(self) -> None:
        tradition = type("Tradition", (), {
            "catalog_key": "",
            "definition_json": json.dumps({
                "drawbacks": [
                    {"name": "Somatic Casting"},
                    {"name": "Incompatible Energies [S&P]"},
                ]
            }),
        })()
        result = casting_tradition_automation(
            [tradition], casting_class_levels=5,
        )
        self.assertEqual(
            ("Somatic Casting", "Incompatible Energies [S&P]"), result.drawbacks
        )
        self.assertEqual(1, len(result.stat_adjustments))
        self.assertEqual("magic_skill_defense", result.stat_adjustments[0].target)
        self.assertEqual(-3, result.stat_adjustments[0].value)
        self.assertTrue(any("successfully dispelled" in note for note in result.reminders))

    def test_drawback_names_merge_legacy_text_without_double_application(self) -> None:
        tradition = type("Tradition", (), {
            "catalog_key": "",
            "definition_json": json.dumps({"drawbacks": "Incompatible Energies, Magical Signs"}),
        })()
        names = casting_drawback_names(
            [tradition], "Incompatible Energies; Verbal Casting x2"
        )
        self.assertEqual(
            ("Incompatible Energies", "Magical Signs", "Verbal Casting"), names
        )

    def test_drawback_boon_balance_and_every_progression_row(self) -> None:
        self.assertEqual(2, drawback_value({"description": "This counts as 2 drawbacks."}))
        self.assertEqual(2, boon_cost({"name": "Easy Focus"}))
        self.assertEqual(3, boon_cost({"name": "Deep Pool (3 drawbacks)"}))
        expected = {0: 0, 1: 2, 2: 3, 3: 3, 4: 5, 5: 6}
        for unused, level_six_bonus in expected.items():
            rule = spell_point_rule_for_unused_drawbacks(unused)
            self.assertEqual(level_six_bonus, spell_point_bonus(rule, 6))

    def test_custom_definition_round_trips_through_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = CharacterRepository(Path(directory) / "characters.db")
            character_id = repository.create_character("Custom Caster", "Spheres")
            definition = {
                "key": "custom-tradition:test",
                "name": "Test Tradition",
                "kind": "Casting",
                "custom": True,
                "spell_point_rule": spell_point_rule_for_unused_drawbacks(2),
                "fixed_grants": [
                    {"kind": "magic", "catalog_key": "warp:base", "name": "Warp Sphere"}
                ],
            }
            repository.add_character_tradition(
                character_id,
                definition["key"],
                definition["name"],
                "Casting",
                definition_json=json.dumps(definition),
            )
            saved = repository.list_character_traditions(character_id)[0]
            self.assertEqual(definition, resolved_tradition_definition(saved))
            repository.close()


if __name__ == "__main__":
    unittest.main()

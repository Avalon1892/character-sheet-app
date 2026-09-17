import tempfile
import unittest
import json
from pathlib import Path

from app.backup import create_database_backup
from app.database import CharacterRepository
from app.models import (
    CastingProfile,
    ClassFeatureState,
    CharacterDetails,
    CurrencyPurse,
    FavoredClassBonus,
    HitPoints,
    MartialFocus,
    MovementProfile,
    ProdigySequence,
    RaceTraitChoice,
    SkillState,
    SphereStatistic,
)
from app.transfer import export_character, import_character


class TransferTests(unittest.TestCase):
    def test_export_reuses_live_database_connection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = CharacterRepository(root / "live-export.db")
            character_id = repository.create_character("Live sheet", "Pathfinder 1e")
            repository.sqlite_connection.execute("BEGIN IMMEDIATE")
            repository.sqlite_connection.execute(
                "UPDATE characters SET name = name WHERE id = ?", (character_id,)
            )

            export_path = root / "live-sheet.character.json"
            export_character(repository, character_id, export_path)

            self.assertTrue(export_path.exists())
            self.assertGreater(export_path.stat().st_size, 0)
            repository.close()

    def test_older_export_without_item_automation_fields_still_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = CharacterRepository(root / "legacy-import.db")
            payload = {
                "format": "character-sheet-app",
                "version": 1,
                "character": {
                    "name": "Legacy export",
                    "character_type": "Pathfinder 1e",
                    "equipment": [{
                        "id": 17, "name": "Traveler's outfit", "category": "Gear",
                        "quantity": 1, "weight": 5, "equipped": False,
                        "ac_bonus": 0, "bonus_type": "untyped",
                        "max_dex_bonus": None, "notes": "old record",
                    }],
                    "attacks": [{
                        "id": 4, "name": "Unarmed", "attack_type": "Melee",
                        "ability": "strength", "attack_bonus": 0,
                        "damage_dice": "1d3", "damage_ability": "strength",
                        "damage_multiplier": 1.0, "damage_bonus": 0,
                        "critical": "20/x2", "notes": "",
                    }],
                },
            }
            path = root / "legacy.character.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            character_id = import_character(repository, path)
            item = repository.list_equipment(character_id)[0]
            self.assertEqual("Traveler's outfit", item.name)
            self.assertEqual("stored", item.state)
            self.assertIsNone(repository.list_attacks(character_id)[0].equipment_id)
            repository.close()

    def test_character_round_trip_and_database_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database_path = root / "characters.db"
            repository = CharacterRepository(database_path)
            original = repository.create_character("Builder", "Pathfinder 1e")
            repository.update_character_details(
                CharacterDetails(
                    original, "Player", "Human", "NG", "", "Medium", "human", "",
                    race_alternate_trait_keys=("race-alt-trait:human:dual-talent",),
                    race_trait_choices=(RaceTraitChoice(
                        "race-alt-trait:human:dual-talent",
                        "ability_scores",
                        ("strength", "dexterity"),
                    ),),
                )
            )
            repository.update_ability_score(original, "strength", 16)
            class_level_id = repository.add_class_level(
                original, "Fighter", 2, "Full", "Good", "Poor", "Poor", "fighter", 10, 16
            )
            repository.update_hit_points(HitPoints(original, 20, 18, 0, 0, True))
            repository.update_favored_class_bonus(
                FavoredClassBonus(original, class_level_id, 1, 1, 0, "")
            )
            repository.update_movement_profile(
                MovementProfile(original, land_speed=35, fly_speed=60, fly_maneuverability="Good")
            )
            armor_id = repository.add_equipment(
                original, "Chain shirt", "Armor", 1, 25, True, 4, "armor", 4, "", 2,
                "Armor", 100, state="armor", enhancement_bonus=1
            )
            repository.add_item_enchantment(
                original,
                armor_id,
                "test:glamoured",
                "Glamoured",
                1,
                "Transfer marker",
            )
            repository.update_currency_purse(
                CurrencyPurse(original, copper=5, silver=4, gold=30, platinum=2)
            )
            repository.add_attack(
                original, "Longsword", "Melee", "strength", 0, "1d8", "strength", 1, 0,
                "19-20/x2", "", equipment_id=armor_id
            )
            repository.update_skill_state(original, SkillState("climb", 2, False, 1, ""))
            repository.add_condition(original, "Shaken")
            repository.add_feat(
                original,
                "Great Fortitude",
                catalog_key="aon:great-fortitude",
                catalog_category="Pathfinder · General",
                source_url="https://aonprd.com/FeatDisplay.aspx?ItemName=Great+Fortitude",
                effects=[
                    {"target": "fortitude", "bonus_type": "untyped", "value": 2}
                ],
            )
            repository.add_trait(original, "Reactionary", "initiative", "trait", 2, "")
            repository.update_martial_focus(
                MartialFocus(original, 0, 2, "Total defense action", "")
            )
            repository.add_martial_talent(
                original,
                "Berserker Sphere",
                "Berserker",
                "Base Sphere",
                "Base rules",
                "berserker:base",
                "Base Sphere",
                "",
                "http://example.test/berserker",
            )
            repository.add_spell(
                original,
                "Teleport",
                "Sphere",
                0,
                "Warp",
                2,
                1,
                "Standard",
                "Close",
                catalog_key="warp:talent:teleport",
                catalog_category="Talent",
                prerequisites="Warp sphere",
                source_url="http://example.test/warp#teleport",
            )
            shield_id = repository.add_spell(
                original, "Shield", system="Prepared", level=1,
                school_or_sphere="Abjuration",
            )
            repository.add_prepared_spell(
                original, class_level_id, shield_id, prepared_count=2, used_count=1
            )
            repository.set_spontaneous_slot_uses(
                original, class_level_id, 2, 1
            )
            repository.update_casting_profile(
                CastingProfile(
                    original,
                    casting_ability="wisdom",
                    casting_class_levels=5,
                    caster_level=4,
                    spell_points_current=8,
                    auto_spell_points=True,
                    tradition_name="Druidic",
                )
            )
            repository.update_sphere_statistic(
                SphereStatistic(original, "Warp", 1, 2, "Focused implement")
            )
            repository.update_prodigy_sequence(
                ProdigySequence(original, True, 3, 5)
            )
            repository.save_class_feature_state(
                ClassFeatureState(
                    original,
                    class_level_id,
                    "judgment",
                    current_value=2,
                    maximum_adjustment=1,
                    active=True,
                    choices_json='["Justice"]',
                    notes="Transfer marker",
                )
            )
            repository.add_sequence_option(
                original, "Attack", "Opener", "Core", 0, "Standard", "Deal damage"
            )
            repository.add_sequence_option(
                original, "Certain Strike", "Finisher", "Core", 3, "Swift", "Touch attack"
            )
            repository.save_character_sheet_layout(
                original, {"freeform": '{"skills":{"x":42}}'}
            )

            export_path = root / "builder.character.json"
            export_character(repository, original, export_path)
            imported = import_character(repository, export_path)

            self.assertEqual(
                {"freeform": '{"skills":{"x":42}}'},
                repository.get_character_sheet_layout(imported),
            )

            imported_details = repository.get_character_details(imported)
            self.assertEqual("human", imported_details.race_key)
            self.assertEqual(("strength", "dexterity"), imported_details.race_trait_choices[0].values)
            self.assertEqual("fighter", repository.list_class_levels(imported)[0].preset_key)
            self.assertEqual(2, repository.list_equipment(imported)[0].armor_check_penalty)
            self.assertEqual("Armor", repository.list_equipment(imported)[0].slot)
            self.assertEqual(100, repository.list_equipment(imported)[0].value_gp)
            self.assertEqual("armor", repository.list_equipment(imported)[0].state)
            self.assertEqual(1, repository.list_equipment(imported)[0].enhancement_bonus)
            imported_enchantments = repository.list_item_enchantments(imported)
            self.assertEqual(1, len(imported_enchantments))
            self.assertEqual("test:glamoured", imported_enchantments[0].key)
            self.assertEqual(
                repository.list_equipment(imported)[0].id,
                imported_enchantments[0].equipment_id,
            )
            self.assertEqual(
                repository.list_equipment(imported)[0].id,
                repository.list_attacks(imported)[0].equipment_id,
            )
            self.assertEqual(30, repository.get_currency_purse(imported).gold)
            self.assertTrue(repository.get_hit_points(imported).auto_calculate)
            imported_class_id = repository.list_class_levels(imported)[0].id
            self.assertEqual(
                1,
                repository.list_favored_class_bonuses(imported)[imported_class_id].hp_bonus,
            )
            self.assertEqual(60, repository.get_movement_profile(imported).fly_speed)
            self.assertEqual("Great Fortitude", repository.list_feats(imported)[0].name)
            self.assertEqual(
                "aon:great-fortitude", repository.list_feats(imported)[0].catalog_key
            )
            self.assertEqual(2, repository.list_feats(imported)[0].effects[0].value)
            self.assertEqual("Reactionary", repository.list_traits(imported)[0].name)
            self.assertEqual(2, repository.get_martial_focus(imported).maximum)
            self.assertEqual("Berserker Sphere", repository.list_martial_talents(imported)[0].name)
            self.assertEqual("berserker:base", repository.list_martial_talents(imported)[0].catalog_key)
            self.assertEqual("Teleport", repository.list_spells(imported)[0].name)
            self.assertEqual(1, repository.list_spells(imported)[0].uses_used)
            self.assertEqual(
                "warp:talent:teleport",
                repository.list_spells(imported)[0].catalog_key,
            )
            self.assertEqual("Talent", repository.list_spells(imported)[0].catalog_category)
            self.assertEqual("Warp sphere", repository.list_spells(imported)[0].prerequisites)
            imported_prepared = repository.list_prepared_spells(imported)
            self.assertEqual(1, len(imported_prepared))
            self.assertEqual("Shield", imported_prepared[0].name)
            self.assertEqual((2, 1), (imported_prepared[0].prepared_count, imported_prepared[0].used_count))
            self.assertEqual(repository.list_class_levels(imported)[0].id, imported_prepared[0].class_level_id)
            imported_spontaneous = repository.list_spontaneous_slot_uses(imported)
            self.assertEqual(1, len(imported_spontaneous))
            self.assertEqual((2, 1), (imported_spontaneous[0].spell_level, imported_spontaneous[0].used_count))
            self.assertEqual(repository.list_class_levels(imported)[0].id, imported_spontaneous[0].class_level_id)
            self.assertEqual("Druidic", repository.get_casting_profile(imported).tradition_name)
            self.assertEqual(2, repository.list_sphere_statistics(imported)[0].dc_bonus)
            self.assertEqual(3, repository.get_prodigy_sequence(imported).current)
            self.assertEqual(5, repository.get_prodigy_sequence(imported).maximum)
            imported_feature_state = repository.list_class_feature_states(imported)[0]
            self.assertEqual(imported_class_id, imported_feature_state.class_level_id)
            self.assertEqual("judgment", imported_feature_state.feature_key)
            self.assertEqual(2, imported_feature_state.current_value)
            self.assertTrue(imported_feature_state.active)
            self.assertEqual('["Justice"]', imported_feature_state.choices_json)
            imported_options = repository.list_sequence_options(imported)
            self.assertEqual(2, len([item for item in imported_options if not item.built_in]))
            self.assertEqual(26, len([item for item in imported_options if item.built_in]))
            repository.close()

            backup = create_database_backup(database_path, keep=2)
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())


if __name__ == "__main__":
    unittest.main()

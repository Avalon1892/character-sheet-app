import tempfile
import unittest
import sqlite3
from pathlib import Path

from app.database import CharacterRepository
from app.models import (
    CastingProfile,
    CharacterDetails,
    CurrencyPurse,
    HitPoints,
    MartialFocus,
    ProdigySequence,
    RaceTraitChoice,
    SkillState,
    SphereStatistic,
)


class CharacterRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temporary_directory.name) / "characters.db"
        self.repository = CharacterRepository(database_path)

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary_directory.cleanup()

    def test_create_and_list_character(self) -> None:
        character_id = self.repository.create_character("Valeros", "Pathfinder 1e")

        characters = self.repository.list_characters()

        self.assertEqual(1, len(characters))
        self.assertEqual(character_id, characters[0].id)
        self.assertEqual("Valeros", characters[0].name)

    def test_character_sheet_layout_is_persisted_and_deleted_with_character(self) -> None:
        character_id = self.repository.create_character("Layout", "Spheres")
        state = {"freeform": '{"skills":{"x":10}}', "colors/skills": "#123456"}
        self.repository.save_character_sheet_layout(character_id, state)
        self.assertEqual(state, self.repository.get_character_sheet_layout(character_id))
        self.repository.delete_character(character_id)
        self.assertEqual({}, self.repository.get_character_sheet_layout(character_id))

    def test_rename_character(self) -> None:
        character_id = self.repository.create_character("Old name", "Spheres")

        self.repository.rename_character(character_id, "New name")

        self.assertEqual("New name", self.repository.list_characters()[0].name)

    def test_delete_character(self) -> None:
        character_id = self.repository.create_character("Temporary", "Pathfinder 1e")

        self.assertTrue(self.repository.character_exists(character_id))

        self.repository.delete_character(character_id)

        self.assertEqual([], self.repository.list_characters())
        self.assertFalse(self.repository.character_exists(character_id))

    def test_blank_name_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repository.create_character("   ", "Pathfinder 1e")

    def test_new_character_receives_six_base_ability_scores(self) -> None:
        character_id = self.repository.create_character("Ezren", "Pathfinder 1e")

        scores = self.repository.get_ability_scores(character_id)

        self.assertEqual(6, len(scores))
        self.assertTrue(all(value == 10 for value in scores.values()))

    def test_ability_score_and_modifiers_persist(self) -> None:
        character_id = self.repository.create_character("Kess", "Spheres")
        self.repository.update_ability_score(character_id, "strength", 16)
        modifier_id = self.repository.add_modifier(
            character_id, "strength", "Magic belt", "enhancement", 2
        )

        self.assertEqual(16, self.repository.get_ability_scores(character_id)["strength"])
        modifiers = self.repository.list_modifiers(character_id, "strength")
        self.assertEqual(modifier_id, modifiers[0].id)
        self.assertEqual(2, modifiers[0].value)

        self.repository.set_modifier_enabled(character_id, modifier_id, False)
        self.assertFalse(self.repository.list_modifiers(character_id, "strength")[0].enabled)

    def test_identity_details_persist(self) -> None:
        character_id = self.repository.create_character("Kyra", "Pathfinder 1e")

        self.repository.update_character_details(
            CharacterDetails(character_id, "Georg", "Human", "NG", "Sarenrae", "Medium")
        )

        details = self.repository.get_character_details(character_id)
        self.assertEqual("Georg", details.player_name)
        self.assertEqual("Human", details.race)
        self.assertEqual("NG", details.alignment)

        preset_details = CharacterDetails(
            character_id, "Georg", "Elf", "NG", "", "Medium", "elf", ""
        )
        self.repository.update_character_details(preset_details)
        self.assertEqual("elf", self.repository.get_character_details(character_id).race_key)

        configured = CharacterDetails(
            character_id, "Georg", "Aasimar", "NG", "", "Medium", "aasimar", "",
            "race-variant:aasimar:angel-blooded-angelkin",
            ("race-alt-trait:aasimar:deathless-spirit",),
            (RaceTraitChoice(
                "race-alt-trait:aasimar:deathless-spirit", "energy", ("positive",)
            ),),
        )
        self.repository.update_character_details(configured)
        loaded = self.repository.get_character_details(character_id)
        self.assertEqual(configured.race_variant_key, loaded.race_variant_key)
        self.assertEqual(configured.race_alternate_trait_keys, loaded.race_alternate_trait_keys)
        self.assertEqual(configured.race_trait_choices, loaded.race_trait_choices)

    def test_class_levels_persist_and_delete(self) -> None:
        character_id = self.repository.create_character("Multiclass", "Spheres")
        class_id = self.repository.add_class_level(
            character_id, "Fighter", 2, "Full", "Good", "Poor", "Poor"
        )

        classes = self.repository.list_class_levels(character_id)
        self.assertEqual(1, len(classes))
        self.assertEqual("Fighter", classes[0].class_name)
        self.assertEqual(2, classes[0].level)

        self.repository.update_class_level(
            character_id,
            class_id,
            "Fighter",
            3,
            "Full",
            "Good",
            "Poor",
            "Poor",
            "fighter",
            10,
            22,
        )
        updated = self.repository.list_class_levels(character_id)[0]
        self.assertEqual("fighter", updated.preset_key)
        self.assertEqual(22, updated.hp_gained)

        self.repository.delete_class_level(character_id, class_id)
        self.assertEqual([], self.repository.list_class_levels(character_id))

    def test_hit_points_persist(self) -> None:
        character_id = self.repository.create_character("Tough", "Pathfinder 1e")

        self.repository.update_hit_points(HitPoints(character_id, 42, 31, 5, 2))

        self.assertEqual(HitPoints(character_id, 42, 31, 5, 2), self.repository.get_hit_points(character_id))

        self.repository.update_hit_points(HitPoints(character_id, 42, 31, 5, 2, True))
        self.assertTrue(self.repository.get_hit_points(character_id).auto_calculate)

    def test_equipment_persists_and_can_be_toggled(self) -> None:
        character_id = self.repository.create_character("Armored", "Pathfinder 1e")
        item_id = self.repository.add_equipment(
            character_id, "Chain shirt", "Armor", 1, 25.0, True, 4, "armor", 4, ""
        )

        item = self.repository.list_equipment(character_id)[0]
        self.assertEqual(item_id, item.id)
        self.assertTrue(item.equipped)
        self.assertEqual(4, item.ac_bonus)

        self.repository.set_equipment_equipped(character_id, item_id, False)
        self.assertFalse(self.repository.list_equipment(character_id)[0].equipped)

        self.repository.update_equipment(
            character_id,
            item_id,
            "Mithral chain shirt",
            "Armor",
            1,
            12.5,
            True,
            4,
            "armor",
            6,
            "lightweight",
            0,
        )
        updated = self.repository.list_equipment(character_id)[0]
        self.assertEqual("Mithral chain shirt", updated.name)
        self.assertEqual(6, updated.max_dex_bonus)

    def test_inventory_slots_values_and_currency_persist(self) -> None:
        character_id = self.repository.create_character("Treasurer", "Spheres")
        self.repository.add_equipment(
            character_id,
            "Belt of Giant Strength",
            "Gear",
            1,
            1.0,
            True,
            0,
            "untyped",
            None,
            "",
            0,
            "Belt",
            4000.0,
        )
        item = self.repository.list_equipment(character_id)[0]
        self.assertEqual("Belt", item.slot)
        self.assertEqual(4000.0, item.value_gp)

        self.repository.update_currency_purse(
            CurrencyPurse(character_id, copper=7, silver=8, gold=90, platinum=2)
        )
        purse = self.repository.get_currency_purse(character_id)
        self.assertEqual(90, purse.gold)
        self.assertEqual(2, purse.platinum)

    def test_casting_profile_and_sphere_adjustments_persist(self) -> None:
        character_id = self.repository.create_character("Incanter", "Spheres")
        self.repository.update_casting_profile(
            CastingProfile(
                character_id,
                casting_ability="intelligence",
                casting_class_levels=7,
                caster_level=7,
                spell_points_current=11,
                auto_spell_points=True,
                tradition_name="Traditional Magic",
                tradition_drawbacks="Somatic, Verbal",
            )
        )
        self.repository.update_sphere_statistic(
            SphereStatistic(character_id, "Destruction", 2, 1, "Implement")
        )

        profile = self.repository.get_casting_profile(character_id)
        self.assertEqual("intelligence", profile.casting_ability)
        self.assertEqual("Traditional Magic", profile.tradition_name)
        statistic = self.repository.list_sphere_statistics(character_id)[0]
        self.assertEqual(2, statistic.caster_level_bonus)
        self.assertEqual(1, statistic.dc_bonus)

    def test_attack_persists_and_deletes(self) -> None:
        character_id = self.repository.create_character("Attacker", "Spheres")
        attack_id = self.repository.add_attack(
            character_id,
            "Longsword",
            "Melee",
            "strength",
            1,
            "1d8",
            "strength",
            1.0,
            0,
            "19-20/x2",
            "masterwork",
        )

        attack = self.repository.list_attacks(character_id)[0]
        self.assertEqual(attack_id, attack.id)
        self.assertEqual("1d8", attack.damage_dice)

        self.repository.delete_attack(character_id, attack_id)
        self.assertEqual([], self.repository.list_attacks(character_id))

    def test_attack_can_be_edited(self) -> None:
        character_id = self.repository.create_character("Archer", "Pathfinder 1e")
        attack_id = self.repository.add_attack(
            character_id, "Bow", "Ranged", "dexterity", 0, "1d8", None, 0.0, 0, "x3", ""
        )

        self.repository.update_attack(
            character_id,
            attack_id,
            "Composite bow",
            "Ranged",
            "dexterity",
            1,
            "1d8",
            "strength",
            1.0,
            0,
            "x3",
            "masterwork",
        )

        updated = self.repository.list_attacks(character_id)[0]
        self.assertEqual("Composite bow", updated.name)
        self.assertEqual(1, updated.attack_bonus)

    def test_skills_and_conditions_persist(self) -> None:
        character_id = self.repository.create_character("Skilled", "Pathfinder 1e")
        self.repository.update_skill_state(
            character_id, SkillState("acrobatics", 3, True, 2, "jumping", "wisdom")
        )
        condition_id = self.repository.add_condition(character_id, "Shaken", "dragon fear")

        skill = self.repository.list_skill_states(character_id)["acrobatics"]
        self.assertEqual(3, skill.ranks)
        self.assertTrue(skill.class_skill)
        self.assertEqual("wisdom", skill.ability_override)
        condition = self.repository.list_conditions(character_id)[0]
        self.assertEqual(condition_id, condition.id)
        self.assertTrue(condition.enabled)

        self.repository.set_condition_enabled(character_id, condition_id, False)
        self.assertFalse(self.repository.list_conditions(character_id)[0].enabled)

        with self.assertRaises(ValueError):
            self.repository.add_condition(character_id, "Shaken")

    def test_custom_feat_persists_edits_and_toggle(self) -> None:
        character_id = self.repository.create_character("Feated", "Pathfinder 1e")
        feat_id = self.repository.add_feat(
            character_id, "Weapon Focus", "attack", "untyped", 1, "longsword"
        )

        feat = self.repository.list_feats(character_id)[0]
        self.assertEqual(feat_id, feat.id)
        self.assertEqual(1, feat.value)

        self.repository.update_feat(
            character_id, feat_id, "Greater Focus", "attack", "competence", 2, "chosen weapon"
        )
        updated = self.repository.list_feats(character_id)[0]
        self.assertEqual("Greater Focus", updated.name)
        self.assertEqual("competence", updated.bonus_type)

        self.repository.set_feat_enabled(character_id, feat_id, False)
        self.assertFalse(self.repository.list_feats(character_id)[0].enabled)
        self.repository.delete_feat(character_id, feat_id)
        self.assertEqual([], self.repository.list_feats(character_id))

    def test_catalog_feats_persist_multiple_effects_choices_and_duplicates(self) -> None:
        character_id = self.repository.create_character("Catalog Hero", "Pathfinder 1e")
        feat_id = self.repository.add_feat(
            character_id,
            "Dodge",
            notes="Gain a +1 dodge bonus to AC.",
            catalog_key="aon:dodge",
            catalog_category="Pathfinder · Combat",
            prerequisites="Dex 13",
            source_url="https://aonprd.com/FeatDisplay.aspx?ItemName=Dodge",
            effects=[
                {"target": "ac", "bonus_type": "dodge", "value": 1},
                {"target": "touch_ac", "bonus_type": "dodge", "value": 1},
            ],
        )
        feat = self.repository.list_feats(character_id)[0]
        self.assertEqual(feat_id, feat.id)
        self.assertEqual("aon:dodge", feat.catalog_key)
        self.assertEqual(2, len(feat.effects))
        self.assertEqual("touch_ac", feat.effects[1].target)
        with self.assertRaises(ValueError):
            self.repository.add_feat(
                character_id,
                "Dodge",
                catalog_key="aon:dodge",
            )

        self.repository.add_feat(
            character_id,
            "Skill Focus",
            catalog_key="aon:skill-focus",
            choice="Perception",
            effects=[
                {
                    "target": "skill:perception",
                    "bonus_type": "untyped",
                    "value": 3,
                    "formula": "rank_scaled_3_6",
                }
            ],
            repeatable=True,
        )
        self.repository.add_feat(
            character_id,
            "Skill Focus",
            catalog_key="aon:skill-focus",
            choice="Stealth",
            effects=[{"target": "skill:stealth", "bonus_type": "untyped", "value": 3}],
            repeatable=True,
        )
        with self.assertRaises(ValueError):
            self.repository.add_feat(
                character_id,
                "Skill Focus",
                catalog_key="aon:skill-focus",
                choice="Perception",
                repeatable=True,
            )

    def test_custom_trait_persists_edits_and_toggle(self) -> None:
        character_id = self.repository.create_character("Traited", "Pathfinder 1e")
        trait_id = self.repository.add_trait(
            character_id, "Reactionary", "initiative", "trait", 2, "quick reflexes"
        )

        trait = self.repository.list_traits(character_id)[0]
        self.assertEqual(trait_id, trait.id)
        self.assertEqual("trait", trait.bonus_type)

        self.repository.update_trait(
            character_id, trait_id, "Focused Mind", "will", "trait", 2, "concentration"
        )
        updated = self.repository.list_traits(character_id)[0]
        self.assertEqual("Focused Mind", updated.name)
        self.assertEqual("will", updated.target)

        self.repository.set_trait_enabled(character_id, trait_id, False)
        self.assertFalse(self.repository.list_traits(character_id)[0].enabled)
        self.repository.delete_trait(character_id, trait_id)
        self.assertEqual([], self.repository.list_traits(character_id))

    def test_martial_focus_and_talents_persist(self) -> None:
        character_id = self.repository.create_character("Conscript", "Spheres")
        self.repository.update_martial_focus(
            MartialFocus(character_id, 0, 2, "Total defense action", "Two-focus talent")
        )
        focus = self.repository.get_martial_focus(character_id)
        self.assertEqual(0, focus.current)
        self.assertEqual(2, focus.maximum)

        talent_id = self.repository.add_martial_talent(
            character_id, "Berserking", "Berserker", "Base Sphere", "Gain battered"
        )
        talent = self.repository.list_martial_talents(character_id)[0]
        self.assertEqual(talent_id, talent.id)
        self.repository.update_martial_talent(
            character_id, talent_id, "Greater Berserking", "Berserker", "Talent", "+2 damage"
        )
        self.assertEqual("Greater Berserking", self.repository.list_martial_talents(character_id)[0].name)
        self.repository.delete_martial_talent(character_id, talent_id)
        self.assertEqual([], self.repository.list_martial_talents(character_id))

        catalog_id = self.repository.add_martial_talent(
            character_id,
            "Berserker Sphere",
            "Berserker",
            "Base Sphere",
            "Base rules",
            "berserker:base",
            "Base Sphere",
            "",
            "http://example.test/berserker",
        )
        catalog_talent = self.repository.list_martial_talents(character_id)[0]
        self.assertEqual(catalog_id, catalog_talent.id)
        self.assertEqual("berserker:base", catalog_talent.catalog_key)
        self.assertEqual("Base Sphere", catalog_talent.catalog_category)
        with self.assertRaises(ValueError):
            self.repository.add_martial_talent(
                character_id,
                "Berserker Sphere",
                "Berserker",
                "Base Sphere",
                "Base rules",
                "berserker:base",
            )

    def test_spells_persist_and_track_uses(self) -> None:
        character_id = self.repository.create_character("Caster", "Spheres")
        spell_id = self.repository.add_spell(
            character_id,
            "Teleport",
            "Sphere",
            0,
            "Warp",
            3,
            0,
            "Standard action",
            "Close",
            "Instantaneous",
            "Will negates",
            "Yes",
            "Spend a spell point",
        )
        self.repository.set_spell_uses_used(character_id, spell_id, 1)
        spell = self.repository.list_spells(character_id)[0]
        self.assertEqual("Warp", spell.school_or_sphere)
        self.assertEqual(1, spell.uses_used)

        self.repository.update_spell(
            character_id,
            spell_id,
            "Greater Teleport",
            "Sphere",
            0,
            "Warp",
            3,
            1,
            "Standard action",
            "Long",
            "Instantaneous",
            "Will negates",
            "Yes",
            "",
        )
        self.assertEqual("Greater Teleport", self.repository.list_spells(character_id)[0].name)
        self.repository.update_spell_duration(
            character_id, spell_id, "Concentration + 1 round/level"
        )
        updated = self.repository.list_spells(character_id)[0]
        self.assertEqual("Concentration + 1 round/level", updated.duration)
        self.assertEqual("Greater Teleport", updated.name)
        self.assertEqual("Warp", updated.school_or_sphere)
        self.repository.delete_spell(character_id, spell_id)
        self.assertEqual([], self.repository.list_spells(character_id))

    def test_magic_catalog_metadata_and_duplicate_prevention(self) -> None:
        character_id = self.repository.create_character("Spherecaster", "Spheres")
        spell_id = self.repository.add_spell(
            character_id,
            "Destruction Sphere",
            "Sphere",
            school_or_sphere="Destruction",
            notes="Base sphere rules",
            catalog_key="destruction:base",
            catalog_category="Base Sphere",
            prerequisites="",
            source_url="http://example.test/destruction",
        )
        spell = self.repository.list_spells(character_id)[0]
        self.assertEqual(spell_id, spell.id)
        self.assertEqual("destruction:base", spell.catalog_key)
        self.assertEqual("Base Sphere", spell.catalog_category)
        self.assertEqual("http://example.test/destruction", spell.source_url)
        with self.assertRaises(ValueError):
            self.repository.add_spell(
                character_id,
                "Destruction Sphere",
                "Sphere",
                school_or_sphere="Destruction",
                catalog_key="destruction:base",
            )

    def test_prodigy_sequence_and_options_persist(self) -> None:
        character_id = self.repository.create_character("Prodigy", "Spheres")
        sequence = self.repository.get_prodigy_sequence(character_id)
        self.assertFalse(sequence.active)
        self.assertEqual(4, sequence.maximum)

        self.repository.update_prodigy_sequence(
            ProdigySequence(character_id, True, 3, 5)
        )
        sequence = self.repository.get_prodigy_sequence(character_id)
        self.assertTrue(sequence.active)
        self.assertEqual(3, sequence.current)

        opener_id = self.repository.add_sequence_option(
            character_id, "Attack", "Opener", "Core", 8, "Standard", "Deal damage"
        )
        finisher_id = self.repository.add_sequence_option(
            character_id, "Certain Strike", "Finisher", "Core", 3, "Swift", "Touch attack"
        )
        opener = next(
            item for item in self.repository.list_sequence_options(character_id, "Opener")
            if item.id == opener_id
        )
        finisher = next(
            item for item in self.repository.list_sequence_options(character_id, "Finisher")
            if item.id == finisher_id
        )
        self.assertEqual(0, opener.minimum_links)
        self.assertEqual(3, finisher.minimum_links)
        self.repository.update_sequence_option(
            character_id, finisher_id, "Certain Strike", "Finisher", "Core", 5, "Swift", "Improved"
        )
        finisher = next(
            item for item in self.repository.list_sequence_options(character_id, "Finisher")
            if item.id == finisher_id
        )
        self.assertEqual(5, finisher.minimum_links)
        self.repository.delete_sequence_option(character_id, opener_id)
        self.repository.delete_sequence_option(character_id, finisher_id)
        remaining = self.repository.list_sequence_options(character_id)
        self.assertTrue(remaining)
        self.assertTrue(all(item.built_in for item in remaining))

    def test_existing_builtin_sequence_descriptions_follow_catalog_updates(self) -> None:
        character_id = self.repository.create_character("Old Prodigy", "Spheres")
        self.repository._connection.execute(
            """
            UPDATE sequence_options
            SET notes = 'Cast sphere effects faster; the available action improves at seven and nine links.'
            WHERE character_id = ? AND name = 'Arcane Apocalypse'
              AND built_in = 1 AND COALESCE(sphere, '') = ''
            """,
            (character_id,),
        )
        self.repository._connection.commit()
        database_path = self.repository.database_path
        self.repository.close()

        self.repository = CharacterRepository(database_path)
        option = next(
            item
            for item in self.repository.list_sequence_options(character_id, "Finisher")
            if item.name == "Arcane Apocalypse" and not item.sphere
        )

        self.assertIn("At 5 links", option.notes)
        self.assertIn("At 9 links", option.notes)
        self.assertNotIn("improves at", option.notes)

    def test_traits_and_sphere_talents_persist_shared_rule_effects(self) -> None:
        character_id = self.repository.create_character("Rules Hero", "Spheres")
        trait_id = self.repository.add_trait(
            character_id,
            "Seeker",
            catalog_key="aon:seeker",
            catalog_category="Pathfinder · Magic",
            source_url="https://aonprd.com/TraitDisplay.aspx?ItemName=Seeker",
            effects=(
                {"target": "skill:perception", "bonus_type": "trait", "value": 1},
                {"target": "skill:perception", "formula": "class_skill"},
            ),
        )
        trait = self.repository.list_traits(character_id)[0]
        self.assertEqual(trait_id, trait.id)
        self.assertEqual("aon:seeker", trait.catalog_key)
        self.assertEqual("class_skill", trait.effects[1].formula)
        with self.assertRaises(ValueError):
            self.repository.add_trait(
                character_id, "Seeker", catalog_key="aon:seeker"
            )

        talent_id = self.repository.add_martial_talent(
            character_id,
            "Unarmored Training",
            "Equipment",
            effects=(
                {
                    "target": "ac",
                    "bonus_type": "armor",
                    "value": 3,
                    "formula": "unarmored_bab_thirds",
                },
            ),
            activation="toggle",
        )
        self.repository.set_martial_talent_enabled(character_id, talent_id, False)
        talent = self.repository.list_martial_talents(character_id)[0]
        self.assertFalse(talent.enabled)
        self.assertEqual("toggle", talent.activation)
        self.assertEqual("unarmored_bab_thirds", talent.effects[0].formula)

        spell_id = self.repository.add_spell(
            character_id,
            "Resolve (mandate)",
            "Sphere",
            school_or_sphere="War",
            effects=({"target": "will", "bonus_type": "morale", "value": 4},),
            activation="toggle",
        )
        self.repository.set_spell_enabled(character_id, spell_id, False)
        spell = self.repository.list_spells(character_id)[0]
        self.assertFalse(spell.enabled)
        self.assertEqual(4, spell.effects[0].value)

    def test_previous_equipment_schema_migrates_armor_check_penalty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    character_type TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
                    name TEXT NOT NULL, category TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 1,
                    weight REAL NOT NULL DEFAULT 0, equipped INTEGER NOT NULL DEFAULT 0,
                    ac_bonus INTEGER NOT NULL DEFAULT 0, bonus_type TEXT NOT NULL DEFAULT 'untyped',
                    max_dex_bonus INTEGER, notes TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE hit_points (
                    character_id INTEGER PRIMARY KEY, maximum INTEGER NOT NULL DEFAULT 0,
                    current INTEGER NOT NULL DEFAULT 0, temporary INTEGER NOT NULL DEFAULT 0,
                    nonlethal INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE character_details (
                    character_id INTEGER PRIMARY KEY, player_name TEXT NOT NULL DEFAULT '',
                    race TEXT NOT NULL DEFAULT '', alignment TEXT NOT NULL DEFAULT '',
                    deity TEXT NOT NULL DEFAULT '', size TEXT NOT NULL DEFAULT 'Medium'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE class_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, character_id INTEGER NOT NULL,
                    class_name TEXT NOT NULL, level INTEGER NOT NULL, bab_progression TEXT NOT NULL,
                    fort_progression TEXT NOT NULL, reflex_progression TEXT NOT NULL,
                    will_progression TEXT NOT NULL
                )
                """
            )
            connection.commit()
            connection.close()

            repository = CharacterRepository(database_path)
            character_id = repository.create_character("Legacy", "Pathfinder 1e")
            repository.add_equipment(
                character_id, "Old armor", "Armor", 1, 20, True, 4, "armor", 4, "", 3
            )
            migrated_item = repository.list_equipment(character_id)[0]
            self.assertEqual(3, migrated_item.armor_check_penalty)
            self.assertEqual("armor", migrated_item.state)
            self.assertEqual("{}", migrated_item.choices_json)
            self.assertEqual(0, migrated_item.enhancement_bonus)
            repository.update_character_details(
                CharacterDetails(character_id, race="Elf", size="Medium", race_key="elf")
            )
            repository.add_class_level(
                character_id, "Wizard", 1, "1/2", "Poor", "Poor", "Good", "wizard", 6, 6
            )
            repository.update_hit_points(HitPoints(character_id, 6, 6, 0, 0, True))
            self.assertEqual("elf", repository.get_character_details(character_id).race_key)
            self.assertEqual("wizard", repository.list_class_levels(character_id)[0].preset_key)
            self.assertTrue(repository.get_hit_points(character_id).auto_calculate)
            repository.close()



if __name__ == "__main__":
    unittest.main()

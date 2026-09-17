import unittest
import random

from app.models import (
    SKILLS,
    Attack,
    CastingProfile,
    ClassLevel,
    Condition,
    CharacterDetails,
    EquipmentItem,
    Feat,
    FeatEffect,
    MartialTalent,
    Spell,
    Trait,
    SkillState,
    StatModifier,
)
from app.rules import (
    SpellPointContribution,
    calculate_ability,
    calculate_casting_statistics,
    calculate_spell_point_pool,
    automatic_class_skills,
    automatic_class_casting,
    automatic_hit_points,
    calculate_combat_statistics,
    calculate_attack,
    calculate_skill,
    carrying_capacity,
    condition_modifiers,
    effect_class_skills,
    effect_untrained_skills,
    feat_modifiers,
    feat_attack_modifiers,
    magic_talent_modifiers,
    martial_talent_modifiers,
    trait_modifiers,
    parse_dice,
    prodigy_adaptation_uses,
    prodigy_caster_level,
    prodigy_inspired_sequence_bonus,
    prodigy_level,
    prodigy_sequence_maximum,
    roll_attack_and_damage,
    race_modifiers,
    recommended_hit_points,
    score_to_modifier,
    total_bab,
    total_base_save,
    total_armor_check_penalty,
)


def modifier(source: str, bonus_type: str, value: int, enabled: bool = True) -> StatModifier:
    return StatModifier(None, "strength", source, bonus_type, value, enabled)


class AbilityRulesTests(unittest.TestCase):
    def test_score_to_modifier_uses_pathfinder_rounding(self) -> None:
        self.assertEqual(-1, score_to_modifier(9))
        self.assertEqual(0, score_to_modifier(10))
        self.assertEqual(0, score_to_modifier(11))
        self.assertEqual(4, score_to_modifier(18))

    def test_carrying_capacity_scales_with_strength_and_size(self) -> None:
        medium = carrying_capacity(10, "Medium")
        small = carrying_capacity(10, "Small")
        mighty = carrying_capacity(30, "Medium")

        self.assertEqual((33, 66, 100), (medium.light, medium.medium, medium.heavy))
        self.assertEqual(75, small.heavy)
        self.assertEqual(1600, mighty.heavy)
        self.assertEqual("Medium", medium.load_for(50))
        self.assertEqual("Overloaded", medium.load_for(101))

    def test_sphere_casting_statistics_follow_profile_and_adjustments(self) -> None:
        profile = CastingProfile(
            1,
            casting_ability="intelligence",
            casting_class_levels=7,
            caster_level=8,
            msb_misc=1,
            dc_misc=1,
            concentration_misc=2,
            auto_spell_points=True,
        )

        result = calculate_casting_statistics(profile, 4, caster_level_bonus=2, dc_bonus=1)

        self.assertEqual(10, result.caster_level)
        self.assertEqual(21, result.save_dc)
        self.assertEqual(8, result.magic_skill_bonus)
        self.assertEqual(19, result.magic_skill_defense)
        self.assertEqual(14, result.concentration_bonus)
        self.assertEqual(11, result.spell_points_maximum)

    def test_spell_point_pool_accepts_modular_future_sources(self) -> None:
        profile = CastingProfile(
            1,
            casting_class_levels=5,
            spell_points_misc=2,
            auto_spell_points=True,
        )
        maximum, sources = calculate_spell_point_pool(
            profile,
            3,
            (SpellPointContribution("Casting tradition", 1, "Future provider"),),
        )
        self.assertEqual(11, maximum)
        self.assertEqual(
            ["Casting-class levels", "Casting ability modifier", "Other adjustment", "Casting tradition"],
            [source.source for source in sources],
        )

    def test_automatic_spell_point_pool_has_a_minimum_of_one(self) -> None:
        profile = CastingProfile(
            1, casting_class_levels=0, spell_points_misc=-5, auto_spell_points=True
        )
        maximum, sources = calculate_spell_point_pool(profile, -2)
        self.assertEqual(1, maximum)
        self.assertEqual("Minimum pool", sources[-1].source)

    def test_prodigy_level_drives_class_progressions(self) -> None:
        classes = [
            ClassLevel(1, "Prodigy (Exploitant)", 5, "3/4", "Poor", "Good", "Good")
        ]
        self.assertEqual(5, prodigy_level(classes))
        self.assertEqual(3, prodigy_caster_level(5))
        self.assertEqual(5, prodigy_sequence_maximum(5))
        self.assertEqual(5, prodigy_adaptation_uses(5))
        self.assertEqual(1, prodigy_inspired_sequence_bonus(5, 3, True))
        self.assertEqual(2, prodigy_inspired_sequence_bonus(5, 4, True))

    def test_pathfinder_caster_level_uses_class_rules_and_delayed_offsets(self) -> None:
        definitions = {
            "wizard": {"casting": {"ability": "int", "progression": "high", "caster_level_offset": 0}},
            "paladin": {"casting": {"ability": "cha", "progression": "low", "caster_level_offset": -3}},
            "fighter": {"casting": {}},
        }
        wizard = ClassLevel(1, "Wizard", 7, "1/2", "Poor", "Poor", "Good", preset_key="wizard")
        paladin = ClassLevel(2, "Paladin", 5, "Full", "Good", "Poor", "Good", preset_key="paladin")
        fighter = ClassLevel(3, "Fighter", 10, "Full", "Good", "Poor", "Poor", preset_key="fighter")
        self.assertEqual((7, 7, "Wizard"), automatic_class_casting([wizard], definitions))
        self.assertEqual((5, 2, "Paladin"), automatic_class_casting([paladin], definitions))
        self.assertEqual((7, 7, "Wizard"), automatic_class_casting([wizard, paladin, fighter], definitions))
        self.assertIsNone(automatic_class_casting([fighter], definitions))

    def test_only_highest_typed_positive_bonus_applies(self) -> None:
        result = calculate_ability(
            14,
            [
                modifier("Lesser belt", "enhancement", 2),
                modifier("Greater belt", "enhancement", 4),
            ],
        )

        self.assertEqual(18, result.total)
        self.assertFalse(result.contributions[1].applied)
        self.assertTrue(result.contributions[2].applied)

    def test_untyped_bonuses_and_penalties_stack(self) -> None:
        result = calculate_ability(
            10,
            [
                modifier("Training", "untyped", 1),
                modifier("Custom feature", "untyped", 2),
                modifier("Poison", "enhancement", -3),
            ],
        )

        self.assertEqual(10, result.total)

    def test_race_presets_produce_racial_adjustments(self) -> None:
        dwarf = CharacterDetails(1, race="Dwarf", size="Medium", race_key="dwarf")
        human = CharacterDetails(
            2, race="Human", size="Medium", race_key="human", race_ability_choice="strength"
        )

        self.assertEqual(2, race_modifiers(dwarf)["constitution"][0].value)
        self.assertEqual(-2, race_modifiers(dwarf)["charisma"][0].value)
        self.assertEqual(2, race_modifiers(human)["strength"][0].value)

    def test_recommended_and_automatic_hit_points(self) -> None:
        fighter = ClassLevel(
            1, "Fighter", 2, "Full", "Good", "Poor", "Poor", "fighter", 10, 16
        )

        self.assertEqual(16, recommended_hit_points(10, 2))
        self.assertEqual(20, automatic_hit_points([fighter], 2).total)
        self.assertIn("climb", automatic_class_skills([fighter]))

    def test_disabled_modifier_is_shown_but_not_applied(self) -> None:
        result = calculate_ability(12, [modifier("Inactive buff", "morale", 4, False)])

        self.assertEqual(12, result.total)
        self.assertEqual("Disabled", result.contributions[1].reason)

    def test_multiclass_bab_and_saves_use_each_class_progression(self) -> None:
        classes = [
            ClassLevel(1, "Fighter", 2, "Full", "Good", "Poor", "Poor"),
            ClassLevel(2, "Wizard", 3, "1/2", "Poor", "Poor", "Good"),
        ]

        self.assertEqual(3, total_bab(classes))
        self.assertEqual(4, total_base_save(classes, "fortitude"))
        self.assertEqual(1, total_base_save(classes, "reflex"))
        self.assertEqual(3, total_base_save(classes, "will"))

    def test_combat_statistics_follow_abilities_classes_and_size(self) -> None:
        classes = [ClassLevel(1, "Fighter", 2, "Full", "Good", "Poor", "Poor")]
        abilities = {
            "strength": calculate_ability(16, []),
            "dexterity": calculate_ability(14, []),
            "constitution": calculate_ability(12, []),
            "intelligence": calculate_ability(10, []),
            "wisdom": calculate_ability(10, []),
            "charisma": calculate_ability(8, []),
        }

        results = calculate_combat_statistics("Medium", classes, abilities, {})

        self.assertEqual(2, results["initiative"].total)
        self.assertEqual(4, results["fortitude"].total)
        self.assertEqual(2, results["reflex"].total)
        self.assertEqual(0, results["will"].total)
        self.assertEqual(12, results["ac"].total)
        self.assertEqual(5, results["cmb"].total)
        self.assertEqual(17, results["cmd"].total)

    def test_large_size_changes_ac_and_maneuver_values(self) -> None:
        abilities = {
            key: calculate_ability(10, [])
            for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
        }

        results = calculate_combat_statistics("Large", [], abilities, {})

        self.assertEqual(9, results["ac"].total)
        self.assertEqual(1, results["cmb"].total)
        self.assertEqual(11, results["cmd"].total)

    def test_armor_affects_normal_and_flat_footed_but_not_touch_ac(self) -> None:
        abilities = {
            key: calculate_ability(14 if key == "dexterity" else 10, [])
            for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
        }
        armor = EquipmentItem(1, "Chain shirt", "Armor", 1, 25, True, 4, "armor", 4)

        results = calculate_combat_statistics("Medium", [], abilities, {}, [armor])

        self.assertEqual(16, results["ac"].total)
        self.assertEqual(12, results["touch_ac"].total)
        self.assertEqual(14, results["flat_footed_ac"].total)

    def test_armor_max_dex_limits_ac(self) -> None:
        abilities = {
            key: calculate_ability(18 if key == "dexterity" else 10, [])
            for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
        }
        armor = EquipmentItem(1, "Heavy armor", "Armor", 1, 50, True, 7, "armor", 1)

        results = calculate_combat_statistics("Medium", [], abilities, {}, [armor])

        self.assertEqual(18, results["ac"].total)
        self.assertEqual(11, results["touch_ac"].total)

    def test_attack_and_damage_use_bab_ability_size_and_flat_bonuses(self) -> None:
        abilities = {
            key: calculate_ability(16 if key == "strength" else 10, [])
            for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
        }
        attack = Attack(1, "Sword", "Melee", "strength", 1, "1d8", "strength", 1.5, 2, "20/x2")

        result = calculate_attack(attack, 4, abilities, "Small")

        self.assertEqual(9, result.attack_bonus)
        self.assertEqual(6, result.damage_bonus)
        self.assertEqual("1d8+6", result.damage_display)

    def test_dice_parser_and_seeded_roll(self) -> None:
        self.assertEqual((2, 6), parse_dice("2d6"))
        with self.assertRaises(ValueError):
            parse_dice("sword")

        attack_result = calculate_attack(
            Attack(1, "Dagger", "Melee", "strength", 0, "1d4", None, 0, 2, "20/x2"),
            0,
            {key: calculate_ability(10, []) for key in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")},
            "Medium",
        )
        natural, total, damage, rolls = roll_attack_and_damage(
            attack_result, "1d4", random.Random(7)
        )
        self.assertEqual(natural + attack_result.attack_bonus, total)
        self.assertEqual(sum(rolls) + 2, damage)

    def test_skill_uses_ranks_class_bonus_and_armor_penalty(self) -> None:
        acrobatics = next(skill for skill in SKILLS if skill.key == "acrobatics")
        armor = EquipmentItem(1, "Scale mail", "Armor", 1, 30, True, 5, "armor", 3, 4)
        state = SkillState("acrobatics", 2, True, 1)

        result = calculate_skill(
            acrobatics,
            state,
            calculate_ability(14, []),
            total_armor_check_penalty([armor]),
        )

        self.assertEqual(4, result.total)  # Dex +2, ranks +2, class +3, misc +1, ACP -4
        self.assertTrue(result.usable)

    def test_trained_only_skill_without_ranks_is_unusable(self) -> None:
        spellcraft = next(skill for skill in SKILLS if skill.key == "spellcraft")
        result = calculate_skill(
            spellcraft, SkillState("spellcraft"), calculate_ability(18, []), 0
        )
        self.assertFalse(result.usable)

    def test_enabled_conditions_create_named_modifiers(self) -> None:
        modifiers = condition_modifiers(
            [Condition(1, "Shaken", True), Condition(2, "Sickened", False)]
        )

        self.assertEqual(-2, modifiers["attack"][0].value)
        self.assertEqual("Condition: Shaken", modifiers["will"][0].source)
        self.assertNotIn("damage", modifiers)

    def test_exhausted_supersedes_fatigued_ability_penalties(self) -> None:
        modifiers = condition_modifiers(
            [Condition(1, "Fatigued", True), Condition(2, "Exhausted", True)]
        )
        self.assertEqual([-6], [item.value for item in modifiers["strength"]])

    def test_enabled_feat_creates_named_typed_modifier(self) -> None:
        modifiers = feat_modifiers(
            [
                Feat(1, "Great Fortitude", True, "fortitude", "untyped", 2),
                Feat(2, "Inactive", False, "will", "insight", 3),
                Feat(3, "Notes only", True, "", "untyped", 0),
            ]
        )

        self.assertEqual(2, modifiers["fortitude"][0].value)
        self.assertEqual("Feat: Great Fortitude", modifiers["fortitude"][0].source)
        self.assertNotIn("will", modifiers)

    def test_structured_feat_effects_scale_with_level_ranks_and_equipment(self) -> None:
        feats = [
            Feat(
                1,
                "Toughness",
                effects=(FeatEffect("hp", formula="character_level_min_3"),),
            ),
            Feat(
                2,
                "Skill Focus",
                choice="Perception",
                effects=(
                    FeatEffect(
                        "skill:perception",
                        value=3,
                        formula="rank_scaled_3_6",
                    ),
                ),
            ),
            Feat(
                3,
                "Shield Focus",
                effects=(
                    FeatEffect(
                        "ac",
                        value=1,
                        formula="equipped_category",
                        scope="Shield",
                    ),
                ),
            ),
        ]
        shield = EquipmentItem(
            1, "Heavy shield", "Shield", 1, 15, True, 2, "shield", None
        )
        modifiers = feat_modifiers(
            feats,
            {"perception": SkillState("perception", 10)},
            character_level=8,
            bab=8,
            equipment=[shield],
        )
        self.assertEqual(8, modifiers["hp"][0].value)
        self.assertEqual(6, modifiers["skill:perception"][0].value)
        self.assertEqual(1, modifiers["ac"][0].value)

        shield_off = EquipmentItem(
            1, "Heavy shield", "Shield", 1, 15, False, 2, "shield", None
        )
        without_shield = feat_modifiers(feats, equipment=[shield_off])
        self.assertNotIn("ac", without_shield)

    def test_weapon_focus_and_power_attack_apply_to_matching_saved_attack(self) -> None:
        attack = Attack(
            1,
            "Greatsword",
            "Melee",
            "strength",
            0,
            "2d6",
            "strength",
            1.5,
            0,
            "19-20/x2",
        )
        feats = [
            Feat(
                1,
                "Weapon Focus",
                choice="Greatsword",
                effects=(FeatEffect("attack", value=1, scope="name:greatsword"),),
            ),
            Feat(
                2,
                "Power Attack",
                effects=(
                    FeatEffect(
                        "attack", value=-1, formula="bab_step", scope="type:Melee"
                    ),
                    FeatEffect(
                        "damage", formula="power_attack_damage", scope="type:Melee"
                    ),
                ),
            ),
        ]
        attack_modifiers, damage_modifiers = feat_attack_modifiers(feats, attack, 8)
        self.assertEqual([1, -3], [modifier.value for modifier in attack_modifiers])
        self.assertEqual([9], [modifier.value for modifier in damage_modifiers])

        bow = Attack(
            2, "Longbow", "Ranged", "dexterity", 0, "1d8", None, 0, 0, "x3"
        )
        bow_attack, bow_damage = feat_attack_modifiers(feats, bow, 8)
        self.assertEqual([], bow_attack)
        self.assertEqual([], bow_damage)

    def test_enabled_trait_creates_trait_modifier(self) -> None:
        modifiers = trait_modifiers(
            [
                Trait(1, "Reactionary", True, "initiative", "trait", 2),
                Trait(2, "Inactive", False, "ac", "trait", 1),
            ]
        )

        self.assertEqual(2, modifiers["initiative"][0].value)
        self.assertEqual("Trait: Reactionary", modifiers["initiative"][0].source)
        self.assertNotIn("ac", modifiers)

    def test_shared_catalog_effects_cover_class_skills_untrained_and_scaling(self) -> None:
        seeker = Trait(
            1,
            "Seeker",
            effects=(
                FeatEffect("skill:perception", "trait", 1),
                FeatEffect("skill:perception", formula="class_skill"),
            ),
        )
        breadth = Feat(
            2,
            "Breadth of Experience",
            effects=(
                FeatEffect("skill:knowledge_arcana", value=2),
                FeatEffect("skill:knowledge_arcana", formula="allow_untrained"),
            ),
        )
        self.assertEqual({"perception"}, effect_class_skills([seeker]))
        self.assertEqual({"knowledge_arcana"}, effect_untrained_skills([breadth]))

        knowledge = next(skill for skill in SKILLS if skill.key == "knowledge_arcana")
        result = calculate_skill(
            knowledge,
            SkillState("knowledge_arcana"),
            calculate_ability(10, []),
            0,
            feat_modifiers([breadth])["skill:knowledge_arcana"],
            allow_untrained=True,
        )
        self.assertTrue(result.usable)
        self.assertEqual(2, result.total)

        marauder = MartialTalent(
            3,
            "Marauder",
            effects=(
                FeatEffect(
                    "skill:acrobatics", "competence", formula="half_bab_min_1"
                ),
            ),
        )
        martial = martial_talent_modifiers([marauder], bab=8)
        self.assertEqual(4, martial["skill:acrobatics"][0].value)

        resolve = Spell(
            4,
            "Resolve",
            system="Sphere",
            enabled=False,
            effects=(FeatEffect("will", "morale", 4),),
        )
        self.assertEqual({}, magic_talent_modifiers([resolve]))


if __name__ == "__main__":
    unittest.main()

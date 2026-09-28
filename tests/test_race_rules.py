from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from app.catalogs import RulesCatalog
from app.models import CharacterDetails, RaceTraitChoice
from app.race_rules import (
    alternate_trait_conflicts,
    generated_racial_attacks,
    race_modifier_map,
    racial_advancement_effects,
    racial_class_skills,
    racial_resistances,
    racial_senses,
    resolved_race,
    resolved_racial_traits,
    validate_race_trait_choices,
)


class RaceCatalogTests(unittest.TestCase):
    def test_variant_choice_survives_database_reopen(self) -> None:
        from app.database import CharacterRepository
        from app.services.character_calculations import CharacterCalculationService
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "race.db"
            repository = CharacterRepository(path)
            character = repository.create_character("Variant", "Spheres")
            trait = "race-alt-trait:aasimar:variant-aasimar-abilities"
            repository.update_character_details(CharacterDetails(character, race="Aasimar", race_key="aasimar",
                race_alternate_trait_keys=(trait,), race_trait_choices=(RaceTraitChoice(trait, "variant_abilities", ("90",)),)))
            repository.close()
            repository = CharacterRepository(path)
            try:
                self.assertEqual(14, CharacterCalculationService(repository, character).ability_result("charisma").total)
            finally:
                repository.close()

    def test_variant_ability_increases_add_to_heritage_adjustments(self) -> None:
        from app.rules import calculate_ability
        cases = (
            ("aasimar", "90", "charisma", 14),
            ("aasimar", "50", "wisdom", 14),
            ("aasimar", "9", "strength", 12),
            ("tiefling", "46", "intelligence", 14),
            ("tiefling", "9", "charisma", 10),
            ("tiefling", "90", "wisdom", 12),
        )
        for race, option, ability, expected in cases:
            with self.subTest(race=race, option=option):
                trait = f"race-alt-trait:{race}:variant-{race}-abilities"
                details = CharacterDetails(1, race_key=race, race_alternate_trait_keys=(trait,),
                    race_trait_choices=(RaceTraitChoice(trait, "variant_abilities", (option,)),))
                self.assertEqual(expected, calculate_ability(10, race_modifier_map(details).get(ability, [])).total)

    def test_variant_save_bonuses_and_invalid_choices(self) -> None:
        for race, option, target in (("aasimar", "22", "will"), ("tiefling", "29", "reflex"), ("tiefling", "79", "fortitude")):
            trait = f"race-alt-trait:{race}:variant-{race}-abilities"
            details = CharacterDetails(1, race_key=race, race_alternate_trait_keys=(trait,),
                race_trait_choices=(RaceTraitChoice(trait, "variant_abilities", (option,)),))
            self.assertEqual(1, sum(value.value for value in race_modifier_map(details)[target]))
        trait = "race-alt-trait:aasimar:variant-aasimar-abilities"
        details = CharacterDetails(1, race_key="aasimar", race_alternate_trait_keys=(trait,),
            race_trait_choices=(RaceTraitChoice(trait, "variant_abilities", ("90", "invalid")),))
        self.assertEqual(2, sum(value.value for value in race_modifier_map(details)["charisma"]))

    def test_complete_first_party_race_index_is_bundled(self) -> None:
        catalog = RulesCatalog()
        self.assertEqual(77, len(catalog.race_entries()))
        self.assertEqual(7, len(catalog.race_entries("Core")))
        self.assertEqual(70, len(catalog.race_entries("Other")))
        self.assertGreaterEqual(
            sum(len(entry.get("alternate_racial_traits", ())) for entry in catalog.race_entries()),
            600,
        )

    def test_core_adjustments_and_speed_remain_compatible(self) -> None:
        details = CharacterDetails(1, race="Dwarf", race_key="dwarf")
        profile = resolved_race(details)
        self.assertEqual(20, profile.base_speed)
        modifiers = race_modifier_map(details)
        self.assertEqual(2, modifiers["constitution"][0].value)
        self.assertEqual(2, modifiers["wisdom"][0].value)
        self.assertEqual(-2, modifiers["charisma"][0].value)

    def test_flexible_and_subrace_adjustments_are_resolved(self) -> None:
        human = race_modifier_map(CharacterDetails(
            1, race="Human", race_key="human", race_ability_choice="dexterity"
        ))
        self.assertEqual(2, human["dexterity"][0].value)
        aasimar = race_modifier_map(CharacterDetails(
            2,
            race="Aasimar",
            race_key="aasimar",
            race_variant_key="race-variant:aasimar:angel-blooded-angelkin",
        ))
        self.assertEqual(2, aasimar["strength"][0].value)
        self.assertEqual(2, aasimar["charisma"][0].value)
        self.assertNotIn("wisdom", aasimar)

    def test_alternate_traits_replace_base_traits_and_conflict_safely(self) -> None:
        catalog = RulesCatalog()
        dwarf = catalog.race_entry("dwarf")
        assert dwarf is not None
        selected = (
            "race-alt-trait:dwarf:low-light-vision",
            "race-alt-trait:dwarf:minesight",
        )
        self.assertIn("darkvision", alternate_trait_conflicts(dwarf, selected))
        details = CharacterDetails(
            1,
            race="Dwarf",
            race_key="dwarf",
            race_alternate_trait_keys=("race-alt-trait:dwarf:low-light-vision",),
        )
        resolved_traits = resolved_racial_traits(details)
        names = {str(trait["name"]) for trait in resolved_traits}
        self.assertIn("Low-Light Vision", names)
        self.assertNotIn("Darkvision", names)

    def test_dual_talent_replaces_human_defaults_and_applies_two_choices(self) -> None:
        catalog = RulesCatalog()
        human = catalog.race_entry("human")
        assert human is not None
        trait_key = "race-alt-trait:human:dual-talent"
        choices = (RaceTraitChoice(
            trait_key, "ability_scores", ("strength", "dexterity")
        ),)
        details = CharacterDetails(
            1,
            race="Human",
            race_key="human",
            race_alternate_trait_keys=(trait_key,),
            race_trait_choices=choices,
        )
        profile = resolved_race(details)
        self.assertEqual(0, profile.flexible_bonus)
        modifiers = race_modifier_map(details)
        self.assertEqual(2, modifiers["strength"][0].value)
        self.assertEqual(2, modifiers["dexterity"][0].value)
        resolved_traits = resolved_racial_traits(details)
        names = {str(trait["name"]) for trait in resolved_traits}
        self.assertIn("Dual Talent", names)
        self.assertNotIn("+2 to One Ability Score", names)
        self.assertNotIn("Bonus Feat", names)
        self.assertNotIn("Skilled", names)
        dual = next(trait for trait in resolved_traits if trait["name"] == "Dual Talent")
        self.assertEqual("Ability scores: Strength, Dexterity", dual["choice_summary"])
        self.assertEqual({}, racial_advancement_effects(details))
        self.assertEqual((), validate_race_trait_choices(
            human, (trait_key,), choices
        ))

        base_human = racial_advancement_effects(CharacterDetails(
            2, race="Human", race_key="human", race_ability_choice="wisdom"
        ))
        self.assertEqual(1, base_human["skill_points_per_level"])
        self.assertEqual(1, base_human["feat_slots"])

    def test_dual_talent_rejects_missing_or_duplicate_answers(self) -> None:
        human = RulesCatalog().race_entry("human")
        assert human is not None
        trait_key = "race-alt-trait:human:dual-talent"
        missing = validate_race_trait_choices(human, (trait_key,), ())
        duplicate = validate_race_trait_choices(human, (trait_key,), (
            RaceTraitChoice(trait_key, "ability_scores", ("strength", "strength")),
        ))
        self.assertTrue(any("requires 2" in error for error in missing))
        self.assertTrue(any("same selection twice" in error for error in duplicate))

    def test_replacement_aware_senses_do_not_keep_removed_darkvision(self) -> None:
        details = CharacterDetails(
            1, race="Dwarf", race_key="dwarf",
            race_alternate_trait_keys=("race-alt-trait:dwarf:low-light-vision",),
        )
        senses = {sense.key: sense for sense in racial_senses(details)}
        self.assertIn("low_light_vision", senses)
        self.assertNotIn("darkvision", senses)

    def test_fey_thoughts_choices_grant_class_skills_and_replace_skilled(self) -> None:
        trait_key = "race-alt-trait:human:fey-thoughts"
        details = CharacterDetails(
            1, race="Human", race_key="human",
            race_alternate_trait_keys=(trait_key,),
            race_trait_choices=(RaceTraitChoice(
                trait_key, "class_skills", ("acrobatics", "use_magic_device")
            ),),
        )
        self.assertEqual(
            {"acrobatics", "use_magic_device"}, racial_class_skills(details)
        )
        self.assertNotIn("skill_points_per_level", racial_advancement_effects(details))

    def test_maw_or_claw_generates_only_the_selected_natural_weapon(self) -> None:
        trait_key = "race-alt-trait:tiefling:maw-or-claw"
        details = CharacterDetails(
            1, race="Tiefling", race_key="tiefling",
            race_alternate_trait_keys=(trait_key,),
            race_trait_choices=(RaceTraitChoice(
                trait_key, "natural_weapon", ("claws",)
            ),),
        )
        attacks = generated_racial_attacks(details)
        self.assertEqual(("Claw 1", "Claw 2"), tuple(item.name for item in attacks))
        self.assertTrue(all(item.damage_dice == "1d4" for item in attacks))
        self.assertTrue(all(item.id < -2_000_000 for item in attacks))

    def test_direct_natural_attack_and_selected_resistance_are_structured(self) -> None:
        toothy = CharacterDetails(
            1, race="Half-Orc", race_key="half-orc",
            race_alternate_trait_keys=("race-alt-trait:half-orc:toothy",),
        )
        attacks = generated_racial_attacks(toothy)
        self.assertEqual("Bite", attacks[0].name)
        self.assertEqual("1d4", attacks[0].damage_dice)

        scaled_key = "race-alt-trait:tiefling:scaled-skin"
        scaled = CharacterDetails(
            2, race="Tiefling", race_key="tiefling",
            race_alternate_trait_keys=(scaled_key,),
            race_trait_choices=(RaceTraitChoice(scaled_key, "energy", ("cold",)),),
        )
        self.assertEqual(5, racial_resistances(scaled)[0].value)
        self.assertEqual("cold", racial_resistances(scaled)[0].energy_type)
        self.assertEqual(1, race_modifier_map(scaled)["ac"][0].value)

    def test_variant_table_choice_applies_only_the_selected_option(self) -> None:
        trait_key = "race-alt-trait:tiefling:variant-tiefling-abilities"
        details = CharacterDetails(
            1, race="Tiefling", race_key="tiefling",
            race_alternate_trait_keys=(trait_key,),
            race_trait_choices=(RaceTraitChoice(
                trait_key, "variant_abilities", ("10",)
            ),),
        )
        attacks = generated_racial_attacks(details)
        self.assertEqual(1, len(attacks))
        self.assertEqual("Bite", attacks[0].name)
        self.assertEqual("1d4", attacks[0].damage_dice)

    def test_every_structured_racial_choice_has_a_valid_completion(self) -> None:
        catalog = RulesCatalog()
        structured_count = 0
        for race in catalog.race_entries():
            for trait in race.get("alternate_racial_traits", ()):
                specs = tuple(trait.get("choice_specs", ()))
                if not specs:
                    continue
                structured_count += 1
                trait_key = str(trait["key"])
                choices = []
                for spec in specs:
                    minimum = int(spec.get("minimum", 1))
                    options = tuple(spec.get("options", ()))
                    values = tuple(
                        str(options[index]["key"]) if index < len(options) else f"choice-{index + 1}"
                        for index in range(minimum)
                    )
                    choices.append(RaceTraitChoice(
                        trait_key, str(spec["key"]), values
                    ))
                self.assertEqual((), validate_race_trait_choices(
                    race, (trait_key,), tuple(choices)
                ), f"{race['name']} — {trait['name']}")
        self.assertEqual(29, structured_count)


if __name__ == "__main__":
    unittest.main()

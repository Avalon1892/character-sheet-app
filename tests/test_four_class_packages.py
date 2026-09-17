from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.class_packages import (
    all_class_packages,
    archetype_package,
    class_package,
)
from app.class_choice_rules import (
    class_choice_selection_record,
    resolve_class_choice_slots,
)
from app.class_feature_systems import (
    class_feature_extra_damage,
    resolve_class_feature_modules,
)
from app.class_feature_rules import archetype_granted_features
from app.class_power_rules import (
    apply_class_power_selection,
    resolve_class_power_sets,
)
from app.class_granted_spells import synchronize_class_granted_spells
from app.class_modifications import resolve_class_profile
from app.content import archetype_entry, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState, SkillState
from app.services.character_calculations import CharacterCalculationService
from app.recovery import FullRestEngine


class FourClassPackageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.temporary.name) / "families.db")

    def tearDown(self) -> None:
        self.repository.close()
        self.temporary.cleanup()

    def add_class(self, name: str, key: str, level: int = 12) -> tuple[int, int]:
        character = self.repository.create_character(name, "Pathfinder 1e")
        class_id = self.repository.add_class_level(
            character, name, level, "3/4", "Poor", "Poor", "Good",
            key, 8, level * 6,
        )
        return character, class_id

    def test_reviewed_packages_and_all_target_archetypes_are_structured(self) -> None:
        self.assertEqual(
            {"alchemist", "antipaladin", "arcanist", "armiger", "armorist", "barbarian", "barbarian-unchained", "bard", "blacksmith", "bloodrager", "brawler", "cavalier", "cleric", "commander", "conscript", "druid", "elementalist", "eliciter", "fey_adept", "fighter", "gunslinger", "hedgewitch", "hunter", "incanter", "inquisitor", "investigator", "kineticist", "mageknight", "magus", "medium", "mesmerist", "monk", "necros", "ninja", "occultist", "oracle", "paladin", "prodigy", "psychic", "ranger", "rogue", "sage", "samurai", "scholar", "sentinel", "shaman", "shifter", "slayer", "sorcerer", "soul-weaver", "spiritualist", "striker", "symbiat", "technician", "thaumaturge", "troubadour", "warden", "warpriest", "wizard", "witch", "wraith"},
            {package.key for package in all_class_packages()} - {"crimson-dancer", "mountebank", "reaper"},
        )
        expected = {
            "bard": 85,
            "cleric": 39,
            "inquisitor": 45,
            "monk": 60,
            "oracle": 28,
            "prodigy": 8,
            "wizard": 39,
            "fighter": 76,
            "rogue": 84,
            "sorcerer": 15,
            "druid": 79,
            "paladin": 59,
            "ranger": 72,
            "alchemist": 76,
            "barbarian": 48,
            "cavalier": 41,
            "arcanist": 17,
            "investigator": 46,
            "magus": 36,
            "bloodrager": 23,
            "warpriest": 24,
            "witch": 45,
            "gunslinger": 32,
            "kineticist": 20,
            "shaman": 19,
            "antipaladin": 19,
            "barbarian-unchained": 4,
            "brawler": 22,
            "hunter": 27,
            "medium": 20,
            "mesmerist": 26,
            "occultist": 23,
            "psychic": 9,
            "spiritualist": 26,
            "ninja": 8,
            "samurai": 11,
            "slayer": 30,
            "armiger": 9,
            "armorist": 18,
            "incanter": 3,
            "blacksmith": 10,
            "conscript": 0,
            "elementalist": 17,
            "commander": 10,
            "scholar": 9,
            "sentinel": 9,
            "striker": 9,
            "technician": 6,
            "mageknight": 19,
            "hedgewitch": 7,
            "shifter": 17,
            "soul-weaver": 9,
            "thaumaturge": 15,
            "fey-adept": 12,
            "symbiat": 17,
            "eliciter": 8,
            "wraith": 7,
            "sage": 5,
            "necros": 2,
            "troubadour": 5,
            "warden": 4,
            "crimson-dancer": 2,
            "mountebank": 3,
            "reaper": 8,
        }
        for family, count in expected.items():
            path = (
                Path(__file__).resolve().parent.parent
                / "app" / "class_packages" / "definitions" / "archetypes"
                / f"{family}.json"
            )
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(count, len(document["entries"]))
            self.assertTrue(all(entry["key"] for entry in document["entries"]))
            self.assertTrue(all("features" in entry for entry in document["entries"]))

    def test_catalog_archetype_is_enriched_from_structured_package(self) -> None:
        key = "spheres-archetype:pathfinder-class:bard:champion-bard"
        packaged = archetype_package(key)
        catalog = archetype_entry(key)
        self.assertIsNotNone(packaged)
        self.assertIsNotNone(catalog)
        self.assertEqual("pathfinder-class:bard", catalog["automation_package"])
        self.assertTrue(catalog["features"])
        self.assertIn("casting", {item["name"].casefold() for item in catalog["features"]})

    def test_title_only_spheres_feature_headings_are_normalized(self) -> None:
        features = archetype_granted_features(
            {
                "name": "Title-only Test",
                "description": (
                    "First Feature\n"
                    "At 1st level, the character gains the first feature.\n"
                    "This replaces the original feature.\n"
                    "Second Feature (Su)\n"
                    "At 3rd level, the character gains the second feature."
                ),
            },
            20,
        )
        self.assertEqual(
            [(1, "First Feature"), (3, "Second Feature")],
            [(feature.level, feature.name) for feature in features],
        )

    def test_corteggiare_reviewed_feature_levels_override_prose_inference(self) -> None:
        catalog = archetype_entry(
            "spheres-archetype:pathfinder-class:bard:corteggiare"
        )
        self.assertEqual(
            {
                "Music is Magic": 1,
                "Choir Performance": 1,
                "Magical Flourish": 1,
                "Wonderful Harmony": 6,
                "Miracle Melody": 12,
            },
            {feature["name"]: feature["level"] for feature in catalog["features"]},
        )

    def test_bard_package_automates_knowledge_and_retained_performances(self) -> None:
        character, class_id = self.add_class("Bard", "pathfinder-class:bard", 15)
        self.repository.update_ability_score(character, "charisma", 18)
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(7, calculator.automatic_total("skill:knowledge_arcana"))

        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "bardic_performance", 20,
                active=True, choices_json=json.dumps(["Inspire Heroics"]),
            )
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.automatic_total("armor_class"))
        self.assertEqual(4, calculator.automatic_total("fortitude"))

    def test_bard_package_resolves_versatile_performance_and_jack_of_all_trades(self) -> None:
        character, _class_id = self.add_class(
            "Bard", "pathfinder-class:bard", 19
        )
        self.repository.update_ability_score(character, "charisma", 18)
        self.repository.update_skill_specialization(
            character, "perform", "perform", "Dance"
        )
        self.repository.update_skill_state(
            character, SkillState("perform", 10, True)
        )
        slot = next(
            item for item in resolve_class_choice_slots(self.repository, character)
            if item.key == "bard-versatile-performance"
        )
        self.assertEqual(5, slot.maximum)
        dance = next(option for option in slot.options if option.name == "Dance")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, slot, (dance.key,))
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(17, calculator.skill_result("acrobatics").total)
        self.assertTrue(calculator.skill_result("disable_device").usable)
        self.assertTrue(calculator.skill_take_ten_allowed("acrobatics"))

        self.repository.update_skill_state(
            character, SkillState("heal", 1, False)
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.skill_result("heal").total)

    def test_bard_lore_master_and_well_versed_are_live_resources(self) -> None:
        character, class_id = self.add_class(
            "Bard", "pathfinder-class:bard", 17
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(
                self.repository, character, {"charisma": 4}
            )
            for resource in module.resources
        }
        self.assertEqual(3, resources["lore_master"].maximum)
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "well_versed", 1, active=True)
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.automatic_total("will"))

    def test_inquisitor_package_exposes_context_toggles_and_passives(self) -> None:
        character, class_id = self.add_class(
            "Inquisitor", "pathfinder-class:inquisitor", 12
        )
        self.repository.update_ability_score(character, "wisdom", 18)
        resources = {
            resource.key: resource
            for resource in resolve_class_feature_modules(
                self.repository, character, {"wisdom": 4}
            )[0].resources
        }
        self.assertIn("monster_lore", resources)
        self.assertIn("track", resources)
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.automatic_total("initiative"))
        self.assertEqual(0, calculator.automatic_total("skill:knowledge_arcana"))

        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "monster_lore", 1, active=True)
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "track", 1, active=True)
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(4, calculator.automatic_total("skill:knowledge_arcana"))
        self.assertEqual(6, calculator.automatic_total("skill:survival"))

    def test_oracle_package_drives_choice_and_power_systems(self) -> None:
        character, _class_id = self.add_class(
            "Oracle", "pathfinder-class:oracle", 7
        )
        choices = {slot.key for slot in resolve_class_choice_slots(self.repository, character)}
        self.assertTrue({"oracle-mystery", "oracle-curse"} <= choices)
        # Revelations remain hidden until their required Mystery is selected.
        self.assertFalse(resolve_class_power_sets(self.repository, character))
        self.assertEqual("oracle", class_package("oracle").key)

    def test_oracle_mystery_grants_level_gated_spells_and_class_skills(self) -> None:
        character, class_id = self.add_class(
            "Oracle", "pathfinder-class:oracle", 7
        )
        mystery = next(
            item for item in resolve_class_choice_slots(self.repository, character)
            if item.key == "oracle-mystery"
        )
        flame = next(option for option in mystery.options if option.name == "Flame Mystery")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, mystery, (flame.key,))
        )
        self.assertTrue(synchronize_class_granted_spells(self.repository, character))
        granted = {
            spell.name for spell in self.repository.list_spells(character)
            if spell.catalog_category == "Class Granted"
        }
        self.assertEqual(
            {"Burning Hands", "Resist Energy", "Fireball"}, granted
        )
        self.assertTrue(
            {"acrobatics", "climb", "intimidate", "perform"}
            <= CharacterCalculationService(
                self.repository, character
            ).resolved_class_skills()
        )

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("spheres-archetype:pathfinder-class:oracle:sphere-oracle",),
        )
        self.assertTrue(synchronize_class_granted_spells(self.repository, character))
        self.assertFalse(
            [
                spell for spell in self.repository.list_spells(character)
                if spell.catalog_category == "Class Granted"
            ]
        )

    def test_oracle_curse_spell_grants_share_the_same_reconciler(self) -> None:
        character, _class_id = self.add_class(
            "Oracle", "pathfinder-class:oracle", 10
        )
        curse = next(
            item for item in resolve_class_choice_slots(self.repository, character)
            if item.key == "oracle-curse"
        )
        haunted = next(option for option in curse.options if option.name == "Haunted Curse")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, curse, (haunted.key,))
        )
        synchronize_class_granted_spells(self.repository, character)
        granted = {
            (spell.name, spell.level)
            for spell in self.repository.list_spells(character)
            if spell.catalog_category == "Class Granted"
        }
        self.assertEqual(
            {
                ("Ghost Sound", 0),
                ("Mage Hand", 0),
                ("Levitate", 2),
                ("Minor Image", 2),
                ("Telekinesis", 5),
            },
            granted,
        )

    def test_prodigy_package_adds_resources_and_exploitant_removes_adaptation(self) -> None:
        character, class_id = self.add_class("Prodigy", "prodigy", 8)
        resources = {
            resource.key: resource
            for resource in resolve_class_feature_modules(
                self.repository, character, {"charisma": 4}
            )[0].resources
        }
        self.assertEqual(7, resources["adaptation"].maximum)
        self.assertEqual(0, resources["steady_skill"].maximum)
        self.assertFalse(resources["steady_skill"].tracks_uses)
        self.assertEqual("martial_focus", resources["steady_skill"].external_cost_key)

        exploitant = "spheres-archetype:prodigy:exploitant"
        self.repository.set_class_archetype_keys(character, class_id, (exploitant,))
        modules = resolve_class_feature_modules(
            self.repository, character, {"charisma": 4}
        )
        resource_keys = {
            resource.key for module in modules for resource in module.resources
        }
        self.assertNotIn("adaptation", resource_keys)

    def test_reviewed_bard_archetype_overlays_supply_resources_and_power_slots(self) -> None:
        character, class_id = self.add_class(
            "Bard", "pathfinder-class:bard", 12
        )
        self.repository.update_ability_score(character, "charisma", 18)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:bard:archaeologist",),
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(8, resources["archaeologists_luck"].maximum)
        powers = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "archaeologist-rogue-talents"
        )
        self.assertEqual((4, 8, 12), powers.slot_levels)

        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "archaeologists_luck", 8, active=True
            )
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(3, calculator.automatic_total("attack"))
        self.assertEqual(3, calculator.automatic_total("skills"))
        self.assertEqual(6, calculator.automatic_total("skill:disable_device"))

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("spheres-archetype:pathfinder-class:bard:kung-fu-exemplar",),
        )
        kung_fu = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "kung-fu-exemplar-ki-powers"
        )
        self.assertEqual(5, kung_fu.maximum)

    def test_reviewed_oracle_archetype_overlays_use_oracle_ability(self) -> None:
        character, class_id = self.add_class(
            "Oracle", "pathfinder-class:oracle", 12
        )
        self.repository.update_ability_score(character, "charisma", 18)
        cases = (
            (
                "pathfinder-archetype:pathfinder-class:oracle:shigenjo",
                "ki_pool",
                10,
            ),
            (
                "pathfinder-archetype:pathfinder-class:oracle:pei-zin-practitioner",
                "healers_way",
                5,
            ),
            (
                "pathfinder-archetype:pathfinder-class:oracle:psychic-searcher",
                "inspiration",
                10,
            ),
            (
                "pathfinder-archetype:pathfinder-class:oracle:warsighted",
                "martial_flexibility",
                9,
            ),
        )
        for archetype, resource_key, expected in cases:
            self.repository.set_class_archetype_keys(
                character, class_id, (archetype,)
            )
            resources = {
                resource.key: resource
                for module in resolve_class_feature_modules(
                    self.repository, character
                )
                for resource in module.resources
            }
            self.assertEqual(expected, resources[resource_key].maximum)

    def test_spirit_guide_uses_exact_spirit_choice_spells_and_retained_revelations(self) -> None:
        character, class_id = self.add_class(
            "Oracle", "pathfinder-class:oracle", 8
        )
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:oracle:spirit-guide",),
        )
        slots = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, character)
        }
        self.assertIn("oracle-spirit-guide-spirit", slots)
        mystery = slots["oracle-mystery"]
        ancestor_mystery = next(
            option for option in mystery.options if option.name == "Ancestor Mystery"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(
                character, mystery, (ancestor_mystery.key,)
            )
        )
        spirit = slots["oracle-spirit-guide-spirit"]
        flame = next(option for option in spirit.options if option.name == "Flame Spirit")
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, spirit, (flame.key,))
        )

        self.assertTrue(synchronize_class_granted_spells(self.repository, character))
        granted = {
            (spell.name, spell.level)
            for spell in self.repository.list_spells(character)
            if spell.catalog_category == "Class Granted"
            and ":oracle-spirit-guide-spirit:" in spell.choice
        }
        self.assertEqual(
            {
                ("Burning Hands", 1),
                ("Resist Energy", 2),
                ("Fireball", 3),
                ("Wall Of Fire", 4),
            },
            granted,
        )
        retained = next(
            power_set
            for power_set in resolve_class_power_sets(self.repository, character)
            if power_set.key == "oracle-revelations"
        )
        self.assertEqual((1,), retained.slot_levels)
        self.assertTrue(
            {
                "knowledge_arcana",
                "knowledge_dungeoneering",
                "knowledge_engineering",
                "knowledge_geography",
                "knowledge_history",
                "knowledge_local",
                "knowledge_nature",
                "knowledge_nobility",
                "knowledge_planes",
                "knowledge_religion",
            }
            <= CharacterCalculationService(
                self.repository, character
            ).resolved_class_skills()
        )

    def test_sanctified_slayer_overlay_uses_exact_non_advanced_slots(self) -> None:
        character, class_id = self.add_class(
            "Inquisitor", "pathfinder-class:inquisitor", 17
        )
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:inquisitor:sanctified-slayer",),
        )
        power_set = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "sanctified-slayer-talents"
        )
        self.assertEqual((8, 16, 17), power_set.slot_levels)
        self.assertTrue(power_set.options)
        self.assertEqual({"Standard"}, {item.category for item in power_set.options})

    def test_gutter_rat_roguish_adaptation_spends_uses_scales_and_ends_on_rest(self) -> None:
        character, class_id = self.add_class("Prodigy", "prodigy", 16)
        self.repository.set_class_archetype_keys(
            character, class_id, ("spheres-archetype:prodigy:gutter-rat",)
        )
        power_set = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "gutter-rat-roguish-adaptation"
        )
        self.assertEqual((2, 5, 13), power_set.slot_levels)
        self.assertNotIn("Advanced", {item.category for item in power_set.options})
        self.assertFalse(
            {"Combat Trick", "Feat", "Forgotten Trick", "Master Tricks (Talent)", "Ninja Trick"}
            & {item.name for item in power_set.options}
        )
        selections = tuple(item.key for item in power_set.options[:3])
        application = apply_class_power_selection(
            self.repository, character, power_set, selections
        )
        self.assertEqual(3, application.resource_cost)
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(8, resources["adaptation"].current)
        self.assertIn("sneak_attack", resources)
        self.repository.save_class_feature_state(
            ClassFeatureState(character, class_id, "sneak_attack", active=True)
        )
        self.assertEqual(
            "3d6", class_feature_extra_damage(self.repository, character)[0].dice
        )

        FullRestEngine(self.repository, character).perform(
            {"class_feature_resources": True}
        )
        rested = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "gutter-rat-roguish-adaptation"
        )
        self.assertEqual((), rested.selected_keys)
        self.assertNotIn(
            "sneak_attack",
            {
                resource.key
                for module in resolve_class_feature_modules(self.repository, character)
                for resource in module.resources
            },
        )

    def test_bard_archetype_choices_and_resources_are_runtime_driven(self) -> None:
        character, class_id = self.add_class("Bard", "pathfinder-class:bard", 14)
        self.repository.update_ability_score(character, "charisma", 18)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:bard:pitax-academy-of-grand-arts",),
        )
        focused = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "pitax-focused-performance"
        )
        self.assertEqual(9, len(focused.options))
        performance = next(
            resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
            if resource.key == "bardic_performance"
        )
        self.assertEqual(52, performance.maximum)

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:bard:busker",),
        )
        self.repository.save_class_feature_state(
            ClassFeatureState(
                character, class_id, "busker_stunts", 8,
                active=True, choices_json=json.dumps(["Quick Hands"]),
            )
        )
        calculator = CharacterCalculationService(self.repository, character)
        self.assertEqual(3, calculator.automatic_total("attack"))
        self.assertEqual(3, calculator.automatic_total("armor_class"))
        self.assertEqual(3, calculator.automatic_total("skill:acrobatics"))

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("spheres-archetype:pathfinder-class:bard:minstrel",),
        )
        passion = next(
            resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
            if resource.key == "passion"
        )
        self.assertEqual(5, passion.maximum)

    def test_inquisitor_archetype_filters_and_unique_pools(self) -> None:
        character, class_id = self.add_class(
            "Inquisitor", "pathfinder-class:inquisitor", 10
        )
        self.repository.update_ability_score(character, "wisdom", 18)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:inquisitor:abolisher",),
        )
        domain = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "inquisitor-domain"
        )
        self.assertEqual(
            {"Air Domain", "Animal Domain", "Earth Domain", "Fire Domain", "Plant Domain", "Water Domain", "Weather Domain"},
            {option.name for option in domain.options},
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(10, resources["escape_corruptions_grasp"].maximum)

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("spheres-archetype:pathfinder-class:inquisitor:ordained-hunter",),
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(4, resources["kismet"].maximum)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("spheres-archetype:pathfinder-class:inquisitor:shield-of-the-gods",),
        )
        resources = {
            resource.key: resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
        }
        self.assertEqual(4, resources["covenant_with_the_gods"].maximum)

    def test_dual_cursed_and_planar_oracle_choices_are_exact(self) -> None:
        character, class_id = self.add_class("Oracle", "pathfinder-class:oracle", 11)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:oracle:dual-cursed-oracle",),
        )
        curse = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "oracle-curse"
        )
        self.assertEqual((2, 2), (curse.minimum, curse.maximum))
        selected = tuple(option.key for option in curse.options[:2])
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, curse, selected)
        )
        stunted = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "dual-cursed-stunted-curse"
        )
        self.assertEqual(set(selected), {option.key for option in stunted.options})

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:oracle:planar-oracle",),
        )
        slots = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, character)
        }
        self.assertEqual(9, len(slots["planar-oracle-plane"].options))
        plane = slots["planar-oracle-plane"]
        self.repository.save_class_feature_selection(
            class_choice_selection_record(character, plane, (plane.options[0].key,))
        )
        slots = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, character)
        }
        self.assertEqual(4, len(slots["planar-oracle-energy"].options))

    def test_voice_of_the_wild_spell_choices_are_level_gated_and_granted(self) -> None:
        character, class_id = self.add_class(
            "Bard", "pathfinder-class:bard", 7
        )
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:bard:voice-of-the-wild",),
        )
        slots = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key.startswith("voice-wild-nature-magic-")
        }
        self.assertEqual(
            {
                "voice-wild-nature-magic-1",
                "voice-wild-nature-magic-4",
                "voice-wild-nature-magic-7",
            },
            set(slots),
        )
        self.assertEqual(
            {"Level 1"},
            {option.category for option in slots["voice-wild-nature-magic-1"].options},
        )
        entangle = next(
            option
            for option in slots["voice-wild-nature-magic-1"].options
            if option.name == "Entangle"
        )
        self.repository.save_class_feature_selection(
            class_choice_selection_record(
                character,
                slots["voice-wild-nature-magic-1"],
                (entangle.key,),
            )
        )
        self.assertTrue(synchronize_class_granted_spells(self.repository, character))
        self.assertIn(
            ("Entangle", 1),
            {
                (spell.name, spell.level)
                for spell in self.repository.list_spells(character)
                if spell.catalog_category == "Class Granted"
            },
        )

    def test_bard_fame_regions_are_persistent_non_usage_choices(self) -> None:
        character, class_id = self.add_class(
            "Bard", "pathfinder-class:bard", 9
        )
        for archetype in (
            "pathfinder-archetype:pathfinder-class:bard:celebrity",
            "pathfinder-archetype:pathfinder-class:bard:chelish-diva",
        ):
            self.repository.set_class_archetype_keys(
                character, class_id, (archetype,)
            )
            region = next(
                resource
                for module in resolve_class_feature_modules(
                    self.repository, character
                )
                for resource in module.resources
                if resource.key == "famous_region"
            )
            self.assertFalse(region.tracks_uses)
            self.assertEqual("Settlement or region name", region.custom_choice_label)

    def test_inquisitor_daily_and_relic_choices_use_shared_modules(self) -> None:
        character, class_id = self.add_class(
            "Inquisitor", "pathfinder-class:inquisitor", 10
        )
        self.repository.update_ability_score(character, "wisdom", 18)
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:inquisitor:infiltrator",),
        )
        alignment = next(
            resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
            if resource.key == "misdirection_alignment"
        )
        self.assertEqual(9, len(alignment.choice_options))
        self.assertFalse(alignment.tracks_uses)

        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:inquisitor:relic-hunter",),
        )
        slots = {
            slot.key: slot
            for slot in resolve_class_choice_slots(self.repository, character)
        }
        self.assertEqual(
            {
                "relic-hunter-school-1",
                "relic-hunter-school-2",
                "relic-hunter-school-4",
                "relic-hunter-school-7",
                "relic-hunter-school-10",
            },
            {key for key in slots if key.startswith("relic-hunter-school-")},
        )
        deific_focus = next(
            resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
            if resource.key == "deific_focus"
        )
        self.assertEqual(14, deific_focus.maximum)
        powers = next(
            item for item in resolve_class_power_sets(self.repository, character)
            if item.key == "relic-hunter-focus-powers"
        )
        self.assertEqual((1, 4, 8), powers.slot_levels)

    def test_inquisitor_suit_and_eldest_rules_alter_exact_shared_choices(self) -> None:
        character, class_id = self.add_class(
            "Inquisitor", "pathfinder-class:inquisitor", 10
        )
        self.repository.set_class_archetype_keys(
            character,
            class_id,
            ("pathfinder-archetype:pathfinder-class:inquisitor:suit-seeker",),
        )
        domain = next(
            slot for slot in resolve_class_choice_slots(self.repository, character)
            if slot.key == "inquisitor-domain"
        )
        self.assertEqual(
            {
                "Knowledge Domain", "Luck Domain", "Memory Subdomain",
                "Fate Subdomain", "Fate", "Fervor", "Illumination",
            },
            {option.name for option in domain.options},
        )

        eldest_key = (
            "pathfinder-archetype:pathfinder-class:inquisitor:sworn-of-the-eldest"
        )
        self.repository.set_class_archetype_keys(
            character, class_id, (eldest_key,)
        )
        self.assertIn(
            "inquisitor-domain",
            {slot.key for slot in resolve_class_choice_slots(self.repository, character)},
        )
        patron = next(
            resource
            for module in resolve_class_feature_modules(self.repository, character)
            for resource in module.resources
            if resource.key == "eldest_patron"
        )
        self.assertEqual("Eldest patron", patron.custom_choice_label)
        profile = resolve_class_profile(
            class_entry("pathfinder-class:inquisitor"),
            (archetype_entry(eldest_key),),
        )
        self.assertEqual("charisma", profile.casting.get("ability"))


if __name__ == "__main__":
    unittest.main()

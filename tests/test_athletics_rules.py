import tempfile
import unittest
from pathlib import Path

from app.athletics_rules import athletics_packages, athletics_granted_ranks
from app.content import martial_entries
from app.database import CharacterRepository
from app.drawback_rules import martial_talent_restriction_reason
from app.models import CharacterDetails, MartialFocus, MovementProfile
from app.services.character_calculations import CharacterCalculationService
from app.services.advancement import character_advancement_budgets


class AthleticsRulesTests(unittest.TestCase):
    def test_run_package_and_speed_boost(self):
        from app.athletics_rules import running_multiplier
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Run")
        talents = self.repository.list_martial_talents(self.character_id)
        self.assertEqual(5, running_multiplier(talents, "medium", "Medium"))
        self.assertEqual(4, running_multiplier(talents, "heavy", "Light"))
        self.assertEqual(4, running_multiplier(talents, "", "Heavy"))
        self.assertEqual(0, running_multiplier(talents, "", "Overloaded"))
        movement = CharacterCalculationService(self.repository, self.character_id).movement_results()
        self.assertEqual(5, movement["run_multiplier"])
        self.assertEqual(movement["land_speed"] * 5, movement["run_speed"])
        self.add_athletics("Speed Boost", "athletics:legendary: speed-boost")
        talents = self.repository.list_martial_talents(self.character_id)
        self.assertEqual(10, running_multiplier(talents, "", "Light"))
        self.assertEqual(8, running_multiplier(talents, "heavy", "Light"))

    def test_imbue_movement_tracks_links_and_sequence_end(self):
        from app.models import ProdigySequence
        self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Good", "Poor", "Good",
            hit_die=8, hp_gained=30,
        )
        for links, active, expected in ((1, True, 10), (4, True, 25), (0, False, 0)):
            self.repository.update_prodigy_sequence(
                ProdigySequence(self.character_id, active, links, 5, "warp_step_between")
            )
            result = CharacterCalculationService(self.repository, self.character_id).movement_results()
            self.assertEqual(expected, result["teleport_speed"])
        self.repository.update_prodigy_sequence(
            ProdigySequence(self.character_id, True, 2, 5, "nature_tunnel")
        )
        result = CharacterCalculationService(self.repository, self.character_id).movement_results()
        self.assertEqual(25, result["burrow_speed"])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Runner", "Spheres")
        self.repository.update_character_details(
            CharacterDetails(self.character_id, race="Human")
        )
        self.repository.add_class_level(
            self.character_id, "Conscript", 10, "Full", "Good", "Poor", "Poor",
            hit_die=10, hp_gained=60,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def add_athletics(self, name, key, category="Talent", choice="") -> int:
        return self.repository.add_martial_talent(
            self.character_id,
            name,
            "Athletics",
            "Base Sphere" if category == "Base Sphere" else "Talent",
            catalog_key=key,
            catalog_category=category,
            choice=choice,
            allow_duplicate_catalog=name == "Expanded Training",
        )

    def test_package_ranks_and_swift_movement_follow_focus(self) -> None:
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Run")
        self.add_athletics("Swift Movement", "athletics:talent:swift-movement")
        service = CharacterCalculationService(self.repository, self.character_id)

        self.assertEqual(10, service.effective_skill_ranks()["acrobatics"])
        self.assertEqual(50, service.movement_results()["land_speed"])

        self.repository.update_martial_focus(
            MartialFocus(self.character_id, 0, 1, "Total defense")
        )
        self.assertEqual(
            30,
            CharacterCalculationService(
                self.repository, self.character_id
            ).movement_results()["land_speed"],
        )

    def test_package_grants_are_rank_floors_not_spent_ranks(self) -> None:
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Climb")
        grants = athletics_granted_ranks(
            self.repository.list_martial_talents(self.character_id), 10
        )
        self.assertEqual({"climb": 5}, grants)
        self.assertEqual(0, self.repository.list_skill_states(self.character_id)["climb"].ranks)
        self.assertEqual(5, CharacterCalculationService(
            self.repository, self.character_id
        ).effective_skill_ranks()["climb"])

    def test_granted_rank_activates_catalog_class_skill_bonus(self) -> None:
        character_id = self.repository.create_character("Prodigy Runner", "Spheres")
        self.repository.add_class_level(
            character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.repository.add_martial_talent(
            character_id,
            "Athletics Sphere",
            "Athletics",
            "Base Sphere",
            catalog_key="athletics:base",
            catalog_category="Base Sphere",
            choice="Run",
        )

        result = CharacterCalculationService(
            self.repository, character_id
        ).skill_result("acrobatics")

        self.assertEqual(8, result.total)  # 5 granted ranks +3 class skill.
        self.assertIn(
            "Class skill bonus",
            {contribution.source for contribution in result.contributions},
        )

    def test_granted_ranks_expand_total_allowance_without_spending_base_points(self) -> None:
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Run")
        budget = next(
            item for item in character_advancement_budgets(
                self.repository, self.character_id
            )
            if item.key == "skill_points"
        )

        self.assertEqual(5, budget.used)
        self.assertEqual(10 * 2, budget.remaining)
        self.assertEqual(25, budget.total)
        self.assertIn("rule-granted ranks +5", budget.explanation)

    def test_expanded_training_adds_packages_and_unlocks_talents(self) -> None:
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Run")
        self.add_athletics(
            "Expanded Training", "athletics:talent:expanded-training", choice="Climb / Fly"
        )
        talents = self.repository.list_martial_talents(self.character_id)
        self.assertEqual(frozenset({"Run", "Climb", "Fly"}), athletics_packages(talents))
        climb = next(
            entry for entry in martial_entries("Athletics")
            if entry["category"] == "Climb Talent"
        )
        swim = next(
            entry for entry in martial_entries("Athletics")
            if entry["category"] == "Swim Talent"
        )
        self.assertEqual("", martial_talent_restriction_reason(climb, talents))
        self.assertIn("Swim package", martial_talent_restriction_reason(swim, talents))

    def test_movement_granting_talents_project_into_movement_panel(self) -> None:
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Fly")
        self.add_athletics("Sparrow’s Path (fly)", "athletics:legendary-talent:sparrow-s-path-fly")
        self.add_athletics("Eagle’s Path (fly)", "athletics:legendary-talent:eagle-s-path-fly")
        movement = CharacterCalculationService(
            self.repository, self.character_id
        ).movement_results()
        self.assertEqual(30, movement["fly_speed"])
        self.assertEqual("Average", movement["fly_maneuverability"])

    def test_mighty_conditioning_uses_both_physical_modifiers(self) -> None:
        self.repository.update_ability_score(self.character_id, "strength", 14)
        self.repository.update_ability_score(self.character_id, "dexterity", 16)
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Run")
        self.add_athletics(
            "Mighty Conditioning [utility]",
            "athletics:talent:mighty-conditioning-utility",
        )
        result = CharacterCalculationService(
            self.repository, self.character_id
        ).skill_result("acrobatics")
        # 10 granted ranks +3 Dexterity +2 Strength.
        self.assertEqual(15, result.total)

    def test_untrained_athlete_grants_mighty_conditioning_but_not_ranks(self) -> None:
        self.repository.update_ability_score(self.character_id, "strength", 14)
        self.repository.update_ability_score(self.character_id, "dexterity", 16)
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Run")
        self.repository.add_martial_talent(
            self.character_id,
            "Untrained Athlete [SA:MD2]",
            "Athletics",
            "Drawback",
            catalog_key="athletics:drawback:untrained-athlete-sa-md2",
            catalog_category="Drawback",
        )
        service = CharacterCalculationService(self.repository, self.character_id)
        self.assertEqual(0, service.effective_skill_ranks()["acrobatics"])
        self.assertEqual(5, service.skill_result("acrobatics").total)

    def test_fixed_drawback_talent_counts_for_package_rank_scaling(self) -> None:
        self.add_athletics("Athletics Sphere", "athletics:base", "Base Sphere", "Run")
        self.repository.add_martial_talent(
            self.character_id,
            "Always Forward [SA:MD]",
            "Athletics",
            "Drawback",
            catalog_key="athletics:drawback:always-forward-sa-md",
            catalog_category="Drawback",
        )
        self.assertEqual(
            10,
            CharacterCalculationService(
                self.repository, self.character_id
            ).effective_skill_ranks()["acrobatics"],
        )


if __name__ == "__main__":
    unittest.main()

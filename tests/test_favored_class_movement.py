import tempfile
import unittest
from pathlib import Path

from app.database import CharacterRepository
from app.models import CharacterDetails, FavoredClassBonus, MovementProfile
from app.services.character_calculations import CharacterCalculationService


class FavoredClassAndMovementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Mobile Hero", "Pathfinder 1e")
        self.class_id = self.repository.add_class_level(
            self.character_id,
            "Fighter",
            3,
            "Full",
            "Good",
            "Poor",
            "Poor",
            preset_key="fighter",
            hit_die=10,
            hp_gained=22,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def test_favored_class_allocations_are_bounded_and_hp_is_automatic(self) -> None:
        allocation = FavoredClassBonus(
            self.character_id,
            self.class_id,
            hp_bonus=2,
            skill_point_bonus=1,
            manual_code="",
        )
        self.repository.update_favored_class_bonus(allocation)
        saved = self.repository.list_favored_class_bonuses(self.character_id)[self.class_id]
        self.assertEqual(allocation, saved)
        self.assertEqual(
            2,
            CharacterCalculationService(
                self.repository, self.character_id
            ).automatic_total("hp"),
        )
        with self.assertRaises(ValueError):
            self.repository.update_favored_class_bonus(
                FavoredClassBonus(self.character_id, self.class_id, 2, 2, 0, "")
            )

    def test_all_movement_modes_have_saved_bases_and_effective_results(self) -> None:
        self.repository.update_character_details(
            CharacterDetails(self.character_id, race="Halfling", race_key="halfling")
        )
        automatic = CharacterCalculationService(
            self.repository, self.character_id
        ).movement_results()
        self.assertEqual(20, automatic["land_speed"])
        self.assertEqual(20, automatic["armor_speed"])

        profile = MovementProfile(
            self.character_id,
            land_speed=35,
            armor_speed=25,
            fly_speed=60,
            swim_speed=30,
            climb_speed=15,
            burrow_speed=10,
            teleport_speed=120,
            fly_maneuverability="Good",
            notes="Test movement",
        )
        self.repository.update_movement_profile(profile)
        self.assertEqual(profile, self.repository.get_movement_profile(self.character_id))
        resolved = CharacterCalculationService(
            self.repository, self.character_id
        ).movement_results()
        self.assertEqual(35, resolved["land_speed"])
        self.assertEqual(60, resolved["fly_speed"])
        self.assertEqual("Good", resolved["fly_maneuverability"])
        self.repository.set_numeric_formula(
            self.character_id,
            "movement",
            0,
            "land_speed",
            "=abilities.dexterity.score * 5",
        )
        formula_resolved = CharacterCalculationService(
            self.repository, self.character_id
        ).movement_results()
        self.assertEqual(60, formula_resolved["land_speed"])
        context = CharacterCalculationService(
            self.repository, self.character_id
        ).formula_context()
        self.assertEqual(95, context.evaluate("movement.land_speed + movement.fly_speed"))

    def test_worn_catalog_armor_reduces_current_speed_and_manual_override_wins(self) -> None:
        armor_id = self.repository.add_equipment(
            self.character_id,
            "Full Plate",
            "Armor",
            1,
            50,
            True,
            9,
            "armor",
            1,
            "",
            6,
            "Armor",
            1500,
            catalog_key="pathfinder:armors-and-shields:h65qEp22nsyRoeRa",
            state="armor",
        )
        service = CharacterCalculationService(self.repository, self.character_id)
        self.assertEqual(("heavy", "Full Plate"), service.worn_armor_movement())
        self.assertEqual(20, service.movement_results()["land_speed"])
        self.assertEqual(20, service.movement_results()["armor_speed"])

        self.repository.update_movement_profile(
            MovementProfile(self.character_id, land_speed=40, armor_speed=35)
        )
        overridden = CharacterCalculationService(
            self.repository, self.character_id
        ).movement_results()
        # A manual armor-speed value can replace the armor's normal reduction,
        # but it cannot bypass an independently active medium/heavy load.
        self.assertEqual(30, overridden["land_speed"])
        self.assertEqual(30, overridden["armor_speed"])

        self.repository.set_equipment_state(
            self.character_id, armor_id, "stored"
        )
        unarmored = CharacterCalculationService(
            self.repository, self.character_id
        ).movement_results()
        # Removing armor from the worn slot does not remove its weight from
        # the carried inventory; the medium-load reduction therefore remains.
        self.assertEqual(30, unarmored["land_speed"])


if __name__ == "__main__":
    unittest.main()

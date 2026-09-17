import tempfile
import unittest
from pathlib import Path

from app.database import CharacterRepository
from app.services.character_calculations import CharacterCalculationService
from app.skill_rank_rules import martial_granted_skill_ranks


class SkillRankRuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Associated Skills", "Spheres")
        self.repository.add_class_level(
            self.character_id, "Conscript", 10, "Full", "Good", "Poor", "Poor",
            hit_die=10, hp_gained=60,
        )

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def add(self, name: str, sphere: str, category: str = "Talent", choice: str = "") -> None:
        key_name = name.casefold().replace(" ", "-")
        self.repository.add_martial_talent(
            self.character_id,
            name,
            sphere,
            "Base Sphere" if category == "Base Sphere" else "Talent",
            catalog_key=f"{sphere.casefold()}:{'base' if category == 'Base Sphere' else 'talent:' + key_name}",
            catalog_category=category,
            choice=choice,
        )

    def grants(self) -> dict[str, int]:
        return martial_granted_skill_ranks(
            self.repository.list_martial_talents(self.character_id), 10
        )

    def test_base_and_explicit_talent_grants_share_one_projection(self) -> None:
        self.add("Fencing Sphere", "Fencing", "Base Sphere")
        self.add("Read Foe", "Fencing")

        self.assertEqual(10, self.grants()["bluff"])
        self.assertEqual(10, self.grants()["sense_motive"])
        ranks = CharacterCalculationService(
            self.repository, self.character_id
        ).effective_skill_ranks()
        self.assertEqual(10, ranks["bluff"])
        self.assertEqual(10, ranks["sense_motive"])

    def test_drawback_substitutes_the_associated_skill(self) -> None:
        self.add("Warleader Sphere", "Warleader", "Base Sphere")
        self.repository.add_martial_talent(
            self.character_id,
            "Conductor [High. HB]",
            "Warleader",
            "Drawback",
            catalog_key="warleader:drawback:conductor-high-hb",
            catalog_category="Drawback",
        )

        self.assertNotIn("diplomacy", self.grants())
        self.assertEqual(5, self.grants()["perform"])

    def test_beastmastery_package_controls_rank_target(self) -> None:
        self.add("Beastmastery Sphere", "Beastmastery", "Base Sphere", "Ride")
        self.assertEqual({"ride": 5}, self.grants())


if __name__ == "__main__":
    unittest.main()

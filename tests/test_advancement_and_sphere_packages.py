import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.content import martial_entries
from app.database import CharacterRepository
from app.models import AdvancementAdjustment, CharacterDetails, RaceTraitChoice
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.dialogs import MartialTalentCatalogDialog, SphereAcquisitionDialog
from app.sphere_rules import base_sphere_choice_options
from app.services.advancement import character_advancement_budgets
from app.transfer import export_character, import_character


class AdvancementAndSpherePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Adaptive Prodigy", "Spheres")
        self.repository.update_character_details(
            CharacterDetails(self.character_id, race="Human")
        )
        self.repository.update_ability_score(self.character_id, "intelligence", 14)
        self.repository.add_class_level(
            self.character_id, "Prodigy", 5, "3/4", "Poor", "Good", "Good",
            preset_key="prodigy", hit_die=8, hp_gained=30,
        )
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.directory.cleanup()

    def _budget_row(self, name: str) -> int:
        return next(
            row for row in range(self.sheet.advancement_table.rowCount())
            if self.sheet.advancement_table.item(row, 0).text() == name
        )

    def test_automatic_budgets_and_manual_layers_are_saved(self) -> None:
        skill_row = self._budget_row("Skill points")
        feat_row = self._budget_row("Feats")
        talent_row = self._budget_row("Sphere talents")
        self.assertEqual("35", self.sheet.advancement_table.item(skill_row, 1).text())
        self.assertEqual("4", self.sheet.advancement_table.item(feat_row, 1).text())
        self.assertEqual("7", self.sheet.advancement_table.item(talent_row, 1).text())

        self.repository.update_advancement_adjustment(
            AdvancementAdjustment(self.character_id, "talents", 2, None, "GM award")
        )
        self.sheet._refresh_advancement_budgets()
        talent_row = self._budget_row("Sphere talents")
        self.assertEqual("9", self.sheet.advancement_table.item(talent_row, 4).text())
        self.assertEqual(
            "GM award",
            self.repository.list_advancement_adjustments(self.character_id)["talents"].note,
        )
        export_path = Path(self.directory.name) / "adaptive.character.json"
        export_character(self.repository, self.character_id, export_path)
        imported_id = import_character(self.repository, export_path)
        imported = self.repository.list_advancement_adjustments(imported_id)["talents"]
        self.assertEqual((2, None, "GM award"), (
            imported.adjustment, imported.override_total, imported.note,
        ))

    def test_class_granted_feats_do_not_spend_general_feat_slots(self) -> None:
        self.repository.add_feat(
            self.character_id,
            "Granted Teamwork Feat",
            catalog_category="Class Granted · Inquisitor Teamwork · Teamwork",
        )
        self.repository.add_feat(self.character_id, "Ordinary Feat")
        feats = next(
            item for item in character_advancement_budgets(
                self.repository, self.character_id
            )
            if item.key == "feats"
        )
        self.assertEqual(1, feats.used)

    def test_dual_talent_removes_human_bonus_feat_and_skilled_budgets(self) -> None:
        trait_key = "race-alt-trait:human:dual-talent"
        self.repository.update_character_details(CharacterDetails(
            self.character_id,
            race="Human",
            race_key="human",
            race_alternate_trait_keys=(trait_key,),
            race_trait_choices=(RaceTraitChoice(
                trait_key, "ability_scores", ("strength", "dexterity")
            ),),
        ))
        budgets = {
            item.key: item for item in character_advancement_budgets(
                self.repository, self.character_id
            )
        }
        self.assertEqual(30, budgets["skill_points"].automatic)
        self.assertEqual(3, budgets["feats"].automatic)

    def test_athletics_starting_package_is_saved_projected_and_enforced(self) -> None:
        dialog = SphereAcquisitionDialog(set(), self.sheet, fixed_sphere="Athletics", sphere_kind="martial")
        self.assertEqual(("Climb", "Fly", "Leap", "Run", "Swim"), tuple(
            dialog.base_choice.itemText(index) for index in range(dialog.base_choice.count())
        ))
        dialog.close()

        self.sheet._acquire_martial_sphere("Athletics", base_choice="Leap")
        self.sheet._martial_talents_changed()
        base = next(
            item for item in self.repository.list_martial_talents(self.character_id)
            if item.catalog_category == "Base Sphere" and item.sphere == "Athletics"
        )
        self.assertEqual("Leap", base.choice)
        displayed = {
            self.sheet.martial_talent_table.item(row, 0).text()
            for row in range(self.sheet.martial_talent_table.rowCount())
        }
        self.assertIn("Coordinated Movement — Leap", displayed)
        self.assertIn("Athletics Package: Leap — Leap", displayed)

        climb = next(
            entry for entry in martial_entries("Athletics")
            if entry["category"] == "Climb Talent"
        )
        leap = next(
            entry for entry in martial_entries("Athletics")
            if entry["category"] == "Leap Talent"
        )
        with self.assertRaisesRegex(ValueError, "requires the Climb package"):
            self.sheet._add_catalog_martial_entry(climb)
        self.assertTrue(self.sheet._add_catalog_martial_entry(leap))

        browser = MartialTalentCatalogDialog(
            self.repository.list_martial_talents(self.character_id), self.sheet
        )
        self.assertFalse(browser._entry_selectable(climb))
        browser.close()

    def test_limited_athleticism_removes_the_starting_package(self) -> None:
        drawback = next(
            entry for entry in martial_entries("Athletics")
            if entry["name"] == "Limited Athleticism"
        )
        self.sheet._acquire_martial_sphere(
            "Athletics", ((drawback["key"], ""),), base_choice="Run"
        )
        base = next(
            item for item in self.repository.list_martial_talents(self.character_id)
            if item.catalog_category == "Base Sphere"
        )
        self.assertEqual("", base.choice)

    def test_other_package_spheres_and_free_base_talents_use_the_same_choice_hook(self) -> None:
        expected = {
            "Beastmastery": ("Handle Animal", "Ride"),
            "Guardian": ("Challenge", "Patrol"),
            "Leadership": ("Cohort", "Follower"),
            "Tinker": ("Augmentation", "Computation", "Modification", "Transmission", "Transportation"),
        }
        for sphere, options in expected.items():
            self.assertEqual(options, base_sphere_choice_options(sphere, "martial"))

        equipment_choice = base_sphere_choice_options("Equipment", "martial")[0]
        self.sheet._acquire_martial_sphere("Equipment", base_choice=equipment_choice)
        equipment = [
            item for item in self.repository.list_martial_talents(self.character_id)
            if item.sphere == "Equipment"
        ]
        self.assertEqual(equipment_choice, next(
            item.choice for item in equipment if item.catalog_category == "Base Sphere"
        ))
        self.assertIn(equipment_choice, {item.name for item in equipment})


if __name__ == "__main__":
    unittest.main()

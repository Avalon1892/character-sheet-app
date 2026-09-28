import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.content import martial_entries
from app.database import CharacterRepository
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget
from app.ui.dialogs import SphereAcquisitionDialog


class ProdigyIntegratedTechniqueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.temp.name) / "characters.db")
        self.character_id = self.repository.create_character("Prodigy", "Spheres")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.temp.cleanup()

    def test_page_zero_has_parallel_magic_and_martial_drawback_tables(self) -> None:
        self.assertEqual(2, self.sheet.sphere_build_table.columnCount())
        self.assertEqual(2, self.sheet.martial_sphere_build_table.columnCount())
        dialog = SphereAcquisitionDialog(set(), self.sheet, sphere_kind="martial")
        self.assertGreater(dialog.sphere.count(), 0)
        dialog.close()

    def test_martial_sphere_drawbacks_and_integrated_techniques_sync(self) -> None:
        drawbacks = [
            entry for entry in martial_entries("Trap") if entry["category"] == "Drawback"
        ][:2]
        self.sheet._acquire_martial_sphere(
            "Trap", tuple((entry["key"], "") for entry in drawbacks)
        )
        self.sheet._martial_talents_changed()
        records = self.repository.list_martial_talents(self.character_id)
        self.assertEqual(1, sum(item.catalog_category == "Base Sphere" for item in records))
        self.assertEqual(2, sum(item.catalog_category == "Drawback" for item in records))
        options = self.repository.list_sequence_options(self.character_id)
        self.assertIn("Trapped", {item.name for item in options})

    def test_owned_martial_sphere_adds_all_official_options_and_removal_syncs(self) -> None:
        self.sheet._acquire_martial_sphere("Gladiator")
        self.sheet._martial_talents_changed()
        names = {
            item.name for item in self.repository.list_sequence_options(self.character_id)
            if item.sphere == "Gladiator"
        }
        self.assertEqual({"Braggadocio", "Roar", "Scare", "Taunt"}, names)
        related = self.repository.list_martial_talents(self.character_id)
        for item in related:
            if item.sphere == "Gladiator":
                self.repository.delete_martial_talent(self.character_id, item.id)
        self.sheet._martial_talents_changed()
        self.assertFalse(any(item.sphere == "Gladiator" for item in self.repository.list_sequence_options(self.character_id)))

    def test_tech_battery_link_requires_the_battery_talent(self) -> None:
        self.sheet._acquire_martial_sphere("Tech")
        self.sheet._martial_talents_changed()
        names = {item.name for item in self.repository.list_sequence_options(self.character_id)}
        self.assertNotIn("Recharge Tech", names)
        battery = next(entry for entry in martial_entries("Tech") if entry["name"].startswith("Battery"))
        self.sheet._add_catalog_martial_entry(battery)
        self.sheet._martial_talents_changed()
        names = {item.name for item in self.repository.list_sequence_options(self.character_id)}
        self.assertIn("Recharge Tech", names)


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.database import CharacterRepository
from app.models import WORN_SLOTS
from app.services.character_calculations import CharacterCalculationService
from app.transfer import export_character, import_character
from app.ui.refined.sheet import RefinedSheetWidget as CharacterSheetWidget


class WornSlotPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Slot Tester", "Pathfinder 1e")

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _neck_item(self, name: str) -> int:
        return self.repository.add_equipment(
            self.character_id, name, "Gear", 1, 1, True, 0, "untyped", None, "",
            slot="Neck", state="worn",
        )

    def test_default_slots_are_virtual_and_character_catalog_is_editable(self) -> None:
        self.assertEqual(tuple(slot for slot in WORN_SLOTS if slot), self.repository.list_worn_slots(self.character_id))
        self.repository.update_worn_slots(self.character_id, ("Neck", "Tattoo"))
        self.assertEqual(("Neck", "Tattoo"), self.repository.list_worn_slots(self.character_id))

    def test_activating_item_replaces_current_slot_occupant(self) -> None:
        first_id = self._neck_item("First amulet")
        second_id = self._neck_item("Second amulet")
        items = {item.id: item for item in self.repository.list_equipment(self.character_id)}
        self.assertEqual("carried", items[first_id].state)
        self.assertEqual("worn", items[second_id].state)
        self.repository.set_equipment_state(self.character_id, first_id, "worn")
        items = {item.id: item for item in self.repository.list_equipment(self.character_id)}
        self.assertEqual("worn", items[first_id].state)
        self.assertEqual("carried", items[second_id].state)

    def test_removing_slot_detaches_item_without_removing_it_from_inventory(self) -> None:
        item_id = self._neck_item("Amulet")
        slots = tuple(slot for slot in self.repository.list_worn_slots(self.character_id) if slot != "Neck")
        self.repository.update_worn_slots(self.character_id, slots)
        item = next(item for item in self.repository.list_equipment(self.character_id) if item.id == item_id)
        self.assertEqual("", item.slot)
        self.assertEqual("carried", item.state)

    def test_slots_round_trip_with_character_export(self) -> None:
        self.repository.update_worn_slots(self.character_id, ("Neck", "Tattoo"))
        path = Path(self.directory.name) / "slots.character.json"
        export_character(self.repository, self.character_id, path)
        imported = import_character(self.repository, path)
        self.assertEqual(("Neck", "Tattoo"), self.repository.list_worn_slots(imported))


class EncumbranceIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Loaded Hero", "Pathfinder 1e")
        self.repository.update_ability_score(self.character_id, "strength", 10)
        self.repository.update_ability_score(self.character_id, "dexterity", 18)

    def tearDown(self) -> None:
        self.repository.close()
        self.directory.cleanup()

    def _set_weight(self, weight: float) -> CharacterCalculationService:
        self.repository.add_equipment(
            self.character_id, f"Load {weight:g}", "Gear", 1, weight, True,
            0, "untyped", None, "", state="carried",
        )
        return CharacterCalculationService(self.repository, self.character_id)

    def test_medium_load_limits_dex_penalizes_skills_and_reduces_speed(self) -> None:
        service = self._set_weight(40)
        self.assertEqual("Medium", service.encumbrance().load)
        self.assertEqual(3, service.encumbrance().maximum_dexterity)
        self.assertEqual(3, service.armor_check_penalty())
        self.assertEqual(13, service.combat_results()["ac"].total)
        self.assertEqual(20, service.movement_results()["land_speed"])
        self.assertEqual(1, service.skill_result("acrobatics").total)

    def test_heavy_and_overloaded_loads_apply_stricter_movement(self) -> None:
        heavy = self._set_weight(80)
        self.assertEqual("Heavy", heavy.encumbrance().load)
        self.assertEqual(1, heavy.encumbrance().maximum_dexterity)
        self.assertEqual(20, heavy.movement_results()["land_speed"])

        second = self.repository.create_character("Overloaded Hero", "Pathfinder 1e")
        self.repository.update_ability_score(second, "strength", 10)
        self.repository.add_equipment(
            second, "Huge load", "Gear", 1, 150, True, 0, "untyped", None, "",
            state="carried",
        )
        overloaded = CharacterCalculationService(self.repository, second)
        self.assertEqual("Overloaded", overloaded.encumbrance().load)
        self.assertEqual(5, overloaded.movement_results()["land_speed"])


class WornSlotUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.repository = CharacterRepository(Path(self.directory.name) / "characters.db")
        self.character_id = self.repository.create_character("Visible Slots", "Pathfinder 1e")
        self.sheet = CharacterSheetWidget(self.repository)
        self.sheet.load_character(self.character_id)

    def tearDown(self) -> None:
        self.sheet.close()
        self.repository.close()
        self.directory.cleanup()

    def test_worn_table_shows_empty_default_slots(self) -> None:
        expected = tuple(slot for slot in WORN_SLOTS if slot)
        self.assertEqual(len(expected), self.sheet.worn_table.rowCount())
        self.assertEqual(expected[0], self.sheet.worn_table.item(0, 0).text())
        self.assertEqual("Empty", self.sheet.worn_table.item(0, 1).text())


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QDropEvent
from app.database import CharacterRepository
from app.equipment_wearing import EquipmentWearService
from app.item_effects import effective_item_state
from app.inventory_organization import InventoryOrganizationService
from app.ui.equipment_drag import item_mime, dropped_item
from app.ui.equipment_figure import EquipmentFigureDialog
from app.ui.inventory_dialog import InventoryOrganizerDialog

class EquipmentFigureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = CharacterRepository(Path(self.temp.name) / "test.db")
        self.cid = self.repo.create_character("Wear test", "Spheres")
        self.service = EquipmentWearService(self.repo, self.cid)

    def tearDown(self):
        self.app.processEvents()
        self.repo.close()
        self.temp.cleanup()

    def add(self, name="Boots", slot="Feet", category="Gear"):
        return self.repo.add_equipment(self.cid, name, category, 1, 1, False, 0,
                                       "untyped", None, "", slot=slot)

    def state(self, item_id):
        return effective_item_state(next(i for i in self.service.items() if i.id == item_id))

    def test_equip_replace_unequip_and_invalid_slot(self):
        a, b = self.add(), self.add("Other Boots")
        self.service.equip(a, "Feet")
        self.assertEqual("worn", self.state(a))
        self.service.equip(b, "Feet")
        self.assertEqual("carried", self.state(a))
        self.assertEqual("worn", self.state(b))
        writes = self.repo.sqlite_connection.total_changes
        with self.assertRaises(ValueError): self.service.equip(b, "Head")
        self.assertEqual(writes, self.repo.sqlite_connection.total_changes)
        self.service.unequip(b)
        self.assertEqual("stored", self.state(b))

    def test_ring_can_move_between_ring_slots(self):
        ring = self.add("Ring", "Ring (Left)")
        self.service.equip(ring, "Ring (Right)")
        self.assertEqual(ring, self.service.occupants()["Ring (Right)"][0].id)

    def test_equipping_removes_container_placement(self):
        bag = self.add("Bag of Holding, Type I", "Slotless")
        boots = self.add()
        organization = InventoryOrganizationService(self.repo, self.cid)
        organization.move_item(boots, container_equipment_id=bag)
        self.service.equip(boots, "Feet")
        placement = next(p for p in self.repo.list_inventory_placements(self.cid) if p.equipment_id == boots)
        self.assertIsNone(placement.container_equipment_id)

    def test_custom_slots_remain_available(self):
        self.repo.update_worn_slots(self.cid, ("Tattoo",))
        item = self.add("Magic Tattoo", "Tattoo")
        self.service.equip(item, "Tattoo")
        dialog = EquipmentFigureDialog(self.service)
        try:
            self.assertIn("Tattoo", dialog.all_targets)
            self.assertFalse(dialog.all_targets["Tattoo"].icon().isNull())
        finally:
            dialog.close()

    def test_scoped_payload_rejects_other_character(self):
        item = self.add()
        mime = item_mime(item, self.service.scope, True)
        self.assertEqual(item, dropped_item(mime, self.service.scope))
        self.assertIsNone(dropped_item(mime, self.service.scope + "other"))

    def test_slot_hover_icon_and_real_drop(self):
        item = self.add()
        dialog = EquipmentFigureDialog(self.service)
        try:
            target = dialog.figure.targets["Feet"]
            self.assertTrue(target.icon().isNull())
            self.assertIn("Feet", target.toolTip())
            mime = item_mime(item, self.service.scope)
            event = QDropEvent(QPointF(15, 15), Qt.DropAction.MoveAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            target.dropEvent(event)
            self.assertEqual("worn", self.state(item))
            self.assertFalse(target.icon().isNull())
            self.assertIn("Boots", target.toolTip())
            self.assertIs(target, dialog.figure.targets["Feet"])
            dialog.change_equipment(item, "")
            self.assertTrue(target.icon().isNull())
        finally:
            dialog.close()

    def test_inventory_unequip_drop_can_be_undone(self):
        item = self.add()
        self.service.equip(item, "Feet")
        dialog = InventoryOrganizerDialog(InventoryOrganizationService(self.repo, self.cid))
        try:
            dialog._move_unequipped_item(item, "Adventuring Gear", "General")
            self.assertEqual("stored", self.state(item))
            dialog.undo_stack.undo()
            self.assertEqual("worn", self.state(item))
            dialog.undo_stack.redo()
            self.assertEqual("stored", self.state(item))
        finally:
            dialog.close()

if __name__ == "__main__":
    unittest.main()

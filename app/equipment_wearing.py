"""Shared equipment-slot operations, independent of drag/drop or presentation."""
from app.item_effects import effective_item_state
from app.inventory_organization import InventoryOrganizationService

WIELDED_SLOT = "Wielded weapons"

class EquipmentWearService:
    def __init__(self, repository, character_id):
        self.repository, self.character_id = repository, character_id

    @property
    def scope(self):
        return f"{self.repository.database_path.resolve()}|{self.character_id}"

    def slots(self):
        return tuple(dict.fromkeys((*self.repository.list_worn_slots(self.character_id), *self.occupants(), WIELDED_SLOT)))

    def items(self):
        return self.repository.list_equipment(self.character_id)

    def occupants(self):
        result = {}
        for item in self.items():
            state = effective_item_state(item)
            if item.quantity <= 0 or state not in {"worn", "armor", "shield", "wielded"}:
                continue
            slot = WIELDED_SLOT if state == "wielded" else item.slot or (item.category if state in {"armor", "shield"} else "")
            if slot:
                result.setdefault(slot, []).append(item)
        return result

    def validate(self, item_id, slot):
        item = next((item for item in self.items() if item.id == item_id), None)
        if item is None:
            raise ValueError("This item is no longer in this character’s inventory.")
        if item.quantity <= 0:
            raise ValueError("This item has no remaining quantity.")
        if slot not in self.slots():
            raise ValueError("This equipment slot no longer exists.")
        natural = WIELDED_SLOT if item.category == "Weapon" else item.slot or (item.category if item.category in {"Armor", "Shield"} else "")
        ring = natural.startswith("Ring") and slot.startswith("Ring")
        if natural != slot and not ring:
            raise ValueError(f"{item.name} belongs in {natural or 'an assigned item slot'}. Use Edit Item to change its slot.")
        return item

    def equip(self, item_id, slot):
        item = self.validate(item_id, slot)
        # Taking an item out of a container must also restore its carried weight.
        placements = self.repository.list_inventory_placements(self.character_id)
        if any(p.equipment_id == item_id and p.container_equipment_id is not None for p in placements):
            InventoryOrganizationService(self.repository, self.character_id).move_item(item_id)
        state = "wielded" if slot == WIELDED_SLOT else "armor" if item.category == "Armor" else "shield" if item.category == "Shield" else "worn"
        self.repository.update_equipment(
            self.character_id, item.id, item.name, item.category, item.quantity,
            item.weight, True, item.ac_bonus, item.bonus_type, item.max_dex_bonus,
            item.notes, armor_check_penalty=item.armor_check_penalty,
            slot=item.slot if slot == WIELDED_SLOT else slot,
            value_gp=item.value_gp, state=state,
        )

    def unequip(self, item_id):
        if not any(item.id == item_id for item in self.items()):
            raise ValueError("This item is no longer in this character’s inventory.")
        self.repository.set_equipment_equipped(self.character_id, item_id, False)

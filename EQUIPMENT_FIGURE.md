# Equipment figure

The Equipment Figure is a modeless window opened from Inventory & Equipment or
Worn Items. It uses the character's existing items and custom worn-slot list.
No duplicate equipment records or new saved-character schema are introduced.

- `app/equipment_wearing.py`: slot validation, equipment-state changes, replacement,
  and removal from containers. Existing repository item updates preserve item
  configuration, enchantments, and automation.
- `app/ui/equipment_drag.py`: shared character/database-scoped drag payload and
  table adapter. Inventory and Worn Items retain their existing table columns.
- `app/ui/equipment_figure.py`: scalable vector silhouette, slot positions, icons,
  tooltips and the unequip target. Extra custom slots appear in a separate tray.
- `app/ui/inventory_dialog.py`: supports dropping worn equipment back into the
  organizer and restoring its usage state with the existing inventory undo.

To add another anatomical placement, extend `SLOT_POSITIONS` and `slot_icon`.
Do not add equipment rules to the painter. The Wielded weapons target follows
existing weapon-state rules; it does not impose a new hand-occupancy system.
When multiple weapons are wielded, the tooltip lists them and the context menu
can unequip each individually; dragging moves the first listed weapon.

Dragging onto an occupied worn slot replaces the current item using existing
repository behavior. Incompatible destinations and foreign-character drags are
rejected. Unequipping does not delete the item.

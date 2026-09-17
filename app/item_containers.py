"""Inventory-container metadata, ordering, and carried-weight projection.

Container membership is presentation/state data stored by equipment id.  Rules
metadata stays here so the inventory organizer, character sheet, calculations,
and future item views all agree without recognizing names independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.models import EquipmentItem, InventoryPlacement


INVENTORY_CONTAINER_TAG = "inventory_container"
EXTRADIMENSIONAL_STORAGE_TAG = "extradimensional_storage"
CONTENTS_WEIGHT_NORMAL = "normal"
CONTENTS_WEIGHT_IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class ItemContainerRule:
    tags: frozenset[str] = frozenset({INVENTORY_CONTAINER_TAG})
    contents_weight_mode: str = CONTENTS_WEIGHT_NORMAL
    capacity_lb: float | None = None


def _normal(*, capacity_lb: float | None = None) -> ItemContainerRule:
    return ItemContainerRule(capacity_lb=capacity_lb)


def _fixed(*, capacity_lb: float | None = None) -> ItemContainerRule:
    return ItemContainerRule(
        frozenset({INVENTORY_CONTAINER_TAG, EXTRADIMENSIONAL_STORAGE_TAG}),
        CONTENTS_WEIGHT_IGNORED,
        capacity_lb,
    )


# Stable catalog keys are preferred to display-name matching.  Name fallbacks
# below keep imported/custom copies of familiar containers useful.
CONTAINER_RULES_BY_CATALOG_KEY: dict[str, ItemContainerRule] = {
    # Extradimensional storage (fixed carried weight).
    "pathfinder:items:K1PJo4dWwVcYbTp7": _fixed(capacity_lb=250),
    "pathfinder:items:TVl5RSEjnrMAnpbY": _fixed(capacity_lb=500),
    "pathfinder:items:ID7M52CCxshLzAZ6": _fixed(capacity_lb=1000),
    "pathfinder:items:At9EUYmQrLCwIDKg": _fixed(capacity_lb=1500),
    "pathfinder:items:qAbTiB9oqB6D5kWX": _fixed(),
    "pathfinder:items:kpAmMcXbDZKAtNfy": _fixed(),
    "pathfinder:items:WoNxxoOiD7cMiaMs": _fixed(),
    "pathfinder:items:KjehdvYS9zI7rtDV": _fixed(),
    "pathfinder:items:PjbUBvxyqsugkbcf": _fixed(capacity_lb=120),
    "pathfinder:items:gZg86Y4wboOKVU2L": _fixed(),
    # Ordinary storage (contents retain their own carried weight).
    "pathfinder:items:VWbxYdMfiRE9e3aD": _normal(),
    "pathfinder:items:lSCPUK5Ea6R0t4fz": _normal(),
    "pathfinder:items:wKplDpQyKjOanXDM": _normal(),
    "pathfinder:items:O1IuoaVvgX5nAl18": _normal(),
    "pathfinder:items:ak6dxsHgXm8OeSPS": _normal(),
    "pathfinder:items:odkdxsxfhzpdrweb": _normal(),
    "pathfinder:items:inldkkumiyknanfv": _normal(),
    "pathfinder:items:wjvxmolafiegvesl": _normal(),
    "pathfinder:items:AOuUAs1ll081PZVW": _normal(),
    "pathfinder:items:Sn1PHyXBi65NEhcO": _normal(),
    "pathfinder:items:dm72XBYOw8W3VGdU": _normal(),
    "pathfinder:items:fTTDytVT1DpHgmme": _normal(),
    "pathfinder:items:83T9wbfXh3FLa0Da": _normal(),
    "pathfinder:items:utmeueljqhfoiihp": _normal(),
    "pathfinder:items:z96sUnPZfQ2vVISm": _normal(),
    "pathfinder:items:8ZO6zyOGAkf82o6l": _normal(),
    "pathfinder:items:R2btFV7q8JXNdHke": _normal(),
    "pathfinder:items:ufPl21w2dk4QLN68": _normal(),
}


def container_rule(item: EquipmentItem) -> ItemContainerRule | None:
    rule = CONTAINER_RULES_BY_CATALOG_KEY.get(str(item.catalog_key or ""))
    if rule is not None:
        return rule
    name = item.name.strip().casefold()
    if any(token in name for token in (
        "bag of holding", "handy haversack", "efficient quiver", "portable hole"
    )):
        return _fixed()
    if (
        name.startswith("backpack")
        or name.startswith("chest")
        or name.startswith("treasure chest")
        or name in {"barrel", "basket", "belt pouch", "sack", "waist pouch"}
    ):
        return _normal()
    return None


def item_container_tags(item: EquipmentItem) -> frozenset[str]:
    """Return stable machine-readable tags for container-aware features."""

    rule = container_rule(item)
    return rule.tags if rule is not None else frozenset()


def is_inventory_container(item: EquipmentItem) -> bool:
    return INVENTORY_CONTAINER_TAG in item_container_tags(item)


def placement_parent_map(
    placements: Iterable[InventoryPlacement],
) -> dict[int, int]:
    return {
        int(placement.equipment_id): int(placement.container_equipment_id)
        for placement in placements
        if placement.container_equipment_id is not None
    }


def ordered_inventory_items(
    items: Iterable[EquipmentItem], placements: Iterable[InventoryPlacement]
) -> tuple[tuple[EquipmentItem, int | None, int], ...]:
    """Return parents followed by descendants and their visual nesting depth."""

    values = tuple(items)
    by_id = {item.id: item for item in values}
    parents = placement_parent_map(placements)
    children: dict[int, list[EquipmentItem]] = {}
    roots: list[EquipmentItem] = []
    for item in values:
        parent_id = parents.get(item.id)
        if parent_id in by_id and parent_id != item.id:
            children.setdefault(parent_id, []).append(item)
        else:
            roots.append(item)

    def sort_key(item: EquipmentItem) -> tuple[str, int]:
        return item.name.casefold(), item.id

    result: list[tuple[EquipmentItem, int | None, int]] = []
    visited: set[int] = set()

    def append(item: EquipmentItem, parent_id: int | None, depth: int) -> None:
        if item.id in visited:
            return
        visited.add(item.id)
        result.append((item, parent_id, depth))
        for child in sorted(children.get(item.id, ()), key=sort_key):
            append(child, item.id, depth + 1)

    for root in roots:
        append(root, None, 0)
    # Corrupt/cyclic legacy data remains visible instead of disappearing.
    for item in values:
        if item.id not in visited:
            append(item, None, 0)
    return tuple(result)


def contained_weight(
    container_id: int,
    items: Iterable[EquipmentItem],
    placements: Iterable[InventoryPlacement],
) -> float:
    parents = placement_parent_map(placements)
    return sum(
        float(item.weight) * int(item.quantity)
        for item in items
        if parents.get(item.id) == int(container_id)
    )


def carried_inventory_weight(
    items: Iterable[EquipmentItem], placements: Iterable[InventoryPlacement]
) -> float:
    """Calculate encumbrance weight with fixed-weight storage applied once."""

    values = tuple(items)
    by_id = {item.id: item for item in values}
    parents = placement_parent_map(placements)

    def hidden_by_fixed_container(item_id: int) -> bool:
        seen: set[int] = set()
        parent_id = parents.get(item_id)
        while parent_id is not None and parent_id not in seen:
            seen.add(parent_id)
            parent = by_id.get(parent_id)
            if parent is None:
                return False
            rule = container_rule(parent)
            if rule is not None and rule.contents_weight_mode == CONTENTS_WEIGHT_IGNORED:
                return True
            parent_id = parents.get(parent_id)
        return False

    return sum(
        float(item.weight) * int(item.quantity)
        for item in values
        if not hidden_by_fixed_container(item.id)
    )

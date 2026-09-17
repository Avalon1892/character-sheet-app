"""Presentation-only grouping for the optional wide Inventory organizer."""
from __future__ import annotations

from dataclasses import dataclass

from app.content import item_entry
from app.models import (
    EquipmentItem,
    InventoryCustomGroup,
    InventoryPlacement,
)
from app.item_containers import (
    container_rule,
    contained_weight,
    is_inventory_container,
    item_container_tags,
)


DEFAULT_SUBCATEGORY = "General"
CATEGORY_ORDER = (
    "Weapons",
    "Armor",
    "Shields",
    "Adventuring Gear",
    "Alchemical Items",
    "Tools & Skill Kits",
    "Clothing",
    "Food & Drink",
    "Animals & Mounts",
    "Animal Gear",
    "Consumables",
    "Magic Items",
    "Technology",
    "Other",
)


@dataclass(frozen=True, slots=True)
class InventoryOrganizationSnapshot:
    placements: tuple[InventoryPlacement, ...]
    custom_groups: tuple[InventoryCustomGroup, ...]


@dataclass(frozen=True, slots=True)
class OrganizedInventoryItem:
    item: EquipmentItem
    category: str
    subcategory: str
    description: str
    container_equipment_id: int | None = None

    @property
    def searchable_text(self) -> str:
        return " ".join(
            (
                self.item.name,
                self.category,
                self.subcategory,
                self.item.notes,
                self.description,
            )
        ).casefold()


@dataclass(frozen=True, slots=True)
class InventoryGroup:
    category: str
    subcategories: tuple[tuple[str, tuple[OrganizedInventoryItem, ...]], ...]
    custom: bool = False


@dataclass(frozen=True, slots=True)
class InventoryContainerGroup:
    """One item-backed over-category with ordinary categories nested inside."""

    container: OrganizedInventoryItem
    categories: tuple[InventoryGroup, ...]
    tags: frozenset[str]
    contents_weight: float
    capacity_lb: float | None = None


def _clean_subcategory(value: object) -> str:
    return str(value or "").strip() or DEFAULT_SUBCATEGORY


def automatic_inventory_group(item: EquipmentItem) -> tuple[str, str]:
    """Resolve one stable user-facing group from saved and catalog metadata."""

    entry = item_entry(item.catalog_key) if item.catalog_key else None
    family = str((entry or {}).get("family") or "").strip()
    category = str((entry or {}).get("category") or "").strip()
    subcategory = _clean_subcategory((entry or {}).get("subcategory"))
    folded_family = family.casefold()
    folded_category = category.casefold()

    if family == "Armor & Shields":
        if folded_category.startswith("armor"):
            armor_class = category.partition(",")[2].strip() or "Other Armor"
            return "Armor", armor_class
        return "Shields", subcategory if subcategory != "Armor" else "Shields"
    if family == "Weapons & Ammunition":
        labels = (
            ("simple", "Simple"),
            ("martial", "Martial"),
            ("exotic", "Exotic"),
            ("firearm", "Firearms"),
            ("siege", "Siege"),
            ("ammunition", "Ammunition"),
            ("magic", "Magic"),
        )
        return "Weapons", next(
            (label for token, label in labels if token in folded_category),
            subcategory,
        )
    if family == "Mundane Equipment":
        mundane = {
            "adventuring gear": "Adventuring Gear",
            "alchemical items": "Alchemical Items",
            "tools and skill kits": "Tools & Skill Kits",
            "clothing": "Clothing",
            "food and drink": "Food & Drink",
            "animals and mounts": "Animals & Mounts",
            "animal gear": "Animal Gear",
            "material components": "Consumables",
            "herbs": "Consumables",
            "mundane equipment": "Adventuring Gear",
        }
        return mundane.get(folded_category, "Adventuring Gear"), subcategory
    if family == "Technology":
        return "Technology", category or subcategory
    if family:
        # Spheres-specific item families remain recognizable rather than being
        # collapsed into a vague Other column.
        if family == "Magic Items":
            return "Magic Items", subcategory
        return family, subcategory

    fallback = {
        "Weapon": ("Weapons", "Other Weapons"),
        "Armor": ("Armor", "Other Armor"),
        "Shield": ("Shields", "Other Shields"),
        "Consumable": ("Consumables", DEFAULT_SUBCATEGORY),
        "Gear": ("Adventuring Gear", DEFAULT_SUBCATEGORY),
    }
    return fallback.get(item.category, ("Other", item.category or DEFAULT_SUBCATEGORY))


class InventoryOrganizationService:
    """Project grouping and persist only explicit user organization choices."""

    def __init__(self, repository, character_id: int) -> None:
        self.repository = repository
        self.character_id = character_id

    def snapshot(self) -> InventoryOrganizationSnapshot:
        return InventoryOrganizationSnapshot(
            self.repository.list_inventory_placements(self.character_id),
            self.repository.list_inventory_custom_groups(self.character_id),
        )

    def apply_snapshot(self, snapshot: InventoryOrganizationSnapshot) -> None:
        self.repository.replace_inventory_organization(
            self.character_id, snapshot.placements, snapshot.custom_groups
        )

    def move_item(
        self,
        equipment_id: int,
        category: str = "",
        subcategory: str = DEFAULT_SUBCATEGORY,
        container_equipment_id: int | None = None,
    ) -> None:
        snapshot = self.snapshot()
        equipment = {
            item.id: item for item in self.repository.list_equipment(self.character_id)
        }
        moving = equipment.get(int(equipment_id))
        if moving is None:
            raise ValueError("That inventory item no longer exists.")
        if container_equipment_id is not None:
            container = equipment.get(int(container_equipment_id))
            if container is None or not is_inventory_container(container):
                raise ValueError("Items can only be placed inside an inventory container.")
            if moving.id == container.id:
                raise ValueError("An item cannot contain itself.")
        existing = next(
            (item for item in snapshot.placements if item.equipment_id == equipment_id),
            None,
        )
        if not category.strip():
            if existing is not None:
                category, subcategory = existing.category, existing.subcategory
            else:
                category, subcategory = automatic_inventory_group(moving)
        category = category.strip()
        subcategory = _clean_subcategory(subcategory)
        placements = [
            item for item in snapshot.placements if item.equipment_id != equipment_id
        ]
        next_order = 1 + max(
            (
                item.sort_order
                for item in placements
                if item.category.casefold() == category.casefold()
                and item.subcategory.casefold() == subcategory.casefold()
                and item.container_equipment_id == container_equipment_id
            ),
            default=-1,
        )
        placements.append(
            InventoryPlacement(
                int(equipment_id),
                category.strip(),
                subcategory,
                next_order,
                container_equipment_id,
            )
        )
        self.repository.replace_inventory_organization(
            self.character_id, placements, snapshot.custom_groups
        )

    def add_custom_group(
        self, category: str, subcategory: str = DEFAULT_SUBCATEGORY
    ) -> None:
        category = category.strip()
        subcategory = _clean_subcategory(subcategory)
        if not category:
            raise ValueError("A custom inventory category needs a name.")
        snapshot = self.snapshot()
        if any(
            item.category.casefold() == category.casefold()
            and item.subcategory.casefold() == subcategory.casefold()
            for item in snapshot.custom_groups
        ):
            raise ValueError("That custom inventory group already exists.")
        groups = (*snapshot.custom_groups, InventoryCustomGroup(
            category, subcategory, len(snapshot.custom_groups)
        ))
        self.repository.replace_inventory_organization(
            self.character_id, snapshot.placements, groups
        )

    def reset_item(self, equipment_id: int) -> None:
        """Return one item to catalog-driven placement without resetting other groups."""

        snapshot = self.snapshot()
        placements = tuple(
            placement
            for placement in snapshot.placements
            if placement.equipment_id != int(equipment_id)
        )
        self.repository.replace_inventory_organization(
            self.character_id, placements, snapshot.custom_groups
        )

    def reset(self) -> None:
        self.repository.reset_inventory_organization(self.character_id)

    def groups(self, query: str = "") -> tuple[InventoryGroup, ...]:
        placement_map = {
            item.equipment_id: item
            for item in self.repository.list_inventory_placements(self.character_id)
        }
        custom_groups = self.repository.list_inventory_custom_groups(self.character_id)
        custom_keys = {
            (group.category.casefold(), group.subcategory.casefold())
            for group in custom_groups
        }
        grouped: dict[str, dict[str, list[OrganizedInventoryItem]]] = {}
        equipment = tuple(self.repository.list_equipment(self.character_id))
        equipment_by_id = {item.id: item for item in equipment}
        for item in equipment:
            entry = item_entry(item.catalog_key) if item.catalog_key else None
            description = str((entry or {}).get("description") or item.notes)
            placement = placement_map.get(item.id)
            category, subcategory = (
                (placement.category, placement.subcategory)
                if placement is not None
                else automatic_inventory_group(item)
            )
            parent_id = (
                placement.container_equipment_id
                if placement is not None
                and placement.container_equipment_id in equipment_by_id
                and is_inventory_container(
                    equipment_by_id[placement.container_equipment_id]
                )
                else None
            )
            organized = OrganizedInventoryItem(
                item,
                category,
                _clean_subcategory(subcategory),
                description,
                parent_id,
            )
            if organized.container_equipment_id is not None:
                continue
            if query and query.casefold() not in organized.searchable_text:
                continue
            grouped.setdefault(category, {}).setdefault(
                organized.subcategory, []
            ).append(organized)

        # Empty built-in groups stay hidden. Empty custom groups remain as the
        # drop target the user just created, but disappear while filtering.
        if not query:
            for custom in custom_groups:
                grouped.setdefault(custom.category, {}).setdefault(
                    custom.subcategory, []
                )

        priority = {name.casefold(): index for index, name in enumerate(CATEGORY_ORDER)}
        custom_order = {
            group.category.casefold(): group.sort_order for group in custom_groups
        }

        def category_key(name: str) -> tuple[int, int, str]:
            folded = name.casefold()
            if folded in priority:
                return (0, priority[folded], folded)
            if folded in custom_order:
                return (2, custom_order[folded], folded)
            return (1, 0, folded)

        result = []
        for category in sorted(grouped, key=category_key):
            subcategories = tuple(
                (
                    subcategory,
                    tuple(
                        sorted(
                            items,
                            key=lambda value: (
                                placement_map.get(
                                    value.item.id,
                                    InventoryPlacement(value.item.id, "", "", 0),
                                ).sort_order,
                                value.item.name.casefold(),
                            ),
                        )
                    ),
                )
                for subcategory, items in sorted(
                    grouped[category].items(), key=lambda value: value[0].casefold()
                )
            )
            result.append(
                InventoryGroup(
                    category,
                    subcategories,
                    any(key[0] == category.casefold() for key in custom_keys),
                )
            )
        return tuple(result)

    def container_groups(
        self, query: str = ""
    ) -> tuple[InventoryContainerGroup, ...]:
        """Project item-backed over-categories without flattening child groups."""

        items = tuple(self.repository.list_equipment(self.character_id))
        by_id = {item.id: item for item in items}
        placements = self.repository.list_inventory_placements(self.character_id)
        placement_map = {item.equipment_id: item for item in placements}
        grouped: dict[int, dict[str, dict[str, list[OrganizedInventoryItem]]]] = {}
        descriptions: dict[int, str] = {}
        for item in items:
            entry = item_entry(item.catalog_key) if item.catalog_key else None
            descriptions[item.id] = str((entry or {}).get("description") or item.notes)
            placement = placement_map.get(item.id)
            parent_id = placement.container_equipment_id if placement is not None else None
            if parent_id is None or parent_id not in by_id:
                continue
            category, subcategory = (
                (placement.category, placement.subcategory)
                if placement is not None else automatic_inventory_group(item)
            )
            organized = OrganizedInventoryItem(
                item,
                category,
                _clean_subcategory(subcategory),
                descriptions[item.id],
                parent_id,
            )
            if query and query.casefold() not in organized.searchable_text:
                continue
            grouped.setdefault(parent_id, {}).setdefault(category, {}).setdefault(
                organized.subcategory, []
            ).append(organized)

        priority = {name.casefold(): index for index, name in enumerate(CATEGORY_ORDER)}
        result: list[InventoryContainerGroup] = []
        for container in items:
            if not is_inventory_container(container):
                continue
            container_description = descriptions[container.id]
            container_grouping = grouped.get(container.id, {})
            container_search = " ".join(
                (container.name, container.notes, container_description)
            ).casefold()
            if query and query.casefold() not in container_search and not container_grouping:
                continue
            container_category, container_subcategory = automatic_inventory_group(container)
            organized_container = OrganizedInventoryItem(
                container,
                container_category,
                container_subcategory,
                container_description,
            )
            categories: list[InventoryGroup] = []
            for category in sorted(
                container_grouping,
                key=lambda value: (
                    priority.get(value.casefold(), len(priority)), value.casefold()
                ),
            ):
                subcategories = tuple(
                    (
                        subcategory,
                        tuple(sorted(values, key=lambda value: value.item.name.casefold())),
                    )
                    for subcategory, values in sorted(
                        container_grouping[category].items(),
                        key=lambda value: value[0].casefold(),
                    )
                )
                categories.append(InventoryGroup(category, subcategories))
            rule = container_rule(container)
            result.append(
                InventoryContainerGroup(
                    organized_container,
                    tuple(categories),
                    item_container_tags(container),
                    contained_weight(container.id, items, placements),
                    rule.capacity_lb if rule is not None else None,
                )
            )
        return tuple(result)

    def contents(self, container_equipment_id: int) -> tuple[OrganizedInventoryItem, ...]:
        return tuple(
            item
            for group in self.container_groups()
            if group.container.item.id == int(container_equipment_id)
            for category in group.categories
            for _subcategory, items in category.subcategories
            for item in items
        )

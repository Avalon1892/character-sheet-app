from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable

from PySide6.QtWidgets import QWidget

from app.building_blocks.schemas import BlockDefinition, CellDefinition


RuntimeCellFactory = Callable[[QWidget, CellDefinition, dict[str, Any]], QWidget]
ConfigValidator = Callable[[dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class CellTypeDescriptor:
    key: str
    name: str
    minimum_width: int
    minimum_height: int
    supports_binding: bool = False
    supports_formula: bool = False
    supports_action: bool = False
    runtime_factory: RuntimeCellFactory | None = None
    validate_config: ConfigValidator | None = None


class BlockRegistry:
    """Process-wide registry; future modules register without editing catalogue UI."""

    def __init__(self) -> None:
        self._definitions: dict[str, BlockDefinition] = {}

    def register(self, definition: BlockDefinition) -> None:
        if not definition.key or definition.key in self._definitions:
            raise ValueError(f"Duplicate or empty block key: {definition.key}")
        self._definitions[definition.key] = definition

    def get(self, key: str) -> BlockDefinition | None:
        return self._definitions.get(key)

    def all(self) -> tuple[BlockDefinition, ...]:
        return tuple(
            sorted(self._definitions.values(), key=lambda item: (item.category.casefold(), item.name.casefold()))
        )


class CellTypeRegistry:
    def __init__(self) -> None:
        self._items: dict[str, CellTypeDescriptor] = {}

    def register(self, item: CellTypeDescriptor) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.:-]*", item.key):
            raise ValueError(f"Invalid cell type key: {item.key}")
        if item.key in self._items:
            raise ValueError(f"Duplicate cell type: {item.key}")
        self._items[item.key] = item

    def unregister(self, key: str) -> None:
        """Remove a dynamically registered type (primarily for plugin teardown/tests)."""
        self._items.pop(key, None)

    def get(self, key: str) -> CellTypeDescriptor:
        try:
            return self._items[key]
        except KeyError:
            raise ValueError(f"Unknown cell type: {key}") from None

    def all(self) -> tuple[CellTypeDescriptor, ...]:
        return tuple(self._items.values())


CELL_TYPE_REGISTRY = CellTypeRegistry()
for descriptor in (
    CellTypeDescriptor("label", "Static text / label", 50, 22),
    CellTypeDescriptor("text", "Editable text", 80, 28, supports_binding=True),
    CellTypeDescriptor("number", "Editable number", 60, 28, supports_binding=True),
    CellTypeDescriptor("formula", "Formula / calculated value", 70, 28, supports_formula=True),
    CellTypeDescriptor("checkbox", "Checkbox", 70, 24, supports_binding=True),
    CellTypeDescriptor("dropdown", "Dropdown list", 90, 28, supports_binding=True),
    CellTypeDescriptor("button", "Button / action", 80, 28, supports_action=True),
    CellTypeDescriptor("table", "Table / repeatable rows", 180, 90, supports_binding=True),
):
    CELL_TYPE_REGISTRY.register(descriptor)


BUILTIN_BLOCK_REGISTRY = BlockRegistry()


def register_builtin_blocks() -> BlockRegistry:
    if BUILTIN_BLOCK_REGISTRY.all():
        return BUILTIN_BLOCK_REGISTRY
    specs = (
        ("overview", "Character & Class Build", "Character", "build"),
        ("favored_class_bonuses", "Favored Class Bonuses", "Character", "build"),
        ("advancement_budgets", "Advancement Budgets", "Character", "build"),
        ("base_abilities", "Base Ability Scores", "Character", "build"),
        ("custom_trackers", "Custom Values & Pools", "Resources", "build"),
        ("traditional_casting", "Traditional Spellcasting", "Magic", "build"),
        ("casting_profile", "Casting Profile", "Magic", "build"),
        ("sphere_drawbacks", "Spheres & Drawbacks", "Spheres", "build"),
        ("proficiencies", "Proficiencies", "Character", "build"),
        ("inquisitor_features", "Class Systems & Choices", "Classes", "core"),
        ("special_abilities", "Special Abilities", "Character", "core"),
        ("classic_statistics", "Classic Statistics", "Combat", "core"),
        ("movement", "Movement", "Character", "core"),
        ("combat_defense", "Combat & Defense", "Combat", "core", False),
        ("abilities", "Abilities", "Character", "core", False),
        ("imbue", "Prodigy Imbue", "Prodigy", "core"),
        ("skills", "Skills", "Character", "core"),
        ("conditions", "Conditions & Effects", "Combat", "core"),
        ("attacks", "Attacks", "Combat", "core"),
        ("martial_focus", "Martial Focus", "Spheres", "core"),
        ("spell_points", "Spell Points", "Magic", "core"),
        ("prodigy_sequence", "Prodigy Sequence", "Prodigy", "core"),
        ("equipment", "Equipment", "Inventory", "inventory"),
        ("worn_items", "Worn Items", "Inventory", "inventory"),
        ("optional_traditions", "Crafting & Tinker Traditions", "Character", "build"),
        ("traditions", "Casting & Martial Traditions", "Character", "build"),
        ("load", "Load & Lift", "Inventory", "inventory"),
        ("currency", "Currency", "Inventory", "inventory"),
        ("crafting", "Crafting", "Crafting", "crafting"),
        ("martial_talents", "Martial Talents", "Talents", "inventory"),
        ("moldable_talents", "Moldable Talents", "Talents", "inventory"),
        ("feats", "Feats", "Features", "inventory"),
        ("traits", "Traits", "Features", "inventory"),
        ("feature_details", "Selected Feature Details", "Features", "inventory"),
        ("casting_play", "Spherecasting", "Magic", "magic"),
        ("spell_level_overview", "Spell Level Overview", "Magic", "magic"),
        ("spells_known", "Spells Known", "Magic", "magic"),
        ("spells_prepared", "Spells Prepared", "Magic", "magic"),
        ("magic_talents", "Magic Spheres", "Magic", "magic"),
        ("magic_ranges", "Magic Ranges", "Magic", "magic"),
        ("animal_identity", "Animal Companion", "Companion", "companion"),
        ("animal_statistics", "Companion Statistics", "Companion", "companion"),
        ("animal_training", "Companion Feats & Tricks", "Companion", "companion"),
    )
    for spec in specs:
        section_key, name, category, tab = spec[:4]
        default_visible = bool(spec[4]) if len(spec) > 4 else True
        BUILTIN_BLOCK_REGISTRY.register(
            BlockDefinition(
                key=f"builtin:{section_key}",
                name=name,
                category=category,
                description=f"Built-in live character-sheet block for {name}.",
                builtin=True,
                section_key=section_key,
                default_tab=tab,
                default_visible=default_visible,
            )
        )
    return BUILTIN_BLOCK_REGISTRY

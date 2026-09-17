from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = 1
CELL_TYPES = (
    "label",
    "text",
    "number",
    "formula",
    "checkbox",
    "dropdown",
    "button",
    "table",
)


@dataclass(frozen=True, slots=True)
class CellDefinition:
    key: str
    cell_type: str
    label: str = ""
    x: int = 12
    y: int = 12
    width: int = 160
    height: int = 38
    binding: str = ""
    formula: str = ""
    action: str = ""
    group_id: str = ""
    anchored: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CellDefinition:
        return cls(
            key=str(value.get("key", "")),
            cell_type=str(value.get("cell_type", "label")),
            label=str(value.get("label", "")),
            x=int(value.get("x", 12)),
            y=int(value.get("y", 12)),
            width=int(value.get("width", 160)),
            height=int(value.get("height", 38)),
            binding=str(value.get("binding", "")),
            formula=str(value.get("formula", "")),
            action=str(value.get("action", "")),
            group_id=str(value.get("group_id", "")),
            anchored=bool(value.get("anchored", True)),
            config=dict(value.get("config") or {}),
            style=dict(value.get("style") or {}),
        )


@dataclass(frozen=True, slots=True)
class BlockDefinition:
    key: str
    name: str
    category: str
    description: str = ""
    builtin: bool = False
    version: int = SCHEMA_VERSION
    width: int = 520
    height: int = 300
    section_key: str = ""
    default_tab: str = "build"
    default_visible: bool = True
    cells: tuple[CellDefinition, ...] = ()
    style: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["cells"] = [cell.to_dict() for cell in self.cells]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> BlockDefinition:
        return cls(
            key=str(value.get("key", "")),
            name=str(value.get("name", "Untitled Block")),
            category=str(value.get("category", "Custom")),
            description=str(value.get("description", "")),
            builtin=bool(value.get("builtin", False)),
            version=int(value.get("version", SCHEMA_VERSION)),
            width=max(160, int(value.get("width", 520))),
            height=max(90, int(value.get("height", 300))),
            section_key=str(value.get("section_key", "")),
            default_tab=str(value.get("default_tab", "build")),
            default_visible=bool(value.get("default_visible", True)),
            cells=tuple(
                CellDefinition.from_dict(cell) for cell in value.get("cells", ())
            ),
            style=dict(value.get("style") or {}),
        )


@dataclass(frozen=True, slots=True)
class SheetTab:
    id: int
    character_id: int
    key: str
    name: str
    order: int
    visible: bool = True
    builtin: bool = False


@dataclass(frozen=True, slots=True)
class BlockInstance:
    id: int
    character_id: int
    instance_key: str
    template_key: str
    tab_key: str
    x: int = 12
    y: int = 12
    width: int = 520
    height: int = 300
    z_order: int = 0
    visible: bool = True
    style: dict[str, Any] = field(default_factory=dict)
    template_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CellOverride:
    id: int
    block_instance_id: int
    cell_key: str
    x: int
    y: int
    width: int
    height: int
    visible: bool = True
    anchored: bool = True
    group_id: str = ""
    binding: str = ""
    formula: str = ""
    action: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)

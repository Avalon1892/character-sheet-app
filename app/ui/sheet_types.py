"""Declarative registry for interchangeable character-sheet presentations."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from PySide6.QtWidgets import QWidget

from app.database import CharacterRepository


@dataclass(frozen=True, slots=True)
class SheetTypeDescriptor:
    key: str
    label: str
    description: str
    factory_path: str
    supports_customization: bool = False

    def create(self, repository: CharacterRepository) -> QWidget:
        module_name, class_name = self.factory_path.split(":", 1)
        widget_class = getattr(import_module(module_name), class_name)
        return widget_class(repository)


SHEET_TYPE_REGISTRY = {
    descriptor.key: descriptor
    for descriptor in (
        SheetTypeDescriptor(
            "refined", "Refined Sheet",
            "A play-focused, independently customizable presentation.",
            "app.ui.refined.sheet:RefinedSheetWidget",
            supports_customization=True,
        ),
    )
}

DEFAULT_SHEET_TYPE = "refined"


def normalize_sheet_type(value: str) -> str:
    return value if value in SHEET_TYPE_REGISTRY else DEFAULT_SHEET_TYPE


def sheet_type_descriptors() -> tuple[SheetTypeDescriptor, ...]:
    return tuple(SHEET_TYPE_REGISTRY.values())

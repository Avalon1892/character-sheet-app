"""Extension registry for the fixed, capability-aware Ultra Sheet.

Ultra is deliberately not a Building Blocks canvas.  It still follows the same
Lego principle: a class subsystem contributes one descriptor and one panel,
while the page composer remains unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from PySide6.QtWidgets import QWidget


class UltraPanel(Protocol):
    """Small contract implemented by every snapshot-backed Ultra panel."""

    def refresh_from_context(self, context: object) -> None: ...


UltraPanelFactory = Callable[[object], QWidget]


@dataclass(frozen=True, slots=True)
class UltraModuleDescriptor:
    key: str
    page: str
    order: int
    factory: UltraPanelFactory
    requires: frozenset[str] = frozenset()
    any_of: frozenset[str] = frozenset()
    full_width: bool = False
    estimated_height: int = 260

    def is_available(self, capabilities: Iterable[str]) -> bool:
        active = frozenset(str(value).strip().casefold() for value in capabilities)
        return self.requires <= active and (not self.any_of or bool(self.any_of & active))


class UltraModuleRegistry:
    """Ordered, copyable registry used by production and extension tests."""

    def __init__(self) -> None:
        self._descriptors: dict[str, UltraModuleDescriptor] = {}

    def register(
        self, descriptor: UltraModuleDescriptor, *, replace: bool = False
    ) -> UltraModuleDescriptor:
        key = descriptor.key.strip().casefold()
        if not key:
            raise ValueError("An Ultra module needs a stable key.")
        if key in self._descriptors and not replace:
            raise ValueError(f"Ultra module already registered: {descriptor.key}")
        self._descriptors[key] = descriptor
        return descriptor

    def unregister(self, key: str) -> None:
        self._descriptors.pop(key.strip().casefold(), None)

    def __contains__(self, key: object) -> bool:
        return (
            isinstance(key, str)
            and key.strip().casefold() in self._descriptors
        )

    def descriptors(self, page: str | None = None) -> tuple[UltraModuleDescriptor, ...]:
        values = self._descriptors.values()
        if page is not None:
            values = (item for item in values if item.page == page)
        return tuple(sorted(values, key=lambda item: (item.page, item.order, item.key)))

    def copy(self) -> "UltraModuleRegistry":
        result = UltraModuleRegistry()
        result._descriptors.update(self._descriptors)
        return result


ULTRA_MODULES = UltraModuleRegistry()


def register_ultra_module(
    descriptor: UltraModuleDescriptor, *, replace: bool = False
) -> UltraModuleDescriptor:
    """Public extension point for future class and Spheres subsystems."""

    return ULTRA_MODULES.register(descriptor, replace=replace)

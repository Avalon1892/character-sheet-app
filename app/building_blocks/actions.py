from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.building_blocks.bindings import BINDINGS
from app.database import CharacterRepository


@dataclass(slots=True)
class ActionContext:
    repository: CharacterRepository
    character_id: int
    config: dict[str, Any]
    callbacks: dict[str, Callable]


@dataclass(frozen=True, slots=True)
class ActionDescriptor:
    key: str
    name: str
    handler: Callable[[ActionContext], None]
    description: str = ""


class ActionRegistry:
    def __init__(self) -> None:
        self._items: dict[str, ActionDescriptor] = {}

    def register(self, descriptor: ActionDescriptor) -> None:
        if not descriptor.key or descriptor.key in self._items:
            raise ValueError(f"Duplicate or empty action: {descriptor.key}")
        self._items[descriptor.key] = descriptor

    def get(self, key: str) -> ActionDescriptor | None:
        return self._items.get(key)

    def all(self) -> tuple[ActionDescriptor, ...]:
        return tuple(sorted(self._items.values(), key=lambda item: item.name.casefold()))

    def execute(self, key: str, context: ActionContext) -> None:
        descriptor = self.get(key)
        if descriptor is None:
            raise ValueError(f"Action is not registered: {key}")
        descriptor.handler(context)


ACTIONS = ActionRegistry()


def _callback(name: str) -> Callable[[ActionContext], None]:
    def invoke(context: ActionContext) -> None:
        callback = context.callbacks.get(name)
        if callback is None:
            raise ValueError(f"Action is unavailable here: {name}")
        callback()
    return invoke


def _adjust_binding(delta: float) -> Callable[[ActionContext], None]:
    def adjust(context: ActionContext) -> None:
        binding = str(context.config.get("binding") or "")
        if not binding:
            raise ValueError("Choose a writable binding for this action.")
        current = float(BINDINGS.resolve(context.repository, context.character_id, binding))
        BINDINGS.write(context.repository, context.character_id, binding, current + delta)
        refresh = context.callbacks.get("refresh")
        if refresh:
            refresh()
    return adjust


for action in (
    ActionDescriptor("full_rest", "Take a Full Rest", _callback("full_rest"), "Runs the character's configured eight-hour rest."),
    ActionDescriptor("open_editor", "Open linked editor", _callback("open_editor"), "Opens the editor registered by the hosting block."),
    ActionDescriptor("increment", "Increase linked value", _adjust_binding(1)),
    ActionDescriptor("decrement", "Decrease linked value", _adjust_binding(-1)),
    ActionDescriptor("spend_resource", "Spend one resource", _adjust_binding(-1)),
    ActionDescriptor("regain_resource", "Regain one resource", _adjust_binding(1)),
):
    ACTIONS.register(action)

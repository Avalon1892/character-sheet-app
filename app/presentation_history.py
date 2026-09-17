from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class PresentationSnapshot:
    character_id: int
    layout: dict[str, str]
    building_blocks: dict
    current_tab: str = ""


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    description: str
    before: PresentationSnapshot
    after: PresentationSnapshot


class PresentationHistory:
    """Bounded undo/redo history for presentation-only sheet operations."""

    def __init__(
        self,
        capture: Callable[[], PresentationSnapshot | None],
        apply: Callable[[PresentationSnapshot], None],
        *,
        limit: int = 100,
    ) -> None:
        self.capture_snapshot = capture
        self.apply_snapshot = apply
        self.limit = max(10, int(limit))
        self._undo: dict[int, list[HistoryEntry]] = {}
        self._redo: dict[int, list[HistoryEntry]] = {}
        self._pending: tuple[str, PresentationSnapshot] | None = None
        self.replaying = False
        self.on_changed: Callable[[], None] = lambda: None

    def begin(self, description: str) -> bool:
        if self.replaying or self._pending is not None:
            return False
        snapshot = self.capture_snapshot()
        if snapshot is None:
            return False
        self._pending = (description.strip() or "Sheet change", snapshot)
        return True

    def commit(self) -> bool:
        if self.replaying or self._pending is None:
            return False
        description, before = self._pending
        self._pending = None
        after = self.capture_snapshot()
        if after is None or after.character_id != before.character_id or after == before:
            return False
        entries = self._undo.setdefault(before.character_id, [])
        entries.append(HistoryEntry(description, before, after))
        del entries[:-self.limit]
        self._redo[before.character_id] = []
        self.on_changed()
        return True

    def cancel(self) -> None:
        self._pending = None

    def discard(self, character_id: int) -> None:
        """Forget presentation history that can no longer be replayed safely."""

        self._undo.pop(character_id, None)
        self._redo.pop(character_id, None)
        if self._pending is not None and self._pending[1].character_id == character_id:
            self._pending = None
        self.on_changed()

    def record(self, description: str, operation: Callable[[], object]) -> object:
        started = self.begin(description)
        try:
            result = operation()
        except Exception:
            if started:
                self.cancel()
            raise
        if started:
            self.commit()
        return result

    def can_undo(self, character_id: int | None) -> bool:
        return bool(character_id is not None and self._undo.get(character_id))

    def can_redo(self, character_id: int | None) -> bool:
        return bool(character_id is not None and self._redo.get(character_id))

    def undo_description(self, character_id: int | None) -> str:
        entries = self._undo.get(character_id or -1, [])
        return entries[-1].description if entries else ""

    def redo_description(self, character_id: int | None) -> str:
        entries = self._redo.get(character_id or -1, [])
        return entries[-1].description if entries else ""

    def undo(self, character_id: int | None) -> bool:
        if not self.can_undo(character_id):
            return False
        self.cancel()
        entry = self._undo[int(character_id)].pop()
        self.replaying = True
        try:
            self.apply_snapshot(entry.before)
        finally:
            self.replaying = False
        self._redo.setdefault(int(character_id), []).append(entry)
        self.on_changed()
        return True

    def redo(self, character_id: int | None) -> bool:
        if not self.can_redo(character_id):
            return False
        self.cancel()
        entry = self._redo[int(character_id)].pop()
        self.replaying = True
        try:
            self.apply_snapshot(entry.after)
        finally:
            self.replaying = False
        self._undo.setdefault(int(character_id), []).append(entry)
        self.on_changed()
        return True

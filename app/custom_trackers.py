from __future__ import annotations

import re
from dataclasses import dataclass

from app.database import CharacterRepository
from app.formulas import (
    DEFAULT_FORMULA_ENGINE,
    FormulaCycleError,
    FormulaError,
    UnknownReferenceError,
)
from app.models import CustomTracker
from app.services.character_calculations import CharacterCalculationService
from app.character_formulas import CharacterFormulaContext, reference_key


def display_number(value: float | None) -> str:
    if value is None:
        return "—"
    rounded = round(value)
    if abs(value - rounded) < 1e-9:
        return str(rounded)
    return f"{value:.2f}".rstrip("0").rstrip(".")


@dataclass(frozen=True, slots=True)
class ResolvedCustomTracker:
    tracker: CustomTracker
    value: float | None
    maximum: float | None
    error: str = ""


class CustomTrackerResolver:
    """Resolves character and tracker references with dependency-cycle protection."""

    def __init__(
        self,
        repository: CharacterRepository,
        character_id: int,
        calculations: CharacterCalculationService | None = None,
    ) -> None:
        self.repository = repository
        self.character_id = character_id
        self.trackers = repository.list_custom_trackers(character_id)
        self.by_key = {tracker.key: tracker for tracker in self.trackers}
        self.context = CharacterFormulaContext(
            calculations
            or CharacterCalculationService(self.repository, self.character_id)
        )
        self.base_values = dict(self.context.values)
        self.cache: dict[str, ResolvedCustomTracker] = {}
        self.stack: list[str] = []

    def resolve_reference(self, path: str) -> float:
        if path in self.base_values:
            return self.base_values[path]
        match = re.fullmatch(
            r"trackers\.([a-z][a-z0-9_]*)\.(value|maximum|current|temporary)", path
        )
        if not match or match.group(1) not in self.by_key:
            raise UnknownReferenceError(f"Unknown value: {path}")
        key, field = match.groups()
        tracker = self.by_key[key]
        if field == "current":
            return tracker.current_value
        if field == "temporary":
            return tracker.temporary_value
        resolved = self.resolve_tracker(key)
        if resolved.error:
            raise FormulaError(f"{tracker.name}: {resolved.error}")
        value = resolved.maximum if field == "maximum" else resolved.value
        if value is None:
            raise FormulaError(f"{tracker.name} has no {field} value.")
        return value

    def resolve_tracker(self, key: str) -> ResolvedCustomTracker:
        if key in self.cache:
            return self.cache[key]
        tracker = self.by_key[key]
        if key in self.stack:
            cycle = " → ".join((*self.stack[self.stack.index(key):], key))
            raise FormulaCycleError(f"Circular tracker formula: {cycle}")
        self.stack.append(key)
        try:
            if tracker.tracker_type == "calculated":
                value = DEFAULT_FORMULA_ENGINE.evaluate(
                    tracker.formula, self.base_values, self.resolve_reference
                )
                resolved = ResolvedCustomTracker(tracker, value, None)
            else:
                maximum = (
                    DEFAULT_FORMULA_ENGINE.evaluate(
                        tracker.formula, self.base_values, self.resolve_reference
                    )
                    if tracker.formula else tracker.manual_maximum
                )
                resolved = ResolvedCustomTracker(tracker, tracker.current_value, maximum)
        except FormulaError as error:
            resolved = ResolvedCustomTracker(
                tracker,
                tracker.current_value if tracker.tracker_type != "calculated" else None,
                tracker.manual_maximum if tracker.tracker_type != "calculated" else None,
                str(error),
            )
        finally:
            self.stack.pop()
        self.cache[key] = resolved
        return resolved

    def resolve_all(self) -> tuple[ResolvedCustomTracker, ...]:
        result = []
        for tracker in self.trackers:
            try:
                result.append(self.resolve_tracker(tracker.key))
            except FormulaError as error:
                resolved = ResolvedCustomTracker(tracker, None, None, str(error))
                self.cache[tracker.key] = resolved
                result.append(resolved)
        return tuple(result)

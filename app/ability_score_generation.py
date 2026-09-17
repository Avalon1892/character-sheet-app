"""Pure ability-score generation helpers used by character creation.

The UI deliberately consumes this registry rather than embedding score arrays
in widgets.  Additional campaign presets can therefore be added without
changing the creator, persistence, or calculation layers.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.models import ABILITY_KEYS


@dataclass(frozen=True, slots=True)
class AbilityArrayPreset:
    key: str
    name: str
    scores: tuple[int, ...]
    description: str

    def default_assignment(self) -> dict[str, int]:
        return dict(zip(ABILITY_KEYS, self.scores, strict=True))


# These are ready-to-use, balanced allocations for the Core Rulebook's named
# point-buy budgets.  They do not replace point buy; they provide a quick array
# assignment for groups that want deterministic starting scores.
ABILITY_ARRAY_PRESETS = (
    AbilityArrayPreset(
        "standard",
        "Standard fantasy · 15 points",
        (15, 14, 13, 12, 10, 8),
        "A balanced player-character array using the standard 15-point budget.",
    ),
    AbilityArrayPreset(
        "high",
        "High fantasy · 20 points",
        (16, 14, 14, 12, 10, 8),
        "A balanced array using the high-fantasy 20-point budget.",
    ),
    AbilityArrayPreset(
        "epic",
        "Epic fantasy · 25 points",
        (16, 15, 14, 13, 12, 8),
        "A balanced array using the epic-fantasy 25-point budget.",
    ),
)

ABILITY_ARRAYS_BY_KEY: Mapping[str, AbilityArrayPreset] = MappingProxyType(
    {preset.key: preset for preset in ABILITY_ARRAY_PRESETS}
)

_POINT_BUY_COSTS = MappingProxyType({
    7: -4,
    8: -2,
    9: -1,
    10: 0,
    11: 1,
    12: 2,
    13: 3,
    14: 5,
    15: 7,
    16: 10,
    17: 13,
    18: 17,
})


def ability_point_buy_cost(scores: Mapping[str, int]) -> int | None:
    """Return the Core Rulebook point-buy total, or ``None`` outside 7–18."""

    values = [int(scores.get(key, 10)) for key in ABILITY_KEYS]
    if any(value not in _POINT_BUY_COSTS for value in values):
        return None
    return sum(_POINT_BUY_COSTS[value] for value in values)


def validate_ability_scores(scores: Mapping[str, int]) -> tuple[str, ...]:
    """Validate a complete set of base (pre-racial) ability scores."""

    missing = [key for key in ABILITY_KEYS if key not in scores]
    errors: list[str] = []
    if missing:
        errors.append("Assign all six ability scores.")
    if any(int(scores.get(key, 10)) < 1 or int(scores.get(key, 10)) > 99 for key in ABILITY_KEYS):
        errors.append("Ability scores must be between 1 and 99.")
    return tuple(errors)


"""PF1e spontaneous spell-slot progressions.

Spontaneous casters expend a shared number of slots for each spell level; they
do not prepare individual spell copies.  Keeping this provider separate from
the UI and persistence makes class/archetype-specific progressions additive.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.prepared_spell_rules import LOW_PREPARED, MED_PREPARED, bonus_spell_slots


@dataclass(frozen=True, slots=True)
class SpontaneousCasterCapacity:
    class_level_id: int
    class_name: str
    class_key: str
    class_level: int
    casting_ability: str
    base_slots: tuple[int, ...]
    bonus_slots: tuple[int, ...]
    total_slots: tuple[int, ...]


# Sorcerer/oracle/psychic nine-level spontaneous progression.  Each row starts
# at 1st-level spells; 0-level spells are at-will and are added as index zero.
HIGH_SPONTANEOUS = (
    (3,), (4,), (5,), (6, 3), (6, 4),
    (6, 5, 3), (6, 6, 4), (6, 6, 5, 3), (6, 6, 6, 4),
    (6, 6, 6, 5, 3), (6, 6, 6, 6, 4), (6, 6, 6, 6, 5, 3),
    (6, 6, 6, 6, 6, 4), (6, 6, 6, 6, 6, 5, 3),
    (6, 6, 6, 6, 6, 6, 4), (6, 6, 6, 6, 6, 6, 5, 3),
    (6, 6, 6, 6, 6, 6, 6, 4), (6, 6, 6, 6, 6, 6, 6, 5, 3),
    (6, 6, 6, 6, 6, 6, 6, 6, 4), (6, 6, 6, 6, 6, 6, 6, 6, 6),
)


def spontaneous_spell_slots(
    class_level: int,
    progression: str,
    ability_modifier: int,
) -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Return ``(base, bonus, total)`` slots indexed by spell level 0-9.

    A printed zero in a class table still unlocks that spell level for bonus
    slots.  Missing columns do not.  Cantrips/orisons are at-will and therefore
    always report zero daily slots.
    """

    level = max(1, min(20, int(class_level)))
    normalized = str(progression).casefold()
    if normalized in {"high", "full"}:
        daily = HIGH_SPONTANEOUS[level - 1]
    elif normalized in {"med", "mid", "medium", "3/4"}:
        daily = MED_PREPARED[level - 1]
    else:
        daily = LOW_PREPARED[level - 1]

    base = (0, *(int(value) for value in daily))
    bonus = (0,) + tuple(
        bonus_spell_slots(ability_modifier, spell_level)
        for spell_level in range(1, len(base))
    )
    total = tuple(base[index] + bonus[index] for index in range(len(base)))
    return base, bonus, total

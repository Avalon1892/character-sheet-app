"""PF1e prepared-spell capacity and validation rules."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreparedCasterCapacity:
    class_level_id: int
    class_name: str
    class_key: str
    class_level: int
    casting_ability: str
    slots: tuple[int, ...]


# Standard 9-level prepared progression used by wizard, cleric, druid, witch,
# shaman, and their unchanged prepared-casting archetypes. Index 0 is cantrips.
HIGH_PREPARED = (
    (3, 1), (4, 2), (4, 2, 1), (4, 3, 2), (4, 3, 2, 1),
    (4, 3, 3, 2), (4, 4, 3, 2, 1), (4, 4, 3, 3, 2),
    (4, 4, 4, 3, 2, 1), (4, 4, 4, 3, 3, 2),
    (4, 4, 4, 4, 3, 2, 1), (4, 4, 4, 4, 3, 3, 2),
    (4, 4, 4, 4, 4, 3, 2, 1), (4, 4, 4, 4, 4, 3, 3, 2),
    (4, 4, 4, 4, 4, 4, 3, 2, 1), (4, 4, 4, 4, 4, 4, 3, 3, 2),
    (4, 4, 4, 4, 4, 4, 4, 3, 2, 1), (4, 4, 4, 4, 4, 4, 4, 3, 3, 2),
    (4, 4, 4, 4, 4, 4, 4, 4, 3, 3), (4, 4, 4, 4, 4, 4, 4, 4, 4, 4),
)

# Six-level progression for extracts and prepared 6-level casters (levels 1-6).
MED_PREPARED = (
    (1,), (2,), (3,), (3, 1), (4, 2), (4, 3), (4, 3, 1),
    (4, 4, 2), (5, 4, 3), (5, 4, 3, 1), (5, 4, 4, 2),
    (5, 5, 4, 3), (5, 5, 4, 3, 1), (5, 5, 4, 4, 2),
    (5, 5, 5, 4, 3), (5, 5, 5, 4, 3, 1), (5, 5, 5, 4, 4, 2),
    (5, 5, 5, 5, 4, 3), (5, 5, 5, 5, 5, 4), (5, 5, 5, 5, 5, 5),
)

# Four-level delayed progression. A zero means only bonus slots are available.
LOW_PREPARED = (
    (), (), (), (0,), (1,), (1,), (1, 0), (1, 1), (2, 1),
    (2, 1, 0), (2, 1, 1), (2, 2, 1), (3, 2, 1, 0), (3, 2, 1, 1),
    (3, 2, 2, 1), (3, 3, 2, 1), (4, 3, 2, 1), (4, 3, 3, 2),
    (4, 4, 3, 3), (4, 4, 4, 4),
)

NO_CANTRIPS = {"alchemist", "investigator", "antipaladin", "paladin", "ranger"}


def _short_key(class_key: str, class_name: str) -> str:
    value = (class_key or class_name).casefold().split(":")[-1]
    return value.replace(" ", "-")


def bonus_spell_slots(ability_modifier: int, spell_level: int) -> int:
    if spell_level <= 0 or ability_modifier < spell_level:
        return 0
    return 1 + (ability_modifier - spell_level) // 4


def prepared_spell_slots(
    class_key: str,
    class_name: str,
    class_level: int,
    progression: str,
    ability_modifier: int,
    *,
    daily_slot_adjustment: int = 0,
    bonus_slot_per_spell_level: int = 0,
) -> tuple[int, ...]:
    """Return total daily slots by spell level, including ability bonuses."""

    level = max(1, min(20, int(class_level)))
    key = _short_key(class_key, class_name)
    normalized = str(progression).casefold()
    if normalized in {"high", "full"}:
        base = HIGH_PREPARED[level - 1]
        first_spell_level = 0
    elif normalized in {"med", "mid", "medium", "3/4"}:
        daily = MED_PREPARED[level - 1]
        first_spell_level = 1 if key in NO_CANTRIPS else 0
        cantrips = 3 if level == 1 else (4 if level <= 5 else 5)
        base = daily if first_spell_level else (cantrips, *daily)
    else:
        base = LOW_PREPARED[level - 1]
        first_spell_level = 1
    totals = []
    for index, value in enumerate(base):
        spell_level = first_spell_level + index
        adjusted_base = max(0, int(value) + int(daily_slot_adjustment))
        dedicated = (
            max(0, int(bonus_slot_per_spell_level))
            if spell_level > 0 else 0
        )
        totals.append(
            adjusted_base
            + bonus_spell_slots(ability_modifier, spell_level)
            + dedicated
        )
    return tuple(([0] * first_spell_level) + totals)


def validate_preparation_capacity(
    slots: tuple[int, ...], prepared_by_level: dict[int, int]
) -> None:
    for level, count in prepared_by_level.items():
        capacity = slots[level] if 0 <= level < len(slots) else 0
        if count > capacity:
            raise ValueError(
                f"Spell level {level} has {count} prepared copies but only {capacity} slots."
            )

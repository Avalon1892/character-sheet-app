"""Shared rules and persistence helpers for catalog and custom traditions.

The UI, spell-point calculator, export/import code, and future sheet types all
consume the same resolved definition.  A custom tradition is therefore data,
not a special widget-only branch.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Iterable

from app.content import tradition_entry


@dataclass(frozen=True, slots=True)
class TraditionStatAdjustment:
    """One permanent sheet adjustment supplied by a tradition rule.

    Tradition rules stay declarative here.  The character calculation service
    translates these records into the shared modifier model used by every
    sheet type, formula projection, and future presentation.
    """

    target: str
    value: int
    source: str
    bonus_type: str = "untyped"


@dataclass(frozen=True, slots=True)
class CastingTraditionAutomation:
    """Resolved, character-specific consequences of casting drawbacks."""

    drawbacks: tuple[str, ...] = ()
    stat_adjustments: tuple[TraditionStatAdjustment, ...] = ()
    reminders: tuple[str, ...] = ()


def _drawback_key(value: object) -> str:
    """Normalize catalog spelling, source tags, and multiplicity markers."""

    text = re.sub(r"\[[^]]+\]", "", str(value or ""))
    text = re.sub(r"\s+(?:x|×)\s*\d+\s*$", "", text, flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _drawback_labels(value: object) -> tuple[str, ...]:
    """Read both catalog text and structured custom-tradition definitions."""

    if isinstance(value, Mapping):
        label = value.get("name") or value.get("label") or value.get("key")
        return (str(label),) if label else ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(
            label
            for item in value
            for label in _drawback_labels(item)
            if label
        )
    return tuple(
        part.strip()
        for part in re.split(r"[,;\n]+", str(value or ""))
        if part.strip()
    )


def casting_drawback_names(
    traditions: Iterable[object], legacy_drawbacks: object = ""
) -> tuple[str, ...]:
    """Return unique drawback names from catalog, custom, and legacy storage."""

    labels: list[str] = []
    for tradition in traditions:
        labels.extend(
            _drawback_labels(resolved_tradition_definition(tradition).get("drawbacks", ""))
        )
    labels.extend(_drawback_labels(legacy_drawbacks))
    unique: dict[str, str] = {}
    for label in labels:
        key = _drawback_key(label)
        if key:
            unique.setdefault(key, re.sub(r"\s+(?:x|×)\s*\d+\s*$", "", label, flags=re.I).strip())
    return tuple(unique.values())


def casting_tradition_automation(
    traditions: Iterable[object], *, casting_class_levels: int,
    legacy_drawbacks: object = "",
) -> CastingTraditionAutomation:
    """Project deterministic drawback rules without mutating saved character data.

    Triggered and opponent-dependent clauses are returned as reminders instead
    of being incorrectly treated as permanent penalties.  New drawbacks can be
    added to this registry without changing any UI or calculation consumer.
    """

    names = casting_drawback_names(traditions, legacy_drawbacks)
    keys = {_drawback_key(name) for name in names}
    adjustments: list[TraditionStatAdjustment] = []
    reminders: list[str] = []
    if "incompatible energies" in keys:
        levels = max(0, int(casting_class_levels))
        # MSD normally uses every casting-class level.  Replace that component
        # with half (rounded down) while leaving MSB, CL, and miscellaneous
        # bonuses untouched.
        penalty = -(levels - levels // 2)
        if penalty:
            adjustments.append(TraditionStatAdjustment(
                "magic_skill_defense",
                penalty,
                "Casting drawback: Incompatible Energies",
            ))
        reminders.append(
            "Incompatible Energies: after one of your sphere effects is "
            "successfully dispelled, you cannot spend spell points for 1 round. "
            "The Alien Source exception depends on the opposing caster or effect."
        )
    return CastingTraditionAutomation(
        drawbacks=names,
        stat_adjustments=tuple(adjustments),
        reminders=tuple(reminders),
    )


def resolved_tradition_definition(tradition) -> dict:
    """Return the catalog entry or the character-owned custom definition."""

    catalog = tradition_entry(str(getattr(tradition, "catalog_key", "")))
    if catalog is not None:
        return dict(catalog)
    try:
        custom = json.loads(str(getattr(tradition, "definition_json", "{}") or "{}"))
    except (TypeError, ValueError):
        return {}
    return dict(custom) if isinstance(custom, dict) else {}


def drawback_value(entry: Mapping[str, object]) -> int:
    """Return how many boon-currency units a general drawback supplies."""

    explicit = int(entry.get("drawback_value", 0) or 0)
    if explicit:
        return max(1, explicit)
    text = " ".join(
        str(entry.get(key, "")) for key in ("name", "description", "rules_text")
    )
    match = re.search(r"counts? as (\d+) drawbacks?", text, re.I)
    return max(1, int(match.group(1))) if match else 1


def boon_cost(entry: Mapping[str, object]) -> int:
    """Return the number of general-drawback units spent on one boon."""

    explicit = int(entry.get("boon_cost", 0) or 0)
    if explicit:
        return max(1, explicit)
    text = " ".join(
        str(entry.get(key, "")) for key in ("name", "description", "rules_text")
    )
    match = re.search(r"(?:costs?|requires?|\()\s*(\d+) drawbacks?", text, re.I)
    return max(1, int(match.group(1))) if match else 2


def spell_point_rule_for_unused_drawbacks(unused: int) -> dict[str, object]:
    """Build the official bonus-pool progression for unspent drawbacks.

    The published table ends at five unused drawbacks.  Additional unused
    drawbacks do not improve the progression beyond +1 per casting-class level.
    """

    unused = max(0, int(unused))
    effective = min(5, unused)
    rules: dict[int, dict[str, object]] = {
        0: {"base": 0, "per": 0, "every_levels": 0, "round_up": False,
            "text": "No bonus spell points; all drawback value is spent on boons."},
        1: {"base": 1, "per": 1, "every_levels": 6, "round_up": False,
            "text": "+1 spell point, +1 per 6 casting-class levels."},
        2: {"base": 1, "per": 1, "every_levels": 3, "round_up": False,
            "text": "+1 spell point, +1 per 3 casting-class levels."},
        3: {"base": 0, "per": 1, "every_levels": 2, "round_up": True,
            "text": "+1 spell point per odd casting-class level."},
        4: {"base": 1, "progression": "two_per_three", "text":
            "+1 spell point, +1 per 1.5 casting-class levels."},
        5: {"base": 0, "per": 1, "every_levels": 1, "round_up": False,
            "text": "+1 spell point per casting-class level."},
    }
    result = dict(rules[effective])
    result["unused_drawbacks"] = unused
    if unused > 5:
        result["text"] = str(result["text"]) + " (Progression capped at the published 5-drawback row.)"
    return result


def spell_point_bonus(rule: Mapping[str, object], casting_levels: int) -> int:
    """Evaluate a catalog/custom tradition spell-point rule."""

    levels = max(0, int(casting_levels))
    base = int(rule.get("base", 0) or 0)
    if rule.get("progression") == "two_per_three" or (
        "1.5" in str(rule.get("text", ""))
        and not int(rule.get("every_levels", 0) or 0)
    ):
        return base + (2 * levels) // 3
    every = int(rule.get("every_levels", 0) or 0)
    if not every:
        return base
    steps = (levels + every - 1) // every if rule.get("round_up") else levels // every
    return base + steps * int(rule.get("per", 0) or 0)

"""Shared presentation ordering for martial and magic talent catalogs.

The catalog data intentionally keeps its published category names.  UI layers
use this module to group those names into a stable browsing hierarchy without
rewriting or duplicating any rules records.
"""

from __future__ import annotations

from typing import Mapping


def talent_category_rank(category: object) -> int:
    """Return the logical browse group for one published talent category."""

    normalized = str(category or "").strip().casefold()
    if normalized == "base sphere":
        return 0
    if normalized == "talent":
        return 10
    if "drawback" in normalized:
        return 50
    if "advanced" in normalized or "legendary" in normalized:
        return 40
    if "talent" in normalized:
        # Form, blast type, formulae, discipline, gadget, and the other
        # published subtypes are ordinary sphere talents with a useful tag.
        return 20
    if "tradition" in normalized or "package" in normalized:
        return 30
    return 30


def talent_category_sort_key(category: object) -> tuple[int, str]:
    return talent_category_rank(category), str(category or "").casefold()


def talent_entry_sort_key(entry: Mapping[str, object]) -> tuple[int, str, str, str]:
    """Sort base access before talents, capstones, and finally drawbacks."""

    category = str(entry.get("category") or "")
    return (
        talent_category_rank(category),
        str(entry.get("sphere") or "").casefold(),
        category.casefold(),
        str(entry.get("name") or "").casefold(),
    )

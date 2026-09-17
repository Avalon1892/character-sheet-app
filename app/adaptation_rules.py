"""Prodigy Adaptation rules built on the provider-neutral talent-slot engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from app.flexible_talent_rules import (
    project_flexible_magic_talents,
    project_flexible_martial_talents,
    validate_flexible_talent_entries,
)
from app.models import MartialTalent, Spell
from app.rules import prodigy_adaptation_uses, prodigy_level


ADAPTATION_SOURCE_KEY = "prodigy:adaptation"
_BATTLE_BORN = "spheres-archetype:prodigy:battle-born"
_CHROMAMANCER = "spheres-archetype:prodigy:chromamancer"
_EXPLOITANT = "spheres-archetype:prodigy:exploitant"
_GUTTER_RAT = "spheres-archetype:prodigy:gutter-rat"
_MIMIC = "spheres-archetype:prodigy:mimic"


@dataclass(frozen=True, slots=True)
class AdaptationProfile:
    available: bool
    level: int
    capacity: int
    allowed_kinds: tuple[str, ...]
    name: str = "Adaptation"
    alternative_kind: str = ""


def _prodigy_archetype_keys(repository, character_id: int) -> frozenset[str]:
    keys_by_level = repository.list_class_archetype_keys(character_id)
    return frozenset(
        key
        for row in repository.list_class_levels(character_id)
        if row.preset_key == "prodigy"
        for key in keys_by_level.get(row.id, ())
    )


def adaptation_profile(repository, character_id: int) -> AdaptationProfile:
    level = prodigy_level(repository.list_class_levels(character_id))
    if level < 2:
        return AdaptationProfile(False, level, 0, ())
    keys = _prodigy_archetype_keys(repository, character_id)
    if _EXPLOITANT in keys or _MIMIC in keys:
        return AdaptationProfile(False, level, 0, ())
    capacity = prodigy_adaptation_uses(level) if level >= 20 else (
        3 if level >= 13 else 2 if level >= 5 else 1
    )
    if _GUTTER_RAT in keys and _BATTLE_BORN not in keys:
        return AdaptationProfile(True, level, capacity, (), "Roguish Adaptation", "rogue")
    if _CHROMAMANCER in keys:
        return AdaptationProfile(True, level, capacity, ("magic",), "Mystic Adaptation")
    if _BATTLE_BORN in keys:
        return AdaptationProfile(True, level, capacity, ("martial",), "Martial Adaptation")
    return AdaptationProfile(True, level, capacity, ("martial", "magic"))


def adaptation_talent_capacity(repository, character_id: int) -> int:
    return adaptation_profile(repository, character_id).capacity


def validate_adaptation_entries(
    repository,
    character_id: int,
    selections: Iterable[Mapping[str, object]],
) -> tuple[dict, ...]:
    profile = adaptation_profile(repository, character_id)
    if not profile.available:
        raise ValueError("This character does not currently have Adaptation.")
    if not profile.allowed_kinds:
        raise ValueError(
            "Roguish Adaptation grants rogue talents; use its dedicated power selector."
        )
    return validate_flexible_talent_entries(
        repository,
        character_id,
        selections,
        source_key=ADAPTATION_SOURCE_KEY,
        capacity=profile.capacity,
        feature_name=profile.name,
        allowed_kinds=profile.allowed_kinds,
        allow_base_spheres=False,
    )


def projected_adaptation_martial_talents(
    repository, character_id: int
) -> tuple[MartialTalent, ...]:
    profile = adaptation_profile(repository, character_id)
    if not profile.available or "martial" not in profile.allowed_kinds:
        return ()
    return project_flexible_martial_talents(
        repository, character_id, ADAPTATION_SOURCE_KEY, profile.capacity
    )


def projected_adaptation_magic_talents(
    repository, character_id: int
) -> tuple[Spell, ...]:
    profile = adaptation_profile(repository, character_id)
    if not profile.available or "magic" not in profile.allowed_kinds:
        return ()
    return project_flexible_magic_talents(
        repository, character_id, ADAPTATION_SOURCE_KEY, profile.capacity
    )


def adaptation_change_cost(existing: Iterable, proposed: Iterable[Mapping[str, object]]) -> int:
    """Return uses spent by newly gained/replaced slots; clearing is free."""

    old = tuple(existing)
    new = tuple(proposed)
    cost = 0
    for index, record in enumerate(new):
        if index >= len(old):
            cost += 1
            continue
        previous = old[index]
        if (
            previous.catalog_key != str(record.get("catalog_key") or "")
            or previous.choice_key != str(record.get("choice_key") or "")
        ):
            cost += 1
    return cost


def adaptation_action_text(level: int, count: int) -> str:
    count = max(0, int(count))
    if count <= 0:
        return "End the current Adaptation"
    if level >= 20:
        return "Swift action"
    if level >= 17:
        return "Immediate action" if count == 1 else "Swift action"
    if level >= 13:
        return {1: "Free action", 2: "Swift action"}.get(count, "Move action")
    if level >= 8:
        return "Swift action" if count == 1 else "Move action"
    if level >= 5:
        return "Move action" if count == 1 else "Standard action"
    return "Standard action"

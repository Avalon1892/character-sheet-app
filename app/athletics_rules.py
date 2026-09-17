"""Pure Spheres of Might Athletics rules used by every sheet presentation.

The catalog remains the source for rules text.  This module contains only the
small, deterministic part of those rules that can be projected onto character
statistics without asking the user for encounter context.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping

from app.models import MartialTalent, SkillState


ATHLETICS_PACKAGES: tuple[str, ...] = ("Climb", "Fly", "Leap", "Run", "Swim")


def running_multiplier(talents, armor_weight: str, load: str, *, run_feat=False) -> int:
    """Resolve running independently of the ordinary movement speed."""
    if load == "Overloaded":
        return 0
    records = tuple(talents)
    heavy = armor_weight == "heavy" or load == "Heavy"
    if has_athletics_rule(records, "speed-boost"):
        return 8 if heavy else 10
    if run_feat or "Run" in athletics_packages(records):
        return 4 if heavy else 5
    return 3 if heavy else 4
PACKAGE_SKILLS: dict[str, str] = {
    "Climb": "climb",
    "Fly": "fly",
    "Leap": "acrobatics",
    "Run": "acrobatics",
    "Swim": "swim",
}

_DRAWBACK_GRANT_MARKERS: dict[str, tuple[str, ...]] = {
    "always-forward": ("strong-lungs", "strong lungs"),
    "driver-eo2": ("ace-pilot", "ace pilot"),
    "limited-athleticism": ("close-quarters-training", "close quarters training"),
    "magnetic-maneuvers": ("sure-grip", "sure grip", "tumbling-recovery", "tumbling recovery"),
    "risky-escape": ("reflexive-twist", "reflexive twist"),
    "trainer-utility-start": ("fitness-instructor", "fitness instructor"),
    "untrained-athlete": ("mighty-conditioning", "mighty conditioning"),
}


def _is_athletics(item: MartialTalent) -> bool:
    return item.sphere.casefold().strip() == "athletics"


def _rule_key(item: MartialTalent) -> str:
    """Prefer stable catalog identity while retaining old-import compatibility."""

    if item.catalog_key:
        return item.catalog_key.casefold().strip()
    return re.sub(r"\s+", " ", item.name.casefold().strip())


def _has_rule(talents: Iterable[MartialTalent], token: str) -> bool:
    token = token.casefold()
    records = tuple(talents)
    direct = any(
        item.enabled
        and _is_athletics(item)
        and (token in _rule_key(item) or token == item.name.casefold().strip())
        for item in records
    )
    if direct:
        return True
    # Athletics drawbacks that grant a talent are rules-equivalent even for
    # older characters created before granted talents were stored separately.
    implied_by_drawback = {
        "mighty-conditioning": ("untrained-athlete",),
        "mighty conditioning": ("untrained-athlete", "untrained athlete"),
        "ace-pilot": ("driver-eo2",),
        "ace pilot": ("driver-eo2", "driver"),
        "strong-lungs": ("always-forward",),
        "strong lungs": ("always-forward", "always forward"),
        "close-quarters-training": ("limited-athleticism",),
        "close quarters training": ("limited-athleticism", "limited athleticism"),
        "reflexive-twist": ("risky-escape",),
        "reflexive twist": ("risky-escape", "risky escape"),
        "fitness-instructor": ("trainer-utility-start",),
        "fitness instructor": ("trainer-utility-start", "trainer (utility start)"),
    }
    return any(
        marker in _rule_key(item)
        for marker in implied_by_drawback.get(token, ())
        for item in records
        if item.enabled and _is_athletics(item)
    )


def _choice_packages(choice: str) -> set[str]:
    pieces = re.split(r"\s*(?:/|,|;|\||\band\b)\s*", choice, flags=re.I)
    lookup = {package.casefold(): package for package in ATHLETICS_PACKAGES}
    return {lookup[piece.casefold()] for piece in pieces if piece.casefold() in lookup}


def athletics_packages(talents: Iterable[MartialTalent]) -> frozenset[str]:
    """Return every currently possessed package, including Expanded Training."""

    records = tuple(talents)
    if _has_rule(records, "limited-athleticism") or _has_rule(
        records, "limited athleticism"
    ):
        return frozenset()
    result: set[str] = set()
    for item in records:
        if not item.enabled or not _is_athletics(item):
            continue
        category = item.catalog_category.casefold().strip()
        key = _rule_key(item)
        if category == "base sphere" or "expanded-training" in key or item.name.casefold().strip() == "expanded training":
            result.update(_choice_packages(item.choice))
    return frozenset(result)


def athletics_talent_count(talents: Iterable[MartialTalent]) -> int:
    """Count base/purchased talents plus fixed talents granted by drawbacks."""

    records = tuple(talents)
    count = sum(
        1
        for item in records
        if item.enabled
        and _is_athletics(item)
        and item.catalog_category.casefold().strip() != "drawback"
        and item.talent_type.casefold().strip() != "drawback"
    )
    direct_rule_keys = tuple(
        _rule_key(item)
        for item in records
        if item.enabled
        and _is_athletics(item)
        and item.catalog_category.casefold().strip() != "drawback"
    )
    for drawback in records:
        if (
            not drawback.enabled
            or not _is_athletics(drawback)
            or drawback.catalog_category.casefold().strip() != "drawback"
        ):
            continue
        drawback_key = _rule_key(drawback)
        markers = next(
            (
                granted
                for drawback_marker, granted in _DRAWBACK_GRANT_MARKERS.items()
                if drawback_marker in drawback_key
            ),
            (),
        )
        if markers and not any(
            marker in rule_key for marker in markers for rule_key in direct_rule_keys
        ):
            count += 1
    return count


def athletics_granted_ranks(talents: Iterable[MartialTalent], hit_dice: int) -> dict[str, int]:
    """Resolve the package rank grant without altering purchased skill ranks."""

    records = tuple(talents)
    packages = athletics_packages(records)
    if not packages or _has_rule(records, "untrained-athlete") or _has_rule(
        records, "untrained athlete"
    ) or _has_rule(records, "driver-eo2") or _has_rule(records, "driver"):
        return {}
    granted = min(max(0, int(hit_dice)), 5 * athletics_talent_count(records))
    return {
        skill: granted
        for skill in {PACKAGE_SKILLS[package] for package in packages}
        if granted
    }


def effective_athletics_ranks(
    talents: Iterable[MartialTalent],
    skill_states: Mapping[str, SkillState],
    hit_dice: int,
) -> dict[str, int]:
    grants = athletics_granted_ranks(talents, hit_dice)
    return {
        key: max(int(state.ranks), grants.get(key, 0))
        for key, state in skill_states.items()
    }


def athletics_skill_keys(talents: Iterable[MartialTalent]) -> frozenset[str]:
    return frozenset(PACKAGE_SKILLS[package] for package in athletics_packages(talents))


def has_athletics_rule(talents: Iterable[MartialTalent], catalog_token: str) -> bool:
    """Public stable-key lookup for reviewed Athletics projections."""

    return _has_rule(tuple(talents), catalog_token)


def mighty_conditioning_extra_ability(
    talents: Iterable[MartialTalent], skill_key: str, effective_ability: str
) -> str:
    """Return the second physical ability applied by Mighty Conditioning."""

    records = tuple(talents)
    if (
        not _has_rule(records, "mighty-conditioning")
        and not _has_rule(records, "mighty conditioning")
    ) or skill_key not in athletics_skill_keys(records):
        return ""
    default = {
        "acrobatics": "dexterity",
        "climb": "strength",
        "fly": "dexterity",
        "swim": "strength",
    }.get(skill_key, "")
    other = "strength" if default == "dexterity" else "dexterity"
    # If another rule replaces the normal ability, the replaced ability stays
    # gone and the other original physical ability is retained.
    return "" if effective_ability == other else other


def armored_athlete_reduction(
    talents: Iterable[MartialTalent], skill_key: str, effective_ranks: int
) -> int:
    records = tuple(talents)
    if (
        _has_rule(records, "armored-athlete")
        or _has_rule(records, "armored athlete")
    ) and skill_key in athletics_skill_keys(records):
        return 2 + max(0, int(effective_ranks)) // 4
    return 0


@dataclass(frozen=True, slots=True)
class AthleticsMovement:
    speeds: dict[str, int]
    fly_maneuverability: str
    sources: tuple[str, ...] = ()


def project_athletics_movement(
    talents: Iterable[MartialTalent],
    skill_states: Mapping[str, SkillState],
    hit_dice: int,
    martial_focus_current: int,
    speeds: Mapping[str, int],
    fly_maneuverability: str = "",
) -> AthleticsMovement:
    """Apply deterministic Athletics movement grants and focused bonuses."""

    records = tuple(talents)
    result = {key: max(0, int(value)) for key, value in speeds.items()}
    sources: list[str] = []
    packages = athletics_packages(records)
    ranks = effective_athletics_ranks(records, skill_states, hit_dice)
    base_speed = result.get("land_speed", 0)

    if _has_rule(records, "sparrow-s-path") or _has_rule(records, "sparrow’s path"):
        result["fly_speed"] = max(result.get("fly_speed", 0), base_speed // 2)
        fly_maneuverability = "Clumsy"
        sources.append("Sparrow's Path: fly speed equals half base speed")
    if _has_rule(records, "eagle-s-path") or _has_rule(records, "eagle’s path"):
        result["fly_speed"] = max(result.get("fly_speed", 0), base_speed)
        fly_maneuverability = "Average"
        sources.append("Eagle's Path: fly speed equals base speed")
    if _has_rule(records, "shark-swim") or _has_rule(records, "shark swim"):
        result["swim_speed"] = max(result.get("swim_speed", 0), base_speed)
        sources.append("Shark Swim: full base speed while swimming")
    if _has_rule(records, "terrain-glide") or _has_rule(records, "terrain glide"):
        current = result.get("burrow_speed", 0)
        result["burrow_speed"] = current + 5 if current else 10
        sources.append("Terrain Glide: 10-foot burrow speed or +5 to an existing speed")
    if _has_rule(records, "earthswimmer"):
        target = result.get("swim_speed", 0) or base_speed // 2
        result["burrow_speed"] = max(result.get("burrow_speed", 0), target)
        sources.append("Earthswimmer: burrow speed equals swim speed or half base speed")

    if martial_focus_current > 0 and (
        _has_rule(records, "swift-movement") or _has_rule(records, "swift movement")
    ):
        package_targets = {
            "Run": "land_speed",
            "Fly": "fly_speed",
            "Swim": "swim_speed",
            "Climb": "climb_speed",
        }
        for package, target in package_targets.items():
            # A package is not itself an extraordinary fly/climb/swim speed.
            # Swift Movement improves those modes only when a real speed exists.
            if package not in packages or (target != "land_speed" and not result.get(target, 0)):
                continue
            skill = PACKAGE_SKILLS[package]
            bonus = 10 + 5 * (ranks.get(skill, 0) // 5)
            result[target] = result.get(target, 0) + bonus
            sources.append(f"Swift Movement ({package}): +{bonus} feet while focused")

    return AthleticsMovement(result, fly_maneuverability, tuple(sources))

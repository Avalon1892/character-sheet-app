"""Deterministic skill-rank grants shared by calculations and advancement.

The stored ``SkillState.ranks`` value remains the number of ranks purchased by
the character.  Spheres and talents add rank *floors* at projection time, so a
grant never destroys a player's allocation and disappears cleanly if its
source is removed or disabled.
"""
from __future__ import annotations

import re
from typing import Iterable, Mapping

from app.athletics_rules import athletics_granted_ranks
from app.models import MartialTalent, SkillState


_BASE_ASSOCIATED_SKILLS: dict[str, str] = {
    "fencing": "bluff",
    "gladiator": "intimidate",
    "leadership": "diplomacy",
    "scoundrel": "sleight_of_hand",
    "scout": "stealth",
    "tech": "craft",
    "tinker": "craft",
    "trap": "craft",
    "warleader": "diplomacy",
}


def _rule_key(item: MartialTalent) -> str:
    return (item.catalog_key or item.name).casefold().strip()


def _has(records: Iterable[MartialTalent], *tokens: str) -> bool:
    folded = tuple(token.casefold() for token in tokens)
    return any(
        item.enabled
        and any(token in _rule_key(item) or token == item.name.casefold().strip() for token in folded)
        for item in records
    )


def _sphere_records(
    talents: Iterable[MartialTalent], sphere: str
) -> tuple[MartialTalent, ...]:
    return tuple(
        item for item in talents
        if item.enabled and item.sphere.casefold().strip() == sphere.casefold()
    )


def _talent_count(records: Iterable[MartialTalent]) -> int:
    return sum(
        1 for item in records
        if item.catalog_category.casefold().strip() not in {"drawback", "tradition"}
        and item.talent_type.casefold().strip() != "drawback"
    )


def _base_sphere_present(records: Iterable[MartialTalent]) -> bool:
    return any(
        item.catalog_category.casefold().strip() == "base sphere"
        or _rule_key(item).endswith(":base")
        for item in records
    )


def _choice_skill(choice: str, default: str) -> str:
    folded = choice.casefold()
    if "profession" in folded:
        return "profession"
    if "perform" in folded:
        return "perform"
    if "bluff" in folded:
        return "bluff"
    if "intimidate" in folded:
        return "intimidate"
    if "knowledge (engineering)" in folded:
        return "knowledge_engineering"
    if "knowledge (religion)" in folded:
        return "knowledge_religion"
    return default


def _put_floor(result: dict[str, int], skill_key: str, amount: int) -> None:
    if skill_key and amount > 0:
        result[skill_key] = max(result.get(skill_key, 0), amount)


def martial_granted_skill_ranks(
    talents: Iterable[MartialTalent], hit_dice: int
) -> dict[str, int]:
    """Return permanent rank floors granted by possessed martial talents.

    The mappings are deliberately keyed to catalog identity rather than parsed
    from rules prose.  Variant drawbacks that replace an associated skill are
    resolved here as part of the same provider.
    """

    records = tuple(item for item in talents if item.enabled)
    maximum = max(0, int(hit_dice))
    result = dict(athletics_granted_ranks(records, maximum))
    if maximum <= 0:
        return result

    for sphere, default_skill in _BASE_ASSOCIATED_SKILLS.items():
        sphere_records = _sphere_records(records, sphere)
        count = _talent_count(sphere_records)
        if not count or not _base_sphere_present(sphere_records):
            continue
        skill = default_skill
        if sphere == "gladiator":
            if _has(sphere_records, "braggart"):
                continue
            if _has(sphere_records, "entertainer"):
                skill = "perform"
        elif sphere == "scout" and _has(
            sphere_records,
            "people-watcher", "people watcher", "sentry", "tracker", "veteran-warrior", "veteran warrior",
        ):
            continue
        elif sphere == "warleader" and _has(sphere_records, "conductor"):
            skill = "perform"
        elif sphere == "leadership":
            if _has(sphere_records, "construct-controller", "construct controller"):
                skill = "knowledge_engineering"
            elif _has(sphere_records, "undead-servants", "undead servants"):
                skill = "knowledge_religion"
            elif _has(sphere_records, "cult-leader", "cult leader"):
                skill = "bluff"
            elif _has(sphere_records, "dread-master", "dread master"):
                skill = "intimidate"
        elif sphere in {"tech", "trap"}:
            alternative = next(
                (item for item in sphere_records if "alternative" in _rule_key(item)),
                None,
            )
            if alternative is not None:
                skill = _choice_skill(alternative.choice, default_skill)
        _put_floor(result, skill, min(maximum, 5 * count))

    beastmastery = _sphere_records(records, "beastmastery")
    beast_count = _talent_count(beastmastery)
    if beast_count and _base_sphere_present(beastmastery):
        base = next(
            (item for item in beastmastery if item.catalog_category.casefold().strip() == "base sphere"),
            None,
        )
        choices = set(re.split(r"\s*(?:/|,|;|\||\band\b)\s*", base.choice, flags=re.I)) if base else set()
        if any(choice.casefold() == "handle animal" for choice in choices):
            _put_floor(result, "handle_animal", min(maximum, 5 * beast_count))
        if any(choice.casefold() == "ride" for choice in choices):
            _put_floor(result, "ride", min(maximum, 5 * beast_count))

    reviewed_talent_grants = (
        ("athletics", ("ace-pilot", "ace pilot"), "profession"),
        ("equipment", ("craftsman",), "craft"),
        ("fencing", ("read-foe", "read foe"), "sense_motive"),
        ("leadership", ("military-training", "military training"), "profession"),
        ("scout", ("great-senses", "great senses"), "perception"),
    )
    for sphere, tokens, skill in reviewed_talent_grants:
        sphere_records = _sphere_records(records, sphere)
        if not _has(sphere_records, *tokens):
            continue
        amount = maximum if sphere == "equipment" else min(maximum, 5 * _talent_count(sphere_records))
        _put_floor(result, skill, amount)
    return result


def effective_skill_ranks(
    talents: Iterable[MartialTalent],
    skill_states: Mapping[str, SkillState],
    hit_dice: int,
) -> dict[str, int]:
    grants = martial_granted_skill_ranks(talents, hit_dice)
    return {
        key: max(int(state.ranks), grants.get(key, 0))
        for key, state in skill_states.items()
    }


def granted_skill_rank_allowance(
    talents: Iterable[MartialTalent],
    skill_states: Mapping[str, SkillState],
    hit_dice: int,
) -> int:
    """Ranks added to both the advancement total and effective usage.

    Only the portion above purchased ranks is free.  This preserves the game's
    immediate-retraining behavior without silently rewriting saved allocations.
    """

    effective = effective_skill_ranks(talents, skill_states, hit_dice)
    return sum(
        max(0, effective.get(key, state.ranks) - int(state.ranks))
        for key, state in skill_states.items()
    )

"""Dynamic Craft, Perform, and Profession rows shared by rules and UI."""
from __future__ import annotations

from dataclasses import replace

from app.models import SKILLS, SkillDefinition


SPECIALIZED_SKILL_KEYS = frozenset({"craft", "perform", "profession"})
_BASE_DEFINITIONS = {item.key: item for item in SKILLS}


def base_skill_key(skill_key: str) -> str:
    for key in SPECIALIZED_SKILL_KEYS:
        if skill_key == key or skill_key.startswith(f"{key}__"):
            return key
    return skill_key


def skill_formula_entity_id(skill_key: str) -> int:
    for index, definition in enumerate(SKILLS, 1):
        if definition.key == skill_key:
            return index
    base = base_skill_key(skill_key)
    try:
        suffix = int(skill_key.rsplit("__", 1)[1])
    except (IndexError, ValueError):
        suffix = sum(ord(character) for character in skill_key)
    base_offset = {"craft": 1, "perform": 2, "profession": 3}.get(base, 9)
    return 100_000 + base_offset * 10_000 + suffix


def character_skill_definitions(repository, character_id: int) -> tuple[SkillDefinition, ...]:
    specializations = {
        item.skill_key: item
        for item in repository.list_skill_specializations(character_id)
    }
    by_base: dict[str, list] = {key: [] for key in SPECIALIZED_SKILL_KEYS}
    for item in specializations.values():
        by_base.setdefault(item.base_skill_key, []).append(item)

    result: list[SkillDefinition] = []
    for definition in SKILLS:
        if definition.key not in SPECIALIZED_SKILL_KEYS:
            result.append(definition)
            continue
        base_record = specializations.get(definition.key)
        specialty = base_record.specialty if base_record is not None else ""
        result.append(
            replace(
                definition,
                name=(
                    f"{definition.name} ({specialty})"
                    if specialty else definition.name
                ),
            )
        )
        extras = sorted(
            (
                item for item in by_base.get(definition.key, ())
                if item.skill_key != definition.key
            ),
            key=lambda item: (item.sort_order, item.skill_key),
        )
        for item in extras:
            result.append(
                replace(
                    definition,
                    key=item.skill_key,
                    name=(
                        f"{definition.name} ({item.specialty})"
                        if item.specialty else definition.name
                    ),
                )
            )
    return tuple(result)


def specialization_for(repository, character_id: int, skill_key: str) -> str:
    return next(
        (
            item.specialty
            for item in repository.list_skill_specializations(character_id)
            if item.skill_key == skill_key
        ),
        "",
    )

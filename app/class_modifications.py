"""Universal class/archetype profile resolution.

Catalog data declares *what* changes; this module applies those declarations
without depending on Qt, persistence, or a particular rules family.  The same
contract is used by Pathfinder, first-party Spheres, 3PP Spheres, and custom
future catalogs.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Mapping

from app.archetype_rules import (
    ArchetypeChoice,
    archetype_choices,
    selected_archetype_choice_options,
)
from app.models import ClassLevel, SKILLS


_BAB = {"Full", "3/4", "1/2"}
_SAVE = {"Good", "Poor"}
_CASTING = {"High", "Mid", "Low"}

_SKILL_KEYS = {definition.key for definition in SKILLS}
_SKILL_NAME_KEYS = {
    definition.name.casefold(): definition.key for definition in SKILLS
}


def _normalized_class_skills(values: Iterable[object]) -> tuple[str, ...]:
    """Translate catalog display names and stable keys to skill keys.

    Older class and archetype catalogs used visible names (``Acrobatics``),
    while newer records use stable keys (``acrobatics``).  Calculation code
    must never have to care which catalog generation supplied the profile.
    """

    if isinstance(values, (str, bytes)):
        values = (values,)
    result: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        folded = text.casefold()
        if not text:
            continue
        if folded in {"knowledge (all)", "knowledge_all", "knowledge:all"}:
            result.update(key for key in _SKILL_KEYS if key.startswith("knowledge_"))
            continue
        key = folded.replace(" ", "_").replace("-", "_")
        if key in _SKILL_KEYS:
            result.add(key)
            continue
        if folded in _SKILL_NAME_KEYS:
            result.add(_SKILL_NAME_KEYS[folded])
    return tuple(sorted(result))


def _recommended_hit_points(hit_die: int, levels: int) -> int:
    return 0 if hit_die <= 0 or levels <= 0 else hit_die + max(0, levels - 1) * (hit_die // 2 + 1)


@dataclass(frozen=True, slots=True)
class ResolvedClassProfile:
    hit_die: int
    bab_progression: str
    fort_progression: str
    reflex_progression: str
    will_progression: str
    skill_points: int
    class_skills: tuple[str, ...]
    casting: Mapping[str, object]
    advancement: Mapping[str, object]
    capabilities: frozenset[str]
    proficiencies: Mapping[str, object]
    changes: tuple[str, ...] = ()


def _document(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _title_progression(value: object, allowed: set[str], fallback: str) -> str:
    text = str(value or "").strip()
    aliases = {
        "medium": "3/4", "mid": "3/4", "three-quarter": "3/4",
        "half": "1/2", "low": "1/2", "high": "Full",
        "good": "Good", "poor": "Poor",
    }
    normalized = aliases.get(text.casefold(), text.title())
    return normalized if normalized in allowed else fallback


def _base_profile(class_definition: Mapping[str, object]) -> ResolvedClassProfile:
    casting = dict(_document(class_definition.get("casting")))
    sphere = str(casting.get("sphere_progression") or "").title()
    if sphere and sphere not in _CASTING:
        casting.pop("sphere_progression", None)
    return ResolvedClassProfile(
        max(0, int(class_definition.get("hit_die") or 0)),
        _title_progression(class_definition.get("bab"), _BAB, "1/2"),
        _title_progression(class_definition.get("fort"), _SAVE, "Poor"),
        _title_progression(class_definition.get("reflex"), _SAVE, "Poor"),
        _title_progression(class_definition.get("will"), _SAVE, "Poor"),
        max(0, int(class_definition.get("skill_points") or 0)),
        _normalized_class_skills(
            tuple(class_definition.get("class_skill_keys") or ())
            + tuple(class_definition.get("class_skills") or ())
        ),
        casting,
        dict(_document(class_definition.get("advancement"))),
        frozenset(str(value) for value in class_definition.get("capabilities", ()) if str(value)),
        dict(_document(class_definition.get("proficiencies"))),
    )


def _apply_modifications(
    profile: ResolvedClassProfile,
    declaration: Mapping[str, object],
    source: str,
) -> ResolvedClassProfile:
    statistics = _document(declaration.get("statistics"))
    casting = dict(profile.casting)
    casting.update(_document(declaration.get("casting")))
    sphere = str(casting.get("sphere_progression") or "").title()
    if sphere:
        if sphere in _CASTING:
            casting["sphere_progression"] = sphere
        else:
            casting.pop("sphere_progression", None)

    advancement = dict(profile.advancement)
    advancement.update(_document(declaration.get("advancement")))
    proficiencies = dict(profile.proficiencies)
    proficiencies.update(_document(declaration.get("proficiencies")))

    capabilities = set(profile.capabilities)
    capability_changes = _document(declaration.get("capabilities"))
    capabilities.update(str(value) for value in capability_changes.get("grants", ()) if str(value))
    capabilities.difference_update(
        str(value) for value in capability_changes.get("removes", ()) if str(value)
    )

    updates = {
        "hit_die": max(0, int(statistics.get("hit_die") or profile.hit_die)),
        "bab_progression": _title_progression(
            statistics.get("bab_progression"), _BAB, profile.bab_progression
        ),
        "fort_progression": _title_progression(
            statistics.get("fort_progression"), _SAVE, profile.fort_progression
        ),
        "reflex_progression": _title_progression(
            statistics.get("reflex_progression"), _SAVE, profile.reflex_progression
        ),
        "will_progression": _title_progression(
            statistics.get("will_progression"), _SAVE, profile.will_progression
        ),
        "skill_points": max(
            0, int(statistics.get("skill_points") if "skill_points" in statistics else profile.skill_points)
        ),
    }
    class_skills = set(profile.class_skills)
    if "class_skills" in statistics:
        class_skills = set(
            _normalized_class_skills(statistics.get("class_skills", ()))
        )
    class_skills.update(
        _normalized_class_skills(statistics.get("add_class_skills", ()))
    )
    class_skills.difference_update(
        _normalized_class_skills(statistics.get("remove_class_skills", ()))
    )
    updates["class_skills"] = tuple(sorted(class_skills))

    changed_labels = []
    labels = {
        "hit_die": "Hit Die", "bab_progression": "BAB",
        "fort_progression": "Fortitude", "reflex_progression": "Reflex",
        "will_progression": "Will", "skill_points": "Skill points",
        "class_skills": "Class skills",
    }
    for key, value in updates.items():
        if getattr(profile, key) != value:
            changed_labels.append(f"{source}: {labels[key]} → {value}")
    if casting != dict(profile.casting):
        changed_labels.append(
            f"{source}: casting → {casting.get('sphere_progression') or casting.get('progression') or 'modified'}"
        )
    if advancement != dict(profile.advancement):
        changed_labels.append(f"{source}: advancement modified")

    return replace(
        profile,
        **updates,
        casting=casting,
        advancement=advancement,
        capabilities=frozenset(capabilities),
        proficiencies=proficiencies,
        changes=profile.changes + tuple(changed_labels),
    )


def resolve_class_profile(
    class_definition: Mapping[str, object],
    archetypes: Iterable[Mapping[str, object]] = (),
    choice_selections: Mapping[str, Iterable[str]] | None = None,
) -> ResolvedClassProfile:
    """Layer selected archetypes and their chosen options over one base class."""

    selected = tuple(archetypes)
    choice_selections = choice_selections or {}
    profile = _base_profile(class_definition)
    for archetype in selected:
        profile = _apply_modifications(
            profile,
            _document(archetype.get("class_modifications")),
            str(archetype.get("name") or "Archetype"),
        )
    declared_choices: tuple[ArchetypeChoice, ...] = tuple(
        choice for archetype in selected for choice in archetype_choices(archetype)
    )
    for option in selected_archetype_choice_options(declared_choices, choice_selections):
        profile = _apply_modifications(
            profile,
            _document(option.class_modifications),
            option.name,
        )
    return profile


def sphere_bonus_spell_conversions(
    class_definition: Mapping[str, object],
    archetypes: Iterable[Mapping[str, object]],
    level: int,
    choice_selections: Mapping[str, Iterable[str]] | None = None,
) -> tuple[Mapping[str, object], ...]:
    """Reviewed spells-known groups, not individual spells or spell-list additions.

    Source: https://spheresofpower.wikidot.com/archetype-rules
    Explicit Sphere Oracle/Sorcerer replacements are not declared here and
    therefore retain their specific rules. No description parsing is involved.
    """
    from app.class_packages import archetype_runtime_package
    from app.class_feature_rules import feature_token, resolve_class_features

    selected = tuple(archetypes)
    declarations = tuple(
        (archetype, group)
        for archetype in selected
        for group in (archetype_runtime_package(str(archetype.get("key", ""))) or {}).get(
            "sphere_spell_known_groups", ())
    )
    if not declarations:
        return ()
    profile = resolve_class_profile(class_definition, selected, choice_selections)
    if (
        str(_document(class_definition.get("casting")).get("type", "")).casefold() != "spontaneous"
    ) or not profile.casting.get("sphere_progression") or profile.casting.get("traditional") is not False:
        return ()
    tokens = {feature_token(feature.name) for feature in resolve_class_features(
        class_definition.get("features", ()), selected, level,
        str(class_definition.get("name", "")),
        selected_archetype_choices=choice_selections,
    )}
    groups = {}
    for archetype, group in declarations:
        if level < int(group.get("level", 1)) or group.get("feature_token") not in tokens:
            continue
        identity = (str(archetype.get("key", "")), str(group["key"]))
        groups[identity] = {**group, "source": f"{archetype.get('name', 'Archetype')}: {group['name']}"}
    return tuple(groups.values())


def resolve_class_level(
    class_level: ClassLevel,
    class_definition: Mapping[str, object],
    archetypes: Iterable[Mapping[str, object]] = (),
    choice_selections: Mapping[str, Iterable[str]] | None = None,
) -> ClassLevel:
    """Project automatic profile changes while preserving manual overrides.

    A stored value equal to its base-class default is considered automatic. A
    differing value remains a character-owned override. Automatically computed
    hit-die HP follows a changed Hit Die; manually entered HP remains untouched.
    """

    profile = resolve_class_profile(class_definition, archetypes, choice_selections)
    base = _base_profile(class_definition)
    field_map = {
        "hit_die": "hit_die",
        "bab_progression": "bab_progression",
        "fort_progression": "fort_progression",
        "reflex_progression": "reflex_progression",
        "will_progression": "will_progression",
    }
    updates: dict[str, object] = {}
    for field, profile_field in field_map.items():
        current = getattr(class_level, field)
        if current == getattr(base, profile_field):
            updates[field] = getattr(profile, profile_field)

    original_hit_die = int(class_level.hit_die)
    effective_hit_die = int(updates.get("hit_die", original_hit_die))
    if (
        original_hit_die > 0
        and class_level.hp_gained == _recommended_hit_points(original_hit_die, class_level.level)
        and effective_hit_die != original_hit_die
    ):
        updates["hp_gained"] = _recommended_hit_points(effective_hit_die, class_level.level)
    return replace(class_level, **updates) if updates else class_level

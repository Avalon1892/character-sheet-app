from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from app.models import ClassLevel


@dataclass(frozen=True, slots=True)
class ClassCapabilities:
    """Resolved sheet modules granted by classes and selected archetypes."""

    traditional_spells: bool = False
    magic: bool = False
    martial: bool = False
    skill: bool = False
    sequence: bool = False
    extra: frozenset[str] = frozenset()

    @property
    def active_tokens(self) -> frozenset[str]:
        """Extensible capability vocabulary consumed by alternate sheets.

        The named booleans remain the compatibility API used throughout the
        mature sheet.  New class systems can declare another catalog token and
        register a presentation module without growing this dataclass again.
        """

        known = {
            name
            for name in ("traditional_spells", "magic", "martial", "skill", "sequence")
            if bool(getattr(self, name))
        }
        return frozenset(known) | self.extra

    def has(self, token: str) -> bool:
        return token.strip().casefold() in self.active_tokens

    @property
    def any_spheres(self) -> bool:
        return self.magic or self.martial or self.skill or self.sequence

    @property
    def any_spellcasting(self) -> bool:
        return self.traditional_spells or self.magic


# Compatibility name retained for extensions and saved tests written before the
# traditional spellcasting tier existed.
SphereCapabilities = ClassCapabilities


def resolve_sphere_capabilities(
    classes: Iterable[ClassLevel],
    archetype_keys_by_class_level: Mapping[int, Iterable[str]],
    archetypes_by_key: Mapping[str, dict],
    class_definitions_by_key: Mapping[str, dict] | None = None,
) -> ClassCapabilities:
    """Resolve capabilities without coupling rules data to Qt or persistence.

    Catalog entries declare additive ``grants`` and explicit ``removes``.  This
    lets exceptional archetypes such as Battle-Born replace part of a Spheres
    class cleanly, while future systems can add another capability token without
    changing page composition code.
    """

    active: set[str] = set()
    class_definitions_by_key = class_definitions_by_key or {}
    for class_level in classes:
        local: set[str] = set()
        definition = class_definitions_by_key.get(class_level.preset_key) or class_definitions_by_key.get(
            f"pathfinder-class:{class_level.preset_key}"
        )
        if definition:
            local.update(str(value) for value in definition.get("capabilities", ()))
            casting = definition.get("casting") or {}
            if casting.get("traditional") is not False and any(
                casting.get(key) for key in ("ability", "progression", "spells")
            ):
                local.add("traditional_spells")
        if class_level.preset_key == "prodigy" or class_level.class_name.casefold() == "prodigy":
            local.update(("magic", "martial", "sequence"))
        local_removed: set[str] = set()
        for key in archetype_keys_by_class_level.get(class_level.id, ()):
            entry = archetypes_by_key.get(key)
            if not entry:
                continue
            declaration = entry.get("sphere_capabilities") or {}
            local.update(str(value) for value in declaration.get("grants", ()))
            local_removed.update(str(value) for value in declaration.get("removes", ()))
            modifications = entry.get("class_modifications") or {}
            capability_changes = (
                modifications.get("capabilities", {})
                if isinstance(modifications, Mapping) else {}
            )
            local.update(
                str(value) for value in capability_changes.get("grants", ())
            )
            local_removed.update(
                str(value) for value in capability_changes.get("removes", ())
            )
            altered_casting = (
                modifications.get("casting", {})
                if isinstance(modifications, Mapping) else {}
            )
            if altered_casting.get("traditional") is True:
                local.add("traditional_spells")
            elif altered_casting.get("traditional") is False:
                local_removed.add("traditional_spells")
            description = str(entry.get("description") or "").casefold()
            if (
                "magic" in declaration.get("grants", ())
                and any(
                    phrase in description
                    for phrase in (
                        "replaces the spells class feature",
                        "replaces spells class feature",
                        "replaces the spellcasting class feature",
                        "replaces the extracts class feature",
                    )
                )
            ):
                local_removed.add("traditional_spells")
        local.difference_update(local_removed)
        active.update(local)
    return ClassCapabilities(
        traditional_spells="traditional_spells" in active,
        magic="magic" in active,
        martial="martial" in active,
        skill="skill" in active,
        sequence="sequence" in active,
        extra=frozenset(
            active
            - {"traditional_spells", "magic", "martial", "skill", "sequence"}
        ),
    )


def resolve_class_capabilities(
    classes: Iterable[ClassLevel],
    archetype_keys_by_class_level: Mapping[int, Iterable[str]],
    archetypes_by_key: Mapping[str, dict],
    class_definitions_by_key: Mapping[str, dict],
) -> ClassCapabilities:
    return resolve_sphere_capabilities(
        classes,
        archetype_keys_by_class_level,
        archetypes_by_key,
        class_definitions_by_key,
    )

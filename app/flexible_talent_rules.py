"""Shared rules for class features that temporarily grant sphere talents.

The persistence table is deliberately provider-neutral.  This module supplies
the equally neutral validation and projection layer; Prodigy Adaptation and
Exploitant Moldable Talents only declare their differing access policies.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from app.content import magic_entry, martial_entry, martial_entries
from app.drawback_rules import (
    magic_talent_restriction_reason,
    martial_talent_restriction_reason,
)
from app.models import FlexibleTalentSelection, MartialTalent, SheetEffect, Spell
from app.sphere_rules import base_sphere_choice_options, martial_base_granted_talent_name
from app.engineering_rules import validate_tinker_package_choice


def _martial_starting_talent(selection):
    """Resolve the catalog talent included in a base-sphere package, not a slot."""
    if selection.category != "Base Sphere":
        return None
    name = martial_base_granted_talent_name(selection.sphere, selection.choice)
    if not name:
        return None
    return next((entry for entry in martial_entries(selection.sphere)
                 if entry["name"] == name
                 and entry.get("category") not in ("Base Sphere", "Drawback", "Legendary Talent")), None)


def _effects(entry: Mapping[str, object], choice_key: str) -> tuple[SheetEffect, ...]:
    automation = entry.get("automation")
    if not isinstance(automation, Mapping):
        return ()
    result = []
    for raw in automation.get("effects", ()) or ():
        if not isinstance(raw, Mapping):
            continue
        try:
            result.append(SheetEffect(
                target=str(raw.get("target") or "").replace("{choice_key}", choice_key),
                bonus_type=str(raw.get("bonus_type") or "untyped"),
                value=int(raw.get("value") or 0),
                formula=str(raw.get("formula") or ""),
                scope=str(raw.get("scope") or "").replace("{choice_key}", choice_key),
            ))
        except (TypeError, ValueError):
            continue
    return tuple(result)


def project_flexible_martial_talents(
    repository,
    character_id: int,
    source_key: str,
    capacity: int,
) -> tuple[MartialTalent, ...]:
    result = []
    for selection in repository.list_flexible_talent_selections(
        character_id, source_key
    )[:max(0, capacity)]:
        if selection.talent_kind != "martial":
            continue
        entry = martial_entry(selection.catalog_key) or {}
        automation = entry.get("automation") if isinstance(entry, Mapping) else {}
        category = selection.category
        result.append(MartialTalent(
            id=-1_000_000 - selection.id,
            name=selection.name,
            sphere=selection.sphere,
            talent_type=(
                "Base Sphere" if category == "Base Sphere" else
                "Drawback" if category == "Drawback" else "Talent"
            ),
            notes=selection.description,
            catalog_key=selection.catalog_key,
            catalog_category=category,
            prerequisites=str(entry.get("prerequisites") or ""),
            source_url=str(entry.get("source_url") or ""),
            enabled=True,
            choice=selection.choice,
            effects=_effects(entry, selection.choice_key),
            activation=str((automation or {}).get("activation") or "always"),
            activation_note=str((automation or {}).get("activation_note") or ""),
        ))
        result.extend(_project_martial_starting_talent(selection))
    return tuple(result)


def project_flexible_magic_talents(
    repository,
    character_id: int,
    source_key: str,
    capacity: int,
) -> tuple[Spell, ...]:
    result = []
    for selection in repository.list_flexible_talent_selections(
        character_id, source_key
    )[:max(0, capacity)]:
        if selection.talent_kind != "magic":
            continue
        entry = magic_entry(selection.catalog_key) or {}
        automation = entry.get("automation") if isinstance(entry, Mapping) else {}
        result.append(Spell(
            id=-2_000_000 - selection.id,
            name=selection.name,
            system="Sphere",
            level=0,
            school_or_sphere=selection.sphere,
            notes=selection.description,
            catalog_key=selection.catalog_key,
            catalog_category=selection.category,
            prerequisites=str(entry.get("prerequisites") or ""),
            source_url=str(entry.get("source_url") or ""),
            enabled=True,
            choice=selection.choice,
            effects=_effects(entry, selection.choice_key),
            activation=str((automation or {}).get("activation") or "always"),
            activation_note=str((automation or {}).get("activation_note") or ""),
        ))
    return tuple(result)


def validate_flexible_talent_entries(
    repository,
    character_id: int,
    selections: Iterable[Mapping[str, object]],
    *,
    source_key: str,
    capacity: int,
    feature_name: str,
    allowed_kinds: Iterable[str] = ("martial", "magic"),
    allow_base_spheres: bool,
) -> tuple[dict, ...]:
    """Validate an ordered temporary talent build against one provider policy."""

    chosen = tuple(dict(item) for item in selections)
    capacity = max(0, int(capacity))
    if len(chosen) > capacity:
        raise ValueError(f"{feature_name} currently grants at most {capacity} talent(s).")
    allowed = {str(value).casefold() for value in allowed_kinds}
    permanent_martial = repository.list_martial_talents(character_id)
    permanent_magic = repository.list_spells(character_id)
    projected_martial: list[MartialTalent] = []
    projected_magic: list[Spell] = []
    used: set[str] = {
        item.catalog_key for item in (*permanent_martial, *permanent_magic)
        if item.catalog_key
    }
    martial_bases = {
        item.sphere.casefold() for item in permanent_martial
        if item.enabled and (item.catalog_category == "Base Sphere" or item.talent_type == "Base Sphere")
    }
    magic_bases = {
        item.school_or_sphere.casefold() for item in permanent_magic
        if item.enabled and item.catalog_category == "Base Sphere"
    }
    result: list[dict] = []
    for index, selection in enumerate(chosen, start=1):
        kind = str(selection.get("talent_kind") or "").casefold()
        if kind not in allowed:
            raise ValueError(f"{feature_name} cannot grant {kind or 'that kind of'} talents.")
        key = str(selection.get("catalog_key") or "")
        entry = (
            martial_entry(key) if kind == "martial"
            else magic_entry(key) if kind == "magic"
            else None
        )
        if entry is None:
            raise ValueError(f"{feature_name} slot {index} no longer matches a catalog talent.")
        category = str(entry.get("category") or "Talent")
        sphere = str(entry.get("sphere") or "")
        if "drawback" in category.casefold():
            raise ValueError(f"{feature_name} cannot grant drawbacks.")
        if category == "Base Sphere" and not allow_base_spheres:
            raise ValueError(
                f"{feature_name} requires an already-owned base sphere and cannot grant the {sphere} base sphere."
            )
        repeatable = bool((entry.get("automation") or {}).get("repeatable"))
        if key in used and not repeatable:
            raise ValueError(f"{entry['name']} is already possessed.")
        bases = martial_bases if kind == "martial" else magic_bases
        if category != "Base Sphere" and sphere.casefold() not in bases:
            if allow_base_spheres:
                raise ValueError(
                    f"Choose the {sphere} base sphere in an earlier slot or possess it permanently before choosing {entry['name']}."
                )
            raise ValueError(
                f"Possess the {sphere} base sphere before choosing {entry['name']} with {feature_name}."
            )
        record = {
            "talent_kind": kind,
            "catalog_key": key,
            "name": str(entry.get("name") or ""),
            "sphere": sphere,
            "category": category,
            "description": str(entry.get("description") or ""),
            "choice": str(selection.get("choice") or ""),
            "choice_key": str(selection.get("choice_key") or ""),
        }
        options=base_sphere_choice_options(sphere,kind) if category=="Base Sphere" else ()
        if options:
            option=next((value for value in options if value.casefold()==record["choice"].strip().casefold()),None)
            if option is None:
                raise ValueError(f"Choose a valid starting package for {entry['name']}.")
            record["choice"]=option
            record["choice_key"]=option.strip().casefold().replace(" ","_")
        elif (entry.get("automation") or {}).get("choice_type") and not (record["choice"].strip() and record["choice_key"].strip()):
            raise ValueError(f"Complete the required choice for {entry['name']}.")
        probe = FlexibleTalentSelection(
            0, character_id, source_key, index - 1, **record
        )
        if kind == "martial":
            if (entry.get("automation") or {}).get("choice_type")=="tinker_packages_two":
                validate_tinker_package_choice(record["choice"],[*permanent_martial,*projected_martial])
            restriction = martial_talent_restriction_reason(
                entry, [*permanent_martial, *projected_martial]
            )
            if restriction:
                raise ValueError(restriction)
            projected_martial.extend(project_flexible_martial_record(probe, entry))
            granted = _martial_starting_talent(probe)
            if granted:
                if granted["key"] in used and not (granted.get("automation") or {}).get("repeatable"):
                    raise ValueError(f"{granted['name']} is already possessed; choose a different starting talent.")
                restriction = martial_talent_restriction_reason(
                    granted, [*permanent_martial, *projected_martial]
                )
                if restriction:
                    raise ValueError(restriction)
                used.add(granted["key"])
            if category == "Base Sphere":
                martial_bases.add(sphere.casefold())
        else:
            restriction = magic_talent_restriction_reason(
                entry, [*permanent_magic, *projected_magic]
            )
            if restriction:
                raise ValueError(restriction)
            projected_magic.extend(project_flexible_magic_record(probe, entry))
            if category == "Base Sphere":
                magic_bases.add(sphere.casefold())
        used.add(key)
        result.append(record)
    return tuple(result)


def project_flexible_martial_record(selection, entry) -> tuple[MartialTalent, ...]:
    category = selection.category
    return (MartialTalent(
        -1, selection.name, selection.sphere,
        "Base Sphere" if category == "Base Sphere" else "Talent",
        selection.description, selection.catalog_key, category,
        str(entry.get("prerequisites") or ""), str(entry.get("source_url") or ""),
        True, selection.choice, _effects(entry, selection.choice_key),
    ), *_project_martial_starting_talent(selection))


def _project_martial_starting_talent(selection) -> tuple[MartialTalent, ...]:
    entry = _martial_starting_talent(selection)
    if entry is None:
        return ()
    automation = entry.get("automation") or {}
    return (MartialTalent(
        id=-3_000_000 - selection.id,
        name=entry["name"], sphere=entry["sphere"], talent_type="Talent",
        notes=str(entry.get("description") or ""), catalog_key=entry["key"],
        catalog_category=str(entry.get("category") or "Talent"),
        prerequisites=str(entry.get("prerequisites") or ""),
        source_url=str(entry.get("source_url") or ""), enabled=True,
        effects=_effects(entry, ""),
        activation=str(automation.get("activation") or "always"),
        activation_note=str(automation.get("activation_note") or ""),
    ),)


def project_flexible_magic_record(selection, entry) -> tuple[Spell, ...]:
    return (Spell(
        -1, selection.name, "Sphere", 0, selection.sphere,
        notes=selection.description, catalog_key=selection.catalog_key,
        catalog_category=selection.category,
        prerequisites=str(entry.get("prerequisites") or ""),
        source_url=str(entry.get("source_url") or ""), choice=selection.choice,
        effects=_effects(entry, selection.choice_key),
    ),)

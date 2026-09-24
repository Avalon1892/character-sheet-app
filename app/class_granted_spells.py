"""Synchronize structured class-choice spell grants with Spells Known.

Catalog importers extract explicit spell progressions into data.  Runtime code
never parses displayed descriptions; it only resolves selected stable keys and
retained archetype features, then reconciles records owned by this service.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re
from typing import Iterable, Mapping

from app.archetype_rules import replaced_features, archetype_choice_selections_from_records
from app.class_choice_rules import ResolvedClassChoice, resolve_class_choice_slots
from app.class_packages import archetype_runtime_package, class_package
from app.content import archetype_entry, class_entry, spell_entries
from app.class_modifications import sphere_bonus_spell_conversions


GRANTED_CATEGORY = "Class Granted"
GRANT_PREFIX = "class-grant:"


@dataclass(frozen=True, slots=True)
class ClassGrantedSpell:
    class_level_id: int
    provider_key: str
    option_key: str
    class_level: int
    spell_level: int
    name: str
    catalog_key: str
    school: str
    casting_time: str
    range: str
    duration: str
    save: str
    spell_resistance: str
    description: str
    source_url: str

    @property
    def marker(self) -> str:
        return (
            f"{GRANT_PREFIX}{self.class_level_id}:{self.provider_key}:"
            f"{self.option_key}:{self.class_level}:{self.spell_level}:"
            f"{_token(self.name)}"
        )


def _token(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value).casefold()).strip("-")


@lru_cache(maxsize=1)
def _spell_index() -> Mapping[str, tuple[dict, ...]]:
    result: dict[str, list[dict]] = {}
    for entry in spell_entries():
        result.setdefault(_token(entry.get("name")), []).append(entry)
    return {
        key: tuple(
            sorted(
                values,
                key=lambda item: (
                    bool(item.get("third_party")),
                    str(item.get("publisher") or "").casefold(),
                    str(item.get("key") or ""),
                ),
            )
        )
        for key, values in result.items()
    }


def _catalog_spell(name: str, index: Mapping[str, tuple[dict, ...]]) -> dict | None:
    candidates = index.get(_token(name), ())
    if not candidates:
        # Mystery lists sometimes append a targeting restriction in
        # parentheses. It changes how the granted spell is used, not its
        # catalog identity.
        candidates = index.get(_token(re.sub(r"\s*\([^)]*only[^)]*\)\s*$", "", name, flags=re.I)), ())
    return dict(candidates[0]) if candidates else None


def _choice_grants_blocked(
    repository,
    character_id: int,
    class_level_id: int,
    provider_key: str,
) -> bool:
    keys = repository.list_class_archetype_keys(character_id).get(class_level_id, ())
    replaced: set[str] = set()
    selected_archetypes = []
    for key in keys:
        entry = archetype_entry(key)
        if entry is not None:
            selected_archetypes.append(entry)
            replaced.update(replaced_features(entry))
    class_level = next((item for item in repository.list_class_levels(character_id)
                        if item.id == class_level_id), None)
    if class_level is not None:
        conversions = sphere_bonus_spell_conversions(
            class_entry(class_level.preset_key) or {}, selected_archetypes, class_level.level,
            archetype_choice_selections_from_records(
                repository.list_class_feature_selections(character_id), class_level_id),
        )
        if any(provider_key in group.get("choice_providers", ()) for group in conversions):
            return True
    if provider_key == "cleric-domains" and any(
        isinstance(entry.get("class_modifications"), Mapping)
        and isinstance(entry.get("class_modifications", {}).get("casting"), Mapping)
        and entry.get("class_modifications", {}).get("casting", {}).get("traditional") is False
        for entry in selected_archetypes
    ):
        # Sphere-casting Cleric replacements keep domain powers but explicitly
        # exchange the traditional domain-spell slots for talents.
        return True
    common = {"oracle-spells", "spellcasting", "oracles-strength"}
    provider_replacements = (
        {"bonus-spells", "mystery-spells", "mystery-bonus-spells"}
        if provider_key == "oracle-mystery"
        else {"oracle-s-curse", "oracles-curse"}
        if provider_key == "oracle-curse"
        else set()
    )
    return bool(replaced & (common | provider_replacements))


def resolve_class_granted_spells(
    repository,
    character_id: int,
    slots: Iterable[ResolvedClassChoice] | None = None,
) -> tuple[ClassGrantedSpell, ...]:
    slots = tuple(slots or resolve_class_choice_slots(repository, character_id))
    by_class = {item.id: item for item in repository.list_class_levels(character_id)}
    index = _spell_index()
    result: list[ClassGrantedSpell] = []
    for slot in slots:
        class_level = by_class.get(slot.class_level_id)
        if class_level is None:
            continue
        package = class_package(class_level.preset_key)
        archetype_keys = repository.list_class_archetype_keys(
            character_id, class_level.id
        ).get(class_level.id, ())
        runtime_provider_keys = {
            str(value)
            for key in archetype_keys
            for value in (archetype_runtime_package(key) or {}).get(
                "spell_grant_choice_providers", ()
            )
            if str(value)
        }
        suppressed_provider_keys = {
            str(value)
            for key in archetype_keys
            for value in (archetype_runtime_package(key) or {}).get(
                "suppress_spell_grant_choice_providers", ()
            )
            if str(value)
        }
        exact_grant_levels = {
            str(provider): max(1, int(level))
            for key in archetype_keys
            for provider, level in dict(
                (archetype_runtime_package(key) or {}).get(
                    "spell_grant_levels", {}
                )
            ).items()
        }
        if (
            slot.key in suppressed_provider_keys
            or
            (package is None or slot.key not in package.spell_grant_choice_providers)
            and slot.key not in runtime_provider_keys
        ) or (
            _choice_grants_blocked(
                repository, character_id, slot.class_level_id, slot.key
            )
        ):
            continue
        for option in slot.selected_options:
            for grant in option.bonus_spells:
                grant_level = max(1, int(grant.get("class_level", 1) or 1))
                if (
                    slot.key in exact_grant_levels
                    and grant_level != exact_grant_levels[slot.key]
                ):
                    continue
                if grant_level > class_level.level:
                    continue
                name = str(grant.get("name") or "").strip()
                if not name:
                    continue
                catalog = _catalog_spell(name, index) or {}
                result.append(
                    ClassGrantedSpell(
                        slot.class_level_id,
                        slot.key,
                        option.key,
                        grant_level,
                        max(0, min(9, int(grant.get("spell_level", 0) or 0))),
                        name,
                        str(catalog.get("key") or ""),
                        str(catalog.get("school") or ""),
                        str(catalog.get("casting_time") or ""),
                        str(catalog.get("range") or ""),
                        str(catalog.get("duration") or ""),
                        str(catalog.get("saving_throw") or ""),
                        str(catalog.get("spell_resistance") or ""),
                        str(catalog.get("description") or catalog.get("summary") or ""),
                        str(catalog.get("source_url") or ""),
                    )
                )
    unique = {grant.marker: grant for grant in result}
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (item.spell_level, item.name.casefold(), item.marker),
        )
    )


def synchronize_class_granted_spells(repository, character_id: int) -> bool:
    """Reconcile only records owned by this service; user spells stay untouched."""

    desired = {item.marker: item for item in resolve_class_granted_spells(repository, character_id)}
    spells = repository.list_spells(character_id)
    automatic = {
        spell.choice: spell
        for spell in spells
        if spell.catalog_category == GRANTED_CATEGORY
        and spell.choice.startswith(GRANT_PREFIX)
    }
    changed = False
    for marker, spell in automatic.items():
        if marker in desired:
            continue
        repository.delete_spell(character_id, spell.id)
        changed = True

    remaining = repository.list_spells(character_id)
    owned_catalogs = {
        spell.catalog_key for spell in remaining if spell.catalog_key
    }
    owned_identities = {
        (_token(spell.name), spell.level) for spell in remaining
    }
    for marker, grant in desired.items():
        if marker in automatic:
            continue
        if (
            grant.catalog_key and grant.catalog_key in owned_catalogs
        ) or ((_token(grant.name), grant.spell_level) in owned_identities):
            continue
        repository.add_spell(
            character_id,
            grant.name,
            "Spontaneous",
            grant.spell_level,
            grant.school,
            0,
            0,
            grant.casting_time,
            grant.range,
            grant.duration,
            grant.save,
            grant.spell_resistance,
            grant.description,
            grant.catalog_key,
            GRANTED_CATEGORY,
            "Automatically granted by a selected class feature.",
            grant.source_url,
            marker,
        )
        if grant.catalog_key:
            owned_catalogs.add(grant.catalog_key)
        owned_identities.add((_token(grant.name), grant.spell_level))
        changed = True
    return changed

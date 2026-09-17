"""Rules-facing state and resource actions for the optional Spell Book UI."""
from __future__ import annotations

from dataclasses import dataclass, replace

from app.content import spell_entry
from app.database import CharacterRepository
from app.exploitant_rules import effective_magic_talents
from app.models import Spell
from app.sphere_rules import granted_sphere_abilities
from app.spell_rules import spell_record_presentation, sphere_spell_point_costs
from app.traditional_spellcasting import (
    prepared_caster_capacities,
    spontaneous_caster_capacities,
    traditional_spellbook_blocked_by_archetype,
)


@dataclass(frozen=True, slots=True)
class SpellBookEntry:
    key: str
    name: str
    level: int
    group: str
    school: str
    description: str
    resource_kind: str
    current: int = 0
    maximum: int = 0
    enabled: bool = True
    costs: tuple[int, ...] = ()
    spell_id: int | None = None
    prepared_ids: tuple[int, ...] = ()
    slot_refs: tuple[tuple[int, int, int], ...] = ()
    class_names: tuple[str, ...] = ()
    limited_remaining: int | None = None
    limited_maximum: int = 0

    @property
    def searchable_text(self) -> str:
        return " ".join((self.name, self.description, self.school)).casefold()

    @property
    def usage_text(self) -> str:
        if not self.enabled:
            return "Unavailable"
        if self.resource_kind == "at_will":
            return "At will"
        if self.resource_kind == "unavailable":
            return "Not available"
        if self.resource_kind == "prepared":
            return f"{self.current} / {self.maximum} prepared"
        if self.resource_kind == "spontaneous":
            return f"{self.current} / {self.maximum} slots"
        if self.resource_kind == "limited":
            return f"{self.current} / {self.maximum} uses"
        return "—"

    @property
    def can_cast(self) -> bool:
        if not self.enabled or self.resource_kind == "unavailable":
            return False
        if self.resource_kind == "at_will":
            return True
        return self.current > 0

    @property
    def can_restore(self) -> bool:
        return (
            self.enabled
            and self.resource_kind in {"prepared", "spontaneous", "limited"}
            and self.current < self.maximum
        )

    def sphere_usage_text(self, cost: int) -> str:
        if not self.enabled:
            return "Unavailable"
        cost = max(0, int(cost))
        if self.limited_remaining is not None and self.limited_remaining <= 0:
            return f"0 / {self.limited_maximum} uses · {cost} SP"
        if cost == 0:
            if self.limited_remaining is not None:
                return f"{self.limited_remaining} / {self.limited_maximum} uses · 0 SP"
            return "At will · 0 SP"
        possible = self.current // cost
        if self.limited_remaining is not None:
            possible = min(possible, self.limited_remaining)
        return f"{cost} SP · {possible} use{'s' if possible != 1 else ''} available"

    def can_use_sphere(self, cost: int) -> bool:
        return (
            self.enabled
            and int(cost) in self.costs
            and self.current >= int(cost)
            and (self.limited_remaining is None or self.limited_remaining > 0)
        )


@dataclass(frozen=True, slots=True)
class SpellBookActionResult:
    changed: bool
    message: str


class SpellBookService:
    """Project the current character and perform bounded spell resource actions."""

    def __init__(self, repository: CharacterRepository, character_id: int) -> None:
        self.repository = repository
        self.character_id = character_id

    @staticmethod
    def _known_description(spell: Spell) -> str:
        rules = "\n\n".join(
            value
            for value in (
                f"School: {spell.school_or_sphere or '—'}",
                f"Spell level: {spell.level}",
                f"Casting time: {spell.casting_time or '—'}; Range: {spell.range or '—'}; Duration: {spell.duration or '—'}",
                f"Save: {spell.save or '—'}; Spell resistance: {spell.spell_resistance or '—'}",
                spell.notes,
            )
            if value
        )
        return rules

    def traditional_entries(self) -> tuple[SpellBookEntry, ...]:
        if traditional_spellbook_blocked_by_archetype(
            self.repository, self.character_id
        ):
            return ()
        spells = tuple(
            spell
            for spell in self.repository.list_spells(self.character_id)
            if spell.system != "Sphere"
            and spell.catalog_category not in {"Base Sphere", "Drawback"}
        )
        prepared = self.repository.list_prepared_spells(self.character_id)
        prepared_by_known: dict[int, list] = {}
        for record in prepared:
            if record.known_spell_id is not None:
                prepared_by_known.setdefault(record.known_spell_id, []).append(record)

        spontaneous = spontaneous_caster_capacities(
            self.repository, self.character_id
        )
        slot_uses = {
            (record.class_level_id, record.spell_level): record.used_count
            for record in self.repository.list_spontaneous_slot_uses(self.character_id)
        }
        result: list[SpellBookEntry] = []
        for spell in spells:
            resource_kind = "unavailable"
            current = maximum = 0
            prepared_ids: tuple[int, ...] = ()
            slot_refs: tuple[tuple[int, int, int], ...] = ()
            class_names: tuple[str, ...] = ()
            if spell.uses_max > 0:
                resource_kind = "limited"
                maximum = spell.uses_max
                current = max(0, spell.uses_max - spell.uses_used)
            elif spell.system.casefold() == "prepared":
                matches = tuple(prepared_by_known.get(spell.id, ()))
                prepared_ids = tuple(record.id for record in matches)
                maximum = sum(record.prepared_count for record in matches)
                current = sum(record.remaining for record in matches)
                resource_kind = (
                    "at_will" if spell.level == 0 and matches else
                    "prepared" if matches else "unavailable"
                )
            elif spell.system.casefold() == "spontaneous":
                candidates = tuple(
                    caster
                    for caster in spontaneous
                    if spell.level < len(caster.total_slots)
                    and (spell.level == 0 or caster.total_slots[spell.level] > 0)
                )
                if spell.level == 0 and candidates:
                    resource_kind = "at_will"
                    class_names = tuple(caster.class_name for caster in candidates)
                elif candidates:
                    resource_kind = "spontaneous"
                    slot_refs = tuple(
                        (
                            caster.class_level_id,
                            spell.level,
                            caster.total_slots[spell.level],
                        )
                        for caster in candidates
                    )
                    class_names = tuple(caster.class_name for caster in candidates)
                    maximum = sum(reference[2] for reference in slot_refs)
                    current = sum(
                        max(
                            0,
                            slot_maximum
                            - slot_uses.get((class_level_id, spell_level), 0),
                        )
                        for class_level_id, spell_level, slot_maximum in slot_refs
                    )
            elif spell.uses_max == 0:
                resource_kind = "at_will"
            result.append(
                SpellBookEntry(
                    key=f"traditional:spell:{spell.id}",
                    name=spell.name,
                    level=spell.level,
                    group=f"Level {spell.level}",
                    school=spell.school_or_sphere,
                    description=self._known_description(spell),
                    resource_kind=resource_kind,
                    current=current,
                    maximum=maximum,
                    enabled=spell.enabled,
                    spell_id=spell.id,
                    prepared_ids=prepared_ids,
                    slot_refs=slot_refs,
                    class_names=class_names,
                )
            )

        # Special-rule preparations may intentionally come from the complete
        # catalog instead of Spells Known.  They remain visible and usable.
        custom_groups: dict[tuple[str, str, int, int], list] = {}
        for record in prepared:
            if not record.custom:
                continue
            identity = (
                record.catalog_key,
                record.name.casefold(),
                record.level,
                record.class_level_id,
            )
            custom_groups.setdefault(identity, []).append(record)
        prepared_classes = {
            caster.class_level_id: caster
            for caster in prepared_caster_capacities(self.repository, self.character_id)
        }
        for (_catalog_key, _name, level, class_level_id), records in custom_groups.items():
            first = records[0]
            catalog = spell_entry(first.catalog_key) if first.catalog_key else None
            description = str((catalog or {}).get("description") or "")
            school = str((catalog or {}).get("school") or "")
            maximum = sum(record.prepared_count for record in records)
            current = sum(record.remaining for record in records)
            caster = prepared_classes.get(class_level_id)
            result.append(
                SpellBookEntry(
                    key=f"traditional:custom:{class_level_id}:{first.catalog_key or first.id}",
                    name=first.name,
                    level=level,
                    group=f"Level {level}",
                    school=school,
                    description="\n\n".join(
                        value
                        for value in (
                            f"School: {school or '—'}",
                            f"Spell level: {level}",
                            description,
                            "Custom catalog preparation for a special rule.",
                        )
                        if value
                    ),
                    resource_kind="at_will" if level == 0 else "prepared",
                    current=current,
                    maximum=maximum,
                    prepared_ids=tuple(record.id for record in records),
                    class_names=(caster.class_name,) if caster else (),
                )
            )
        return tuple(sorted(result, key=lambda item: (item.level, item.name.casefold())))

    def traditional_level_ceiling(
        self, entries: tuple[SpellBookEntry, ...] | None = None
    ) -> int | None:
        """Return the highest traditional spell level relevant to this character.

        The spell book should follow the character's effective class/archetype
        progression instead of rendering empty level bands through level 9.
        Positive prepared or spontaneous capacity unlocks a level.  A character
        without a class-backed progression may still have a limited-use or
        otherwise custom traditional spell, so those records remain visible.
        """

        entries = self.traditional_entries() if entries is None else entries
        if not entries:
            return None

        prepared = prepared_caster_capacities(self.repository, self.character_id)
        spontaneous = spontaneous_caster_capacities(
            self.repository, self.character_id
        )
        unlocked = [
            level
            for caster in prepared
            for level, amount in enumerate(caster.slots)
            if amount > 0
        ]
        unlocked.extend(
            level
            for caster in spontaneous
            for level, amount in enumerate(caster.total_slots)
            if level == 0 or amount > 0
        )
        if unlocked:
            return max(unlocked)

        # Standalone/custom spell resources do not necessarily belong to a
        # traditional caster class, but are still legitimate book entries.
        if not prepared and not spontaneous:
            return max(entry.level for entry in entries)
        return None

    def sphere_entries(self) -> tuple[SpellBookEntry, ...]:
        saved = tuple(effective_magic_talents(self.repository, self.character_id))
        rows = (
            *granted_sphere_abilities(saved),
            *(
                spell
                for spell in saved
                if spell.system == "Sphere"
                and spell.catalog_category not in {"Base Sphere", "Drawback"}
            ),
        )
        profile = self.repository.get_casting_profile(self.character_id)
        spell_points = max(
            0, profile.spell_points_current + profile.spell_points_temporary
        )
        result = []
        for record in rows:
            presentation = spell_record_presentation(record, saved)
            category = str(getattr(record, "catalog_category", "") or "")
            description = str(getattr(record, "notes", "") or "")
            costs = sphere_spell_point_costs(
                description,
                base_sphere=category in {"Base Sphere", "Sphere Ability"},
            )
            spell_id = int(
                getattr(record, "id", 0) or getattr(record, "source_id", 0) or 0
            ) or None
            uses_max = int(getattr(record, "uses_max", 0) or 0)
            uses_used = int(getattr(record, "uses_used", 0) or 0)
            key_value = (
                f"spell:{getattr(record, 'id')}"
                if getattr(record, "id", None) is not None
                else str(getattr(record, "key", ""))
            )
            result.append(
                SpellBookEntry(
                    key=f"sphere:{key_value}",
                    name=presentation.name,
                    level=0,
                    group=presentation.sphere or "Other",
                    school=presentation.sphere,
                    description="\n\n".join(
                        value
                        for value in (
                            f"Sphere: {presentation.sphere}",
                            f"Spell-point cost: {presentation.cost}",
                            f"Action: {presentation.action}; Range: {presentation.range}; Duration: {presentation.duration}",
                            f"Save: {presentation.save}; Spell resistance: {presentation.spell_resistance}",
                            description,
                        )
                        if value
                    ),
                    resource_kind="sphere",
                    current=spell_points,
                    maximum=spell_points,
                    enabled=bool(getattr(record, "enabled", True)),
                    costs=costs,
                    spell_id=spell_id,
                    limited_remaining=(max(0, uses_max - uses_used) if uses_max else None),
                    limited_maximum=uses_max,
                )
            )
        return tuple(sorted(result, key=lambda item: (item.group.casefold(), item.name.casefold())))

    def cast_traditional(self, key: str) -> SpellBookActionResult:
        entry = next((item for item in self.traditional_entries() if item.key == key), None)
        if entry is None or not entry.can_cast:
            return SpellBookActionResult(False, "That spell is not currently available.")
        if entry.resource_kind == "at_will":
            return SpellBookActionResult(False, f"{entry.name} is at will; no resource was spent.")
        if entry.resource_kind == "prepared":
            prepared = {
                record.id: record
                for record in self.repository.list_prepared_spells(self.character_id)
            }
            record = next(
                (prepared[value] for value in entry.prepared_ids if prepared[value].remaining > 0),
                None,
            )
            if record is None:
                return SpellBookActionResult(False, "No prepared copies remain.")
            self.repository.update_prepared_spell_counts(
                self.character_id,
                record.id,
                record.prepared_count,
                record.used_count + 1,
            )
        elif entry.resource_kind == "spontaneous":
            used = {
                (record.class_level_id, record.spell_level): record.used_count
                for record in self.repository.list_spontaneous_slot_uses(self.character_id)
            }
            reference = next(
                (
                    value
                    for value in entry.slot_refs
                    if used.get((value[0], value[1]), 0) < value[2]
                ),
                None,
            )
            if reference is None:
                return SpellBookActionResult(False, "No spell slots remain at this level.")
            class_level_id, level, _maximum = reference
            self.repository.set_spontaneous_slot_uses(
                self.character_id,
                class_level_id,
                level,
                used.get((class_level_id, level), 0) + 1,
            )
        elif entry.resource_kind == "limited" and entry.spell_id is not None:
            spell = next(
                item
                for item in self.repository.list_spells(self.character_id)
                if item.id == entry.spell_id
            )
            self.repository.set_spell_uses_used(
                self.character_id, spell.id, spell.uses_used + 1
            )
        return SpellBookActionResult(True, f"Cast {entry.name}.")

    def restore_traditional(self, key: str) -> SpellBookActionResult:
        entry = next((item for item in self.traditional_entries() if item.key == key), None)
        if entry is None or not entry.can_restore:
            return SpellBookActionResult(False, "Nothing can be restored for that spell.")
        if entry.resource_kind == "prepared":
            prepared = {
                record.id: record
                for record in self.repository.list_prepared_spells(self.character_id)
            }
            record = next(
                (prepared[value] for value in entry.prepared_ids if prepared[value].used_count > 0),
                None,
            )
            if record is None:
                return SpellBookActionResult(False, "No expended prepared copy was found.")
            self.repository.update_prepared_spell_counts(
                self.character_id,
                record.id,
                record.prepared_count,
                record.used_count - 1,
            )
        elif entry.resource_kind == "spontaneous":
            used = {
                (record.class_level_id, record.spell_level): record.used_count
                for record in self.repository.list_spontaneous_slot_uses(self.character_id)
            }
            reference = next(
                (
                    value
                    for value in entry.slot_refs
                    if used.get((value[0], value[1]), 0) > 0
                ),
                None,
            )
            if reference is None:
                return SpellBookActionResult(False, "No expended slot was found.")
            class_level_id, level, _maximum = reference
            self.repository.set_spontaneous_slot_uses(
                self.character_id,
                class_level_id,
                level,
                used[(class_level_id, level)] - 1,
            )
        elif entry.resource_kind == "limited" and entry.spell_id is not None:
            spell = next(
                item
                for item in self.repository.list_spells(self.character_id)
                if item.id == entry.spell_id
            )
            self.repository.set_spell_uses_used(
                self.character_id, spell.id, spell.uses_used - 1
            )
        return SpellBookActionResult(True, f"Restored one use of {entry.name}.")

    def set_traditional_remaining(
        self, key: str, remaining: int
    ) -> SpellBookActionResult:
        """Set a bounded remaining value without changing prepared maxima."""

        entry = next((item for item in self.traditional_entries() if item.key == key), None)
        if entry is None or entry.resource_kind not in {
            "prepared", "spontaneous", "limited"
        }:
            return SpellBookActionResult(False, "That spell has no editable daily usage value.")
        target = max(0, min(entry.maximum, int(remaining)))
        if target == entry.current:
            return SpellBookActionResult(False, "The remaining value is unchanged.")
        target_used = entry.maximum - target
        if entry.resource_kind == "prepared":
            prepared = {
                record.id: record
                for record in self.repository.list_prepared_spells(self.character_id)
            }
            for record_id in entry.prepared_ids:
                record = prepared[record_id]
                used_count = min(record.prepared_count, target_used)
                target_used -= used_count
                self.repository.update_prepared_spell_counts(
                    self.character_id,
                    record.id,
                    record.prepared_count,
                    used_count,
                )
        elif entry.resource_kind == "spontaneous":
            for class_level_id, level, maximum in entry.slot_refs:
                used_count = min(maximum, target_used)
                target_used -= used_count
                self.repository.set_spontaneous_slot_uses(
                    self.character_id, class_level_id, level, used_count
                )
        elif entry.spell_id is not None:
            spell = next(
                item
                for item in self.repository.list_spells(self.character_id)
                if item.id == entry.spell_id
            )
            self.repository.set_spell_uses_used(
                self.character_id, spell.id, spell.uses_max - target
            )
        return SpellBookActionResult(
            True, f"Set {entry.name} to {target} remaining."
        )

    def use_sphere(self, key: str, cost: int) -> SpellBookActionResult:
        entry = next((item for item in self.sphere_entries() if item.key == key), None)
        cost = max(0, int(cost))
        if entry is None or not entry.can_use_sphere(cost):
            return SpellBookActionResult(False, "That sphere effect is not currently available.")
        profile = self.repository.get_casting_profile(self.character_id)
        remaining = cost
        temporary_spent = min(profile.spell_points_temporary, remaining)
        remaining -= temporary_spent
        current_spent = min(profile.spell_points_current, remaining)
        remaining -= current_spent
        if remaining:
            return SpellBookActionResult(False, "Not enough spell points remain.")
        if cost:
            self.repository.update_casting_profile(
                replace(
                    profile,
                    spell_points_temporary=profile.spell_points_temporary - temporary_spent,
                    spell_points_current=profile.spell_points_current - current_spent,
                )
            )
        if entry.limited_remaining is not None and entry.spell_id is not None:
            spell = next(
                (
                    item
                    for item in self.repository.list_spells(self.character_id)
                    if item.id == entry.spell_id
                ),
                None,
            )
            if spell is not None and spell.uses_max:
                self.repository.set_spell_uses_used(
                    self.character_id, spell.id, spell.uses_used + 1
                )
        return SpellBookActionResult(
            bool(cost or entry.limited_remaining is not None),
            f"Used {entry.name}" + (f" for {cost} spell point{'s' if cost != 1 else ''}." if cost else "."),
        )

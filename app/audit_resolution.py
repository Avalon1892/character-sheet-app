"""Rules-facing remedies for character-audit findings.

The registry is intentionally independent of Qt.  Interactive remedies expose
descriptors for the UI adapter; deterministic remedies validate and mutate via
the repository, returning a one-step reversible token.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Protocol

from app.character_audit import AuditContext, AuditFinding
from app.rules import calculate_casting_statistics


@dataclass(frozen=True, slots=True)
class AuditRemedy:
    key: str
    label: str
    description: str
    kind: str = "interactive"
    confirmation: str = ""
    destructive: bool = False


@dataclass(frozen=True, slots=True)
class AuditResolutionPreview:
    """Presentation-neutral preview of one proposed audit resolution.

    Resolvers own these values because only the rules layer knows which saved
    record is affected and what the legal result will be.  Qt merely renders
    the strings and asks for confirmation.
    """

    affected: str
    current: str = ""
    proposed: str = ""
    consequences: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuditUndoToken:
    description: str
    restore: Callable[[], None]


@dataclass(frozen=True, slots=True)
class AuditResolutionOutcome:
    changed: bool
    message: str = ""
    undo: AuditUndoToken | None = None


class AuditResolver(Protocol):
    def remedies(self, context: AuditContext, finding: AuditFinding) -> tuple[AuditRemedy, ...]: ...
    def preview(
        self,
        context: AuditContext,
        finding: AuditFinding,
        remedy_key: str = "",
    ) -> AuditResolutionPreview: ...
    def apply(self, context: AuditContext, finding: AuditFinding, remedy_key: str) -> AuditResolutionOutcome: ...


class AuditResolutionRegistry:
    def __init__(self) -> None:
        self._resolvers: dict[str, AuditResolver] = {}

    def register(self, key: str, resolver: AuditResolver) -> None:
        clean = key.strip()
        if not clean:
            raise ValueError("An audit resolver needs a stable key.")
        self._resolvers[clean] = resolver

    def resolver(self, key: str) -> AuditResolver | None:
        return self._resolvers.get(key)

    def keys(self) -> tuple[str, ...]:
        """Return stable resolver keys for diagnostics and extension tests."""

        return tuple(self._resolvers)

    def remedies(self, context: AuditContext, finding: AuditFinding) -> tuple[AuditRemedy, ...]:
        resolver = self.resolver(finding.resolver_key)
        return resolver.remedies(context, finding) if resolver is not None else ()

    def preview(
        self,
        context: AuditContext,
        finding: AuditFinding,
        remedy_key: str = "",
    ) -> AuditResolutionPreview:
        resolver = self.resolver(finding.resolver_key)
        if resolver is None:
            return AuditResolutionPreview(
                affected=finding.title,
                current=finding.summary,
                consequences=("No direct resolver is registered for this finding.",),
            )
        return resolver.preview(context, finding, remedy_key)

    def apply(self, context: AuditContext, finding: AuditFinding, remedy_key: str) -> AuditResolutionOutcome:
        resolver = self.resolver(finding.resolver_key)
        if resolver is None:
            return AuditResolutionOutcome(False, "No resolver is registered for this finding.")
        return resolver.apply(context, finding, remedy_key)


class InteractiveResolver:
    def __init__(self, *remedies: AuditRemedy) -> None:
        self._remedies = tuple(remedies)

    def remedies(self, _context: AuditContext, _finding: AuditFinding) -> tuple[AuditRemedy, ...]:
        return self._remedies

    def preview(
        self,
        _context: AuditContext,
        finding: AuditFinding,
        remedy_key: str = "",
    ) -> AuditResolutionPreview:
        remedy = next((item for item in self._remedies if item.key == remedy_key), None)
        consequence = remedy.description if remedy is not None else finding.details
        return AuditResolutionPreview(
            affected=finding.title,
            current=finding.summary,
            proposed=remedy.label if remedy is not None else "Choose a valid remedy",
            consequences=tuple(value for value in (consequence,) if value),
        )

    def apply(self, _context: AuditContext, _finding: AuditFinding, _remedy_key: str) -> AuditResolutionOutcome:
        return AuditResolutionOutcome(False, "This remedy requires a user choice.")


class ResourceClampResolver:
    def remedies(self, context: AuditContext, finding: AuditFinding) -> tuple[AuditRemedy, ...]:
        current, maximum = self._values(context, finding)
        if current <= maximum:
            return ()
        return (AuditRemedy(
            "clamp", "Set to maximum",
            f"Change {finding.title.lower()} from {current} to {maximum}.",
            "automatic",
            f"Apply this correction?\n\nCurrent: {current}\nMaximum: {maximum}\nNew value: {maximum}",
        ),)

    def preview(
        self,
        context: AuditContext,
        finding: AuditFinding,
        remedy_key: str = "",
    ) -> AuditResolutionPreview:
        current, maximum = self._values(context, finding)
        return AuditResolutionPreview(
            affected=finding.title,
            current=str(current),
            proposed=str(maximum),
            consequences=(
                "Only the current value changes; the maximum and all other character records are preserved.",
            ),
        )

    def _values(self, context: AuditContext, finding: AuditFinding) -> tuple[int, int]:
        repository = context.repository
        key = finding.subject.key
        if key == "hit-points":
            hp = context.calculator.resolved_hit_points()
            return hp.current, max(0, hp.maximum)
        if key == "martial-focus":
            focus = repository.get_martial_focus(context.character_id)
            return focus.current, max(0, focus.maximum)
        if key == "spell-points":
            profile = context.calculator.resolved_casting_profile()
            ability_modifier = context.calculator.ability_result(profile.casting_ability).ability_modifier
            statistics = calculate_casting_statistics(
                profile, ability_modifier,
                spell_point_sources=context.calculator.spell_point_contributions(),
            )
            maximum = statistics.spell_points_maximum if profile.auto_spell_points else profile.spell_points_maximum
            return profile.spell_points_current, max(0, maximum)
        if key == "prodigy-sequence":
            sequence = repository.get_prodigy_sequence(context.character_id)
            return sequence.current, max(0, sequence.maximum)
        raise ValueError(f"Unsupported resource audit subject: {key}")

    def apply(self, context: AuditContext, finding: AuditFinding, remedy_key: str) -> AuditResolutionOutcome:
        if remedy_key != "clamp":
            return AuditResolutionOutcome(False, "Unknown resource remedy.")
        repository = context.repository
        key = finding.subject.key
        current, maximum = self._values(context, finding)
        if current <= maximum:
            return AuditResolutionOutcome(False, "The resource is already within its maximum.")
        if key == "hit-points":
            before = repository.get_hit_points(context.character_id)
            repository.update_hit_points(replace(before, current=maximum))
            restore = lambda: repository.update_hit_points(before)
        elif key == "martial-focus":
            before = repository.get_martial_focus(context.character_id)
            repository.update_martial_focus(replace(before, current=maximum))
            restore = lambda: repository.update_martial_focus(before)
        elif key == "spell-points":
            before = repository.get_casting_profile(context.character_id)
            repository.update_casting_profile(replace(before, spell_points_current=maximum))
            restore = lambda: repository.update_casting_profile(before)
        elif key == "prodigy-sequence":
            before = repository.get_prodigy_sequence(context.character_id)
            repository.update_prodigy_sequence(replace(before, current=maximum, active=before.active and maximum > 0))
            restore = lambda: repository.update_prodigy_sequence(before)
        else:
            return AuditResolutionOutcome(False, "Unsupported resource remedy.")
        return AuditResolutionOutcome(
            True,
            f"Changed {current} to {maximum}.",
            AuditUndoToken(f"Undo {finding.title}", restore),
        )


class SpontaneousOverageResolver:
    def remedies(self, context: AuditContext, finding: AuditFinding) -> tuple[AuditRemedy, ...]:
        allowed = self._allowed(context, finding)
        return (AuditRemedy(
            "clamp", "Set spent slots to maximum",
            f"Reduce recorded spent level {finding.subject.level} slots to {allowed}.",
            "automatic",
            f"Set spent level {finding.subject.level} slots to {allowed}?",
        ),)

    def preview(
        self,
        context: AuditContext,
        finding: AuditFinding,
        remedy_key: str = "",
    ) -> AuditResolutionPreview:
        records = context.repository.list_spontaneous_slot_uses(context.character_id)
        record = next(
            (
                item for item in records
                if item.class_level_id == finding.subject.class_level_id
                and item.spell_level == finding.subject.level
            ),
            None,
        )
        allowed = self._allowed(context, finding)
        return AuditResolutionPreview(
            affected=f"Level {finding.subject.level} spent spell slots",
            current=str(record.used_count if record is not None else 0),
            proposed=str(allowed),
            consequences=(
                "Known spells and spells per day are unchanged; only the recorded number of spent slots is corrected.",
            ),
        )

    @staticmethod
    def _allowed(context: AuditContext, finding: AuditFinding) -> int:
        from app.traditional_spellcasting import spontaneous_caster_capacities
        capacity = next(
            (item for item in spontaneous_caster_capacities(context.repository, context.character_id)
             if item.class_level_id == finding.subject.class_level_id), None
        )
        level = finding.subject.level
        return max(
            0,
            capacity.total_slots[level]
            if capacity is not None and 0 <= level < len(capacity.total_slots)
            else 0,
        )

    def apply(self, context: AuditContext, finding: AuditFinding, remedy_key: str) -> AuditResolutionOutcome:
        if remedy_key != "clamp":
            return AuditResolutionOutcome(False, "Unknown spell-slot remedy.")
        records = context.repository.list_spontaneous_slot_uses(context.character_id)
        before = next((item for item in records if item.class_level_id == finding.subject.class_level_id and item.spell_level == finding.subject.level), None)
        if before is None:
            return AuditResolutionOutcome(False, "The spent-slot record no longer exists.")
        allowed = self._allowed(context, finding)
        context.repository.set_spontaneous_slot_uses(
            context.character_id, before.class_level_id, before.spell_level, allowed
        )
        return AuditResolutionOutcome(
            True, f"Spent slots set to {allowed}.",
            AuditUndoToken(
                "Undo spell-slot correction",
                lambda: context.repository.set_spontaneous_slot_uses(
                    context.character_id, before.class_level_id, before.spell_level, before.used_count
                ),
            ),
        )


DEFAULT_AUDIT_RESOLVERS = AuditResolutionRegistry()
DEFAULT_AUDIT_RESOLVERS.register("resource-clamp", ResourceClampResolver())
DEFAULT_AUDIT_RESOLVERS.register("spontaneous-overage", SpontaneousOverageResolver())
for _key, _label in (
    ("advancement-choice", "Resolve allocation"),
    ("advancement-overage", "Adjust allocation"),
    ("favored-class", "Edit allocation"),
    ("race-choice", "Configure race"),
    ("class-choice", "Choose options"),
    ("archetype-choice", "Edit archetype choices"),
    ("class-power", "Choose powers"),
    ("magic-sphere-choice", "Choose sphere option"),
    ("martial-sphere-choice", "Choose sphere option"),
    ("prepared-overage", "Edit prepared quantities"),
    ("formula", "Edit formula"),
    ("feat-choice", "Choose feat option"),
):
    DEFAULT_AUDIT_RESOLVERS.register(
        _key,
        InteractiveResolver(AuditRemedy("edit", _label, "Open the exact affected choice in a focused editor.")),
    )
DEFAULT_AUDIT_RESOLVERS.register(
    "invalid-selection",
    InteractiveResolver(
        AuditRemedy("deactivate", "Deactivate", "Keep the entry but stop applying its effects.", destructive=True,
                    confirmation="Deactivate this entry and stop applying its automatic effects?"),
        AuditRemedy("replace", "Replace", "Choose a valid replacement, then remove this invalid entry.", destructive=True,
                    confirmation="Choose a replacement for this invalid entry? The old entry is removed only after a replacement is added."),
        AuditRemedy("remove", "Remove", "Remove the invalid entry and leave its choice unspent.", destructive=True,
                    confirmation="Remove this entry? Its advancement choice will become available again."),
    ),
)
DEFAULT_AUDIT_RESOLVERS.register(
    "invalid-class-power",
    InteractiveResolver(
        AuditRemedy(
            "replace",
            "Replace",
            "Open the exact class-power set with this invalid selection removed from the working choice list.",
            destructive=True,
            confirmation=(
                "Choose a legal replacement. The saved power is changed only after the picker is confirmed."
            ),
        ),
        AuditRemedy(
            "remove",
            "Remove",
            "Remove this exact saved power and leave its class-power slot open.",
            destructive=True,
            confirmation="Remove this invalid class power and leave its slot unspent?",
        ),
    ),
)


def audit_context(repository, character_id: int) -> AuditContext:
    from app.services.character_calculations import CharacterCalculationService
    return AuditContext(repository, character_id, CharacterCalculationService(repository, character_id))

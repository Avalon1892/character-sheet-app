"""Extensible character validation and unresolved-choice projection.

The audit consumes existing rules services; it never owns Pathfinder rules or
mutates character data.  Providers return stable findings which presentation
layers may filter, acknowledge, or route to an existing editor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Protocol

from app.archetype_rules import (
    archetype_choice_selections_from_records,
    archetype_choices,
)
from app.class_choice_rules import resolve_class_choice_slots
from app.class_power_rules import decode_class_power_keys, resolve_class_power_sets
from app.content import archetype_entry, feat_entry, magic_entry, martial_entry
from app.drawback_rules import (
    drawback_requires_choice,
    magic_talent_restriction_reason,
    martial_talent_restriction_reason,
)
from app.formulas import FormulaError
from app.rules import calculate_casting_statistics
from app.race_rules import (
    alternate_trait_conflicts,
    race_entry as racial_catalog_entry,
    validate_race_trait_choices,
)
from app.services.advancement import character_advancement_budgets
from app.services.character_calculations import CharacterCalculationService
from app.sphere_rules import base_sphere_choice_options
from app.traditional_spellcasting import (
    prepared_caster_capacities,
    spontaneous_caster_capacities,
)


AUDIT_SEVERITIES = ("error", "warning", "choice", "review")


@dataclass(frozen=True, slots=True)
class AuditSubject:
    """Stable identity of the record or rule slot described by a finding."""

    kind: str
    record_id: int = 0
    class_level_id: int = 0
    key: str = ""
    field: str = ""
    level: int = -1


@dataclass(frozen=True, slots=True)
class AuditFinding:
    key: str
    severity: str
    category: str
    title: str
    summary: str = ""
    details: str = ""
    action_key: str = ""
    action_label: str = "Review"
    can_ignore: bool = False
    subject: AuditSubject = field(default_factory=lambda: AuditSubject("character"))
    resolver_key: str = ""

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("Audit findings need stable keys.")
        if self.severity not in AUDIT_SEVERITIES:
            raise ValueError(f"Unsupported audit severity: {self.severity}")
        if self.can_ignore and self.severity not in {"warning", "review"}:
            raise ValueError("Only warnings and review findings may be ignored.")


@dataclass(frozen=True, slots=True)
class AuditContext:
    repository: object
    character_id: int
    calculator: CharacterCalculationService


class AuditProvider(Protocol):
    def __call__(self, context: AuditContext) -> Iterable[AuditFinding]: ...


class AuditProviderRegistry:
    """Stable extension point for future class and campaign validators."""

    def __init__(self) -> None:
        self._providers: dict[str, AuditProvider] = {}

    def register(self, key: str, provider: AuditProvider) -> None:
        clean = key.strip()
        if not clean:
            raise ValueError("An audit provider needs a stable key.")
        self._providers[clean] = provider

    def providers(self) -> tuple[tuple[str, AuditProvider], ...]:
        return tuple(self._providers.items())


@dataclass(frozen=True, slots=True)
class CharacterAuditReport:
    character_id: int
    findings: tuple[AuditFinding, ...]
    ignored_keys: frozenset[str] = frozenset()

    @property
    def active_findings(self) -> tuple[AuditFinding, ...]:
        return tuple(
            item for item in self.findings
            if not item.can_ignore or item.key not in self.ignored_keys
        )

    @property
    def ignored_findings(self) -> tuple[AuditFinding, ...]:
        return tuple(
            item for item in self.findings
            if item.can_ignore and item.key in self.ignored_keys
        )

    @property
    def choices(self) -> tuple[AuditFinding, ...]:
        return tuple(item for item in self.active_findings if item.severity == "choice")

    @property
    def errors(self) -> tuple[AuditFinding, ...]:
        return tuple(item for item in self.active_findings if item.severity == "error")

    @property
    def warnings(self) -> tuple[AuditFinding, ...]:
        return tuple(item for item in self.active_findings if item.severity == "warning")

    @property
    def status_text(self) -> str:
        if self.errors:
            return f"{len(self.errors)} rules conflict{'s' if len(self.errors) != 1 else ''}"
        if self.choices:
            return f"{len(self.choices)} choice{'s' if len(self.choices) != 1 else ''} remaining"
        if self.warnings:
            return f"{len(self.warnings)} item{'s' if len(self.warnings) != 1 else ''} to review"
        return "Character valid"

    @property
    def status_kind(self) -> str:
        if self.errors:
            return "error"
        if self.choices:
            return "choice"
        if self.warnings:
            return "warning"
        return "valid"


def _advancement_findings(context: AuditContext) -> Iterable[AuditFinding]:
    for budget in character_advancement_budgets(
        context.repository, context.character_id
    ):
        if budget.remaining > 0:
            action_key = {
                "ability_score_increases": "ability_score_increases",
                "skill_points": "skills",
                "feats": "feats",
                "talents": "talents",
                "spells": "spells",
            }.get(budget.key, "advancement")
            yield AuditFinding(
                f"advancement:{budget.key}:remaining",
                "choice",
                "Advancement",
                f"{budget.remaining} {budget.name.lower()} remaining",
                summary=f"Used {budget.used} of {budget.total}.",
                details=budget.explanation,
                action_key=action_key,
                action_label="Resolve",
                subject=AuditSubject("advancement", key=budget.key),
                resolver_key="advancement-choice",
            )
        elif budget.remaining < 0:
            yield AuditFinding(
                f"advancement:{budget.key}:overspent",
                "error",
                "Advancement",
                f"{budget.name} is overspent by {abs(budget.remaining)}",
                summary=f"Used {budget.used}, but the current allowance is {budget.total}.",
                details=budget.explanation,
                action_key="advancement",
                action_label="Review budget",
                subject=AuditSubject("advancement", key=budget.key),
                resolver_key="advancement-overage",
            )


def _favored_class_findings(context: AuditContext) -> Iterable[AuditFinding]:
    repository = context.repository
    allocations = repository.list_favored_class_bonuses(context.character_id)
    for class_level in repository.list_class_levels(context.character_id):
        record = allocations.get(class_level.id)
        used = 0 if record is None else (
            record.hp_bonus + record.skill_point_bonus + record.manual_bonus
        )
        remaining = class_level.level - used
        if remaining > 0:
            yield AuditFinding(
                f"favored-class:{class_level.id}:remaining",
                "choice",
                "Advancement",
                f"{remaining} favored-class bonus choice{'s' if remaining != 1 else ''} remaining",
                summary=f"{class_level.class_name} has allocated {used} of {class_level.level} level-based favored-class bonuses.",
                action_key="favored_class",
                action_label="Allocate",
                subject=AuditSubject("favored-class", class_level_id=class_level.id),
                resolver_key="favored-class",
            )
        elif remaining < 0:
            yield AuditFinding(
                f"favored-class:{class_level.id}:overspent",
                "error",
                "Advancement",
                f"{class_level.class_name} favored-class bonuses are overspent",
                summary=f"Allocated {used} bonuses for {class_level.level} class levels.",
                action_key="favored_class",
                action_label="Review",
                subject=AuditSubject("favored-class", class_level_id=class_level.id),
                resolver_key="favored-class",
            )


def _racial_choice_findings(context: AuditContext) -> Iterable[AuditFinding]:
    details = context.repository.get_character_details(context.character_id)
    entry = racial_catalog_entry(details.race_key)
    if entry is None:
        return
    conflicts = alternate_trait_conflicts(entry, details.race_alternate_trait_keys)
    if conflicts:
        names = ", ".join(sorted(conflicts))
        yield AuditFinding(
            f"race:{details.race_key}:alternate-conflict",
            "error", "Race", "Conflicting alternate racial traits",
            summary=f"More than one selected trait replaces: {names}.",
            details="Choose only one alternate racial trait for each replaced base trait.",
            action_key="race", action_label="Configure race",
            subject=AuditSubject("race", key=details.race_key),
            resolver_key="race-choice",
        )
    errors = validate_race_trait_choices(
        entry, details.race_alternate_trait_keys, details.race_trait_choices
    )
    if errors:
        yield AuditFinding(
            f"race:{details.race_key}:missing-choice",
            "choice", "Race", "Complete racial trait choices",
            summary=" ".join(errors),
            details="Incomplete choice-driven racial traits do not apply partial automation.",
            action_key="race", action_label="Choose options",
            subject=AuditSubject("race", key=details.race_key),
            resolver_key="race-choice",
        )
def _class_choice_findings(context: AuditContext) -> Iterable[AuditFinding]:
    for slot in resolve_class_choice_slots(context.repository, context.character_id):
        count = len(slot.selected_options)
        if count < slot.minimum:
            missing = slot.minimum - count
            yield AuditFinding(
                f"class-choice:{slot.class_level_id}:{slot.key}:missing",
                "choice",
                "Class choices",
                f"Choose {slot.label}",
                summary=f"{slot.class_name} requires {slot.minimum}; {count} selected and {missing} still needed.",
                details=slot.description,
                action_key="class_choices",
                action_label="Choose",
                subject=AuditSubject("class-choice", class_level_id=slot.class_level_id, key=slot.key),
                resolver_key="class-choice",
            )
        elif count > slot.maximum:
            yield AuditFinding(
                f"class-choice:{slot.class_level_id}:{slot.key}:too-many",
                "error",
                "Class choices",
                f"Too many {slot.label.lower()} selections",
                summary=f"{slot.class_name} allows {slot.maximum}, but {count} are selected.",
                action_key="class_choices",
                action_label="Review",
                subject=AuditSubject("class-choice", class_level_id=slot.class_level_id, key=slot.key),
                resolver_key="class-choice",
            )


def _archetype_choice_findings(context: AuditContext) -> Iterable[AuditFinding]:
    repository = context.repository
    records = repository.list_class_feature_selections(context.character_id)
    selected_archetypes = repository.list_class_archetype_keys(context.character_id)
    for class_level in repository.list_class_levels(context.character_id):
        selected = archetype_choice_selections_from_records(records, class_level.id)
        for archetype_key in selected_archetypes.get(class_level.id, ()):
            definition = archetype_entry(archetype_key) or {}
            for choice in archetype_choices(definition, class_level.level):
                count = len(selected.get(choice.key, ()))
                if count < choice.minimum:
                    yield AuditFinding(
                        f"archetype-choice:{class_level.id}:{choice.key}:missing",
                        "choice",
                        "Archetype choices",
                        f"Choose {choice.name}",
                        summary=f"{definition.get('name', archetype_key)} requires {choice.minimum}; {count} selected.",
                        details=choice.description,
                        action_key="class_choices",
                        action_label="Edit class",
                        subject=AuditSubject("archetype-choice", class_level_id=class_level.id, key=choice.key),
                        resolver_key="archetype-choice",
                    )
                elif count > choice.maximum:
                    yield AuditFinding(
                        f"archetype-choice:{class_level.id}:{choice.key}:too-many",
                        "error",
                        "Archetype choices",
                        f"Too many selections for {choice.name}",
                        summary=f"The archetype allows {choice.maximum}, but {count} are saved.",
                        action_key="class_choices",
                        action_label="Edit class",
                        subject=AuditSubject("archetype-choice", class_level_id=class_level.id, key=choice.key),
                        resolver_key="archetype-choice",
                    )


def _class_power_findings(context: AuditContext) -> Iterable[AuditFinding]:
    records = {
        (item.class_level_id, item.feature_key): item
        for item in context.repository.list_class_feature_selections(
            context.character_id
        )
    }
    for power_set in resolve_class_power_sets(
        context.repository, context.character_id
    ):
        count = len(power_set.selected_options)
        if count < power_set.maximum:
            remaining = power_set.maximum - count
            yield AuditFinding(
                f"class-power:{power_set.class_level_id}:{power_set.key}:remaining",
                "choice",
                "Class powers",
                f"Choose {power_set.label}",
                summary=f"{power_set.class_name} has selected {count} of {power_set.maximum}; {remaining} slot(s) remain.",
                details=power_set.description,
                action_key="class_choices",
                action_label="Choose powers",
                subject=AuditSubject("class-power", class_level_id=power_set.class_level_id, key=power_set.key),
                resolver_key="class-power",
            )
        record = records.get((power_set.class_level_id, power_set.feature_key))
        stored_keys = decode_class_power_keys(record.option_key) if record else ()
        valid_remaining: dict[str, int] = {}
        for option_key in power_set.selected_keys:
            valid_remaining[option_key] = valid_remaining.get(option_key, 0) + 1
        option_map = {option.key: option for option in power_set.options}
        for stored_index, option_key in enumerate(stored_keys):
            remaining = valid_remaining.get(option_key, 0)
            if remaining:
                valid_remaining[option_key] = remaining - 1
                continue
            option = option_map.get(option_key)
            option_name = option.name if option is not None else option_key
            reason = power_set.unavailable_reasons.get(option_key, "")
            if not reason:
                if option is None:
                    reason = "This saved power is no longer available in the current class-power catalog."
                elif stored_index >= power_set.maximum:
                    reason = f"Only {power_set.maximum} {power_set.label.lower()} slot(s) are available."
                else:
                    reason = "This power does not satisfy the current level, prerequisite, archetype, or dependency rules."
            yield AuditFinding(
                f"class-power:{power_set.class_level_id}:{power_set.key}:{stored_index}:{option_key}:unavailable",
                "error",
                "Prerequisites and restrictions",
                f"{option_name} is not currently available",
                summary=reason,
                details=(
                    f"Saved in {power_set.class_name}'s {power_set.label} selection at position "
                    f"{stored_index + 1}. Remove it or replace it with a currently legal option."
                ),
                action_key="class_choices",
                action_label="Resolve power",
                subject=AuditSubject(
                    "class-power",
                    class_level_id=power_set.class_level_id,
                    key=power_set.key,
                    field=option_key,
                    level=stored_index,
                ),
                resolver_key="invalid-class-power",
            )


def _sphere_choice_findings(context: AuditContext) -> Iterable[AuditFinding]:
    repository = context.repository
    for spell in repository.list_spells(context.character_id):
        entry = magic_entry(spell.catalog_key) if spell.catalog_key else None
        category = spell.catalog_category or (str(entry.get("category", "")) if entry else "")
        if category == "Base Sphere":
            options = base_sphere_choice_options(spell.school_or_sphere, "magic")
            if options and not spell.choice.strip():
                yield AuditFinding(
                    f"magic-sphere:{spell.id}:base-choice",
                    "choice",
                    "Sphere choices",
                    f"Choose the {spell.school_or_sphere} starting package",
                    summary="This base sphere grants a required initial package or form choice.",
                    action_key="magic_talents",
                    action_label="Edit sphere",
                    subject=AuditSubject("magic-talent", record_id=spell.id, key=spell.catalog_key, field="choice"),
                    resolver_key="magic-sphere-choice",
                )
        if category == "Drawback" and entry and drawback_requires_choice(entry) and not spell.choice.strip():
            yield AuditFinding(
                f"magic-sphere:{spell.id}:drawback-choice",
                "choice",
                "Sphere choices",
                f"Complete {spell.name}",
                summary="This drawback requires a specific option before its restrictions can be applied correctly.",
                action_key="magic_talents",
                action_label="Edit drawback",
                subject=AuditSubject("magic-talent", record_id=spell.id, key=spell.catalog_key, field="choice"),
                resolver_key="magic-sphere-choice",
            )

    for talent in repository.list_martial_talents(context.character_id):
        entry = martial_entry(talent.catalog_key) if talent.catalog_key else None
        category = talent.catalog_category or talent.talent_type
        if category == "Base Sphere":
            options = base_sphere_choice_options(talent.sphere, "martial")
            if options and not talent.choice.strip():
                yield AuditFinding(
                    f"martial-sphere:{talent.id}:base-choice",
                    "choice",
                    "Sphere choices",
                    f"Choose the {talent.sphere} starting package",
                    summary="This base sphere requires an initial package or granted talent choice.",
                    action_key="martial_talents",
                    action_label="Edit sphere",
                    subject=AuditSubject("martial-talent", record_id=talent.id, key=talent.catalog_key, field="choice"),
                    resolver_key="martial-sphere-choice",
                )
        if category == "Drawback" and entry and drawback_requires_choice(entry) and not talent.choice.strip():
            yield AuditFinding(
                f"martial-sphere:{talent.id}:drawback-choice",
                "choice",
                "Sphere choices",
                f"Complete {talent.name}",
                summary="This drawback requires a specific option before its restrictions can be applied correctly.",
                action_key="martial_talents",
                action_label="Edit drawback",
                subject=AuditSubject("martial-talent", record_id=talent.id, key=talent.catalog_key, field="choice"),
                resolver_key="martial-sphere-choice",
            )


def _sphere_restriction_findings(context: AuditContext) -> Iterable[AuditFinding]:
    repository = context.repository
    spells = repository.list_spells(context.character_id)
    talents = repository.list_martial_talents(context.character_id)
    for spell in spells:
        if not spell.enabled or spell.catalog_category in {"Base Sphere", "Drawback"}:
            continue
        entry = magic_entry(spell.catalog_key) if spell.catalog_key else None
        if not entry:
            continue
        reason = magic_talent_restriction_reason(entry, spells)
        if reason:
            yield AuditFinding(
                f"magic-restriction:{spell.id}",
                "error",
                "Prerequisites and restrictions",
                f"{spell.name} is currently unavailable",
                summary=reason,
                action_key="magic_talents",
                action_label="Review talent",
                subject=AuditSubject("magic-talent", record_id=spell.id, key=spell.catalog_key),
                resolver_key="invalid-selection",
            )
    for talent in talents:
        if not talent.enabled or talent.catalog_category in {"Base Sphere", "Drawback"}:
            continue
        entry = martial_entry(talent.catalog_key) if talent.catalog_key else None
        if not entry:
            continue
        reason = martial_talent_restriction_reason(entry, talents)
        if reason:
            yield AuditFinding(
                f"martial-restriction:{talent.id}",
                "error",
                "Prerequisites and restrictions",
                f"{talent.name} is currently unavailable",
                summary=reason,
                action_key="martial_talents",
                action_label="Review talent",
                subject=AuditSubject("martial-talent", record_id=talent.id, key=talent.catalog_key),
                resolver_key="invalid-selection",
            )


def _feat_choice_findings(context: AuditContext) -> Iterable[AuditFinding]:
    for feat in context.repository.list_feats(context.character_id):
        entry = feat_entry(feat.catalog_key) if feat.catalog_key else None
        automation = dict(entry.get("automation", {})) if entry else {}
        if feat.enabled and automation.get("choice_type") and not feat.choice.strip():
            yield AuditFinding(
                f"feat:{feat.id}:choice",
                "choice",
                "Feat choices",
                f"Complete {feat.name}",
                summary=str(automation.get("choice_label") or "This feat requires a choice."),
                action_key="feats",
                action_label="Choose",
                subject=AuditSubject("feat", record_id=feat.id, key=feat.catalog_key, field="choice"),
                resolver_key="feat-choice",
            )


def _spell_capacity_findings(context: AuditContext) -> Iterable[AuditFinding]:
    repository = context.repository
    prepared = repository.list_prepared_spells(context.character_id)
    for capacity in prepared_caster_capacities(repository, context.character_id):
        by_level: dict[int, int] = {}
        for record in prepared:
            if record.class_level_id == capacity.class_level_id:
                by_level[record.level] = by_level.get(record.level, 0) + record.prepared_count
        for level, count in by_level.items():
            allowed = capacity.slots[level] if 0 <= level < len(capacity.slots) else 0
            if count > allowed:
                yield AuditFinding(
                    f"prepared:{capacity.class_level_id}:{level}:over",
                    "error",
                    "Spellcasting",
                    f"Too many level {level} spells prepared",
                    summary=f"{capacity.class_name} has {count} prepared copies but only {allowed} slots.",
                    action_key="spells_prepared",
                    action_label="Review preparation",
                    subject=AuditSubject("prepared-spells", class_level_id=capacity.class_level_id, level=level),
                    resolver_key="prepared-overage",
                )
    uses = {
        (item.class_level_id, item.spell_level): item.used_count
        for item in repository.list_spontaneous_slot_uses(context.character_id)
    }
    for capacity in spontaneous_caster_capacities(repository, context.character_id):
        for level, used in (
            (level, uses.get((capacity.class_level_id, level), 0))
            for level in range(len(capacity.total_slots))
        ):
            if used > capacity.total_slots[level]:
                yield AuditFinding(
                    f"spontaneous:{capacity.class_level_id}:{level}:over",
                    "error",
                    "Spellcasting",
                    f"Too many level {level} spell slots spent",
                    summary=f"{capacity.class_name} has spent {used} of {capacity.total_slots[level]} slots.",
                    action_key="spells",
                    action_label="Review spell slots",
                    subject=AuditSubject("spontaneous-slots", class_level_id=capacity.class_level_id, level=level),
                    resolver_key="spontaneous-overage",
                )


def _resource_findings(context: AuditContext) -> Iterable[AuditFinding]:
    repository = context.repository
    hp = context.calculator.resolved_hit_points()
    if hp.maximum and hp.current > hp.maximum:
        yield AuditFinding(
            "resource:hp:above-maximum", "warning", "Resources",
            "Current HP exceeds maximum HP",
            summary=f"Current HP is {hp.current}; maximum HP is {hp.maximum}.",
            details="Temporary HP should normally use its separate field.",
            action_key="hit_points", action_label="Review HP",
            can_ignore=True,
            subject=AuditSubject("resource", key="hit-points", field="current"),
            resolver_key="resource-clamp",
        )
    focus = repository.get_martial_focus(context.character_id)
    if focus.current > focus.maximum:
        yield AuditFinding(
            "resource:martial-focus:above-maximum", "error", "Resources",
            "Martial focus exceeds its maximum",
            summary=f"Current focus is {focus.current}; maximum is {focus.maximum}.",
            action_key="martial_focus", action_label="Review focus",
            subject=AuditSubject("resource", key="martial-focus", field="current"),
            resolver_key="resource-clamp",
        )
    profile = context.calculator.resolved_casting_profile()
    ability_modifier = context.calculator.ability_result(
        profile.casting_ability
    ).ability_modifier
    statistics = calculate_casting_statistics(
        profile,
        ability_modifier,
        spell_point_sources=context.calculator.spell_point_contributions(),
    )
    maximum = statistics.spell_points_maximum if profile.auto_spell_points else profile.spell_points_maximum
    if profile.spell_points_current > maximum:
        yield AuditFinding(
            "resource:spell-points:above-maximum", "error", "Resources",
            "Spell points exceed their maximum",
            summary=f"Current spell points are {profile.spell_points_current}; maximum is {maximum}.",
            action_key="casting_profile", action_label="Review spell points",
            subject=AuditSubject("resource", key="spell-points", field="current"),
            resolver_key="resource-clamp",
        )
    sequence = repository.get_prodigy_sequence(context.character_id)
    if sequence.current > sequence.maximum:
        yield AuditFinding(
            "resource:sequence:above-maximum", "error", "Resources",
            "Sequence links exceed their maximum",
            summary=f"Current links are {sequence.current}; maximum is {sequence.maximum}.",
            action_key="prodigy_sequence", action_label="Review Sequence",
            subject=AuditSubject("resource", key="prodigy-sequence", field="current"),
            resolver_key="resource-clamp",
        )


def _formula_findings(context: AuditContext) -> Iterable[AuditFinding]:
    formulas = context.repository.numeric_formulas(context.character_id)
    formula_context = context.calculator.formula_context()
    for (entity_type, entity_id, field_key), expression in formulas.items():
        try:
            formula_context.evaluate(expression)
        except (FormulaError, ArithmeticError, ValueError) as error:
            yield AuditFinding(
                f"formula:{entity_type}:{entity_id}:{field_key}",
                "warning",
                "Formulas",
                f"Formula needs review: {entity_type} · {field_key}",
                summary=str(error),
                action_key="formulas",
                action_label="Review formula",
                can_ignore=True,
                subject=AuditSubject("formula", record_id=entity_id, key=entity_type, field=field_key),
                resolver_key="formula",
            )


DEFAULT_AUDIT_PROVIDERS = AuditProviderRegistry()
for _key, _provider in (
    ("advancement", _advancement_findings),
    ("favored-class", _favored_class_findings),
    ("racial-choices", _racial_choice_findings),
    ("class-choices", _class_choice_findings),
    ("archetype-choices", _archetype_choice_findings),
    ("class-powers", _class_power_findings),
    ("sphere-choices", _sphere_choice_findings),
    ("sphere-restrictions", _sphere_restriction_findings),
    ("feat-choices", _feat_choice_findings),
    ("spell-capacity", _spell_capacity_findings),
    ("resources", _resource_findings),
    ("formulas", _formula_findings),
):
    DEFAULT_AUDIT_PROVIDERS.register(_key, _provider)


def build_character_audit(
    repository,
    character_id: int,
    registry: AuditProviderRegistry = DEFAULT_AUDIT_PROVIDERS,
) -> CharacterAuditReport:
    context = AuditContext(
        repository,
        character_id,
        CharacterCalculationService(repository, character_id),
    )
    findings: dict[str, AuditFinding] = {}
    for _provider_key, provider in registry.providers():
        for finding in provider(context):
            findings[finding.key] = finding
    severity_order = {"error": 0, "choice": 1, "warning": 2, "review": 3}
    ordered = tuple(sorted(
        findings.values(),
        key=lambda item: (
            severity_order[item.severity],
            item.category.casefold(),
            item.title.casefold(),
            item.key,
        ),
    ))
    ignored = frozenset(repository.list_audit_ignores(character_id))
    return CharacterAuditReport(character_id, ordered, ignored)

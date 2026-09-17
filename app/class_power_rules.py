"""Reusable, archetype-aware selections for recurring class powers.

Providers declare progression slots and catalog families.  The resolver owns
all validation and persistence adapters, leaving sheet pages and dialogs free
of class-specific branching.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Iterable, Mapping

from app.catalogs import DEFAULT_CATALOG, RulesCatalog
from app.class_choice_rules import resolve_class_choice_slots
from app.class_feature_context import resolved_class_features_for_level
from app.class_feature_rules import feature_token
from app.class_packages import archetype_runtime_package, class_package
from app.content import archetype_entry, class_entry
from app.models import ClassFeatureSelection, ClassFeatureState, ClassLevel, StatModifier


@dataclass(frozen=True, slots=True)
class ClassPowerOption:
    key: str
    name: str
    description: str
    family: str
    category: str
    minimum_level: int
    prerequisite_names: tuple[str, ...]
    repeatable: bool
    activatable: bool
    automatic_modifiers: tuple[Mapping[str, object], ...]
    source: str
    source_url: str


@dataclass(frozen=True, slots=True)
class ClassPowerProvider:
    key: str
    label: str
    family: str
    feature_tokens: tuple[str, ...]
    owner_class_keys: frozenset[str]
    slot_levels: tuple[int, ...]
    description: str
    depends_on_choice: str = ""
    option_names: tuple[str, ...] = ()
    excluded_categories: tuple[str, ...] = ()
    excluded_option_names: tuple[str, ...] = ()
    excluded_description_patterns: tuple[str, ...] = ()
    restrict_catalog_to_class: bool = True
    change_resource_key: str = ""
    clear_on_full_rest: bool = False

    def applies(self, class_level: ClassLevel, tokens: frozenset[str]) -> bool:
        return class_level.preset_key in self.owner_class_keys and any(
            token in tokens for token in self.feature_tokens
        )


@dataclass(frozen=True, slots=True)
class ResolvedClassPowerSet:
    class_level_id: int
    class_name: str
    class_level: int
    key: str
    label: str
    description: str
    family: str
    slot_levels: tuple[int, ...]
    options: tuple[ClassPowerOption, ...]
    selected_keys: tuple[str, ...]
    selected_options: tuple[ClassPowerOption, ...]
    active_keys: tuple[str, ...]
    unavailable_reasons: Mapping[str, str]
    feature_key: str
    change_resource_key: str = ""
    clear_on_full_rest: bool = False

    @property
    def maximum(self) -> int:
        return len(self.slot_levels)


CLASS_POWER_PROVIDERS: tuple[ClassPowerProvider, ...] = (
    ClassPowerProvider(
        "unchained-monk-ki-powers",
        "Ki Powers",
        "ki_power",
        ("ki-powers", "ki-power"),
        frozenset({"pathfinder-class:monk-unchained"}),
        tuple(range(4, 21, 2)),
        "Choose one ki power at 4th level and every 2 levels thereafter. Level and power prerequisites are checked automatically.",
    ),
    ClassPowerProvider(
        "barbarian-rage-powers",
        "Rage Powers",
        "rage_power",
        ("rage-powers", "rage-power"),
        frozenset({"pathfinder-class:barbarian", "pathfinder-class:barbarian-unchained"}),
        tuple(range(2, 21, 2)),
        "Choose one rage power at 2nd level and every 2 levels thereafter. Archetype-exchanged slots are removed automatically.",
    ),
    ClassPowerProvider(
        "skald-rage-powers",
        "Rage Powers",
        "rage_power",
        ("rage-powers-ska", "rage-powers"),
        frozenset({"pathfinder-class:skald"}),
        tuple(range(3, 21, 3)),
        "Choose one rage power at 3rd level and every 3 Skald levels thereafter. Selected powers are granted through Inspired Rage and retain their normal prerequisites.",
    ),
    ClassPowerProvider(
        "oracle-revelations",
        "Revelations",
        "revelation",
        ("revelation", "revelations"),
        frozenset({"pathfinder-class:oracle"}),
        (1, 3, 7, 11, 15, 19),
        "Choose revelations from the currently selected mystery at 1st, 3rd, 7th, 11th, 15th, and 19th level.",
        "oracle-mystery",
    ),
    ClassPowerProvider(
        "rogue-talents", "Rogue Talents", "rogue_talent",
        ("rogue-talents", "rogue-talent"),
        frozenset({"pathfinder-class:rogue", "pathfinder-class:rogue-unchained"}),
        tuple(range(2, 21, 2)),
        "Choose a rogue talent at 2nd level and every 2 levels thereafter. Advanced talents become available from 10th level.",
    ),
    ClassPowerProvider(
        "slayer-talents", "Slayer Talents", "slayer_talent",
        ("slayer-talents", "slayer-talent"), frozenset({"pathfinder-class:slayer"}),
        tuple(range(2, 21, 2)),
        "Choose a slayer talent at 2nd level and every 2 levels thereafter. Advanced talents become available from 10th level.",
    ),
    ClassPowerProvider(
        "alchemist-discoveries", "Alchemist Discoveries", "alchemist_discovery",
        ("discovery", "discoveries"), frozenset({"pathfinder-class:alchemist"}),
        (*tuple(range(2, 21, 2)), 20, 20),
        "Choose an alchemist discovery at 2nd level and every 2 levels thereafter. Grand Discovery grants two additional normal discoveries at 20th level.",
    ),
    ClassPowerProvider(
        "alchemist-grand-discovery", "Grand Discovery", "alchemist_grand_discovery",
        ("grand-discovery",), frozenset({"pathfinder-class:alchemist"}), (20,),
        "Choose one grand discovery at 20th level, separately from the normal discoveries granted at that level.",
    ),
    ClassPowerProvider(
        "investigator-talents", "Investigator Talents", "investigator_talent",
        ("investigator-talent", "investigator-talents"), frozenset({"pathfinder-class:investigator"}),
        tuple(range(3, 20, 2)),
        "Choose an investigator talent at 3rd level and every 2 levels thereafter.",
    ),
    ClassPowerProvider(
        "witch-hexes", "Witch Hexes", "witch_hex", ("hex", "hexes"),
        frozenset({"pathfinder-class:witch"}), (1, 2, *tuple(range(4, 21, 2))),
        "Choose a hex at 1st and 2nd level and every 2 levels thereafter. Major hexes unlock at 10th level and grand hexes at 18th.",
    ),
    ClassPowerProvider(
        "magus-arcana", "Magus Arcana", "magus_arcana", ("magus-arcana",),
        frozenset({"pathfinder-class:magus"}), tuple(range(3, 21, 3)),
        "Choose one magus arcana at 3rd level and every 3 levels thereafter.",
    ),
    ClassPowerProvider(
        "arcanist-exploits", "Arcanist Exploits", "arcanist_exploit",
        ("arcanist-exploits", "arcanist-exploit"), frozenset({"pathfinder-class:arcanist"}),
        tuple(range(1, 20, 2)),
        "Choose an arcanist exploit at 1st level and every 2 levels thereafter. Greater exploits unlock at 11th level.",
    ),
    ClassPowerProvider(
        "ninja-tricks", "Ninja Tricks", "ninja_trick",
        ("ninja-tricks", "ninja-trick"), frozenset({"pathfinder-class:ninja"}),
        tuple(range(2, 21, 2)),
        "Choose a ninja trick at 2nd level and every 2 levels thereafter. Master tricks unlock at 10th level.",
    ),
    ClassPowerProvider(
        "shaman-hexes", "Shaman Hexes", "shaman_hex",
        ("hex-sha", "hex"), frozenset({"pathfinder-class:shaman"}),
        tuple(range(2, 21, 2)),
        "Choose one general or selected-spirit hex at 2nd level and every 2 Shaman levels thereafter. Spirit access and listed prerequisites remain visible in the picker.",
    ),
    ClassPowerProvider(
        "occultist-focus-powers", "Focus Powers", "occultist_focus_power",
        ("focus-powers",), frozenset({"pathfinder-class:occultist"}),
        (1, *tuple(range(3, 20, 2))),
        "Choose one additional focus power at 1st level and another at 3rd level and every 2 levels thereafter. Base focus powers granted by implement schools are documented by the selected implements.",
    ),
    ClassPowerProvider(
        "vigilante-talents", "Vigilante Talents", "vigilante_talent",
        ("vigilante-talent",), frozenset({"pathfinder-class:vigilante"}),
        tuple(range(2, 21, 2)),
        "Choose one vigilante talent at 2nd level and every 2 levels thereafter. Specialization and level prerequisites are checked from the imported catalog where declared.",
    ),
    ClassPowerProvider(
        "vigilante-social-talents", "Social Talents", "vigilante_social_talent",
        ("social-talent",), frozenset({"pathfinder-class:vigilante"}),
        tuple(range(1, 20, 2)),
        "Choose one social talent at 1st level and every 2 levels thereafter. Level and named prerequisites remain visible and are validated by the shared power picker.",
    ),
)


def _package_power_providers(class_level: ClassLevel) -> tuple[ClassPowerProvider, ...]:
    """Adapt reviewed class-package declarations to the shared power engine."""

    package = class_package(class_level.preset_key)
    if package is None:
        return ()
    return tuple(
        ClassPowerProvider(
            provider.key,
            provider.label,
            provider.family,
            provider.feature_tokens,
            frozenset({class_level.preset_key}),
            provider.slot_levels,
            provider.description,
            provider.depends_on_choice,
            provider.option_names,
            provider.excluded_categories,
            provider.excluded_option_names,
            provider.excluded_description_patterns,
            provider.restrict_catalog_to_class,
            provider.change_resource_key,
            provider.clear_on_full_rest,
        )
        for provider in package.power_providers
        if provider.key and provider.family and provider.slot_levels
    )


def _runtime_power_providers(
    class_level: ClassLevel,
    archetype_keys: Iterable[str],
) -> tuple[ClassPowerProvider, ...]:
    result: list[ClassPowerProvider] = []
    for archetype_key in archetype_keys:
        overlay = archetype_runtime_package(archetype_key) or {}
        for raw in overlay.get("power_providers", ()):
            if not isinstance(raw, Mapping):
                continue
            result.append(
                ClassPowerProvider(
                    str(raw.get("key") or ""),
                    str(raw.get("label") or "Class Powers"),
                    str(raw.get("family") or ""),
                    tuple(str(value) for value in raw.get("feature_tokens", ())),
                    frozenset({class_level.preset_key}),
                    tuple(max(1, int(value)) for value in raw.get("slot_levels", ())),
                    str(raw.get("description") or ""),
                    str(raw.get("depends_on_choice") or ""),
                    tuple(str(value) for value in raw.get("option_names", ()) if str(value)),
                    tuple(
                        str(value)
                        for value in raw.get("excluded_categories", ())
                        if str(value)
                    ),
                    tuple(
                        str(value)
                        for value in raw.get("excluded_option_names", ())
                        if str(value)
                    ),
                    tuple(
                        str(value)
                        for value in raw.get("excluded_description_patterns", ())
                        if str(value)
                    ),
                    False,
                    str(raw.get("change_resource_key") or ""),
                    bool(raw.get("clear_on_full_rest")),
                )
            )
    return tuple(result)


FAMILY_REPLACEMENT_PATTERNS: Mapping[str, str] = {
    "ki_power": r"ki powers?",
    "rage_power": r"rage powers?",
    "revelation": r"revelations?",
    "rogue_talent": r"(?:rogue )?talents?",
    "slayer_talent": r"(?:slayer )?talents?",
    "alchemist_discovery": r"discover(?:y|ies)",
    "alchemist_grand_discovery": r"grand discover(?:y|ies)",
    "investigator_talent": r"(?:investigator )?talents?",
    "witch_hex": r"(?:major |grand )?hex(?:es)?",
    "magus_arcana": r"(?:magus )?arcana",
    "arcanist_exploit": r"(?:arcanist )?exploits?",
    "ninja_trick": r"(?:ninja )?tricks?",
    "shaman_hex": r"(?:shaman )?hex(?:es)?",
    "occultist_focus_power": r"focus powers?",
    "vigilante_talent": r"vigilante talents?",
    "vigilante_social_talent": r"social talents?",
    "mesmerist_trick": r"(?:masterful )?mesmerist tricks?|masterful tricks?",
    "bold_stare": r"bold stare(?: improvements?)?",
}


def class_power_feature_key(provider_key: str) -> str:
    return f"class-power-selection:{provider_key}"


def class_power_active_feature_key(option_key: str) -> str:
    return f"class-power-active:{option_key}"


def encode_class_power_keys(values: Iterable[str]) -> str:
    # Order is meaningful: it assigns selections to their acquisition slots.
    return json.dumps([str(value) for value in values if str(value)])


def decode_class_power_keys(value: str) -> tuple[str, ...]:
    try:
        decoded = json.loads(str(value or "[]"))
    except (TypeError, ValueError):
        return ()
    return tuple(str(item) for item in decoded if str(item)) if isinstance(decoded, list) else ()


def is_class_power_selection(selection: ClassFeatureSelection) -> bool:
    return selection.feature_key.startswith("class-power-selection:") or selection.option_type.casefold() == "class power"


def _option(entry: Mapping[str, object]) -> ClassPowerOption:
    return ClassPowerOption(
        str(entry.get("key") or ""),
        str(entry.get("name") or "Unnamed Power"),
        str(entry.get("description") or ""),
        str(entry.get("family") or ""),
        str(entry.get("category") or "General"),
        max(1, int(entry.get("minimum_level") or 1)),
        tuple(str(value) for value in entry.get("prerequisite_names", ()) if str(value)),
        bool(entry.get("repeatable")),
        bool(entry.get("activatable")),
        tuple(
            dict(value)
            for value in entry.get("automatic_modifiers", ())
            if isinstance(value, Mapping)
        ),
        str(entry.get("source") or "Pathfinder RPG"),
        str(entry.get("source_url") or ""),
    )


def _selected_archetypes(repository, character_id: int, class_level: ClassLevel) -> tuple[dict, ...]:
    keys = repository.list_class_archetype_keys(character_id, class_level.id).get(class_level.id, ())
    return tuple(entry for key in keys if (entry := archetype_entry(key)) is not None)


def _replacement_text(archetype: Mapping[str, object]) -> str:
    values = [str(archetype.get("replaces") or "")]
    values.extend(str(value) for value in archetype.get("removed_features", ()))
    return "; ".join(values)


def _provider_applies(
    repository,
    character_id: int,
    class_level: ClassLevel,
    provider: ClassPowerProvider,
    retained_tokens: frozenset[str],
) -> bool:
    if class_level.preset_key not in provider.owner_class_keys:
        return False
    if any(token in retained_tokens for token in provider.feature_tokens):
        return True
    if len(provider.slot_levels) <= 1:
        return False

    # A recurring feature is commonly represented by one base row at its first
    # acquisition level.  Replacing that first slot must not erase every later
    # slot. Recover the provider only when the catalog's matching replacement
    # clauses are explicitly level-scoped; unscoped exchanges still remove the
    # complete system.
    definition = class_entry(class_level.preset_key) or {}
    base_tokens = {
        feature_token(feature.get("name", ""))
        for feature in definition.get("features", ())
        if isinstance(feature, Mapping)
    }
    if not any(token in base_tokens for token in provider.feature_tokens):
        return False
    label = FAMILY_REPLACEMENT_PATTERNS.get(provider.family, re.escape(provider.label))
    matching_clauses: list[str] = []
    for archetype in _selected_archetypes(repository, character_id, class_level):
        # The generated package deliberately normalizes names for feature
        # resolution (``2nd-level Discovery`` becomes ``discovery``).  Power
        # slots still need the original level qualifier, so prefer matching
        # clauses from the catalog's authored ``replaces`` field and only
        # fall back to normalized declarations when no authored match exists.
        authored = [
            part.strip()
            for part in str(archetype.get("replaces") or "").split(";")
            if part.strip()
        ]
        authored_matches = [
            clause for clause in authored
            if re.search(rf"\b{label}\b", clause, re.I)
        ]
        if authored_matches:
            matching_clauses.extend(authored_matches)
            continue
        matching_clauses.extend(
            clause
            for clause in (
                str(value)
                for value in archetype.get("removed_features", ())
                if str(value)
            )
            if re.search(rf"\b{label}\b", clause, re.I)
        )
    return bool(matching_clauses) and all(
        re.search(r"\b\d+(?:st|nd|rd|th)(?:-level)?\b", clause, re.I)
        for clause in matching_clauses
    )


def _removed_slot_levels(
    repository,
    character_id: int,
    class_level: ClassLevel,
    provider: ClassPowerProvider,
) -> frozenset[int]:
    label = FAMILY_REPLACEMENT_PATTERNS.get(provider.family, re.escape(provider.label.casefold()))
    removed: set[int] = set()
    for archetype in _selected_archetypes(repository, character_id, class_level):
        text = _replacement_text(archetype)
        # Match the level list immediately preceding the relevant feature.
        for match in re.finditer(rf"([^;.]{{0,100}}?)\b{label}\b", text, re.I):
            clause = match.group(1)
            removed.update(
                int(value)
                for value in re.findall(r"\b(\d+)(?:st|nd|rd|th)?(?:-level)?\b", clause, re.I)
            )
    return frozenset(removed)


def _dependency_category(repository, character_id: int, provider: ClassPowerProvider) -> str:
    if not provider.depends_on_choice:
        return ""
    for slot in resolve_class_choice_slots(repository, character_id):
        if slot.key != provider.depends_on_choice or not slot.selected_options:
            continue
        name = slot.selected_options[0].name
        return re.sub(r"\s+Mystery$", "", name, flags=re.I).strip()
    return ""


def _normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _unavailable_reasons(
    options: Iterable[ClassPowerOption],
    acquisition_level: int,
    selected: Iterable[ClassPowerOption],
) -> dict[str, str]:
    owned = {_normalize_name(option.name) for option in selected}
    reasons: dict[str, str] = {}
    for option in options:
        if acquisition_level < option.minimum_level:
            reasons[option.key] = (
                f"Requires class level {option.minimum_level}; the next open power slot is level {acquisition_level}."
            )
            continue
        missing = [name for name in option.prerequisite_names if _normalize_name(name) not in owned]
        if missing:
            reasons[option.key] = "Requires: " + ", ".join(missing)
    return reasons


def resolve_class_power_sets(
    repository,
    character_id: int,
    catalog: RulesCatalog = DEFAULT_CATALOG,
) -> tuple[ResolvedClassPowerSet, ...]:
    selections = repository.list_class_feature_selections(character_id)
    records = {(item.class_level_id, item.feature_key): item for item in selections}
    states = {
        (item.class_level_id, item.feature_key): item
        for item in repository.list_class_feature_states(character_id)
    }
    result: list[ResolvedClassPowerSet] = []
    for class_level in repository.list_class_levels(character_id):
        resolved_features = resolved_class_features_for_level(repository, character_id, class_level)
        tokens = frozenset(feature_token(getattr(feature, "name", "")) for feature in resolved_features)
        archetype_keys = repository.list_class_archetype_keys(
            character_id, class_level.id
        ).get(class_level.id, ())
        runtime_overlays = tuple(
            archetype_runtime_package(key) or {} for key in archetype_keys
        )
        tokens = tokens | frozenset(
            feature_token(value)
            for overlay in runtime_overlays
            for value in overlay.get("system_features", ())
            if str(value)
        )
        providers = (
            *CLASS_POWER_PROVIDERS,
            *_package_power_providers(class_level),
            *_runtime_power_providers(class_level, archetype_keys),
        )
        for provider in providers:
            if not _provider_applies(repository, character_id, class_level, provider, tokens):
                continue
            category = _dependency_category(repository, character_id, provider)
            # A dependent system is intentionally unavailable until its parent choice is made.
            if provider.depends_on_choice and not category:
                continue
            slots = tuple(
                level for level in provider.slot_levels
                if level <= class_level.level
                and level not in _removed_slot_levels(repository, character_id, class_level, provider)
            )
            entries = catalog.class_power_entries(
                provider.family,
                class_level.class_name if provider.restrict_catalog_to_class else None,
            )
            if provider.option_names:
                permitted = {_normalize_name(value) for value in provider.option_names}
                entries = tuple(
                    entry for entry in entries
                    if _normalize_name(entry.get("name")) in permitted
                )
            if provider.excluded_categories:
                excluded = {
                    value.casefold() for value in provider.excluded_categories
                }
                entries = tuple(
                    entry for entry in entries
                    if str(entry.get("category") or "").casefold() not in excluded
                )
            if provider.excluded_option_names:
                excluded_names = {
                    _normalize_name(value) for value in provider.excluded_option_names
                }
                entries = tuple(
                    entry for entry in entries
                    if _normalize_name(entry.get("name")) not in excluded_names
                )
            if provider.excluded_description_patterns:
                entries = tuple(
                    entry for entry in entries
                    if not any(
                        re.search(pattern, str(entry.get("description") or ""), re.I)
                        for pattern in provider.excluded_description_patterns
                    )
                )
            if category:
                entries = tuple(
                    entry for entry in entries
                    if str(entry.get("category") or "").casefold() == category.casefold()
                )
            options = tuple(_option(entry) for entry in entries)
            feature_key = class_power_feature_key(provider.key)
            record = records.get((class_level.id, feature_key))
            stored_keys = decode_class_power_keys(record.option_key) if record else ()
            option_map = {option.key: option for option in options}
            selected_list: list[ClassPowerOption] = []
            owned_names: set[str] = set()
            for key in stored_keys:
                option = option_map.get(key)
                if option is None or len(selected_list) >= len(slots):
                    continue
                acquisition_level = slots[len(selected_list)]
                if acquisition_level < option.minimum_level:
                    continue
                if any(_normalize_name(name) not in owned_names for name in option.prerequisite_names):
                    continue
                if option in selected_list and not option.repeatable:
                    continue
                selected_list.append(option)
                owned_names.add(_normalize_name(option.name))
            selected = tuple(selected_list)
            keys = tuple(option.key for option in selected)
            active_keys = tuple(
                dict.fromkeys(
                    option.key
                    for option in selected
                    if option.activatable
                    and bool(
                        states.get(
                            (class_level.id, class_power_active_feature_key(option.key))
                        )
                        and states[(class_level.id, class_power_active_feature_key(option.key))].active
                    )
                )
            )
            next_level = slots[len(selected)] if len(selected) < len(slots) else class_level.level
            result.append(
                ResolvedClassPowerSet(
                    class_level.id,
                    class_level.class_name,
                    class_level.level,
                    provider.key,
                    provider.label,
                    provider.description,
                    provider.family,
                    slots,
                    options,
                    keys,
                    selected,
                    active_keys,
                    _unavailable_reasons(options, next_level, selected),
                    feature_key,
                    provider.change_resource_key,
                    provider.clear_on_full_rest,
                )
            )
    return tuple(result)


def class_power_selection_record(
    character_id: int,
    power_set: ResolvedClassPowerSet,
    selected_keys: Iterable[str],
) -> ClassFeatureSelection:
    option_map = {option.key: option for option in power_set.options}
    selected: list[ClassPowerOption] = []
    seen: set[str] = set()
    owned_names: set[str] = set()
    for key in selected_keys:
        option = option_map.get(str(key))
        if option is None or len(selected) >= power_set.maximum:
            continue
        acquisition_level = power_set.slot_levels[len(selected)]
        if acquisition_level < option.minimum_level:
            continue
        if any(_normalize_name(name) not in owned_names for name in option.prerequisite_names):
            continue
        if str(key) in seen and not option.repeatable:
            continue
        selected.append(option)
        seen.add(str(key))
        owned_names.add(_normalize_name(option.name))
        if len(selected) >= power_set.maximum:
            break
    return ClassFeatureSelection(
        character_id,
        power_set.class_level_id,
        power_set.feature_key,
        "Class power",
        encode_class_power_keys(option.key for option in selected),
        ", ".join(option.name for option in selected),
        "\n\n".join(f"{option.name}\n{option.description}" for option in selected),
    )


@dataclass(frozen=True, slots=True)
class ClassPowerApplication:
    record: ClassFeatureSelection
    resource_before: ClassFeatureState | None = None
    resource_cost: int = 0


def class_power_change_cost(
    power_set: ResolvedClassPowerSet,
    selected_keys: Iterable[str],
) -> int:
    """Count newly gained or replaced temporary slots; clearing is free."""

    record = class_power_selection_record(0, power_set, selected_keys)
    proposed = decode_class_power_keys(record.option_key)
    previous = power_set.selected_keys
    return sum(
        1
        for index, key in enumerate(proposed)
        if index >= len(previous) or previous[index] != key
    )


def apply_class_power_selection(
    repository,
    character_id: int,
    power_set: ResolvedClassPowerSet,
    selected_keys: Iterable[str],
) -> ClassPowerApplication:
    """Validate and persist one power set, including declared change costs.

    Runtime providers can opt into a shared class resource without adding UI
    branches.  Deterministic validation happens before either record is
    written, making this adapter reusable from the sheet and audit resolver.
    """

    record = class_power_selection_record(character_id, power_set, selected_keys)
    cost = class_power_change_cost(
        power_set, decode_class_power_keys(record.option_key)
    )
    resource_before = None
    if power_set.change_resource_key and cost:
        from app.class_feature_systems import resolve_class_feature_modules

        resource = next(
            (
                resource
                for module in resolve_class_feature_modules(repository, character_id)
                if module.class_level_id == power_set.class_level_id
                for resource in module.resources
                if resource.key == power_set.change_resource_key
            ),
            None,
        )
        if resource is None:
            raise ValueError(
                f"{power_set.label} requires the {power_set.change_resource_key} resource."
            )
        if resource.current < cost:
            raise ValueError(
                f"This change costs {cost} use(s), but only {resource.current} remain."
            )
        resource_before = resource.state
        repository.save_class_feature_state(
            ClassFeatureState(
                character_id=resource.state.character_id,
                class_level_id=resource.state.class_level_id,
                feature_key=resource.state.feature_key,
                current_value=resource.current - cost,
                maximum_adjustment=resource.state.maximum_adjustment,
                maximum_override=resource.state.maximum_override,
                active=resource.state.active,
                choices_json=resource.state.choices_json,
                notes=resource.state.notes,
            )
        )
    repository.save_class_feature_selection(record)
    return ClassPowerApplication(record, resource_before, cost)


def full_rest_class_power_selections(
    repository, character_id: int,
) -> tuple[ResolvedClassPowerSet, ...]:
    """Return selected temporary power sets declared to end on a full rest."""

    return tuple(
        power_set
        for power_set in resolve_class_power_sets(repository, character_id)
        if power_set.clear_on_full_rest and power_set.selected_keys
    )


def class_power_activation_record(
    character_id: int,
    power_set: ResolvedClassPowerSet,
    option_key: str,
    active: bool,
) -> ClassFeatureState:
    option = next(
        (
            item for item in power_set.selected_options
            if item.key == option_key and item.activatable
        ),
        None,
    )
    return ClassFeatureState(
        character_id=character_id,
        class_level_id=power_set.class_level_id,
        feature_key=class_power_active_feature_key(option_key),
        active=bool(active and option is not None),
        notes=(option.name if option is not None else "Class power no longer selected"),
    )


def projected_class_power_features(
    power_sets: Iterable[ResolvedClassPowerSet],
) -> tuple[tuple[int, int, str, str, str], ...]:
    return tuple(
        (power_set.class_level_id, level, option.name, option.description, power_set.label)
        for power_set in power_sets
        for level, option in zip(power_set.slot_levels, power_set.selected_options)
    )


def class_power_reference_values(
    power_sets: Iterable[ResolvedClassPowerSet],
) -> dict[str, float | bool]:
    def token(value: object) -> str:
        return re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_") or "power"

    values: dict[str, float | bool] = {}
    for power_set in power_sets:
        prefix = f"class_power.{token(power_set.class_name)}.{token(power_set.key)}"
        values[f"{prefix}.count"] = float(len(power_set.selected_options))
        values[f"{prefix}.maximum"] = float(power_set.maximum)
        selected = set(power_set.selected_keys)
        active = set(power_set.active_keys)
        for option in power_set.options:
            option_prefix = f"{prefix}.{token(option.name)}"
            values[option_prefix] = option.key in selected
            values[f"{option_prefix}.selected"] = option.key in selected
            values[f"{option_prefix}.active"] = option.key in active
    return values


def class_power_modifier_map(
    repository,
    character_id: int,
    catalog: RulesCatalog = DEFAULT_CATALOG,
) -> dict[str, list[StatModifier]]:
    """Project only reviewed, unambiguous selected-power modifiers.

    Conditional powers remain formula-visible through ``.active`` instead of
    applying a speculative global bonus. New reviewed effects are catalog data,
    so calculations do not gain class- or power-specific branches.
    """

    result: dict[str, list[StatModifier]] = {}
    for power_set in resolve_class_power_sets(repository, character_id, catalog):
        active = set(power_set.active_keys)
        for option in power_set.selected_options:
            for effect in option.automatic_modifiers:
                if effect.get("requires_active") and option.key not in active:
                    continue
                target = str(effect.get("target") or "").strip()
                value = int(effect.get("value") or 0)
                if not target or not value:
                    continue
                result.setdefault(target, []).append(
                    StatModifier(
                        None,
                        target,
                        f"{power_set.label}: {option.name}",
                        str(effect.get("bonus_type") or "untyped"),
                        value,
                        True,
                    )
                )
    return result

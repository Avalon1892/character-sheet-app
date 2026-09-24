"""Archetype-aware, reusable class-feature choices.

Class features declare that a choice slot exists. Catalogs provide the options.
Persistence stores only stable selected keys and immutable display snapshots.
No provider in this module depends on Qt or a particular sheet layout.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import re
from typing import Callable, Iterable, Mapping

from app.catalogs import DEFAULT_CATALOG, RulesCatalog
from app.class_packages import all_class_packages, archetype_runtime_package, class_package
from app.class_feature_rules import (
    archetype_granted_features,
    feature_token,
)
from app.class_feature_context import resolved_class_features_for_level
from app.content import spell_entries
from app.models import ClassFeatureSelection, ClassLevel


@dataclass(frozen=True, slots=True)
class ClassChoiceOption:
    key: str
    name: str
    description: str = ""
    family: str = ""
    category: str = ""
    granted_features: tuple[Mapping[str, object], ...] = ()
    source: str = ""
    source_url: str = ""
    custom: bool = False
    bonus_spells: tuple[Mapping[str, object], ...] = ()
    class_skills: tuple[str, ...] = ()
    cost: int = 1
    minimum_level: int = 1


@dataclass(frozen=True, slots=True)
class ClassChoiceProvider:
    key: str
    label: str
    feature_tokens: tuple[str, ...]
    option_families: tuple[str, ...] = ()
    fixed_options: tuple[ClassChoiceOption, ...] = ()
    minimum: int = 1
    maximum: int = 1
    owner_class_keys: frozenset[str] = frozenset()
    description: str = ""
    depends_on: str = ""
    depends_on_option: str = ""
    minimum_resolver: Callable[[int], int] | None = None
    maximum_resolver: Callable[[int], int] | None = None
    options_from_dependency: bool = False
    minimum_class_level: int = 1
    spell_lists: tuple[str, ...] = ()
    minimum_spell_level: int = 0
    maximum_spell_level: int = -1
    catalog_class_name: str = ""
    point_budget: int = 0
    options_from_provider: str = ""

    def applies(self, class_level: ClassLevel, tokens: frozenset[str]) -> bool:
        if class_level.level < self.minimum_class_level:
            return False
        if self.owner_class_keys and class_level.preset_key not in self.owner_class_keys:
            normalized = (
                class_level.preset_key
                if class_level.preset_key.startswith("pathfinder-class:")
                else f"pathfinder-class:{class_level.preset_key}"
            )
            if normalized not in self.owner_class_keys:
                return False
        return any(
            token in tokens or any(
                re.fullmatch(rf"{re.escape(token)}-\d+(?:d\d+)?(?:-.+)?", owned)
                for owned in tokens
            ) for token in self.feature_tokens
        )


@dataclass(frozen=True, slots=True)
class ResolvedClassChoice:
    class_level_id: int
    class_name: str
    class_level: int
    key: str
    label: str
    description: str
    minimum: int
    maximum: int
    options: tuple[ClassChoiceOption, ...]
    selected_keys: tuple[str, ...]
    selected_options: tuple[ClassChoiceOption, ...]
    feature_key: str
    legacy_feature_keys: tuple[str, ...] = ()
    point_budget: int = 0


@dataclass(frozen=True, slots=True)
class ResolvedSkillSubstitution:
    class_level_id: int
    choice_provider: str
    source_skill: str
    source_specialty: str
    target_skill: str
    source: str
    selection_index: int


@dataclass(frozen=True, slots=True)
class ResolvedPackageSkillRules:
    allow_all_untrained: bool = False
    all_class_skills: bool = False
    take_ten_all: bool = False
    class_skills: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    take_ten_trained_knowledge: bool = False
    allow_knowledge_untrained: bool = False


def _fixed(
    provider: str, key: str, name: str, description: str
) -> ClassChoiceOption:
    return ClassChoiceOption(
        f"class-choice-fixed:{provider}:{key}", name, description, "fixed", provider
    )


ARCANE_BOND_OPTIONS = (
    _fixed("arcane-bond", "familiar", "Familiar", "Gain a familiar using the wizard's effective class level."),
    _fixed("arcane-bond", "bonded-object", "Bonded Object", "Gain a bonded amulet, ring, staff, wand, or weapon and its once-per-day spell benefit."),
)
DIVINE_BOND_OPTIONS = (
    _fixed("divine-bond", "weapon", "Bonded Weapon", "Enhance a weapon through the divine bond class feature."),
    _fixed("divine-bond", "mount", "Divine Mount", "Gain an intelligent special mount using the paladin bond progression."),
)
HUNTERS_BOND_OPTIONS = (
    _fixed("hunters-bond", "companions", "Hunting Companions", "Share part of the favored enemy bonus with allies."),
    _fixed("hunters-bond", "animal-companion", "Animal Companion", "Gain an animal companion using effective druid level equal to ranger level – 3."),
)
NATURE_BOND_OPTIONS = (
    _fixed("nature-bond", "animal-companion", "Animal Companion", "Gain a druid animal companion at full druid level."),
    _fixed("nature-bond", "domain", "Druid Domain", "Choose one permitted cleric or druid domain and gain its powers and domain spell slots."),
)


def _package_choice_providers() -> tuple[ClassChoiceProvider, ...]:
    """Adapt data-only class packages to the shared choice engine.

    Package declarations use stable strings and level thresholds.  The adapter
    owns the small callable bridge required by the runtime resolver, keeping
    JSON definitions free of executable code and Qt dependencies.
    """

    result: list[ClassChoiceProvider] = []
    for package in all_class_packages():
        owner_keys = {package.class_key}
        if package.class_key.startswith("pathfinder-class:"):
            owner_keys.add(package.class_key.removeprefix("pathfinder-class:"))
        for declared in package.choice_providers:
            fixed_options = tuple(
                _fixed(
                    declared.key,
                    option.key,
                    option.name,
                    option.description,
                )
                for option in declared.fixed_options
            )
            category_by_key = {
                option.key: option.category for option in declared.fixed_options
            }
            class_skills_by_key = {
                option.key: option.class_skills for option in declared.fixed_options
            }
            granted_features_by_key = {
                option.key: option.granted_features
                for option in declared.fixed_options
            }
            fixed_options = tuple(
                replace(
                    option,
                    category=category_by_key.get(
                        option.key.rsplit(":", 1)[-1], ""
                    ),
                    cost=next(
                        (
                            declared_option.cost
                            for declared_option in declared.fixed_options
                            if declared_option.key == option.key.rsplit(":", 1)[-1]
                        ),
                        1,
                    ),
                    class_skills=class_skills_by_key.get(
                        option.key.rsplit(":", 1)[-1], ()
                    ),
                    granted_features=granted_features_by_key.get(
                        option.key.rsplit(":", 1)[-1], ()
                    ),
                    minimum_level=next(
                        (item.minimum_level for item in declared.fixed_options
                         if item.key == option.key.rsplit(":", 1)[-1]), 1
                    ),
                )
                for option in fixed_options
            )
            thresholds = tuple(declared.maximum_levels)
            minimum_thresholds = tuple(declared.minimum_levels)
            result.append(
                ClassChoiceProvider(
                    key=declared.key,
                    label=declared.label,
                    feature_tokens=declared.feature_tokens,
                    option_families=declared.option_families,
                    fixed_options=fixed_options,
                    minimum=declared.minimum,
                    maximum=declared.maximum,
                    minimum_resolver=(
                        (lambda level, levels=minimum_thresholds: sum(level >= value for value in levels))
                        if minimum_thresholds else None
                    ),
                    maximum_resolver=(
                        (lambda level, levels=thresholds: sum(level >= value for value in levels))
                        if thresholds else None
                    ),
                    owner_class_keys=frozenset(owner_keys),
                    description=declared.description,
                    minimum_class_level=declared.minimum_class_level,
                    spell_lists=declared.spell_lists,
                    minimum_spell_level=declared.minimum_spell_level,
                    maximum_spell_level=declared.maximum_spell_level,
                    point_budget=declared.point_budget,
                    depends_on=declared.depends_on,
                    depends_on_option=declared.depends_on_option,
                    options_from_dependency=declared.options_from_dependency,
                    options_from_provider=declared.options_from_provider,
                )
            )
    return tuple(result)


def _runtime_choice_providers(
    class_level: ClassLevel,
    archetype_keys: Iterable[str],
) -> tuple[ClassChoiceProvider, ...]:
    """Adapt archetype-only choices without adding class-named resolver code."""

    result: list[ClassChoiceProvider] = []
    for archetype_key in archetype_keys:
        overlay = archetype_runtime_package(archetype_key) or {}
        for raw in overlay.get("choice_providers", ()):
            if not isinstance(raw, Mapping):
                continue
            fixed_options = tuple(
                replace(
                    _fixed(
                        str(raw.get("key") or "runtime-choice"),
                        str(option.get("key") or ""),
                        str(option.get("name") or "Unnamed option"),
                        str(option.get("description") or ""),
                    ),
                    category=str(option.get("category") or ""),
                    minimum_level=max(1, int(option.get("minimum_level") or 1)),
                    cost=max(1, int(option.get("cost", 1) or 1)),
                    class_skills=tuple(
                        str(value)
                        for value in option.get("class_skills", ())
                        if str(value)
                    ),
                    granted_features=tuple(
                        dict(value)
                        for value in option.get("granted_features", ())
                        if isinstance(value, Mapping)
                    ),
                )
                for option in raw.get("fixed_options", ())
                if isinstance(option, Mapping)
            )
            thresholds = tuple(
                max(1, int(value)) for value in raw.get("maximum_levels", ())
            )
            minimum_thresholds = tuple(
                max(1, int(value)) for value in raw.get("minimum_levels", ())
            )
            result.append(ClassChoiceProvider(
                key=str(raw.get("key") or ""),
                label=str(raw.get("label") or "Class choice"),
                feature_tokens=tuple(
                    str(value) for value in raw.get("feature_tokens", ())
                ),
                option_families=tuple(
                    str(value) for value in raw.get("option_families", ())
                ),
                fixed_options=fixed_options,
                minimum=max(0, int(raw.get("minimum", 1) or 0)),
                maximum=max(0, int(raw.get("maximum", 1) or 0)),
                minimum_resolver=(
                    (lambda level, levels=minimum_thresholds: sum(level >= value for value in levels))
                    if minimum_thresholds else None
                ),
                maximum_resolver=(
                    (lambda level, levels=thresholds: sum(level >= value for value in levels))
                    if thresholds else None
                ),
                owner_class_keys=frozenset({class_level.preset_key}),
                description=str(raw.get("description") or ""),
                depends_on=str(raw.get("depends_on") or ""),
                depends_on_option=str(raw.get("depends_on_option") or ""),
                options_from_dependency=bool(raw.get("options_from_dependency")),
                options_from_provider=str(raw.get("options_from_provider") or ""),
                minimum_class_level=max(
                    1, int(raw.get("minimum_class_level", 1) or 1)
                ),
                spell_lists=tuple(
                    str(value)
                    for value in raw.get("spell_lists", ())
                    if str(value)
                ),
                minimum_spell_level=max(
                    0, int(raw.get("minimum_spell_level", 0) or 0)
                ),
                maximum_spell_level=int(raw.get("maximum_spell_level", -1)),
                catalog_class_name=str(raw.get("catalog_class_name") or ""),
                point_budget=max(0, int(raw.get("point_budget", 0) or 0)),
            ))
    return tuple(result)


def _runtime_choice_configuration(
    archetype_keys: Iterable[str],
) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return provider overrides and option filters from archetype overlays."""

    overrides: dict[str, dict] = {}
    filters: dict[str, dict] = {}
    for archetype_key in archetype_keys:
        overlay = archetype_runtime_package(archetype_key) or {}
        for raw in overlay.get("choice_provider_overrides", ()):
            if isinstance(raw, Mapping) and str(raw.get("key") or ""):
                overrides[str(raw["key"])] = dict(raw)
        for raw in overlay.get("choice_option_filters", ()):
            if isinstance(raw, Mapping) and str(raw.get("key") or ""):
                filters[str(raw["key"])] = dict(raw)
    return overrides, filters


def _configured_providers(
    providers: Iterable[ClassChoiceProvider],
    overrides: Mapping[str, Mapping[str, object]],
) -> tuple[ClassChoiceProvider, ...]:
    result = []
    for provider in providers:
        declaration = overrides.get(provider.key, {})
        updates = {}
        for field in ("minimum", "maximum"):
            if field in declaration:
                updates[field] = max(0, int(declaration[field]))
        if "minimum_levels" in declaration:
            levels = tuple(
                max(1, int(value))
                for value in declaration.get("minimum_levels", ())
            )
            updates["minimum_resolver"] = (
                lambda level, thresholds=levels: sum(
                    level >= value for value in thresholds
                )
            )
        if "maximum_levels" in declaration:
            levels = tuple(
                max(1, int(value))
                for value in declaration.get("maximum_levels", ())
            )
            updates["maximum_resolver"] = (
                lambda level, thresholds=levels: sum(
                    level >= value for value in thresholds
                )
            )
        for field in ("label", "description", "catalog_class_name"):
            if field in declaration:
                updates[field] = str(declaration[field])
        if "option_families" in declaration:
            updates["option_families"] = tuple(
                str(value)
                for value in declaration.get("option_families", ())
                if str(value)
            )
        if "fixed_options" in declaration:
            updates["fixed_options"] = tuple(
                ClassChoiceOption(
                    key=str(raw.get("key") or ""),
                    name=str(raw.get("name") or ""),
                    description=str(raw.get("description") or ""),
                    family=str(raw.get("family") or ""),
                    category=str(raw.get("category") or ""),
                    granted_features=tuple(raw.get("granted_features", ())),
                    source=str(raw.get("source") or ""),
                    source_url=str(raw.get("source_url") or ""),
                    bonus_spells=tuple(raw.get("bonus_spells", ())),
                    class_skills=tuple(
                        str(value) for value in raw.get("class_skills", ()) if str(value)
                    ),
                )
                for raw in declaration.get("fixed_options", ())
                if isinstance(raw, Mapping)
                and str(raw.get("key") or "")
                and str(raw.get("name") or "")
            )
        result.append(replace(provider, **updates) if updates else provider)
    return tuple(result)


def _filter_choice_options(
    options: Iterable[ClassChoiceOption],
    declaration: Mapping[str, object],
) -> tuple[ClassChoiceOption, ...]:
    include_names = {
        str(value).casefold() for value in declaration.get("include_names", ())
    }
    include_families = {
        str(value).casefold() for value in declaration.get("include_families", ())
    }
    exclude_names = {
        str(value).casefold() for value in declaration.get("exclude_names", ())
    }
    return tuple(
        option
        for option in options
        if (not include_names or option.name.casefold() in include_names)
        and (not include_families or option.family.casefold() in include_families)
        and option.name.casefold() not in exclude_names
    )


CLASS_CHOICE_PROVIDERS: tuple[ClassChoiceProvider, ...] = (
    *_package_choice_providers(),
    ClassChoiceProvider(
        "cleric-domains", "Domains", ("domain",), ("domain",), minimum=2, maximum=2,
        owner_class_keys=frozenset({"pathfinder-class:cleric"}),
        description="A cleric normally selects two domains granted by the chosen deity or faith.",
    ),
    ClassChoiceProvider(
        "inquisitor-domain", "Domain or Inquisition", ("domain",), ("domain", "inquisition"),
        owner_class_keys=frozenset({"pathfinder-class:inquisitor"}),
        description=(
            "Choose one domain or one inquisition. An inquisitor gains the selected "
            "domain's granted powers, but does not gain its domain spells or bonus "
            "spell slots. Inquisitions likewise grant powers rather than spells."
        ),
    ),
    ClassChoiceProvider(
        "sorcerer-bloodline", "Bloodline", ("sorcerer-bloodline",), ("bloodline",),
        owner_class_keys=frozenset({"pathfinder-class:sorcerer"}),
        description="Choose the source of the sorcerer's inherited magic.",
    ),
    ClassChoiceProvider(
        "bloodrager-bloodline", "Bloodrager Bloodline", ("bloodrager-bloodline",), ("bloodline",),
        owner_class_keys=frozenset({"pathfinder-class:bloodrager"}),
        description="Choose the bloodline that shapes bloodrage powers and bonus spells.",
    ),
    ClassChoiceProvider(
        "oracle-mystery", "Mystery", ("mystery",), ("mystery",),
        owner_class_keys=frozenset({"pathfinder-class:oracle"}),
        description="Choose the divine mystery that grants class skills, bonus spells, and revelations.",
    ),
    ClassChoiceProvider(
        "oracle-curse", "Oracle's Curse", ("oracle-s-curse",), ("oracle_curse",),
        owner_class_keys=frozenset({"pathfinder-class:oracle"}),
        description="Choose the curse whose drawbacks and level-scaled benefits remain part of the Oracle's advancement.",
    ),
    ClassChoiceProvider(
        "witch-patron", "Patron", ("patron-spells",), ("witch_patron",),
        owner_class_keys=frozenset({"pathfinder-class:witch"}),
        description="Choose the patron theme that adds its listed spells to the Witch familiar at the appropriate levels.",
    ),
    ClassChoiceProvider(
        "psychic-discipline", "Psychic Discipline", ("psychic-discipline",), ("psychic_discipline",),
        owner_class_keys=frozenset({"pathfinder-class:psychic"}),
        description="Choose the discipline that grants discipline spells, phrenic-pool ability, and discipline powers.",
    ),
    ClassChoiceProvider(
        "arcane-school", "Arcane School", ("arcane-school",), ("arcane_school",),
        owner_class_keys=frozenset({"pathfinder-class:wizard"}),
        description="Choose a specialist or universalist arcane school.",
    ),
    ClassChoiceProvider(
        "opposition-schools", "Opposition Schools", ("arcane-school",), ("arcane_school",),
        minimum=2, maximum=2, owner_class_keys=frozenset({"pathfinder-class:wizard"}),
        description="A specialist wizard selects two opposition schools.",
        depends_on="arcane-school",
    ),
    ClassChoiceProvider(
        "arcane-bond", "Arcane Bond", ("arcane-bond",), fixed_options=ARCANE_BOND_OPTIONS,
        owner_class_keys=frozenset({"pathfinder-class:wizard"}),
        description="Choose a familiar or a bonded object.",
    ),
    ClassChoiceProvider(
        "divine-bond", "Divine Bond", ("divine-bond",), fixed_options=DIVINE_BOND_OPTIONS,
        owner_class_keys=frozenset({"pathfinder-class:paladin"}),
        description="Choose the form of the paladin's divine bond.",
    ),
    ClassChoiceProvider(
        "hunters-bond", "Hunter's Bond", ("hunter-s-bond",), fixed_options=HUNTERS_BOND_OPTIONS,
        owner_class_keys=frozenset({"pathfinder-class:ranger"}),
        description="Choose hunting companions or an animal companion.",
    ),
    ClassChoiceProvider(
        "nature-bond", "Nature Bond", ("nature-bond",), fixed_options=NATURE_BOND_OPTIONS,
        owner_class_keys=frozenset({"pathfinder-class:druid"}),
        description="Choose an animal companion or a druid domain.",
    ),
    ClassChoiceProvider(
        "nature-domain", "Druid Domain", ("nature-bond",), ("domain",),
        owner_class_keys=frozenset({"pathfinder-class:druid"}),
        description="Choose the domain granted by Nature Bond.",
        depends_on="nature-bond",
        depends_on_option="class-choice-fixed:nature-bond:domain",
    ),
    ClassChoiceProvider(
        "cavalier-order", "Order", ("order",), ("order",),
        owner_class_keys=frozenset({"pathfinder-class:cavalier"}),
        description="Choose the Cavalier order that grants edicts, challenge benefits, skills, and order abilities.",
    ),
    ClassChoiceProvider(
        "samurai-order", "Order", ("order-sam",), ("order",),
        owner_class_keys=frozenset({"pathfinder-class:samurai"}),
        description="Choose the Samurai order that grants edicts, challenge benefits, skills, and order abilities.",
    ),
    ClassChoiceProvider(
        "kineticist-elements", "Elemental Focus / Expanded Elements",
        ("elemental-focus",), ("kineticist_element",),
        owner_class_keys=frozenset({"pathfinder-class:kineticist"}),
        description="Choose the primary element at 1st level and additional elements gained through Expanded Element.",
        maximum_resolver=lambda level: 1 + int(level >= 7) + int(level >= 15),
    ),
    ClassChoiceProvider(
        "shaman-spirit", "Spirit", ("spirit",), ("shaman_spirit",),
        owner_class_keys=frozenset({"pathfinder-class:shaman"}),
        description="Choose the permanent spirit that grants spirit magic, a spirit ability, and spirit-specific hex access.",
    ),
    ClassChoiceProvider(
        "shifter-aspects", "Shifter Aspects", ("shifter-aspect",), ("shifter_aspect",),
        owner_class_keys=frozenset({"pathfinder-class:shifter"}),
        description="Choose one aspect at 1st level and another at 5th level and every 5 levels thereafter.",
        maximum_resolver=lambda level: 1 + sum(level >= threshold for threshold in (5, 10, 15)),
    ),
    ClassChoiceProvider(
        "warpriest-blessings", "Blessings", ("blessings",), ("warpriest_blessing",),
        minimum=2, maximum=2,
        owner_class_keys=frozenset({"pathfinder-class:warpriest"}),
        description="Choose two blessings associated with the Warpriest's deity; each grants its minor and major blessing at the listed levels.",
    ),
)


def class_choice_feature_key(provider_key: str) -> str:
    return f"class-choice:{provider_key}"


def encode_class_choice_option_keys(values: Iterable[str]) -> str:
    return json.dumps(list(dict.fromkeys(str(value) for value in values if str(value))))


def decode_class_choice_option_keys(value: str) -> tuple[str, ...]:
    text = str(value or "").strip()
    if not text:
        return ()
    try:
        decoded = json.loads(text)
    except (TypeError, ValueError):
        return (text,)
    if isinstance(decoded, list):
        return tuple(dict.fromkeys(str(item) for item in decoded if str(item)))
    return (text,)


def is_class_choice_selection(selection: ClassFeatureSelection) -> bool:
    return str(selection.feature_key).startswith("class-choice:") or str(
        selection.option_type
    ).casefold() == "class choice"


def _catalog_option(entry: Mapping[str, object]) -> ClassChoiceOption:
    return ClassChoiceOption(
        str(entry.get("key") or ""),
        str(entry.get("name") or "Unnamed option"),
        str(entry.get("description") or ""),
        str(entry.get("family") or ""),
        str(entry.get("category") or ""),
        tuple(
            item for item in entry.get("granted_features", ())
            if isinstance(item, Mapping)
        ),
        str(entry.get("source") or ""),
        str(entry.get("source_url") or ""),
        False,
        tuple(
            item for item in entry.get("bonus_spells", ())
            if isinstance(item, Mapping)
        ),
        tuple(str(item) for item in entry.get("class_skills", ()) if str(item)),
    )


def _provider_options(
    provider: ClassChoiceProvider,
    class_level: ClassLevel,
    catalog: RulesCatalog,
) -> tuple[ClassChoiceOption, ...]:
    result = list(provider.fixed_options)
    if provider.options_from_provider:
        source = next((item for item in CLASS_CHOICE_PROVIDERS
                       if item.key == provider.options_from_provider), None)
        if source is None or source.options_from_provider:
            raise ValueError(f"Invalid shared choice provider: {provider.options_from_provider}")
        result.extend(source.fixed_options)
    if provider.spell_lists:
        wanted_lists = {value.casefold() for value in provider.spell_lists}
        for entry in spell_entries():
            levels = {
                str(name): int(level)
                for name, level in dict(entry.get("class_levels") or {}).items()
                if str(name).casefold() in wanted_lists
            }
            if not levels:
                continue
            spell_level = min(levels.values())
            if spell_level < provider.minimum_spell_level:
                continue
            if (
                provider.maximum_spell_level >= 0
                and spell_level > provider.maximum_spell_level
            ):
                continue
            catalog_key = str(entry.get("key") or "")
            if not catalog_key:
                continue
            result.append(ClassChoiceOption(
                key=f"spell-choice:{provider.key}:{catalog_key}",
                name=str(entry.get("name") or "Unnamed spell"),
                description=str(
                    entry.get("description") or entry.get("summary") or ""
                ),
                family="spell",
                category=f"Level {spell_level}",
                source=str(
                    entry.get("publisher")
                    or entry.get("source_name")
                    or entry.get("source_group")
                    or "Spell catalog"
                ),
                source_url=str(entry.get("source_url") or ""),
                bonus_spells=({
                    "class_level": provider.minimum_class_level,
                    "spell_level": spell_level,
                    "name": str(entry.get("name") or "Unnamed spell"),
                },),
            ))
    for family in provider.option_families:
        catalog_class_name = provider.catalog_class_name or class_level.class_name
        for entry in catalog.class_choice_entries(family, catalog_class_name):
            option = _catalog_option(entry)
            if provider.key == "inquisitor-domain" and option.family == "domain":
                powers = re.split(
                    r"\bDomain Spells\b", option.description, maxsplit=1, flags=re.I
                )[0].rstrip()
                option = replace(
                    option,
                    description=(
                        f"{powers}\n\n" if powers else ""
                    ) + (
                        "Inquisitor domain rule: this choice grants the domain powers "
                        "above, but it does not grant domain spells or bonus domain "
                        "spell slots."
                    ),
                )
            result.append(option)
    unique = {option.key: option for option in result
              if option.minimum_level <= class_level.level}
    return tuple(sorted(unique.values(), key=lambda option: (option.category, option.name.casefold())))


def _legacy_selection(
    provider: ClassChoiceProvider,
    selections: Mapping[str, ClassFeatureSelection],
) -> ClassFeatureSelection | None:
    if provider.key == "inquisitor-domain":
        return selections.get("domain")
    return None


def _custom_option(selection: ClassFeatureSelection) -> ClassChoiceOption:
    return ClassChoiceOption(
        selection.option_key or f"custom:{feature_token(selection.name)}",
        selection.name or "Custom choice",
        selection.description,
        "custom",
        selection.option_type or "Custom",
        custom=True,
    )


def resolve_class_choice_slots_for_class(
    class_level: ClassLevel,
    resolved_features: Iterable[object],
    feature_selections: Iterable[ClassFeatureSelection],
    catalog: RulesCatalog = DEFAULT_CATALOG,
    providers: Iterable[ClassChoiceProvider] = CLASS_CHOICE_PROVIDERS,
    option_filters: Mapping[str, Mapping[str, object]] | None = None,
    additional_feature_tokens: Iterable[str] = (),
) -> tuple[ResolvedClassChoice, ...]:
    tokens = frozenset(
        feature_token(getattr(feature, "name", "")) for feature in resolved_features
    ) | frozenset(feature_token(value) for value in additional_feature_tokens)
    records = {
        selection.feature_key: selection
        for selection in feature_selections
        if selection.class_level_id == class_level.id
    }
    resolved: list[ResolvedClassChoice] = []
    selected_by_provider: dict[str, tuple[str, ...]] = {}
    options_by_provider: dict[str, tuple[ClassChoiceOption, ...]] = {}
    selected_options_by_provider: dict[str, tuple[ClassChoiceOption, ...]] = {}
    option_filters = option_filters or {}
    for provider in providers:
        if not provider.applies(class_level, tokens):
            continue
        if provider.depends_on:
            dependency = selected_by_provider.get(provider.depends_on, ())
            if not dependency:
                continue
            if provider.depends_on_option and provider.depends_on_option not in dependency:
                continue
            if provider.key == "opposition-schools" and any(
                "universalist" in value for value in dependency
            ):
                continue
        feature_key = class_choice_feature_key(provider.key)
        minimum = (
            max(0, int(provider.minimum_resolver(class_level.level)))
            if provider.minimum_resolver is not None else provider.minimum
        )
        maximum = (
            max(minimum, int(provider.maximum_resolver(class_level.level)))
            if provider.maximum_resolver is not None else provider.maximum
        )
        selection = records.get(feature_key) or _legacy_selection(provider, records)
        if provider.options_from_dependency:
            options = list(
                selected_options_by_provider.get(provider.depends_on, ())
            )
        else:
            options = list(_provider_options(provider, class_level, catalog))
        if provider.key in option_filters:
            options = list(
                _filter_choice_options(options, option_filters[provider.key])
            )
        selected_keys = decode_class_choice_option_keys(selection.option_key) if selection else ()
        if selection and selection.name:
            known_keys = {option.key for option in options}
            if not any(key in known_keys for key in selected_keys):
                matched = next(
                    (
                        option for option in options
                        if option.name.casefold() == selection.name.casefold()
                    ),
                    None,
                )
                if matched:
                    selected_keys = (matched.key,)
                else:
                    # Old saves used free-text names and short keys such as
                    # ``fire``. Preserve those records as custom snapshots
                    # until the user deliberately replaces the choice.
                    custom = _custom_option(selection)
                    options.append(custom)
                    selected_keys = (custom.key,)
        if provider.key == "opposition-schools":
            primary = set(selected_by_provider.get("arcane-school", ()))
            selected_school = next(
                iter(selected_options_by_provider.get("arcane-school", ())),
                None,
            )
            school_category = (
                selected_school.category.casefold() if selected_school else ""
            )
            if "elemental" in school_category:
                # Elemental schools use one opposed elemental school rather
                # than two opposition schools from the eight traditional
                # schools.  The selected element itself is never offered.
                minimum = maximum = 1
                options = [
                    option for option in options
                    if "elemental" in option.category.casefold()
                    and option.key not in primary
                ]
            else:
                options = [
                    option for option in options
                    if option.key not in primary
                    and "elemental" not in option.category.casefold()
                    and "universalist" not in option.name.casefold()
                ]
        option_map = {option.key: option for option in options}
        selected_candidates = tuple(
            option_map[key] for key in selected_keys if key in option_map
        )[:maximum]
        selected_options_list: list[ClassChoiceOption] = []
        spent_points = 0
        for option in selected_candidates:
            if provider.point_budget and spent_points + option.cost > provider.point_budget:
                continue
            selected_options_list.append(option)
            spent_points += option.cost
        selected_options = tuple(selected_options_list)
        selected_keys = tuple(option.key for option in selected_options)
        selected_by_provider[provider.key] = selected_keys
        options_by_provider[provider.key] = tuple(options)
        selected_options_by_provider[provider.key] = selected_options
        resolved.append(
            ResolvedClassChoice(
                class_level.id,
                class_level.class_name,
                class_level.level,
                provider.key,
                provider.label,
                provider.description,
                minimum,
                maximum,
                tuple(options),
                selected_keys,
                selected_options,
                feature_key,
                ("domain",) if provider.key == "inquisitor-domain" else (),
                provider.point_budget,
            )
        )
    return tuple(resolved)


def resolve_class_choice_slots(
    repository,
    character_id: int,
    catalog: RulesCatalog = DEFAULT_CATALOG,
) -> tuple[ResolvedClassChoice, ...]:
    selections = repository.list_class_feature_selections(character_id)
    archetypes = repository.list_class_archetype_keys(character_id)
    result = []
    for class_level in repository.list_class_levels(character_id):
        archetype_keys = archetypes.get(class_level.id, ())
        from app.content import class_entry, archetype_entry
        from app.class_modifications import sphere_bonus_spell_conversions
        from app.archetype_rules import archetype_choice_selections_from_records

        conversions = sphere_bonus_spell_conversions(
            class_entry(class_level.preset_key) or {},
            tuple(entry for key in archetype_keys if (entry := archetype_entry(key))),
            class_level.level,
            archetype_choice_selections_from_records(selections, class_level.id),
        )
        converted_providers = {key for group in conversions for key in group.get("choice_providers", ())}
        overrides, filters = _runtime_choice_configuration(archetype_keys)
        runtime_overlays = tuple(
            archetype_runtime_package(key) or {} for key in archetype_keys
        )
        providers = _configured_providers(
            (
                *CLASS_CHOICE_PROVIDERS,
                *_runtime_choice_providers(class_level, archetype_keys),
            ),
            overrides,
        )
        providers = tuple(provider for provider in providers if provider.key not in converted_providers)
        additional_tokens = {
            str(value)
            for overlay in runtime_overlays
            for value in overlay.get("system_features", ())
            if str(value)
        }
        # An explicit provider override means the archetype retains or
        # replaces that decision even when its generated feature list marks
        # the base feature as altered.  Reuse the provider's own feature
        # tokens instead of requiring every archetype JSON entry to repeat
        # implementation details such as "domains".
        additional_tokens.update(
            token
            for provider in providers
            if provider.key in overrides
            for token in provider.feature_tokens
        )
        result.extend(
            resolve_class_choice_slots_for_class(
                class_level,
                resolved_class_features_for_level(
                    repository, character_id, class_level
                ),
                selections,
                catalog,
                providers,
                filters,
                additional_tokens,
            )
        )
    return tuple(result)


def resolved_package_skill_substitutions(
    repository,
    character_id: int,
    catalog: RulesCatalog = DEFAULT_CATALOG,
) -> tuple[ResolvedSkillSubstitution, ...]:
    """Resolve selected package choices into presentation-independent skill swaps."""

    slots = {
        (slot.class_level_id, slot.key): slot
        for slot in resolve_class_choice_slots(repository, character_id, catalog)
    }
    result: list[ResolvedSkillSubstitution] = []
    for class_level in repository.list_class_levels(character_id):
        package = class_package(class_level.preset_key)
        if package is None:
            continue
        for declared in package.skill_substitutions:
            slot = slots.get((class_level.id, declared.choice_provider))
            if slot is None:
                continue
            expected = f"class-choice-fixed:{declared.choice_provider}:{declared.option_key}"
            try:
                selection_index = slot.selected_keys.index(expected)
            except ValueError:
                continue
            for target in declared.targets:
                result.append(
                    ResolvedSkillSubstitution(
                        class_level.id,
                        declared.choice_provider,
                        declared.source_skill,
                        declared.source_specialty,
                        target,
                        declared.source,
                        selection_index,
                    )
                )
    return tuple(result)


def resolved_package_skill_rules(
    repository,
    character_id: int,
) -> ResolvedPackageSkillRules:
    """Return additive skill permissions declared by retained class features."""

    allow_all_untrained = False
    all_class_skills = False
    take_ten_all = False
    take_ten_trained_knowledge = False
    allow_knowledge_untrained = False
    class_skills: set[str] = set()
    sources: list[str] = []
    for class_level in repository.list_class_levels(character_id):
        package = class_package(class_level.preset_key)
        features = resolved_class_features_for_level(repository, character_id, class_level)
        tokens = frozenset(feature_token(getattr(feature, "name", "")) for feature in features)
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
        declared_rules = [
            (
                rule.minimum_level,
                rule.feature_tokens,
                rule.rule,
                rule.source,
                (),
            )
            for rule in (package.skill_rules if package is not None else ())
        ]
        declared_rules.extend(
            (
                max(1, int(raw.get("minimum_level", 1) or 1)),
                tuple(str(value) for value in raw.get("feature_tokens", ())),
                str(raw.get("rule") or ""),
                str(raw.get("source") or "Class feature"),
                tuple(str(value) for value in raw.get("class_skills", ())),
            )
            for overlay in runtime_overlays
            for raw in overlay.get("skill_rules", ())
            if isinstance(raw, Mapping)
        )
        for minimum_level, feature_tokens, rule_name, source, granted_skills in declared_rules:
            if class_level.level < minimum_level:
                continue
            if feature_tokens and not any(token in tokens for token in feature_tokens):
                continue
            if rule_name == "allow_all_untrained":
                allow_all_untrained = True
            elif rule_name == "all_class_skills":
                all_class_skills = True
            elif rule_name == "take_ten_all":
                take_ten_all = True
            elif rule_name == "take_ten_trained_knowledge":
                take_ten_trained_knowledge = True
            elif rule_name == "allow_knowledge_untrained":
                allow_knowledge_untrained = True
            elif rule_name == "grant_class_skills":
                class_skills.update(granted_skills)
            else:
                continue
            sources.append(source)
    return ResolvedPackageSkillRules(
        allow_all_untrained,
        all_class_skills,
        take_ten_all,
        tuple(sorted(class_skills)),
        tuple(dict.fromkeys(sources)),
        take_ten_trained_knowledge,
        allow_knowledge_untrained,
    )


def class_choice_selection_record(
    character_id: int,
    slot: ResolvedClassChoice,
    selected_keys: Iterable[str],
) -> ClassFeatureSelection:
    keys = tuple(dict.fromkeys(str(value) for value in selected_keys if str(value)))[: slot.maximum]
    options = {option.key: option for option in slot.options}
    selected_list: list[ClassChoiceOption] = []
    spent_points = 0
    for key in keys:
        option = options.get(key)
        if option is None:
            continue
        if slot.point_budget and spent_points + option.cost > slot.point_budget:
            continue
        selected_list.append(option)
        spent_points += option.cost
    selected = tuple(selected_list)
    return ClassFeatureSelection(
        character_id,
        slot.class_level_id,
        slot.feature_key,
        "Class choice",
        encode_class_choice_option_keys(option.key for option in selected),
        ", ".join(option.name for option in selected),
        "\n\n".join(
            f"{option.name}\n{option.description}" if option.description else option.name
            for option in selected
        ),
    )


def class_choice_reference_values(
    slots: Iterable[ResolvedClassChoice],
) -> dict[str, float | bool]:
    def reference_token(value: object) -> str:
        token = re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_")
        return token or "choice"

    values: dict[str, float | bool] = {}
    for slot in slots:
        prefix = (
            f"class_choice.{reference_token(slot.class_name)}."
            f"{reference_token(slot.key)}"
        )
        values[f"{prefix}.selected"] = bool(slot.selected_options)
        values[f"{prefix}.count"] = float(len(slot.selected_options))
        for option in slot.options:
            values[f"{prefix}.{reference_token(option.name)}"] = (
                option.key in slot.selected_keys
            )
    return values


def projected_class_choice_features(
    slots: Iterable[ResolvedClassChoice],
) -> tuple[tuple[str, int, str, str, str], ...]:
    """Project selected choices and their level-gated grants for any sheet.

    The tuple layout is ``(stable_key, level, name, description, source)`` so
    alternate sheet presentations can consume it without importing Qt or a
    UI-specific model.
    """

    result: list[tuple[str, int, str, str, str]] = []
    for slot in slots:
        for option in slot.selected_options:
            prefix = f"class-choice:{slot.class_level_id}:{slot.key}:{option.key}"
            source = f"{slot.class_name}: {slot.label}"
            display_name = (
                f"{option.category} — {option.name}"
                if option.custom and option.category
                else option.name
            )
            result.append(
                (prefix, 1, display_name, option.description, source)
            )
            granted = tuple(option.granted_features)
            if not granted and option.family == "inquisition" and option.description:
                granted = tuple(
                    {
                        "level": feature.level,
                        "name": feature.name,
                        "description": feature.description,
                    }
                    for feature in archetype_granted_features(
                        {
                            "name": f"{option.name} Inquisition",
                            "description": option.description,
                        },
                        slot.class_level,
                    )
                )
            for feature in granted:
                level = int(feature.get("level", 1) or 1)
                if level > slot.class_level:
                    continue
                name = str(feature.get("name") or "Granted feature")
                result.append(
                    (
                        f"{prefix}:{feature.get('key') or feature_token(name)}",
                        level,
                        name,
                        str(feature.get("description") or ""),
                        option.name,
                    )
                )
    return tuple(result)


def selected_class_skill_names(
    slots: Iterable[ResolvedClassChoice],
) -> tuple[str, ...]:
    """Names of class skills granted by selected structured class choices."""

    return tuple(
        dict.fromkeys(
            name
            for slot in slots
            for option in slot.selected_options
            for name in option.class_skills
            if name
        )
    )


def selected_character_class_skill_names(
    repository,
    character_id: int,
) -> tuple[str, ...]:
    """Resolve choice-granted skills after archetype suppression rules."""

    archetypes = repository.list_class_archetype_keys(character_id)
    suppressed: dict[int, set[str]] = {}
    for class_level_id, keys in archetypes.items():
        for key in keys:
            overlay = archetype_runtime_package(key) or {}
            suppressed.setdefault(int(class_level_id), set()).update(
                str(value)
                for value in overlay.get("suppress_choice_class_skills", ())
                if str(value)
            )
    return tuple(
        dict.fromkeys(
            name
            for slot in resolve_class_choice_slots(repository, character_id)
            if slot.key not in suppressed.get(slot.class_level_id, set())
            for option in slot.selected_options
            for name in option.class_skills
            if name
        )
    )

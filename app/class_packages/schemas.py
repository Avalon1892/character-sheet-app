"""Immutable, presentation-independent class-package declarations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PackageResource:
    key: str
    name: str
    feature_tokens: tuple[str, ...]
    progression: str
    description: str
    can_activate: bool = False
    choice_options: tuple[str, ...] = ()
    activate_on_spend: bool = False
    recover_on_full_rest: bool = True
    end_on_full_rest: bool = True
    custom_choice_label: str = ""
    use_requires_active: bool = False
    use_cost: int = 1
    tracks_uses: bool = True
    external_cost_key: str = ""
    requires_choice_provider: str = ""
    requires_choice_option: str = ""
    extra_damage_levels: tuple[int, ...] = ()
    extra_damage_die: str = ""
    extra_damage_type: str = "precision"
    maximum_choices_progression: str = ""
    recovery_progression: str = ""
    use_increases: bool = False
    restore_toward_zero: bool = False


@dataclass(frozen=True, slots=True)
class PackageResourceModule:
    key: str
    title: str
    governing_ability: str
    resources: tuple[PackageResource, ...]
    grantable: bool = True


@dataclass(frozen=True, slots=True)
class PackageEffect:
    key: str
    feature_tokens: tuple[str, ...]
    targets: tuple[str, ...]
    target_family: str
    progression: str
    bonus_type: str
    source: str
    minimum_level: int = 1
    ability: str = ""
    requires_resource_active: str = ""
    requires_resource_choice: str = ""
    requires_resource_key: str = ""
    requires_unarmored: bool = False
    requires_unencumbered: bool = False
    replaces_ability: str = ""
    replacement_cap_progression: str = ""
    only_if_better: bool = False


@dataclass(frozen=True, slots=True)
class PackageChoiceOption:
    key: str
    name: str
    description: str = ""
    category: str = ""
    cost: int = 1
    class_skills: tuple[str, ...] = ()
    granted_features: tuple[Mapping[str, object], ...] = ()
    minimum_level: int = 1
    required_options: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PackageChoiceProvider:
    key: str
    label: str
    feature_tokens: tuple[str, ...]
    option_families: tuple[str, ...] = ()
    fixed_options: tuple[PackageChoiceOption, ...] = ()
    minimum: int = 1
    maximum: int = 1
    minimum_levels: tuple[int, ...] = ()
    maximum_levels: tuple[int, ...] = ()
    description: str = ""
    minimum_class_level: int = 1
    spell_lists: tuple[str, ...] = ()
    minimum_spell_level: int = 0
    maximum_spell_level: int = -1
    point_budget: int = 0
    depends_on: str = ""
    depends_on_option: str = ""
    options_from_dependency: bool = False
    options_from_provider: str = ""


@dataclass(frozen=True, slots=True)
class PackagePowerProvider:
    """Recurring class-power picker declared by a reviewed class package."""

    key: str
    label: str
    family: str
    feature_tokens: tuple[str, ...]
    slot_levels: tuple[int, ...]
    description: str = ""
    depends_on_choice: str = ""
    option_names: tuple[str, ...] = ()
    excluded_categories: tuple[str, ...] = ()
    excluded_option_names: tuple[str, ...] = ()
    excluded_description_patterns: tuple[str, ...] = ()
    restrict_catalog_to_class: bool = True
    change_resource_key: str = ""
    clear_on_full_rest: bool = False


@dataclass(frozen=True, slots=True)
class PackageSkillSubstitution:
    choice_provider: str
    option_key: str
    source_skill: str
    source_specialty: str
    targets: tuple[str, ...]
    source: str


@dataclass(frozen=True, slots=True)
class PackageSkillRule:
    key: str
    feature_tokens: tuple[str, ...]
    minimum_level: int
    rule: str
    source: str


@dataclass(frozen=True, slots=True)
class ClassFamilyPackage:
    key: str
    class_key: str
    class_name: str
    governing_ability: str
    catalog_profile: Mapping[str, object]
    optional_blocks: tuple[str, ...]
    external_systems: tuple[str, ...]
    resource_modules: tuple[PackageResourceModule, ...]
    passive_effects: tuple[PackageEffect, ...]
    choice_providers: tuple[PackageChoiceProvider, ...] = ()
    power_providers: tuple[PackagePowerProvider, ...] = ()
    skill_substitutions: tuple[PackageSkillSubstitution, ...] = ()
    skill_rules: tuple[PackageSkillRule, ...] = ()
    spell_grant_choice_providers: tuple[str, ...] = ()
    prepared_bonus_slot_choice_provider: str = ""
    bonus_feat_levels: tuple[int, ...] = ()
    bonus_feat_label: str = ""
    bonus_feat_replacement_choice_provider: str = ""
    bonus_feat_replacement_levels_by_points: Mapping[int, tuple[int, ...]] | None = None
    governing_ability_choice_provider: str = ""
    notes: str = ""


def package_resource(source: Mapping[str, object]) -> PackageResource:
    return PackageResource(
        key=str(source.get("key") or ""),
        name=str(source.get("name") or ""),
        feature_tokens=tuple(str(value) for value in source.get("feature_tokens", ())),
        progression=str(source.get("progression") or "zero"),
        description=str(source.get("description") or ""),
        can_activate=bool(source.get("can_activate")),
        choice_options=tuple(str(value) for value in source.get("choice_options", ())),
        activate_on_spend=bool(source.get("activate_on_spend")),
        recover_on_full_rest=bool(source.get("recover_on_full_rest", True)),
        end_on_full_rest=bool(source.get("end_on_full_rest", True)),
        custom_choice_label=str(source.get("custom_choice_label") or ""),
        use_requires_active=bool(source.get("use_requires_active")),
        use_cost=max(1, int(source.get("use_cost") or 1)),
        tracks_uses=bool(source.get("tracks_uses", True)),
        external_cost_key=str(source.get("external_cost_key") or ""),
        requires_choice_provider=str(source.get("requires_choice_provider") or ""),
        requires_choice_option=str(source.get("requires_choice_option") or ""),
        extra_damage_levels=tuple(
            max(1, int(value)) for value in source.get("extra_damage_levels", ())
        ),
        extra_damage_die=str(source.get("extra_damage_die") or ""),
        extra_damage_type=str(source.get("extra_damage_type") or "precision"),
        maximum_choices_progression=str(
            source.get("maximum_choices_progression") or ""
        ),
        recovery_progression=str(source.get("recovery_progression") or ""),
        use_increases=bool(source.get("use_increases")),
        restore_toward_zero=bool(source.get("restore_toward_zero")),
    )


def package_module(source: Mapping[str, object]) -> PackageResourceModule:
    return PackageResourceModule(
        key=str(source.get("key") or ""),
        title=str(source.get("title") or "Class Features"),
        governing_ability=str(source.get("governing_ability") or "charisma"),
        resources=tuple(
            package_resource(value)
            for value in source.get("resources", ())
            if isinstance(value, Mapping)
        ),
        grantable=bool(source.get("grantable", True)),
    )


def package_effect(source: Mapping[str, object]) -> PackageEffect:
    return PackageEffect(
        key=str(source.get("key") or ""),
        feature_tokens=tuple(str(value) for value in source.get("feature_tokens", ())),
        targets=tuple(str(value) for value in source.get("targets", ())),
        target_family=str(source.get("target_family") or ""),
        progression=str(source.get("progression") or "zero"),
        bonus_type=str(source.get("bonus_type") or "untyped"),
        source=str(source.get("source") or "Class feature"),
        minimum_level=max(1, int(source.get("minimum_level") or 1)),
        ability=str(source.get("ability") or ""),
        requires_resource_active=str(source.get("requires_resource_active") or ""),
        requires_resource_choice=str(source.get("requires_resource_choice") or ""),
        requires_resource_key=str(source.get("requires_resource_key") or ""),
        requires_unarmored=bool(source.get("requires_unarmored")),
        requires_unencumbered=bool(source.get("requires_unencumbered")),
        replaces_ability=str(source.get("replaces_ability") or ""),
        replacement_cap_progression=str(
            source.get("replacement_cap_progression") or ""
        ),
        only_if_better=bool(source.get("only_if_better")),
    )


def package_choice_option(source: Mapping[str, object]) -> PackageChoiceOption:
    return PackageChoiceOption(
        key=str(source.get("key") or ""),
        name=str(source.get("name") or "Unnamed option"),
        description=str(source.get("description") or ""),
        category=str(source.get("category") or ""),
        minimum_level=max(1, int(source.get("minimum_level") or 1)),
        required_options=tuple(str(value) for value in source.get("required_options", ())),
        cost=max(1, int(source.get("cost", 1) or 1)),
        class_skills=tuple(
            str(value) for value in source.get("class_skills", ()) if str(value)
        ),
        granted_features=tuple(
            dict(value)
            for value in source.get("granted_features", ())
            if isinstance(value, Mapping)
        ),
    )


def package_choice_provider(source: Mapping[str, object]) -> PackageChoiceProvider:
    return PackageChoiceProvider(
        key=str(source.get("key") or ""),
        label=str(source.get("label") or "Class choice"),
        feature_tokens=tuple(str(value) for value in source.get("feature_tokens", ())),
        option_families=tuple(str(value) for value in source.get("option_families", ())),
        fixed_options=tuple(
            package_choice_option(value)
            for value in source.get("fixed_options", ())
            if isinstance(value, Mapping)
        ),
        minimum=max(0, int(source.get("minimum", 1) or 0)),
        maximum=max(0, int(source.get("maximum", 1) or 0)),
        minimum_levels=tuple(
            max(1, int(value)) for value in source.get("minimum_levels", ())
        ),
        maximum_levels=tuple(
            max(1, int(value)) for value in source.get("maximum_levels", ())
        ),
        description=str(source.get("description") or ""),
        minimum_class_level=max(
            1, int(source.get("minimum_class_level", 1) or 1)
        ),
        spell_lists=tuple(
            str(value) for value in source.get("spell_lists", ()) if str(value)
        ),
        minimum_spell_level=max(
            0, int(source.get("minimum_spell_level", 0) or 0)
        ),
        maximum_spell_level=int(source.get("maximum_spell_level", -1)),
        point_budget=max(0, int(source.get("point_budget", 0) or 0)),
        depends_on=str(source.get("depends_on") or ""),
        depends_on_option=str(source.get("depends_on_option") or ""),
        options_from_dependency=bool(source.get("options_from_dependency")),
        options_from_provider=str(source.get("options_from_provider") or ""),
    )


def package_power_provider(source: Mapping[str, object]) -> PackagePowerProvider:
    return PackagePowerProvider(
        key=str(source.get("key") or ""),
        label=str(source.get("label") or "Class Powers"),
        family=str(source.get("family") or ""),
        feature_tokens=tuple(
            str(value) for value in source.get("feature_tokens", ()) if str(value)
        ),
        slot_levels=tuple(
            max(1, int(value)) for value in source.get("slot_levels", ())
        ),
        description=str(source.get("description") or ""),
        depends_on_choice=str(source.get("depends_on_choice") or ""),
        option_names=tuple(
            str(value) for value in source.get("option_names", ()) if str(value)
        ),
        excluded_categories=tuple(
            str(value) for value in source.get("excluded_categories", ()) if str(value)
        ),
        excluded_option_names=tuple(
            str(value) for value in source.get("excluded_option_names", ()) if str(value)
        ),
        excluded_description_patterns=tuple(
            str(value)
            for value in source.get("excluded_description_patterns", ())
            if str(value)
        ),
        restrict_catalog_to_class=bool(
            source.get("restrict_catalog_to_class", True)
        ),
        change_resource_key=str(source.get("change_resource_key") or ""),
        clear_on_full_rest=bool(source.get("clear_on_full_rest")),
    )


def package_skill_substitution(source: Mapping[str, object]) -> PackageSkillSubstitution:
    return PackageSkillSubstitution(
        choice_provider=str(source.get("choice_provider") or ""),
        option_key=str(source.get("option_key") or ""),
        source_skill=str(source.get("source_skill") or ""),
        source_specialty=str(source.get("source_specialty") or ""),
        targets=tuple(str(value) for value in source.get("targets", ())),
        source=str(source.get("source") or "Class feature"),
    )


def package_skill_rule(source: Mapping[str, object]) -> PackageSkillRule:
    return PackageSkillRule(
        key=str(source.get("key") or ""),
        feature_tokens=tuple(str(value) for value in source.get("feature_tokens", ())),
        minimum_level=max(1, int(source.get("minimum_level", 1) or 1)),
        rule=str(source.get("rule") or ""),
        source=str(source.get("source") or "Class feature"),
    )


def class_family_package(source: Mapping[str, object]) -> ClassFamilyPackage:
    return ClassFamilyPackage(
        key=str(source.get("key") or ""),
        class_key=str(source.get("class_key") or ""),
        class_name=str(source.get("class_name") or ""),
        governing_ability=str(source.get("governing_ability") or ""),
        catalog_profile=dict(
            source.get("catalog_profile", {})
            if isinstance(source.get("catalog_profile"), Mapping)
            else {}
        ),
        optional_blocks=tuple(str(value) for value in source.get("optional_blocks", ())),
        external_systems=tuple(str(value) for value in source.get("external_systems", ())),
        resource_modules=tuple(
            package_module(value)
            for value in source.get("resource_modules", ())
            if isinstance(value, Mapping)
        ),
        passive_effects=tuple(
            package_effect(value)
            for value in source.get("passive_effects", ())
            if isinstance(value, Mapping)
        ),
        choice_providers=tuple(
            package_choice_provider(value)
            for value in source.get("choice_providers", ())
            if isinstance(value, Mapping)
        ),
        power_providers=tuple(
            package_power_provider(value)
            for value in source.get("power_providers", ())
            if isinstance(value, Mapping)
        ),
        skill_substitutions=tuple(
            package_skill_substitution(value)
            for value in source.get("skill_substitutions", ())
            if isinstance(value, Mapping)
        ),
        skill_rules=tuple(
            package_skill_rule(value)
            for value in source.get("skill_rules", ())
            if isinstance(value, Mapping)
        ),
        spell_grant_choice_providers=tuple(
            str(value)
            for value in source.get("spell_grant_choice_providers", ())
            if str(value)
        ),
        prepared_bonus_slot_choice_provider=str(
            source.get("prepared_bonus_slot_choice_provider") or ""
        ),
        bonus_feat_levels=tuple(
            max(1, int(value))
            for value in source.get("bonus_feat_levels", ())
        ),
        bonus_feat_label=str(source.get("bonus_feat_label") or "Class bonus feats"),
        bonus_feat_replacement_choice_provider=str(
            source.get("bonus_feat_replacement_choice_provider") or ""
        ),
        bonus_feat_replacement_levels_by_points={
            int(points): tuple(max(1, int(level)) for level in levels)
            for points, levels in dict(
                source.get("bonus_feat_replacement_levels_by_points") or {}
            ).items()
        },
        governing_ability_choice_provider=str(
            source.get("governing_ability_choice_provider") or ""
        ),
        notes=str(source.get("notes") or ""),
    )

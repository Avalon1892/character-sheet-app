from __future__ import annotations

from app.database import CharacterRepository
from dataclasses import replace

from app.archetype_rules import (
    archetype_choice_selections_from_records, replaced_features,
)
from app.class_modifications import resolve_class_level, resolve_class_profile
from app.attack_profiles import (
    AttackProfileResolution,
    ExtraDamageComponent,
    resolve_attack_profile,
)
from app.content import archetype_entry, class_entry, tradition_entry
from app.tradition_rules import (
    casting_tradition_automation,
    resolved_tradition_definition,
    spell_point_bonus,
)
from app.models import (
    ABILITIES,
    ABILITY_KEYS,
    COMBAT_TARGETS,
    SKILLS,
    Attack,
    CastingProfile,
    EquipmentItem,
    Feat,
    HitPoints,
    MartialFocus,
    OngoingEffect,
    SkillState,
    SphereStatistic,
    StatModifier,
    Trait,
)
from app.rules import (
    CalculationResult,
    CastingStatistics,
    Contribution,
    Encumbrance,
    SkillResult,
    SpellPointContribution,
    automatic_hit_points,
    calculate_ability,
    calculate_casting_statistics,
    calculate_combat_statistics,
    calculate_encumbrance,
    calculate_skill,
    calculate_stat,
    condition_modifiers,
    ongoing_effect_modifiers,
    effect_class_skills,
    effect_untrained_skills,
    feat_attack_modifiers,
    feat_modifiers,
    magic_talent_attack_modifiers,
    magic_talent_modifiers,
    martial_talent_attack_modifiers,
    martial_talent_modifiers,
    prodigy_inspired_sequence_bonus,
    prodigy_level,
    racial_land_speed,
    race_modifiers,
    reduced_armor_speed,
    total_bab,
    total_armor_check_penalty,
    trait_attack_modifiers,
    trait_modifiers,
    worn_armor_movement_category,
)
from app.item_effects import effective_item_state, item_modifiers
from app.item_enchantments import (
    effective_enhancement_bonus,
    is_amulet_of_mighty_fists,
    item_is_active_for_attack,
)
from app.item_containers import carried_inventory_weight
from app.services.character_state import CharacterStateSnapshot
from app.character_formulas import CharacterFormulaContext, reference_key
from app.formulas import FormulaError
from app.athletics_rules import (
    armored_athlete_reduction,
    mighty_conditioning_extra_ability,
    project_athletics_movement,
)
from app.skill_rank_rules import effective_skill_ranks as projected_skill_ranks
from app.skill_specializations import base_skill_key, character_skill_definitions
from app.class_feature_systems import (
    class_feature_attack_modifiers,
    class_feature_extra_damage,
    class_feature_modifier_map,
    resolve_class_feature_modules,
)
from app.class_power_rules import class_power_modifier_map
from app.engineering_rules import physical_augmentor_bonus,jet_movement,LOAD_BEARER_KEY
from app.class_combat_rules import generated_class_attacks, class_attack_context_notes
from app.race_rules import generated_racial_attacks, racial_class_skills, racial_automatic_values, racial_per_level_hit_points
from app.class_choice_rules import (
    resolve_class_choice_slots,
    resolved_package_skill_rules,
    resolved_package_skill_substitutions,
    selected_character_class_skill_names,
)


class CharacterCalculationService:
    """Coordinates repository state and the pure PF1e rules functions."""

    def __init__(
        self,
        repository: CharacterRepository,
        character_id: int,
        *,
        sequence_active: bool = False,
        sequence_links: int = 0,
        formulas_enabled: bool = True,
    ) -> None:
        self.repository = repository
        self.character_id = character_id
        self.sequence_active = sequence_active
        self.sequence_links = sequence_links
        self.formulas_enabled = formulas_enabled
        self.state = CharacterStateSnapshot.load(repository, character_id)
        self._automatic_modifiers: dict[str, list[StatModifier]] | None = None
        self._ability_results: dict[str, CalculationResult] | None = None
        self._formula_context: CharacterFormulaContext | None = None
        self._resolved_equipment: tuple[EquipmentItem, ...] | None = None
        self._resolved_feats: tuple[Feat, ...] | None = None
        self._resolved_traits: tuple[Trait, ...] | None = None
        self._resolved_ongoing_effects: tuple[OngoingEffect, ...] | None = None
        self._resolved_classes = None
        self._resolved_class_skills: set[str] | None = None
        self._resolved_casting_profile: CastingProfile | None = None
        self._effective_skill_ranks: dict[str, int] | None = None
        self._encumbrance_results: dict[int, Encumbrance] = {}
        self._armor_check_penalty: int | None = None
        self._numeric_formula_cache = None
        self._selected_archetype_cache: tuple[dict, ...] | None = None
        self._package_skill_rules = None
        self._package_skill_substitutions = None

    def _class_package_skill_rules(self):
        if self._package_skill_rules is None:
            self._package_skill_rules = resolved_package_skill_rules(
                self.repository, self.character_id
            )
        return self._package_skill_rules

    def _class_package_skill_substitutions(self):
        if self._package_skill_substitutions is None:
            self._package_skill_substitutions = resolved_package_skill_substitutions(
                self.repository, self.character_id
            )
        return self._package_skill_substitutions

    def _numeric_formulas(self):
        """Load the character's formula map once per immutable calculation snapshot."""

        if self._numeric_formula_cache is None:
            self._numeric_formula_cache = self.repository.numeric_formulas(
                self.character_id
            )
        return self._numeric_formula_cache

    def resolved_classes(self):
        """Class rows after catalog-declared archetype and choice modifications."""

        if self._resolved_classes is not None:
            return self._resolved_classes
        archetypes_by_level = self.repository.list_class_archetype_keys(self.character_id)
        selections = self.repository.list_class_feature_selections(self.character_id)
        resolved = []
        for class_level in self.state.classes:
            definition = class_entry(class_level.preset_key)
            if definition is None:
                resolved.append(class_level)
                continue
            archetypes = tuple(
                entry for key in archetypes_by_level.get(class_level.id, ())
                if (entry := archetype_entry(key)) is not None
            )
            resolved.append(resolve_class_level(
                class_level,
                definition,
                archetypes,
                archetype_choice_selections_from_records(selections, class_level.id),
            ))
        self._resolved_classes = resolved
        return self._resolved_classes

    def resolved_class_skills(self) -> set[str]:
        if self._resolved_class_skills is not None:
            return self._resolved_class_skills
        archetypes_by_level = self.repository.list_class_archetype_keys(self.character_id)
        selections = self.repository.list_class_feature_selections(self.character_id)
        result: set[str] = set()
        for class_level in self.state.classes:
            definition = class_entry(class_level.preset_key)
            if definition is None:
                continue
            archetypes = tuple(
                entry for key in archetypes_by_level.get(class_level.id, ())
                if (entry := archetype_entry(key)) is not None
            )
            profile = resolve_class_profile(
                definition,
                archetypes,
                archetype_choice_selections_from_records(selections, class_level.id),
            )
            result.update(profile.class_skills)
        skill_name_map = {
            definition.name.casefold(): definition.key for definition in SKILLS
        }
        for name in selected_character_class_skill_names(
            self.repository, self.character_id
        ):
            key = skill_name_map.get(name.casefold())
            if key:
                result.add(key)
        package_skill_rules = self._class_package_skill_rules()
        result.update(package_skill_rules.class_skills)
        result.update(racial_class_skills(self.state.details))
        if package_skill_rules.all_class_skills:
            result.update(definition.key for definition in SKILLS)
        self._resolved_class_skills = result
        return self._resolved_class_skills

    def numeric_formula_value(
        self,
        entity_type: str,
        entity_id: int,
        field_key: str,
        fallback: int | float,
        *,
        minimum: int | float = -1_000_000_000,
        maximum: int | float = 1_000_000_000,
        integer: bool = True,
    ) -> int | float:
        """Resolve one saved numeric formula with a stable literal fallback.

        Formula evaluation intentionally uses a literal snapshot of the same
        character.  This makes ordinary fields composable without allowing an
        equipment bonus (for example) to recursively redefine the ability score
        that its own formula reads.  Invalid and temporarily incomplete formulas
        remain saved for correction while normal sheet calculations keep using
        the last valid literal value.
        """

        if not self.formulas_enabled:
            return fallback
        expression = self._numeric_formulas().get(
            (entity_type, entity_id, field_key), ""
        )
        if not expression:
            return fallback
        try:
            value = float(self.formula_context().evaluate(expression))
            if integer:
                rounded = round(value)
                if abs(value - rounded) > 1e-9:
                    raise FormulaError("The formula must resolve to a whole number.")
                value = int(rounded)
            if not float(minimum) <= float(value) <= float(maximum):
                raise FormulaError(
                    f"The formula result must be between {minimum:g} and {maximum:g}."
                )
            return value
        except FormulaError:
            return fallback

    def resolved_equipment(self) -> tuple[EquipmentItem, ...]:
        if self._resolved_equipment is not None:
            return self._resolved_equipment
        integer_fields = {
            "ac_bonus": (-9999, 9999),
            "max_dex_bonus": (-9999, 9999),
            "armor_check_penalty": (-9999, 9999),
            "enhancement_bonus": (0, 99),
        }
        decimal_fields = {
            "weight": (0, 1_000_000),
            "value_gp": (0, 1_000_000_000),
        }
        resolved = []
        for item in self.state.equipment:
            updates = {}
            for field, (minimum, maximum) in integer_fields.items():
                fallback = getattr(item, field)
                if fallback is None:
                    # max Dex may legitimately be unlimited.  A formula opts
                    # into a concrete value; otherwise preserve None.
                    expression = self._numeric_formulas().get(
                        ("equipment", item.id, field), ""
                    )
                    if not expression:
                        continue
                    fallback = 0
                updates[field] = self.numeric_formula_value(
                    "equipment", item.id, field, fallback,
                    minimum=minimum, maximum=maximum,
                )
            for field, (minimum, maximum) in decimal_fields.items():
                updates[field] = self.numeric_formula_value(
                    "equipment", item.id, field, getattr(item, field),
                    minimum=minimum, maximum=maximum, integer=False,
                )
            resolved.append(replace(item, **updates))
        self._resolved_equipment = tuple(resolved)
        return self._resolved_equipment

    def resolved_feats(self) -> tuple[Feat, ...]:
        if self._resolved_feats is None:
            self._resolved_feats = tuple(
                replace(
                    feat,
                    value=int(self.numeric_formula_value(
                        "feat", feat.id, "value", feat.value,
                        minimum=-9999, maximum=9999,
                    )),
                )
                for feat in self.state.feats
            )
        return self._resolved_feats

    def resolved_traits(self) -> tuple[Trait, ...]:
        if self._resolved_traits is None:
            self._resolved_traits = tuple(
                replace(
                    trait,
                    value=int(self.numeric_formula_value(
                        "trait", trait.id, "value", trait.value,
                        minimum=-9999, maximum=9999,
                    )),
                )
                for trait in self.state.traits
            )
        return self._resolved_traits

    def resolved_ongoing_effects(self) -> tuple[OngoingEffect, ...]:
        if self._resolved_ongoing_effects is None:
            self._resolved_ongoing_effects = tuple(
                replace(
                    effect,
                    value=int(
                        self.numeric_formula_value(
                            "ongoing_effect",
                            effect.id,
                            "value",
                            effect.value,
                            minimum=-9999,
                            maximum=9999,
                        )
                    ),
                )
                for effect in self.state.ongoing_effects
            )
        return self._resolved_ongoing_effects

    def resolved_modifiers(
        self, modifiers: list[StatModifier]
    ) -> list[StatModifier]:
        return [
            replace(
                modifier,
                value=int(self.numeric_formula_value(
                    "modifier", int(modifier.id), "value", modifier.value,
                    minimum=-9999, maximum=9999,
                )),
            )
            if modifier.id is not None else modifier
            for modifier in modifiers
        ]

    def resolved_casting_profile(self) -> CastingProfile:
        if self._resolved_casting_profile is not None:
            return self._resolved_casting_profile
        profile = self.repository.get_casting_profile(self.character_id)
        ranges = {
            "casting_class_levels": (0, 999),
            "caster_level": (0, 999),
            "msb_misc": (-99, 99),
            "dc_misc": (-99, 99),
            "concentration_misc": (-99, 99),
            "spell_points_maximum": (0, 99999),
            "spell_points_misc": (-9999, 9999),
        }
        self._resolved_casting_profile = replace(
            profile,
            **{
                field: int(self.numeric_formula_value(
                    "casting", 0, field, getattr(profile, field),
                    minimum=minimum, maximum=maximum,
                ))
                for field, (minimum, maximum) in ranges.items()
            },
        )
        return self._resolved_casting_profile

    def resolved_sphere_statistic(
        self, statistic: SphereStatistic
    ) -> SphereStatistic:
        slug = reference_key(statistic.sphere)[:61]
        return replace(
            statistic,
            caster_level_bonus=int(self.numeric_formula_value(
                "sphere_stat", 0, f"{slug}_cl", statistic.caster_level_bonus,
                minimum=-999, maximum=999,
            )),
            dc_bonus=int(self.numeric_formula_value(
                "sphere_stat", 0, f"{slug}_dc", statistic.dc_bonus,
                minimum=-999, maximum=999,
            )),
        )

    def resolved_hit_points(self) -> HitPoints:
        hit_points = self.repository.get_hit_points(self.character_id)
        return replace(
            hit_points,
            maximum=int(self.numeric_formula_value(
                "hit_points", 0, "maximum", hit_points.maximum,
                minimum=0, maximum=99999,
            )),
        )

    def hit_point_maximum(self) -> int:
        """Return the same live maximum HP used by every presentation/provider."""

        hit_points = self.resolved_hit_points()
        modifiers = self.resolved_modifiers(
            self.repository.list_modifiers(self.character_id, "hp")
        )
        modifiers += self.automatic_modifier_map().get("hp", [])
        racial_hp = racial_per_level_hit_points(self.state.details) * self.state.character_level
        if racial_hp:
            modifiers.append(StatModifier(None, "hp", "Racial hit points per level", "untyped", racial_hp, True))
        if hit_points.auto_calculate:
            return automatic_hit_points(
                self.resolved_classes(),
                self.ability_results()["constitution"].ability_modifier,
                modifiers,
            ).total
        return max(0, hit_points.maximum + calculate_stat([], modifiers).total)

    def resolved_martial_focus(self) -> MartialFocus:
        focus = self.repository.get_martial_focus(self.character_id)
        maximum = int(self.numeric_formula_value(
            "martial_focus", 0, "maximum", focus.maximum,
            minimum=1, maximum=99,
        ))
        return replace(focus, maximum=maximum, current=min(focus.current, maximum))

    def _selected_archetypes(self) -> tuple[dict, ...]:
        if self._selected_archetype_cache is not None:
            return self._selected_archetype_cache
        keys_by_level = self.repository.list_class_archetype_keys(self.character_id)
        self._selected_archetype_cache = tuple(
            entry
            for class_level in self.state.classes
            for key in keys_by_level.get(class_level.id, ())
            if (entry := archetype_entry(key)) is not None
        )
        return self._selected_archetype_cache

    def native_unarmed_level(self) -> int:
        """Highest retained Monk/Brawler-style native unarmed progression."""
        keys_by_level = self.repository.list_class_archetype_keys(self.character_id)
        result = 0
        for class_level in self.state.classes:
            if class_level.class_name.casefold() not in {"monk", "brawler"}:
                continue
            archetypes = tuple(
                entry
                for key in keys_by_level.get(class_level.id, ())
                if (entry := archetype_entry(key)) is not None
            )
            if any("unarmed-strike" in replaced_features(entry) for entry in archetypes):
                continue
            result = max(result, class_level.level)
        return result

    def additional_unarmed_counting_spheres(self) -> frozenset[str]:
        """Archetype extensions to the normal four unarmed spheres."""
        if any(
            str(entry.get("name") or "").casefold() == "barfighter"
            for entry in self._selected_archetypes()
        ):
            return frozenset({"barroom"})
        return frozenset()

    def resolve_attack_profile(self, attack: Attack) -> AttackProfileResolution:
        formula_sources: list[str] = []
        formula_extra_damage: list[ExtraDamageComponent] = []
        formula_values = self._numeric_formulas()
        resolved_input = attack
        replacements = {}
        for field in ("attack_bonus", "damage_bonus"):
            expression = formula_values.get(("attack", attack.id, field), "")
            if not expression:
                continue
            try:
                if field == "damage_bonus":
                    symbolic = self.formula_context().evaluate_symbolic_dice(expression)
                    if any(count < 0 for count, _sides in symbolic.dice):
                        raise FormulaError("Damage formulas cannot subtract dice.")
                    value = symbolic.constant
                    formula_extra_damage.extend(
                        ExtraDamageComponent(
                            f"{count}d{sides}",
                            "untyped",
                            f"Damage bonus formula: {expression}",
                        )
                        for count, sides in symbolic.dice
                        if count
                    )
                    rendered = symbolic.format()
                else:
                    value = self.formula_context().evaluate(expression)
                    rendered = str(round(value))
                rounded = round(value)
                if abs(value - rounded) > 1e-9:
                    raise FormulaError(f"{field.replace('_', ' ').title()} must resolve to a whole number.")
                if not -9999 <= rounded <= 9999:
                    raise FormulaError(f"{field.replace('_', ' ').title()} is outside the supported range.")
                replacements[field] = int(rounded)
                formula_sources.append(
                    f"{field.replace('_', ' ').title()}: {expression} = {rendered}"
                )
            except FormulaError as error:
                formula_sources.append(
                    f"{field.replace('_', ' ').title()} formula inactive: {error}"
                )
        if replacements:
            resolved_input = replace(attack, **replacements)
        resolution = resolve_attack_profile(
            resolved_input,
            size=self.state.details.size,
            martial_talents=self.state.martial_talents,
            feats=self.resolved_feats(),
            traits=self.resolved_traits(),
            equipment=self.resolved_equipment(),
            enchantments=self.state.item_enchantments,
            native_unarmed_level=self.native_unarmed_level(),
            additional_counting_spheres=self.additional_unarmed_counting_spheres(),
        )
        return replace(
            resolution,
            sources=tuple(formula_sources) + resolution.sources,
            extra_damage=(
                resolution.extra_damage
                + tuple(formula_extra_damage)
                + class_feature_extra_damage(
                    self.repository, self.character_id, resolution.attack
                )
            ),
            conditional_effects=(
                resolution.conditional_effects
                + class_attack_context_notes(
                    self.repository, self.character_id, resolution.attack
                )
            ),
        )

    def attacks(self) -> tuple[Attack, ...]:
        """Persisted attacks plus derived class attacks for every sheet type."""

        modifiers = {
            key: result.ability_modifier
            for key, result in self.ability_results().items()
        }
        return (
            tuple(self.repository.list_attacks(self.character_id))
            + generated_class_attacks(self.repository, self.character_id, modifiers)
            + generated_racial_attacks(self.state.details)
        )

    def formula_context(self) -> CharacterFormulaContext:
        if self._formula_context is None:
            baseline = CharacterCalculationService(
                self.repository,
                self.character_id,
                sequence_active=self.sequence_active,
                sequence_links=self.sequence_links,
                formulas_enabled=False,
            )
            self._formula_context = CharacterFormulaContext(baseline)
        return self._formula_context

    def attack_is_visible(self, attack: Attack) -> bool:
        """Return whether a saved conditional attack belongs on the live sheet."""

        condition = attack.visibility_condition.strip()
        if not condition:
            return True
        try:
            return bool(self.formula_context().evaluate(condition))
        except FormulaError:
            # Keep a temporarily broken dependency from breaking the whole
            # character sheet.  The expression remains saved for editing.
            return False

    def automatic_modifier_map(self) -> dict[str, list[StatModifier]]:
        if self._automatic_modifiers is not None:
            return self._automatic_modifiers
        state = self.state
        result = condition_modifiers(state.conditions)
        bab = total_bab(self.resolved_classes())
        effective_ranks = projected_skill_ranks(
            state.martial_talents, state.skills, state.character_level
        )
        effective_skill_states = {
            key: replace(skill_state, ranks=effective_ranks.get(key, skill_state.ranks))
            for key, skill_state in state.skills.items()
        }
        modifier_maps = (
            {
                target: modifiers
                for target, modifiers in race_modifiers(state.details).items()
                if target not in ABILITY_KEYS
            },
            ongoing_effect_modifiers(self.resolved_ongoing_effects()),
            item_modifiers(self.resolved_equipment()),
            feat_modifiers(
                self.resolved_feats(),
                effective_skill_states,
                state.character_level,
                bab,
                self.resolved_equipment(),
            ),
            trait_modifiers(
                self.resolved_traits(),
                effective_skill_states,
                state.character_level,
                bab,
                self.resolved_equipment(),
            ),
            martial_talent_modifiers(
                state.martial_talents,
                effective_skill_states,
                state.character_level,
                bab,
                self.resolved_equipment(),
            ),
            magic_talent_modifiers(
                state.magic_talents,
                effective_skill_states,
                state.character_level,
                bab,
                self.resolved_equipment(),
            ),
            class_feature_modifier_map(self.repository, self.character_id),
            class_power_modifier_map(self.repository, self.character_id),
        )
        for modifier_map in modifier_maps:
            for target, modifiers in modifier_map.items():
                result.setdefault(target, []).extend(modifiers)
        for device in self.repository.list_engineering_devices(self.character_id):
            bonus=physical_augmentor_bonus(device)
            if not bonus:
                continue
            for definition in character_skill_definitions(self.repository,self.character_id):
                skill_state=state.skills.get(definition.key)
                ability=(skill_state.ability_override if skill_state else "") or definition.ability
                if ability==device["configuration"]:
                    target=f"skill:{definition.key}"
                    result.setdefault(target,[]).append(StatModifier(None,target,
                        f"{device['name']} #{device['id']}","competence",bonus,True))
        profile = self.resolved_casting_profile()
        tradition_automation = casting_tradition_automation(
            self.repository.list_character_traditions(self.character_id, "Casting"),
            casting_class_levels=profile.casting_class_levels,
            legacy_drawbacks=profile.tradition_drawbacks,
        )
        for adjustment in tradition_automation.stat_adjustments:
            result.setdefault(adjustment.target, []).append(StatModifier(
                None,
                adjustment.target,
                adjustment.source,
                adjustment.bonus_type,
                adjustment.value,
                True,
            ))
        for ability, allocation in state.ability_score_increases.items():
            if allocation.points:
                result.setdefault(ability, []).append(
                    StatModifier(
                        None,
                        ability,
                        "Level ability-score increases",
                        "untyped",
                        allocation.points,
                        True,
                    )
                )
        favored_hp = sum(
            allocation.hp_bonus
            for allocation in state.favored_class_bonuses.values()
        )
        if favored_hp:
            result.setdefault("hp", []).append(
                StatModifier(
                    None,
                    "hp",
                    "Favored class bonus",
                    "untyped",
                    favored_hp,
                    True,
                )
            )
        inspired_bonus = prodigy_inspired_sequence_bonus(
            prodigy_level(state.classes), self.sequence_links, self.sequence_active
        )
        if inspired_bonus:
            for target in ("attack", "damage"):
                result.setdefault(target, []).append(
                    StatModifier(
                        None,
                        target,
                        "Prodigy: Inspired Sequence",
                        "insight",
                        inspired_bonus,
                        True,
                    )
                )
        self._automatic_modifiers = result
        return result

    def casting_tradition_automation(self):
        """Expose applied drawback rules and conditional reminders to presenters."""

        profile = self.resolved_casting_profile()
        return casting_tradition_automation(
            self.repository.list_character_traditions(self.character_id, "Casting"),
            casting_class_levels=profile.casting_class_levels,
            legacy_drawbacks=profile.tradition_drawbacks,
        )

    def automatic_total(self, target: str) -> int:
        """Return the stacked total for one registered automatic-effect target."""
        return calculate_stat([], self.automatic_modifier_map().get(target, [])).total

    def movement_results(self) -> dict[str, int | str]:
        """Resolve literal/formula movement bases plus automatic effects."""

        profile = self.state.movement
        formulas = {
            field_key: expression
            for (_entity_type, _entity_id, field_key), expression
            in self._numeric_formulas().items()
        }
        bases = {
            key: int(getattr(profile, key))
            for key in (
                "land_speed", "armor_speed", "fly_speed", "swim_speed",
                "climb_speed", "burrow_speed", "teleport_speed",
            )
        }
        if formulas:
            context = self.formula_context()
            for key, expression in formulas.items():
                if key not in bases:
                    continue
                try:
                    value = context.evaluate(expression)
                    rounded = round(value)
                    if abs(value - rounded) > 1e-9 or not 0 <= rounded <= 9999:
                        raise FormulaError("Movement must resolve to a whole number from 0 to 9,999.")
                    bases[key] = int(rounded)
                except FormulaError:
                    # Keep the saved literal as a stable fallback while the UI
                    # displays the formula error for correction.
                    pass
        return self._movement_results_from_bases(bases)

    def literal_movement_results(self) -> dict[str, int | str]:
        """Movement projection used while constructing the formula namespace."""

        profile = self.state.movement
        bases = {
            key: int(getattr(profile, key))
            for key in (
                "land_speed", "armor_speed", "fly_speed", "swim_speed",
                "climb_speed", "burrow_speed", "teleport_speed",
            )
        }
        return self._movement_results_from_bases(bases)

    def _movement_results_from_bases(
        self, bases: dict[str, int]
    ) -> dict[str, int | str]:
        profile = self.state.movement
        for target, value in racial_automatic_values(self.state.details, "movement_grants").items():
            bases[target] = max(bases.get(target, 0), value)
        racial = racial_land_speed(self.state.details)
        land_base = bases["land_speed"] or racial
        unrestricted_land = max(0, land_base + self.automatic_total("land_speed"))
        jet_sources={}
        maneuverability=profile.fly_maneuverability
        for device in self.repository.list_engineering_devices(self.character_id):
            grant=jet_movement(device,light_load=self.encumbrance(unrestricted_land).load=="Light")
            if grant:
                target,speed,jet_maneuverability=grant
                if speed>bases[target]:
                    bases[target]=speed
                    jet_sources[target]=device
                    if target=="fly_speed":maneuverability=jet_maneuverability
        athletics = project_athletics_movement(
            self.state.martial_talents,
            self.state.skills,
            self.state.character_level,
            self.resolved_martial_focus().current,
            {
                "land_speed": unrestricted_land,
                "fly_speed": bases["fly_speed"] + self.automatic_total("fly_speed"),
                "swim_speed": bases["swim_speed"] + self.automatic_total("swim_speed"),
                "climb_speed": bases["climb_speed"] + self.automatic_total("climb_speed"),
                "burrow_speed": bases["burrow_speed"] + self.automatic_total("burrow_speed"),
                "teleport_speed": bases["teleport_speed"] + self.automatic_total("teleport_speed"),
            },
            maneuverability,
        )
        unrestricted_land = athletics.speeds["land_speed"]
        armor_weight, _armor_name = worn_armor_movement_category(
            self.resolved_equipment()
        )
        if bases["armor_speed"]:
            armor_base = bases["armor_speed"]
        elif armor_weight in {"medium", "heavy"}:
            armor_base = reduced_armor_speed(unrestricted_land)
        else:
            armor_base = unrestricted_land
        armor_speed = max(
            0, armor_base + self.automatic_total("armor_speed")
        )
        encumbrance = self.encumbrance(unrestricted_land)
        if encumbrance.load != "Light":
            armor_speed = min(armor_speed, encumbrance.speed)
        armor_changes_current_speed = (
            armor_weight in {"medium", "heavy"}
            or bool(armor_weight and bases["armor_speed"])
            or encumbrance.load != "Light"
        )
        land = armor_speed if armor_changes_current_speed else unrestricted_land
        result: dict[str, int | str] = {
            "land_speed": land,
            "armor_speed": armor_speed,
            "fly_speed": athletics.speeds["fly_speed"],
            "swim_speed": athletics.speeds["swim_speed"],
            "climb_speed": athletics.speeds["climb_speed"],
            "burrow_speed": athletics.speeds["burrow_speed"],
            "teleport_speed": athletics.speeds["teleport_speed"],
            "fly_maneuverability": athletics.fly_maneuverability,
        }
        for target,device in jet_sources.items():
            result[target+"_source"]=f"{device['name']} · {device['function_mode'].replace('_',' ')}"
        from app.athletics_rules import running_multiplier
        from app.prodigy_content import SPHERE_IMBUES, imbue_numeric_value
        result["run_multiplier"] = running_multiplier(
            self.state.martial_talents, armor_weight, encumbrance.load,
            run_feat=any(feat.enabled and feat.name.strip().casefold() == "run"
                         for feat in self.resolved_feats()),
        )
        result["run_speed"] = land * int(result["run_multiplier"])
        sequence = self.repository.get_prodigy_sequence(self.character_id)
        level = prodigy_level(self.state.classes)
        if sequence.active and sequence.current > 0 and level >= 2:
            imbue = next((entry for entry in SPHERE_IMBUES
                          if entry.key == sequence.imbue_key), None)
            movement_target = {
                "warp_step_between": "teleport_speed",
                "nature_tunnel": "burrow_speed",
            }.get(sequence.imbue_key)
            if imbue is not None and movement_target:
                result[movement_target] = max(
                    int(result[movement_target]),
                    imbue_numeric_value(imbue, sequence.current, level),
                )
                result[movement_target + "_source"] = (
                    f"{imbue.name} · once per turn, move action"
                    if movement_target == "teleport_speed" else imbue.name
                )
        return result

    def worn_armor_movement(self) -> tuple[str, str]:
        """Expose the resolved armor source used by movement presentation."""

        return worn_armor_movement_category(self.resolved_equipment())

    def encumbrance(self, base_speed: int = 0) -> Encumbrance:
        """Return current weight-load restrictions from resolved item weights."""

        if base_speed in self._encumbrance_results:
            return self._encumbrance_results[base_speed]
        equipment = self.resolved_equipment()
        weight = carried_inventory_weight(
            equipment,
            self.repository.list_inventory_placements(self.character_id),
        )
        result = calculate_encumbrance(
            self.ability_result("strength").total + max((
                physical_augmentor_bonus(device) * (2 if device["advanced"] else 1)
                for device in self.repository.list_engineering_devices(self.character_id)
                if device["catalog_key"]==LOAD_BEARER_KEY), default=0),
            self.state.details.size,
            weight,
            base_speed,
        )
        self._encumbrance_results[base_speed] = result
        return result

    def armor_check_penalty(self) -> int:
        """Use the worse armor or encumbrance penalty; PF1e does not stack them."""

        if self._armor_check_penalty is not None:
            return self._armor_check_penalty
        self._armor_check_penalty = max(
            total_armor_check_penalty(list(self.resolved_equipment())),
            self.encumbrance().check_penalty,
        )
        return self._armor_check_penalty

    def casting_statistics(self) -> CastingStatistics:
        """Global effective spherecasting values; sphere-specific bonuses stay scoped."""
        profile = self.resolved_casting_profile()
        sequence_bonus = prodigy_inspired_sequence_bonus(
            prodigy_level(self.state.classes), self.sequence_links, self.sequence_active
        )
        return calculate_casting_statistics(
            profile,
            self.ability_result(profile.casting_ability).ability_modifier,
            caster_level_bonus=sequence_bonus + self.automatic_total("caster_level"),
            dc_bonus=self.automatic_total("save_dc"),
            msb_bonus=self.automatic_total("magic_skill_bonus"),
            msd_bonus=self.automatic_total("magic_skill_defense"),
            concentration_bonus=self.automatic_total("concentration"),
            spell_point_sources=self.spell_point_contributions(),
        )

    def spell_point_contributions(self) -> tuple[SpellPointContribution, ...]:
        """Expose enabled feature bonuses as modular spell-pool sources.

        This keeps feats, class features, traditions, and future providers out of
        the base spherecasting formula. Providers only need to emit the shared
        ``spell_points`` effect target.
        """
        result = calculate_stat(
            [], self.automatic_modifier_map().get("spell_points", [])
        )
        contributions = list(
            SpellPointContribution(
                contribution.source,
                contribution.value,
                f"{contribution.bonus_type.title()} feature bonus",
            )
            for contribution in result.contributions
            if contribution.applied and contribution.value
        )
        profile = self.resolved_casting_profile()
        levels = profile.casting_class_levels
        for selected in self.repository.list_character_traditions(self.character_id, "Casting"):
            entry = resolved_tradition_definition(selected)
            rule = dict(entry.get("spell_point_rule", {}))
            value = spell_point_bonus(rule, levels)
            if value:
                contributions.append(
                    SpellPointContribution(
                        f"Tradition: {selected.name}", value, str(rule.get("text", ""))
                    )
                )
        return tuple(contributions)

    def sphere_dc_bonus(self, sphere: str) -> int:
        """Return sphere-only bonuses without changing traditional spell DCs."""
        return self.automatic_total("sphere_save_dc") + self.automatic_total(
            f"sphere_save_dc:{sphere.strip().casefold()}"
        )

    def ability_result(self, ability: str) -> CalculationResult:
        modifiers = self.resolved_modifiers(
            self.repository.list_modifiers(self.character_id, ability)
        )
        modifiers += self.automatic_modifier_map().get(ability, [])
        modifiers += race_modifiers(self.state.details).get(ability, [])
        return calculate_ability(self.state.ability_scores[ability], modifiers)

    def ability_results(self) -> dict[str, CalculationResult]:
        if self._ability_results is None:
            self._ability_results = {
                key: self.ability_result(key) for key, _, _ in ABILITIES
            }
        return self._ability_results

    def combat_results(self) -> dict[str, CalculationResult]:
        modifier_map = {
            target: self.resolved_modifiers(
                self.repository.list_modifiers(self.character_id, target)
            )
            for target in COMBAT_TARGETS
        }
        automatic = self.automatic_modifier_map()
        for target in COMBAT_TARGETS:
            modifier_map[target] += automatic.get(target, [])
        modifier_map["shield_bonus_increase"] = automatic.get("shield_bonus_increase", [])
        ability_results = self.ability_results()
        ability_modifiers = {
            key: value.ability_modifier for key, value in ability_results.items()
        }
        modules = resolve_class_feature_modules(
            self.repository, self.character_id, ability_modifiers
        )
        if any("divine-grace" in module.feature_tokens for module in modules):
            grace = max(0, ability_modifiers.get("charisma", 0))
            for target in ("fortitude", "reflex", "will"):
                if grace:
                    modifier_map[target].append(StatModifier(
                        None, target, "Paladin: Divine Grace", "untyped", grace, True,
                    ))
        for module in modules:
            if "cunning-initiative" not in module.feature_tokens:
                continue
            value = ability_modifiers.get(module.governing_ability, 0)
            if value:
                modifier_map["initiative"].append(
                    StatModifier(
                        None,
                        "initiative",
                        "Inquisitor: Cunning Initiative",
                        "untyped",
                        value,
                        True,
                    )
                )
        return calculate_combat_statistics(
            self.state.details.size,
            self.resolved_classes(),
            ability_results,
            modifier_map,
            self.resolved_equipment(),
            self.encumbrance(),
        )

    def _versatile_performance_source_key(self, substitution) -> str:
        """Match a package substitution to a character-owned Perform row."""

        definitions = character_skill_definitions(self.repository, self.character_id)
        candidates = [
            item for item in definitions
            if base_skill_key(item.key) == substitution.source_skill
        ]
        wanted = substitution.source_specialty.casefold()
        exact = next(
            (
                item.key for item in candidates
                if wanted and wanted in item.name.casefold()
            ),
            "",
        )
        if exact:
            return exact
        if substitution.selection_index < len(candidates):
            return candidates[substitution.selection_index].key
        return ""

    def skill_take_ten_allowed(self, skill_key: str = "") -> bool:
        """Whether a retained package feature permits taking 10 under pressure."""

        rules = self._class_package_skill_rules()
        return bool(rules.take_ten_all or (
            rules.take_ten_trained_knowledge
            and skill_key.startswith("knowledge_")
            and self.effective_skill_ranks().get(skill_key, 0) > 0
        ))

    def skill_result(self, skill_key: str):
        """Return the same fully automated total used by the Core skill table."""
        return self._skill_result(skill_key, apply_package_substitution=True)

    def _skill_result(
        self, skill_key: str, *, apply_package_substitution: bool
    ) -> SkillResult:
        definitions = character_skill_definitions(
            self.repository, self.character_id
        )
        definition = next((item for item in definitions if item.key == skill_key), None)
        if definition is None:
            raise KeyError(f"Unknown skill: {skill_key}")
        state = self.state.skills[skill_key]
        from app.skill_specializations import skill_formula_entity_id
        skill_entity_id = skill_formula_entity_id(skill_key)
        state = replace(
            state,
            misc_bonus=int(self.numeric_formula_value(
                "skill", skill_entity_id, "misc_bonus", state.misc_bonus,
                minimum=-9999, maximum=9999,
            )),
        )
        rule_items = (
            list(self.resolved_feats())
            + list(self.resolved_traits())
            + list(self.state.martial_talents)
            + list(self.state.magic_talents)
        )
        class_skills = self.resolved_class_skills()
        granted_class_skills = effect_class_skills(rule_items)
        untrained_skills = effect_untrained_skills(rule_items)
        root_skill_key = base_skill_key(skill_key)
        effective_ranks = self.effective_skill_ranks().get(skill_key, state.ranks)
        resolved_class_skill = (
            state.class_skill
            or skill_key in class_skills
            or root_skill_key in class_skills
            or skill_key in granted_class_skills
            or root_skill_key in granted_class_skills
        )
        if state.class_skill_override is not None:
            resolved_class_skill = state.class_skill_override
        effective_state = replace(
            state,
            ranks=effective_ranks,
            class_skill=resolved_class_skill,
        )
        effective_ability = state.ability_override or definition.ability
        armor_penalty = self.armor_check_penalty()
        reduction = armored_athlete_reduction(
            self.state.martial_talents, skill_key, effective_ranks
        )
        if reduction and definition.armor_check_multiplier:
            armor_penalty = max(
                self.encumbrance().check_penalty,
                max(0, total_armor_check_penalty(list(self.resolved_equipment())) - reduction),
            )
        skill_modifiers = (
            self.automatic_modifier_map().get("skills", [])
            + self.automatic_modifier_map().get(f"skill:{skill_key}", [])
            + (
                self.automatic_modifier_map().get(f"skill:{root_skill_key}", [])
                if root_skill_key != skill_key else []
            )
        )
        extra_ability = mighty_conditioning_extra_ability(
            self.state.martial_talents, skill_key, effective_ability
        )
        if extra_ability:
            skill_modifiers.append(
                StatModifier(
                    None,
                    f"skill:{skill_key}",
                    f"Athletics: Mighty Conditioning ({extra_ability.title()})",
                    "untyped",
                    self.ability_result(extra_ability).ability_modifier,
                    True,
                )
            )
        package_skill_rules = self._class_package_skill_rules()
        result = calculate_skill(
            replace(definition, ability=effective_ability),
            effective_state,
            self.ability_result(effective_ability),
            armor_penalty,
            skill_modifiers,
            package_skill_rules.allow_all_untrained
            or (package_skill_rules.allow_knowledge_untrained
                and root_skill_key.startswith("knowledge_"))
            or skill_key in untrained_skills
            or root_skill_key in untrained_skills,
        )
        if not apply_package_substitution:
            return result
        substitutions = (
            item
            for item in self._class_package_skill_substitutions()
            if item.target_skill == root_skill_key
        )
        best = result
        for substitution in substitutions:
            source_key = self._versatile_performance_source_key(substitution)
            if not source_key or source_key == skill_key:
                continue
            source_result = self._skill_result(
                source_key, apply_package_substitution=False
            )
            if source_result.total <= best.total:
                continue
            best = SkillResult(
                source_result.total,
                source_result.usable,
                source_result.contributions
                + (
                    Contribution(
                        substitution.source,
                        "replacement",
                        0,
                        True,
                        f"Uses {substitution.source_specialty} Perform total in place of {definition.name}.",
                    ),
                ),
            )
        return best

    def effective_skill_ranks(self) -> dict[str, int]:
        """Purchased ranks with deterministic rule-granted rank floors applied."""

        if self._effective_skill_ranks is None:
            self._effective_skill_ranks = projected_skill_ranks(
                self.state.martial_talents,
                self.state.skills,
                self.state.character_level,
            )
        return self._effective_skill_ranks

    def attack_effects(
        self, attack: Attack, bab: int
    ) -> tuple[list[StatModifier], list[StatModifier]]:
        attack_modifiers: list[StatModifier] = []
        damage_modifiers: list[StatModifier] = []
        class_attack, class_damage = class_feature_attack_modifiers(
            self.repository, self.character_id, attack
        )
        attack_modifiers.extend(class_attack)
        damage_modifiers.extend(class_damage)
        groups = (
            feat_attack_modifiers(self.resolved_feats(), attack, bab),
            trait_attack_modifiers(self.resolved_traits(), attack, bab),
            martial_talent_attack_modifiers(self.state.martial_talents, attack, bab),
            magic_talent_attack_modifiers(self.state.magic_talents, attack, bab),
        )
        for attack_values, damage_values in groups:
            attack_modifiers.extend(attack_values)
            damage_modifiers.extend(damage_values)
        weapon = next(
            (item for item in self.resolved_equipment() if item.id == attack.equipment_id),
            None,
        )
        if (
            weapon is not None
            and effective_item_state(weapon) == "wielded"
            and weapon.quantity > 0
        ):
            if weapon.masterwork:
                attack_modifiers.append(
                    StatModifier(None, "attack", f"Weapon: {weapon.name} — masterwork", "enhancement", 1, True)
                )
            if weapon.enhancement_bonus:
                attack_modifiers.append(
                    StatModifier(None, "attack", f"Weapon: {weapon.name} — magical enhancement", "enhancement", weapon.enhancement_bonus, True)
                )
                damage_modifiers.append(
                    StatModifier(None, "damage", f"Weapon: {weapon.name} — magical enhancement", "enhancement", weapon.enhancement_bonus, True)
                )
        if attack.profile_key in {"unarmed", "natural"}:
            for item in self.resolved_equipment():
                if not is_amulet_of_mighty_fists(item) or not item_is_active_for_attack(item):
                    continue
                bonus = effective_enhancement_bonus(item)
                if bonus:
                    source = f"Item: {item.name} — mighty fists enhancement"
                    attack_modifiers.append(
                        StatModifier(None, "attack", source, "enhancement", bonus, True)
                    )
                    damage_modifiers.append(
                        StatModifier(None, "damage", source, "enhancement", bonus, True)
                    )
        return attack_modifiers, damage_modifiers

"""Shared character formula namespace for trackers and ordinary numeric fields."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.formulas import (
    DEFAULT_FORMULA_ENGINE,
    FormulaCycleError,
    FormulaError,
    SymbolicDiceResult,
    UnknownReferenceError,
)
from app.item_effects import effective_item_state
from app.class_feature_systems import class_feature_reference_values
from app.class_choice_rules import (
    class_choice_reference_values,
    resolve_class_choice_slots,
)
from app.class_power_rules import class_power_reference_values, resolve_class_power_sets
from app.models import ABILITIES
from app.engineering_rules import device_condition
from app.prodigy_content import SPHERE_IMBUES, imbue_numeric_value
from app.race_rules import (
    racial_identity_tags,
    racial_resistances,
    racial_senses,
    resolved_racial_traits,
)
from app.rules import (
    calculate_casting_statistics,
    prodigy_caster_level,
    prodigy_inspired_sequence_bonus,
    prodigy_level,
    total_bab,
)


@dataclass(frozen=True, slots=True)
class FormulaSuggestion:
    reference: str
    value: str
    description: str
    insertion: str = ""


FORMULA_FUNCTION_SUGGESTIONS = (
    FormulaSuggestion(
        "IF()",
        "Function",
        "Choose one value when a condition is true and another when it is false.",
        "IF()",
    ),
    FormulaSuggestion("floor()", "Function", "Round a value downward.", "floor()"),
    FormulaSuggestion("ceil()", "Function", "Round a value upward.", "ceil()"),
    FormulaSuggestion("round()", "Function", "Round to the nearest whole number.", "round()"),
    FormulaSuggestion("min()", "Function", "Use the smallest supplied value.", "min()"),
    FormulaSuggestion("max()", "Function", "Use the largest supplied value.", "max()"),
    FormulaSuggestion("clamp()", "Function", "Keep a value between a minimum and maximum.", "clamp()"),
    FormulaSuggestion("abs()", "Function", "Return the distance from zero.", "abs()"),
    FormulaSuggestion(
        "dice()",
        "Function",
        "Roll dice. Use dice(3, 8) or the shorter 3d8 notation.",
        "dice()",
    ),
    FormulaSuggestion(
        "1d6",
        "Dice",
        "Roll one six-sided die; dice notation can be combined with ordinary arithmetic.",
        "1d6",
    ),
    FormulaSuggestion("and", "Operator", "True only when both conditions are true.", "and "),
    FormulaSuggestion("&", "Operator", "Short alias for the boolean and operator.", "& "),
)


def reference_key(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    if not clean or not clean[0].isalpha():
        clean = f"value_{clean}" if clean else "custom_value"
    return clean[:64]


class CharacterFormulaContext:
    """Resolve one stable namespace regardless of which field owns a formula."""

    def __init__(self, calculations) -> None:
        self.calculations = calculations
        self.repository = calculations.repository
        self.character_id = calculations.character_id
        self.state = calculations.state
        self.devices={f"device_{device['id']}":device for device in self.repository.list_engineering_devices(self.character_id)}
        self.values = self._base_values()
        self.trackers = {tracker.key: tracker for tracker in self.state.custom_trackers}
        self._tracker_cache: dict[tuple[str, str], float] = {}
        self._tracker_stack: list[str] = []
        self._suggestions_cache: tuple[FormulaSuggestion, ...] | None = None

    def _base_values(self) -> dict[str, float | bool]:
        state = self.state
        bab = float(total_bab(self.calculations.resolved_classes()))
        values: dict[str, float | bool] = {
            "bab": bab,
            "character.bab": bab,
            "character.level": float(state.character_level),
            "character.total_level": float(state.character_level),
        }
        class_levels: dict[str, int] = {}
        for class_level in state.classes:
            key = reference_key(class_level.preset_key or class_level.class_name)
            class_levels[key] = class_levels.get(key, 0) + class_level.level
        for key, level in class_levels.items():
            values[f"classes.{key}.level"] = float(level)

        for tag in racial_identity_tags(state.details):
            values[f"race.{reference_key(tag)}"] = True
        for trait in resolved_racial_traits(state.details):
            trait_key = reference_key(str(trait.get("name") or trait.get("key") or "trait"))
            values[f"race_trait.{trait_key}"] = True
        for sense in racial_senses(state.details):
            values[f"sense.{reference_key(sense.key)}"] = float(sense.range) if sense.range else True
        for resistance in racial_resistances(state.details):
            values[f"resistance.{reference_key(resistance.energy_type)}"] = float(resistance.value)

        for ability, result in self.calculations.ability_results().items():
            values[f"abilities.{ability}.score"] = float(result.total)
            values[f"abilities.{ability}.modifier"] = float(result.ability_modifier)
            values[f"abilities.{ability}.mod"] = float(result.ability_modifier)

        values.update(
            class_feature_reference_values(
                self.repository,
                self.character_id,
                {
                    ability: int(values[f"abilities.{ability}.modifier"])
                    for ability, _label, _short in ABILITIES
                },
            )
        )
        values.update(
            class_choice_reference_values(
                resolve_class_choice_slots(self.repository, self.character_id)
            )
        )
        values.update(
            class_power_reference_values(
                resolve_class_power_sets(self.repository, self.character_id)
            )
        )

        effective_skill_ranks = self.calculations.effective_skill_ranks()
        for skill_key, state_value in state.skills.items():
            result = self.calculations.skill_result(skill_key)
            total = float(result.total)
            ranks = float(effective_skill_ranks.get(skill_key, state_value.ranks))
            for prefix in ("skills", "skill"):
                values[f"{prefix}.{skill_key}"] = total
                values[f"{prefix}.{skill_key}.total"] = total
                values[f"{prefix}.{skill_key}.ranks"] = ranks
            values[f"skillranks.{skill_key}"] = ranks

        for feat in state.feats:
            key = reference_key(feat.name)
            owned = True
            enabled = bool(feat.enabled)
            values[f"feats.{key}"] = enabled
            values[f"feats.{key}.owned"] = owned
            values[f"feats.{key}.enabled"] = enabled
            values[f"feat.{key}"] = enabled
            values[f"feat.{key}.owned"] = owned
            values[f"feat.{key}.enabled"] = enabled

        for condition in state.conditions:
            key = reference_key(condition.name)
            values[f"condition.{key}"] = bool(condition.enabled)
            values[f"conditions.{key}"] = bool(condition.enabled)

        for effect in state.ongoing_effects:
            key = reference_key(effect.name)
            values[f"effect.{key}"] = bool(effect.enabled)
            values[f"effects.{key}"] = bool(effect.enabled)

        def add_talent_references(talent, sphere_name: str, kind: str) -> None:
            category = str(
                talent.catalog_category or getattr(talent, "talent_type", "") or ""
            ).casefold()
            if category in {"base sphere", "drawback", "tradition"}:
                return
            name_key = reference_key(talent.name)
            sphere_key = reference_key(sphere_name or "general")
            enabled = bool(talent.enabled)
            for prefix in ("talent", "talents"):
                path = f"{prefix}.{name_key}"
                values[path] = bool(values.get(path, False) or enabled)
                values[f"{path}.owned"] = True
                values[f"{path}.enabled"] = bool(
                    values.get(f"{path}.enabled", False) or enabled
                )
                scoped = f"{prefix}.{sphere_key}.{name_key}"
                values[scoped] = bool(values.get(scoped, False) or enabled)
                values[f"{scoped}.owned"] = True
                values[f"{scoped}.enabled"] = bool(
                    values.get(f"{scoped}.enabled", False) or enabled
                )
            typed = f"{kind}_talent.{sphere_key}.{name_key}"
            values[typed] = enabled
            values[f"{typed}.owned"] = True
            values[f"{typed}.enabled"] = enabled

        for talent in state.martial_talents:
            sphere_key = reference_key(
                talent.sphere or talent.name.removesuffix(" Sphere")
            )
            if talent.catalog_category == "Base Sphere":
                path = f"sphere.{sphere_key}"
                values[path] = bool(values.get(path, False) or talent.enabled)
            elif talent.catalog_category == "Drawback":
                drawback_key = reference_key(talent.name)
                path = f"drawback.{sphere_key}.{drawback_key}"
                values[path] = bool(values.get(path, False) or talent.enabled)
            add_talent_references(talent, talent.sphere, "martial")

        for talent in state.magic_talents:
            sphere_key = reference_key(
                talent.school_or_sphere or talent.name.removesuffix(" Sphere")
            )
            if talent.catalog_category == "Base Sphere":
                path = f"sphere.{sphere_key}"
                values[path] = bool(values.get(path, False) or talent.enabled)
            elif talent.catalog_category == "Drawback":
                drawback_key = reference_key(talent.name)
                path = f"drawback.{sphere_key}.{drawback_key}"
                values[path] = bool(values.get(path, False) or talent.enabled)
            add_talent_references(
                talent, talent.school_or_sphere, "magic"
            )

        item_values: dict[str, dict[str, float | bool]] = {}
        for item in state.equipment:
            key = reference_key(item.name)
            aggregate = item_values.setdefault(
                key,
                {
                    "quantity": 0.0,
                    "owned": False,
                    "active": False,
                    "carried": False,
                    "worn": False,
                    "wielded": False,
                    "equipped": False,
                },
            )
            quantity = max(0, item.quantity)
            state_name = effective_item_state(item)
            owned = quantity > 0
            carried = owned and state_name != "stored"
            equipped = owned and state_name in {"worn", "wielded", "armor", "shield"}
            aggregate["quantity"] = float(aggregate["quantity"]) + quantity
            aggregate["owned"] = bool(aggregate["owned"] or owned)
            aggregate["active"] = bool(aggregate["active"] or carried)
            aggregate["carried"] = bool(aggregate["carried"] or carried)
            aggregate["worn"] = bool(aggregate["worn"] or (owned and state_name == "worn"))
            aggregate["wielded"] = bool(
                aggregate["wielded"] or (owned and state_name == "wielded")
            )
            aggregate["equipped"] = bool(aggregate["equipped"] or equipped)
        for key, aggregate in item_values.items():
            values[f"item.{key}"] = bool(aggregate["active"])
            for field, value in aggregate.items():
                values[f"item.{key}.{field}"] = value

        for device in self.devices.values():
            condition=device_condition(device)
            prefix=f"devices.device_{device['id']}"
            values.update({
                f"{prefix}.level":float(device["level"]),
                f"{prefix}.effective_level":float(condition["effective_level"]),
                f"{prefix}.hp.current":float(condition["current_hp"]),
                f"{prefix}.hp.maximum":float(condition["maximum_hp"]),
                f"{prefix}.charges":float(device["charges"]),
                f"{prefix}.rounds_remaining":float(device["effect_rounds"]),
                f"{prefix}.active":device["state"]=="active" and not condition["destroyed"],
                f"{prefix}.worn":bool(device["applied_to_character"]),
                f"{prefix}.broken":condition["broken"],
                f"{prefix}.destroyed":condition["destroyed"],
                f"{prefix}.depleted":device["state"]=="depleted",
                f"{prefix}.abandoned":device["state"]=="abandoned",
            })

        focus = self.repository.get_martial_focus(self.character_id)
        focused = focus.current > 0
        values.update(
            {
                "martial_focus": focused,
                "martial_focus.active": focused,
                "martial_focus.focused": focused,
                "martial_focus.current": float(focus.current),
                "martial_focus.maximum": float(focus.maximum),
                "focus": focused,
            }
        )
        sequence = self.repository.get_prodigy_sequence(self.character_id)
        current_prodigy_level = prodigy_level(state.classes)
        sequence_active = bool(sequence.active and sequence.current > 0)
        sequence_links = int(sequence.current if sequence_active else 0)
        sequence_bonus = prodigy_inspired_sequence_bonus(
            current_prodigy_level, sequence_links, sequence_active
        )
        selected_imbue = next(
            (imbue for imbue in SPHERE_IMBUES if imbue.key == sequence.imbue_key),
            None,
        )
        imbue_active = bool(sequence_active and selected_imbue is not None)
        imbue_value = (
            imbue_numeric_value(selected_imbue, sequence_links, current_prodigy_level)
            if imbue_active and selected_imbue is not None
            else 0
        )
        values.update(
            {
                "prodigy.level": float(current_prodigy_level),
                "prodigy.sequence.active": sequence_active,
                "prodigy.sequence.links": float(sequence_links),
                "prodigy.sequence.current": float(sequence_links),
                "prodigy.sequence.maximum": float(sequence.maximum),
                "prodigy.sequence.remaining": float(max(0, sequence.maximum - sequence_links)),
                "prodigy.sequence.inspired_bonus": float(sequence_bonus),
                "prodigy.sequence.effective_caster_level": float(
                    prodigy_caster_level(current_prodigy_level) + sequence_bonus
                ),
                "prodigy.imbue.selected": selected_imbue is not None,
                "prodigy.imbue.active": imbue_active,
                "prodigy.imbue.value": float(imbue_value),
                # Short aliases keep common table formulas readable while the
                # fully qualified Prodigy namespace remains canonical.
                "sequence.active": sequence_active,
                "sequence.links": float(sequence_links),
                "sequence.maximum": float(sequence.maximum),
                "sequence.remaining": float(max(0, sequence.maximum - sequence_links)),
            }
        )
        for imbue in SPHERE_IMBUES:
            key = reference_key(imbue.key)
            selected = selected_imbue is not None and imbue.key == selected_imbue.key
            active = bool(sequence_active and selected)
            numeric = (
                imbue_numeric_value(imbue, sequence_links, current_prodigy_level)
                if active else 0
            )
            values[f"prodigy.imbue.{key}"] = active
            values[f"prodigy.imbue.{key}.selected"] = selected
            values[f"prodigy.imbue.{key}.active"] = active
            values[f"prodigy.imbue.{key}.value"] = float(numeric)
            if imbue.metric:
                metric_path = f"prodigy.imbue.{reference_key(imbue.metric)}"
                values.setdefault(metric_path, 0.0)
                if active:
                    values[metric_path] = float(numeric)
        # Baseline inputs intentionally exclude saved casting formulas and effective
        # casting/pool contributions, allowing formulas to refer to their own base.
        profile = self.repository.get_casting_profile(self.character_id)
        casting_ability = self.calculations.ability_result(
            profile.casting_ability
        ).ability_modifier
        casting = calculate_casting_statistics(profile, casting_ability)
        values.update(
            {
                "casting.caster_level": float(casting.caster_level),
                "casting.class_levels": float(profile.casting_class_levels),
                "spell_points.current": float(profile.spell_points_current),
                "spell_points.maximum": float(casting.spell_points_maximum),
                "spell_points.temporary": float(profile.spell_points_temporary),
            }
        )
        hit_points = self.repository.get_hit_points(self.character_id)
        values.update(
            {
                "hit_points.maximum": float(hit_points.maximum),
                "hit_points.current": float(hit_points.current),
                "hit_points.temporary": float(hit_points.temporary),
                "hit_points.nonlethal": float(hit_points.nonlethal),
            }
        )
        favored = self.repository.list_favored_class_bonuses(self.character_id)
        values.update(
            {
                "favored_class.hp": float(sum(item.hp_bonus for item in favored.values())),
                "favored_class.skill_points": float(
                    sum(item.skill_point_bonus for item in favored.values())
                ),
                "favored_class.manual": float(
                    sum(item.manual_bonus for item in favored.values())
                ),
            }
        )
        for mode, value in self.calculations.literal_movement_results().items():
            if mode.endswith("_speed"):
                values[f"movement.{mode}"] = float(value)
        return values

    def resolve_reference(self, path: str) -> float | bool:
        if path in self.values:
            return self.values[path]
        # Feat tests are deliberately total: asking about a feat the character
        # does not own is a normal false condition, not a misspelled-value
        # failure.  Other unknown references remain errors so typos stay visible.
        if re.fullmatch(
            r"(?:feat|feats)\.[a-z][a-z0-9_]*(?:\.(?:owned|enabled))?",
            path,
        ):
            return False
        if re.fullmatch(
            r"(?:condition|conditions|effect|effects)\.[a-z][a-z0-9_]*",
            path,
        ):
            return False
        if re.fullmatch(r"sphere\.[a-z][a-z0-9_]*", path):
            return False
        if re.fullmatch(r"(?:race|race_trait|sense)\.[a-z][a-z0-9_]*", path):
            return False
        if re.fullmatch(r"resistance\.[a-z][a-z0-9_]*", path):
            return 0.0
        if re.fullmatch(
            r"(?:(?:talent|talents)\.[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?"
            r"|(?:martial_talent|magic_talent)\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*)"
            r"(?:\.(?:owned|enabled))?",
            path,
        ):
            return False
        if re.fullmatch(
            r"drawback\.[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*", path
        ):
            return False
        item_match = re.fullmatch(
            r"item\.[a-z][a-z0-9_]*(?:\.(owned|active|carried|worn|wielded|equipped|quantity))?",
            path,
        )
        if item_match:
            return 0.0 if item_match.group(1) == "quantity" else False
        match = re.fullmatch(
            r"trackers\.([a-z][a-z0-9_]*)\.(value|maximum|current|temporary)",
            path,
        )
        if not match or match.group(1) not in self.trackers:
            raise UnknownReferenceError(f"Unknown value: {path}")
        key, field = match.groups()
        tracker = self.trackers[key]
        if field == "current":
            return float(tracker.current_value)
        if field == "temporary":
            return float(tracker.temporary_value)
        return self._resolve_tracker_field(key, field)

    def _resolve_tracker_field(self, key: str, field: str) -> float:
        cache_key = (key, field)
        if cache_key in self._tracker_cache:
            return self._tracker_cache[cache_key]
        if key in self._tracker_stack:
            cycle = " → ".join((*self._tracker_stack[self._tracker_stack.index(key):], key))
            raise FormulaCycleError(f"Circular tracker formula: {cycle}")
        tracker = self.trackers[key]
        self._tracker_stack.append(key)
        try:
            if field == "value":
                if tracker.tracker_type != "calculated":
                    result = float(tracker.current_value)
                else:
                    result = DEFAULT_FORMULA_ENGINE.evaluate(
                        tracker.formula, self.values, self.resolve_reference
                    )
            else:
                result = (
                    DEFAULT_FORMULA_ENGINE.evaluate(
                        tracker.formula, self.values, self.resolve_reference
                    )
                    if tracker.formula else float(tracker.manual_maximum)
                )
        finally:
            self._tracker_stack.pop()
        self._tracker_cache[cache_key] = float(result)
        return float(result)

    def evaluate(self, expression: str) -> float:
        return DEFAULT_FORMULA_ENGINE.evaluate(
            expression, self.values, self.resolve_reference
        )

    def evaluate_symbolic_dice(self, expression: str) -> SymbolicDiceResult:
        """Resolve references without rolling dice until an explicit roll action."""
        return DEFAULT_FORMULA_ENGINE.evaluate_symbolic_dice(
            expression, self.values, self.resolve_reference
        )

    def suggestions(self) -> tuple[FormulaSuggestion, ...]:
        """Canonical, character-aware entries for every shared formula editor."""
        if self._suggestions_cache is not None:
            return self._suggestions_cache
        entries: list[FormulaSuggestion] = list(FORMULA_FUNCTION_SUGGESTIONS)
        for reference in self._canonical_references():
            try:
                display = self._display_value(self.resolve_reference(reference))
            except FormulaError as error:
                display = f"Error: {error}"
            entries.append(
                FormulaSuggestion(
                    reference,
                    display,
                    ((self.devices[reference.split(".")[1]]["name"]+": ") if reference.startswith("devices.") else "") + self._reference_description(reference),
                )
            )
        self._suggestions_cache = tuple(entries)
        return self._suggestions_cache

    def _canonical_references(self) -> tuple[str, ...]:
        references = {
            "bab",
            "character.level",
            "martial_focus",
            "martial_focus.current",
            "martial_focus.maximum",
            "casting.caster_level",
            "casting.class_levels",
            "spell_points.current",
            "spell_points.maximum",
            "spell_points.temporary",
            "hit_points.current",
            "hit_points.maximum",
            "hit_points.temporary",
            "hit_points.nonlethal",
            "favored_class.hp",
            "favored_class.skill_points",
            "favored_class.manual",
        }
        references.update(
            path for path in self.values
            if (
                path.startswith("classes.")
                or (path.startswith("abilities.") and not path.endswith(".mod"))
                or (
                    path.startswith("skills.")
                    and not path.endswith((".total", ".ranks"))
                )
                or path.startswith("skillranks.")
                or (
                    path.startswith("feats.")
                    and not path.endswith(".enabled")
                )
                or path.startswith((
                    "sphere.", "drawback.", "talent.", "talents.",
                    "martial_talent.", "magic_talent.", "item.",
                ))
                or path.startswith(("condition.", "effect."))
                or path.startswith(("race.", "race_trait.", "sense.", "resistance."))
                or path.startswith("movement.")
                or path.startswith(("prodigy.", "sequence."))
                or path.startswith("class_feature.")
                or path.startswith("class_choice.")
                or path.startswith("devices.")
            )
        )
        for key in self.trackers:
            references.update(
                f"trackers.{key}.{field}"
                for field in ("value", "maximum", "current", "temporary")
            )
        return tuple(sorted(references, key=str.casefold))

    @staticmethod
    def _display_value(value: float | bool) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        rounded = round(value)
        return str(rounded) if abs(value - rounded) < 1e-9 else f"{value:.2f}".rstrip("0").rstrip(".")

    @staticmethod
    def _reference_description(reference: str) -> str:
        if reference == "bab":
            return "Current total base attack bonus."
        if reference == "character.level":
            return "Total character level across all classes."
        if reference.startswith("classes."):
            return "Levels in this class."
        if reference.startswith("favored_class."):
            return "Current favored-class allocation total."
        if reference.startswith("movement."):
            return "Current effective movement speed in feet."
        if reference.startswith(("prodigy.sequence.", "sequence.")):
            return "Current Prodigy sequence state, capacity, or Inspired Sequence value."
        if reference.startswith("class_feature."):
            return "Current archetype-aware class feature resource or activation state."
        if reference.startswith("class_choice."):
            return "Whether a class-feature choice is selected, or how many choices are selected."
        if reference == "prodigy.level":
            return "Current total Prodigy class level."
        if reference.startswith("prodigy.imbue."):
            return "Current Prodigy imbue selection, active state, or primary numeric benefit."
        if reference.startswith("abilities."):
            return "Current ability score or modifier, including active effects."
        if reference.startswith("skillranks."):
            return "Ranks invested in this skill."
        if reference.startswith("skills."):
            return "Current calculated skill total."
        if reference.startswith("feats."):
            return "Whether this feat is enabled, or whether it is owned."
        if reference.startswith("sphere."):
            return "Whether this martial or magical base sphere is currently possessed."
        if reference.startswith("race."):
            return "Whether the character counts as this race or ancestry."
        if reference.startswith("race_trait."):
            return "Whether this racial trait is currently retained."
        if reference.startswith("sense."):
            return "Whether this sense is present; ranged senses return their range in feet."
        if reference.startswith("resistance."):
            return "Current racial energy resistance value."
        if reference.startswith(("talent.", "talents.", "martial_talent.", "magic_talent.")):
            return "Whether this martial or magical talent is owned and currently enabled."
        if reference.startswith("drawback."):
            return "Whether this sphere-specific drawback is currently possessed."
        if reference.startswith("item."):
            if reference.endswith(".owned"):
                return "Whether at least one copy of this item is owned."
            if reference.endswith(".quantity"):
                return "Total quantity of this item in the inventory."
            if reference.endswith((".worn", ".wielded", ".equipped", ".carried")):
                return "Whether at least one copy is currently in this item state."
            return "Whether at least one copy of this item is currently active (not stored)."
        if reference == "martial_focus":
            return "Yes while the character currently has martial focus."
        if reference.startswith("martial_focus."):
            return "Current martial-focus resource value."
        if reference.startswith("casting."):
            return "Baseline casting value before saved casting formulas and effective bonuses."
        if reference == "spell_points.maximum":
            return "Baseline pool before saved casting formulas and feature/tradition contributions."
        if reference.startswith("spell_points."):
            return "Current spell-point resource value."
        if reference.startswith("hit_points."):
            return "Current hit-point resource value."
        if reference.startswith("trackers."):
            return "Value from a custom calculated value, counter, or pool."
        if reference.startswith("devices."):
            return "Saved engineering device state. Device IDs distinguish copies; charges are this device's own storage, excluding attached batteries."
        return "Character formula value."

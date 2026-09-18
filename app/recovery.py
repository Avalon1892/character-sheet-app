from __future__ import annotations

from dataclasses import dataclass, replace

from app.custom_trackers import CustomTrackerResolver, display_number
from app.database import CharacterRepository
from app.models import HitPoints, MartialFocus, ProdigySequence
from app.services.character_calculations import CharacterCalculationService
from app.class_feature_systems import resolve_class_feature_modules
from app.class_power_rules import full_rest_class_power_selections
from app.exploitant_rules import MOLDABLE_SOURCE_KEY, exploitant_has_moldable_talents
from app.adaptation_rules import ADAPTATION_SOURCE_KEY


@dataclass(frozen=True, slots=True)
class RecoveryTarget:
    key: str
    name: str
    description: str
    category: str
    default_enabled: bool = True


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    key: str
    name: str
    summary: str


class FullRestEngine:
    """One extensible registry for every effect produced by an eight-hour rest."""

    BUILT_IN_TARGETS = (
        RecoveryTarget(
            "hit_points.natural_healing",
            "Natural HP healing",
            "Heal hit points equal to total character level after eight hours of rest.",
            "Health",
        ),
        RecoveryTarget(
            "hit_points.nonlethal",
            "Nonlethal damage healing",
            "Remove nonlethal damage equal to character level per hour (eight hours total).",
            "Health",
        ),
        RecoveryTarget(
            "hit_points.temporary",
            "Clear temporary hit points",
            "Temporary hit points are removed when the rest completes.",
            "Health",
        ),
        RecoveryTarget(
            "spell_points",
            "Restore spell points",
            "Set current spell points to the current calculated maximum and clear temporary spell points.",
            "Resources",
        ),
        RecoveryTarget(
            "limited_spell_uses",
            "Restore limited spell uses",
            "Clear used charges for spells and abilities that have a limited uses value.",
            "Resources",
        ),
        RecoveryTarget(
            "prepared_spells",
            "Restore prepared spells",
            "Restore every expended prepared spell copy to its prepared maximum.",
            "Resources",
        ),
        RecoveryTarget(
            "spontaneous_spell_slots",
            "Restore spontaneous spell slots",
            "Restore every expended spontaneous spell slot after eight hours of rest.",
            "Resources",
        ),
        RecoveryTarget(
            "martial_focus",
            "Restore martial focus",
            "Set current martial focus to its maximum.",
            "Resources",
        ),
        RecoveryTarget(
            "prodigy_sequence",
            "End Prodigy sequence",
            "End the active sequence, clear its links, and remove its active imbue.",
            "Class systems",
        ),
        RecoveryTarget(
            "exploitant.moldable_talents",
            "Refresh Moldable Talents",
            "Allow the Exploitant to replace any Moldable Talents after this rest.",
            "Class systems",
        ),
        RecoveryTarget(
            "class_feature_resources",
            "Restore class feature resources",
            "Restore archetype-aware class pools and end active class resources and class powers.",
            "Class systems",
        ),
    )

    def __init__(self, repository: CharacterRepository, character_id: int) -> None:
        self.repository = repository
        self.character_id = character_id

    def targets(self) -> tuple[RecoveryTarget, ...]:
        custom = tuple(
            RecoveryTarget(
                f"tracker.{tracker.key}",
                tracker.name,
                (
                    "Set current value to its calculated maximum."
                    if tracker.recovery_operation == "set_to_max"
                    or (
                        tracker.recovery_operation == "none"
                        and tracker.tracker_type == "pool"
                    )
                    else "Reset current value to zero."
                ),
                "Custom trackers",
                tracker.recovery_event == "full_rest"
                and tracker.recovery_operation != "none",
            )
            for tracker in self.repository.list_custom_trackers(self.character_id)
            if tracker.tracker_type != "calculated"
        )
        return (*self.BUILT_IN_TARGETS, *custom)

    def effective_preferences(self) -> dict[str, bool]:
        saved = self.repository.get_rest_preferences(self.character_id)
        return {
            target.key: saved.get(target.key, target.default_enabled)
            for target in self.targets()
        }

    def perform(self, enabled: dict[str, bool] | None = None) -> tuple[RecoveryResult, ...]:
        choices = enabled or self.effective_preferences()
        results: list[RecoveryResult] = []
        total_level = sum(
            item.level for item in self.repository.list_class_levels(self.character_id)
        )

        if choices.get("hit_points.natural_healing", False):
            hp = self.repository.get_hit_points(self.character_id)
            healed = max(0, min(max(0, hp.maximum - hp.current), total_level))
            self.repository.update_hit_points(replace(hp, current=hp.current + healed))
            results.append(RecoveryResult("hit_points.natural_healing", "Natural HP healing", f"Healed {healed} HP."))
        if choices.get("hit_points.nonlethal", False):
            hp = self.repository.get_hit_points(self.character_id)
            removed = min(hp.nonlethal, max(0, total_level * 8))
            self.repository.update_hit_points(replace(hp, nonlethal=hp.nonlethal - removed))
            results.append(RecoveryResult("hit_points.nonlethal", "Nonlethal damage healing", f"Removed {removed} nonlethal damage."))
        if choices.get("hit_points.temporary", False):
            hp = self.repository.get_hit_points(self.character_id)
            cleared = hp.temporary
            self.repository.update_hit_points(replace(hp, temporary=0))
            results.append(RecoveryResult("hit_points.temporary", "Temporary hit points", f"Cleared {cleared} temporary HP."))
        if choices.get("spell_points", False):
            profile = self.repository.get_casting_profile(self.character_id)
            sequence = self.repository.get_prodigy_sequence(self.character_id)
            calculations = CharacterCalculationService(
                self.repository, self.character_id,
                sequence_active=sequence.active, sequence_links=sequence.current,
            )
            maximum = calculations.casting_statistics().spell_points_maximum
            self.repository.update_casting_profile(
                replace(profile, spell_points_current=maximum, spell_points_temporary=0)
            )
            results.append(RecoveryResult("spell_points", "Spell points", f"Restored to {maximum}."))
        if choices.get("limited_spell_uses", False):
            restored = 0
            for spell in self.repository.list_spells(self.character_id):
                if spell.uses_max and spell.uses_used:
                    restored += spell.uses_used
                    self.repository.set_spell_uses_used(self.character_id, spell.id, 0)
            results.append(RecoveryResult("limited_spell_uses", "Limited spell uses", f"Restored {restored} expended uses."))
        if choices.get("prepared_spells", False):
            restored = self.repository.reset_prepared_spell_uses(self.character_id)
            results.append(
                RecoveryResult(
                    "prepared_spells",
                    "Prepared spells",
                    f"Restored {restored} expended prepared spell copies.",
                )
            )
        if choices.get("spontaneous_spell_slots", False):
            restored = self.repository.reset_spontaneous_slot_uses(self.character_id)
            results.append(
                RecoveryResult(
                    "spontaneous_spell_slots",
                    "Spontaneous spell slots",
                    f"Restored {restored} expended spontaneous spell slots.",
                )
            )
        if choices.get("martial_focus", False):
            focus = self.repository.get_martial_focus(self.character_id)
            self.repository.update_martial_focus(replace(focus, current=focus.maximum))
            results.append(RecoveryResult("martial_focus", "Martial focus", f"Restored to {focus.maximum}."))
        if choices.get("prodigy_sequence", False):
            sequence = self.repository.get_prodigy_sequence(self.character_id)
            self.repository.update_prodigy_sequence(
                ProdigySequence(self.character_id, False, 0, sequence.maximum, "")
            )
            results.append(RecoveryResult("prodigy_sequence", "Prodigy sequence", "Sequence ended."))
        if (
            choices.get("exploitant.moldable_talents", False)
            and exploitant_has_moldable_talents(self.repository, self.character_id)
        ):
            self.repository.set_flexible_talent_change_available(
                self.character_id, MOLDABLE_SOURCE_KEY, True
            )
            results.append(RecoveryResult(
                "exploitant.moldable_talents",
                "Moldable Talents",
                "Moldable Talents may now be changed.",
            ))

        if choices.get("class_feature_resources", False):
            calculations = CharacterCalculationService(
                self.repository, self.character_id
            )
            ability_modifiers = {
                key: value.ability_modifier
                for key, value in calculations.ability_results().items()
            }
            restored = 0
            for module in resolve_class_feature_modules(
                self.repository, self.character_id, ability_modifiers
            ):
                for resource in module.resources:
                    target_value = (
                        resource.recovery_value
                        if resource.recover_on_full_rest
                        else resource.current
                    )
                    target_active = (
                        False if resource.end_on_full_rest else resource.active
                    )
                    if resource.current != target_value or resource.active != target_active:
                        restored += 1
                    if (
                        resource.current == target_value
                        and resource.active == target_active
                    ):
                        continue
                    self.repository.save_class_feature_state(
                        replace(
                            resource.state,
                            current_value=target_value,
                            active=target_active,
                        )
                    )
            ended_powers = 0
            for state in self.repository.list_class_feature_states(self.character_id):
                if state.feature_key.startswith("class-power-active:") and state.active:
                    ended_powers += 1
                    self.repository.save_class_feature_state(replace(state, active=False))
            active_adaptations = self.repository.list_flexible_talent_selections(
                self.character_id, ADAPTATION_SOURCE_KEY
            )
            if active_adaptations:
                self.repository.replace_flexible_talent_selections(
                    self.character_id, ADAPTATION_SOURCE_KEY, ()
                )
            temporary_power_sets = full_rest_class_power_selections(
                self.repository, self.character_id
            )
            for power_set in temporary_power_sets:
                self.repository.delete_class_feature_selection(
                    self.character_id,
                    power_set.class_level_id,
                    power_set.feature_key,
                )
            results.append(
                RecoveryResult(
                    "class_feature_resources",
                    "Class feature resources",
                    f"Restored {restored} class resource trackers, ended {ended_powers} active class powers"
                    + (
                        f", ended {len(temporary_power_sets)} temporary power selection(s)"
                        if temporary_power_sets else ""
                    )
                    + (", and ended Adaptation." if active_adaptations else "."),
                )
            )

        resolver = CustomTrackerResolver(self.repository, self.character_id)
        for resolved in resolver.resolve_all():
            tracker = resolved.tracker
            key = f"tracker.{tracker.key}"
            if not choices.get(key, False) or tracker.tracker_type == "calculated":
                continue
            operation = tracker.recovery_operation
            if operation == "none":
                operation = (
                    "set_to_max" if tracker.tracker_type == "pool" else "reset_to_zero"
                )
            if operation == "set_to_max":
                if resolved.error or resolved.maximum is None:
                    results.append(RecoveryResult(key, tracker.name, f"Not reset: {resolved.error or 'maximum unavailable'}."))
                    continue
                new_value = resolved.maximum
            elif operation == "reset_to_zero":
                new_value = 0.0
            else:
                continue
            self.repository.set_custom_tracker_values(
                self.character_id,
                tracker.id,
                current_value=new_value,
                temporary_value=0,
            )
            results.append(RecoveryResult(key, tracker.name, f"Current value is now {display_number(new_value)}."))
        return tuple(results)

from __future__ import annotations

from dataclasses import dataclass

from app.database import CharacterRepository
from app.models import (
    AbilityScoreIncreaseAllocation,
    CharacterDetails,
    ClassLevel,
    Condition,
    OngoingEffect,
    CustomTracker,
    EquipmentItem,
    FavoredClassBonus,
    Feat,
    MartialTalent,
    MovementProfile,
    ItemEnchantment,
    SkillState,
    Spell,
    Trait,
)
from app.exploitant_rules import effective_magic_talents, effective_martial_talents


@dataclass(frozen=True, slots=True)
class CharacterStateSnapshot:
    """Immutable calculation input assembled from the persistence repository."""

    character_id: int
    details: CharacterDetails
    ability_scores: dict[str, int]
    ability_score_increases: dict[str, AbilityScoreIncreaseAllocation]
    classes: list[ClassLevel]
    skills: dict[str, SkillState]
    equipment: list[EquipmentItem]
    item_enchantments: list[ItemEnchantment]
    conditions: list[Condition]
    ongoing_effects: list[OngoingEffect]
    feats: list[Feat]
    traits: list[Trait]
    martial_talents: list[MartialTalent]
    magic_talents: list[Spell]
    custom_trackers: list[CustomTracker]
    favored_class_bonuses: dict[int, FavoredClassBonus]
    movement: MovementProfile

    @classmethod
    def load(
        cls, repository: CharacterRepository, character_id: int
    ) -> CharacterStateSnapshot:
        return cls(
            character_id=character_id,
            details=repository.get_character_details(character_id),
            ability_scores=repository.get_ability_scores(character_id),
            ability_score_increases=repository.list_ability_score_increases(character_id),
            classes=repository.list_class_levels(character_id),
            skills=repository.list_skill_states(character_id),
            equipment=repository.list_equipment(character_id),
            item_enchantments=repository.list_item_enchantments(character_id),
            conditions=repository.list_conditions(character_id),
            ongoing_effects=repository.list_ongoing_effects(character_id),
            feats=repository.list_feats(character_id),
            traits=repository.list_traits(character_id),
            martial_talents=effective_martial_talents(repository, character_id),
            magic_talents=effective_magic_talents(repository, character_id),
            custom_trackers=repository.list_custom_trackers(character_id),
            favored_class_bonuses=repository.list_favored_class_bonuses(character_id),
            movement=repository.get_movement_profile(character_id),
        )

    @property
    def character_level(self) -> int:
        return sum(item.level for item in self.classes)

    @property
    def all_rule_features(self) -> tuple[Feat | Trait | MartialTalent | Spell, ...]:
        return tuple(
            [*self.feats, *self.traits, *self.martial_talents, *self.magic_talents]
        )

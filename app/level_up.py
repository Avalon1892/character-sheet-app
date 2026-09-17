"""Capability-neutral guided advancement registry and validation report."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.advancement_rules import AdvancementBudget
from app.services.advancement import character_advancement_budgets


@dataclass(frozen=True, slots=True)
class LevelUpStepDefinition:
    key: str
    title: str
    description: str
    budget_keys: tuple[str, ...] = ()
    action_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LevelUpStepState:
    definition: LevelUpStepDefinition
    budgets: tuple[AdvancementBudget, ...]

    @property
    def remaining(self) -> int | None:
        known = [item.remaining for item in self.budgets if item.automatic is not None]
        return sum(known) if known else None

    @property
    def status(self) -> str:
        if not self.budgets:
            return "Review"
        if any(item.remaining < 0 for item in self.budgets):
            return "Overspent"
        if any(item.remaining > 0 for item in self.budgets):
            return "Choice available"
        if any(item.automatic is None for item in self.budgets):
            return "Manual progression"
        return "Complete"


class LevelUpStepRegistry:
    """Small extension point for future class systems and campaign rules."""

    def __init__(self) -> None:
        self._definitions: dict[str, LevelUpStepDefinition] = {}

    def register(self, definition: LevelUpStepDefinition) -> None:
        if not definition.key.strip():
            raise ValueError("A level-up step needs a stable key.")
        self._definitions[definition.key] = definition

    def definitions(self) -> tuple[LevelUpStepDefinition, ...]:
        return tuple(self._definitions.values())


LEVEL_UP_STEPS = LevelUpStepRegistry()
for _definition in (
    LevelUpStepDefinition(
        "favored_class",
        "Favored class bonus",
        "Allocate the newly gained favored-class choice to HP, a skill point, or a campaign-specific option.",
        action_keys=("favored_class",),
    ),
    LevelUpStepDefinition(
        "ability_score_increases",
        "Ability score increases",
        "Allocate level-based ability score increases when the advancement budget grants one.",
        budget_keys=("ability_score_increases",),
        action_keys=("ability_score_increases",),
    ),
    LevelUpStepDefinition(
        "skill_points",
        "Skill ranks",
        "Spend newly available skill ranks. Class skills and governing abilities remain editable per skill.",
        budget_keys=("skill_points",),
        action_keys=("skills",),
    ),
    LevelUpStepDefinition(
        "feats",
        "Feats",
        "Choose any newly available general or bonus feats and review prerequisites.",
        budget_keys=("feats",),
        action_keys=("feats",),
    ),
    LevelUpStepDefinition(
        "sphere_talents",
        "Sphere talents",
        "Spend martial or magical talent choices granted by classes, traditions and drawbacks.",
        budget_keys=("talents",),
        action_keys=("martial_talents", "magic_talents"),
    ),
    LevelUpStepDefinition(
        "spells",
        "Spells known or recorded",
        "Review the class repertoire and add newly learned traditional spells when applicable.",
        budget_keys=("spells",),
        action_keys=("spells",),
    ),
    LevelUpStepDefinition(
        "class_choices",
        "Class features and choices",
        "Review newly granted class features, archetype exchanges and class-specific selections.",
        action_keys=("class_choices",),
    ),
):
    LEVEL_UP_STEPS.register(_definition)


@dataclass(frozen=True, slots=True)
class LevelUpReport:
    total_level: int
    steps: tuple[LevelUpStepState, ...]
    issues: tuple[str, ...]


def build_level_up_report(
    repository,
    character_id: int,
    registry: LevelUpStepRegistry = LEVEL_UP_STEPS,
) -> LevelUpReport:
    budgets = character_advancement_budgets(repository, character_id)
    by_key = {item.key: item for item in budgets}
    states = tuple(
        LevelUpStepState(
            definition,
            tuple(by_key[key] for key in definition.budget_keys if key in by_key),
        )
        for definition in registry.definitions()
        if not definition.budget_keys
        or any(key in by_key for key in definition.budget_keys)
    )
    issues = tuple(
        f"{budget.name}: {abs(budget.remaining)} over the current allowance."
        for budget in budgets
        if budget.remaining < 0
    )
    return LevelUpReport(
        sum(item.level for item in repository.list_class_levels(character_id)),
        states,
        issues,
    )

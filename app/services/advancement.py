"""Repository-facing advancement projection shared by UI workflows.

The pure budget rules remain in :mod:`app.advancement_rules`.  This adapter is
the one place that gathers character records, formula-backed adjustments and
catalog declarations so Page 0, guided level-up and future validation tools
cannot drift apart.
"""
from __future__ import annotations

from dataclasses import replace

from app.advancement_rules import AdvancementBudget, calculate_advancement_budgets
from app.character_formulas import reference_key
from app.content import archetype_entry, class_entry
from app.services.character_calculations import CharacterCalculationService
from app.skill_rank_rules import granted_skill_rank_allowance
from app.race_rules import racial_advancement_effects


def character_advancement_budgets(
    repository, character_id: int
) -> tuple[AdvancementBudget, ...]:
    classes = repository.list_class_levels(character_id)
    details = repository.get_character_details(character_id)
    skills = repository.list_skill_states(character_id)
    favored = repository.list_favored_class_bonuses(character_id)
    saved_adjustments = repository.list_advancement_adjustments(character_id)
    calculator = CharacterCalculationService(repository, character_id)
    saved_skill_ranks = sum(item.ranks for item in skills.values())
    granted_ranks = granted_skill_rank_allowance(
        calculator.state.martial_talents,
        skills,
        calculator.state.character_level,
    )
    formulas = {
        field_key: expression
        for (_entity_type, _entity_id, field_key), expression
        in repository.numeric_formulas(character_id, "advancement", 0).items()
    }
    effective_adjustments = {}
    for key, item in saved_adjustments.items():
        slug = reference_key(key)[:50]
        override_field = f"{slug}_override"
        effective_adjustments[key] = replace(
            item,
            adjustment=int(
                calculator.numeric_formula_value(
                    "advancement",
                    0,
                    f"{slug}_adjustment",
                    item.adjustment,
                    minimum=-999,
                    maximum=999,
                )
            ),
            override_total=(
                int(
                    calculator.numeric_formula_value(
                        "advancement",
                        0,
                        override_field,
                        item.override_total if item.override_total is not None else 0,
                        minimum=0,
                        maximum=999999,
                    )
                )
                if item.override_total is not None or bool(formulas.get(override_field))
                else None
            ),
        )
    return calculate_advancement_budgets(
        classes=classes,
        class_lookup=class_entry,
        intelligence_modifier=calculator.ability_result(
            "intelligence"
        ).ability_modifier,
        race=details.race,
        skill_ranks=saved_skill_ranks + granted_ranks,
        granted_skill_ranks=granted_ranks,
        favored_skill_points=sum(item.skill_point_bonus for item in favored.values()),
        feats=repository.list_feats(character_id),
        martial_talents=repository.list_martial_talents(character_id),
        spells=repository.list_spells(character_id),
        traditions=repository.list_character_traditions(character_id),
        adjustments=effective_adjustments,
        ability_score_increases=repository.list_ability_score_increases(character_id),
        archetype_keys_by_class_level=repository.list_class_archetype_keys(
            character_id
        ),
        archetype_lookup=archetype_entry,
        feature_selections=repository.list_class_feature_selections(character_id),
        racial_advancement=(racial_advancement_effects(details) if details.race_key else None),
    )

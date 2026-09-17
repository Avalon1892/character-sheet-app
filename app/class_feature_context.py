"""One repository adapter for archetype-resolved class features.

Resource, primary-choice, recurring-power, audit, and future class-system
providers must all see the same retained features and optional exchanges.
"""
from __future__ import annotations

from app.archetype_rules import archetype_choice_selections_from_records
from app.class_feature_rules import resolve_class_features
from app.content import archetype_entry, class_entry


def resolved_class_features_for_level(repository, character_id: int, class_level) -> tuple:
    definition = class_entry(class_level.preset_key)
    if definition is None:
        return ()
    keys = repository.list_class_archetype_keys(character_id, class_level.id).get(class_level.id, ())
    archetypes = tuple(
        entry for key in keys if (entry := archetype_entry(key)) is not None
    )
    selections = repository.list_class_feature_selections(character_id)
    optional_keys = (
        item.feature_key
        for item in selections
        if item.class_level_id == class_level.id
        and (
            item.feature_key.startswith("archetype-option:")
            or item.option_type.casefold() in {"archetype exchange", "optional exchange"}
        )
    )
    return resolve_class_features(
        definition.get("features", ()),
        archetypes,
        class_level.level,
        class_level.class_name,
        optional_keys,
        archetype_choice_selections_from_records(selections, class_level.id),
    )

"""Optional, transaction-friendly guided character creation extension point."""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from app.archetype_rules import archetype_choices, encode_archetype_choice_option_keys
from app.class_feature_rules import archetype_optional_features
from app.content import archetype_entry
from app.models import ABILITY_KEYS, ClassFeatureSelection, RaceTraitChoice


@dataclass(frozen=True, slots=True)
class CharacterCreationDraft:
    name: str
    character_type: str
    player_name: str = ""
    race: str = ""
    alignment: str = ""
    deity: str = ""
    size: str = "Medium"
    race_key: str = ""
    race_ability_choice: str = ""
    race_variant_key: str = ""
    race_alternate_trait_keys: tuple[str, ...] = ()
    race_trait_choices: tuple[RaceTraitChoice, ...] = ()
    abilities: dict[str, int] = field(
        default_factory=lambda: {key: 10 for key in ABILITY_KEYS}
    )
    class_values: dict | None = None
    archetype_keys: tuple[str, ...] = ()
    optional_feature_keys: tuple[str, ...] = ()
    archetype_choice_values: dict[str, tuple[str, ...]] = field(default_factory=dict)


def apply_character_creation_draft(repository, character_id: int, draft: CharacterCreationDraft) -> None:
    """Apply one draft; callers may fall back to shell creation by omitting it."""
    details = repository.get_character_details(character_id)
    repository.update_character_details(
        replace(
            details,
            player_name=draft.player_name,
            race=draft.race,
            alignment=draft.alignment,
            deity=draft.deity,
            size=draft.size,
            race_key=draft.race_key,
            race_ability_choice=draft.race_ability_choice,
            race_variant_key=draft.race_variant_key,
            race_alternate_trait_keys=draft.race_alternate_trait_keys,
            race_trait_choices=draft.race_trait_choices,
        )
    )
    for ability, score in draft.abilities.items():
        if ability in ABILITY_KEYS:
            repository.update_ability_score(character_id, ability, int(score))
    if not draft.class_values:
        return
    class_level_id = repository.add_class_level(character_id, **draft.class_values)
    repository.set_class_archetype_keys(
        character_id, class_level_id, draft.archetype_keys
    )
    level = int(draft.class_values.get("level", 1))
    selected_optional = frozenset(draft.optional_feature_keys)
    for archetype_key in draft.archetype_keys:
        definition = archetype_entry(archetype_key)
        if definition is None:
            continue
        for option in archetype_optional_features(definition, level):
            if option.key not in selected_optional:
                continue
            repository.save_class_feature_selection(
                ClassFeatureSelection(
                    character_id, class_level_id, option.key,
                    "Archetype exchange", archetype_key, option.name, option.description,
                )
            )
        for choice in archetype_choices(definition, level):
            values = draft.archetype_choice_values.get(choice.key, ())
            options = {option.key: option for option in choice.options}
            chosen = [options[key] for key in values if key in options]
            if not chosen:
                continue
            repository.save_class_feature_selection(
                ClassFeatureSelection(
                    character_id,
                    class_level_id,
                    choice.key,
                    "Archetype choice",
                    encode_archetype_choice_option_keys(item.key for item in chosen),
                    ", ".join(item.name for item in chosen),
                    "\n\n".join(item.description for item in chosen if item.description),
                )
            )

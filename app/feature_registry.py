from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FeatureKind(StrEnum):
    MARTIAL_TALENT = "martial_talent"
    MAGIC_TALENT = "magic_talent"
    FEAT = "feat"
    TRAIT = "trait"
    SPELL = "spell"
    SPECIAL_ABILITY = "special_ability"
    PRODIGY_OPENER = "prodigy_opener"
    PRODIGY_LINK = "prodigy_link"
    PRODIGY_FINISHER = "prodigy_finisher"
    EQUIPMENT = "equipment"


@dataclass(frozen=True, slots=True)
class FeatureCategory:
    kind: FeatureKind
    singular: str
    plural: str
    repository_list_method: str | None
    supports_activation: bool
    supports_choice: bool
    catalog_family: str


FEATURE_CATEGORIES = {
    FeatureKind.MARTIAL_TALENT: FeatureCategory(
        FeatureKind.MARTIAL_TALENT,
        "Martial Talent",
        "Martial Talents",
        "list_martial_talents",
        True,
        True,
        "martial",
    ),
    FeatureKind.MAGIC_TALENT: FeatureCategory(
        FeatureKind.MAGIC_TALENT,
        "Magic Talent",
        "Magic Talents",
        "list_spells",
        True,
        True,
        "magic",
    ),
    FeatureKind.FEAT: FeatureCategory(
        FeatureKind.FEAT, "Feat", "Feats", "list_feats", True, True, "feat"
    ),
    FeatureKind.TRAIT: FeatureCategory(
        FeatureKind.TRAIT, "Trait", "Traits", "list_traits", True, True, "trait"
    ),
    FeatureKind.SPELL: FeatureCategory(
        FeatureKind.SPELL, "Spell", "Spells", "list_spells", True, True, "magic"
    ),
    FeatureKind.SPECIAL_ABILITY: FeatureCategory(
        FeatureKind.SPECIAL_ABILITY,
        "Special Ability",
        "Special Abilities",
        None,
        False,
        False,
        "class",
    ),
    FeatureKind.PRODIGY_OPENER: FeatureCategory(
        FeatureKind.PRODIGY_OPENER,
        "Opener",
        "Openers",
        "list_sequence_options",
        False,
        False,
        "prodigy",
    ),
    FeatureKind.PRODIGY_LINK: FeatureCategory(
        FeatureKind.PRODIGY_LINK,
        "Link",
        "Links",
        "list_sequence_options",
        False,
        False,
        "prodigy",
    ),
    FeatureKind.PRODIGY_FINISHER: FeatureCategory(
        FeatureKind.PRODIGY_FINISHER,
        "Finisher",
        "Finishers",
        "list_sequence_options",
        False,
        False,
        "prodigy",
    ),
    FeatureKind.EQUIPMENT: FeatureCategory(
        FeatureKind.EQUIPMENT, "Item", "Equipment & Items", "list_equipment",
        True, False, "equipment",
    ),
}


def feature_category(kind: FeatureKind | str) -> FeatureCategory:
    return FEATURE_CATEGORIES[FeatureKind(kind)]

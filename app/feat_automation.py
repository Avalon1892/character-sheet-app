from __future__ import annotations

from copy import deepcopy


def _effect(
    target: str,
    value: int,
    bonus_type: str = "untyped",
    formula: str = "",
    scope: str = "",
) -> dict:
    return {
        "target": target,
        "bonus_type": bonus_type,
        "value": value,
        "formula": formula,
        "scope": scope,
    }


def _static(*effects: dict, note: str = "Applied automatically while enabled.") -> dict:
    return {
        "effects": list(effects),
        "choice_type": "",
        "choice_label": "",
        "activation": "always",
        "activation_note": note,
        "default_enabled": True,
    }


def _choice(
    choice_type: str,
    choice_label: str,
    *effects: dict,
    note: str = "Applied automatically to the selected option while enabled.",
) -> dict:
    return {
        "effects": list(effects),
        "choice_type": choice_type,
        "choice_label": choice_label,
        "activation": "always",
        "activation_note": note,
        "default_enabled": True,
    }


def _toggle(*effects: dict, note: str) -> dict:
    return {
        "effects": list(effects),
        "choice_type": "",
        "choice_label": "",
        "activation": "toggle",
        "activation_note": note,
        "default_enabled": False,
    }


def _toggle_choice(
    choice_type: str, choice_label: str, *effects: dict, note: str
) -> dict:
    return {
        "effects": list(effects),
        "choice_type": choice_type,
        "choice_label": choice_label,
        "activation": "toggle",
        "activation_note": note,
        "default_enabled": False,
    }


_PAIR_SKILL_FEATS = {
    "acrobatic": ("acrobatics", "fly"),
    "alertness": ("perception", "sense_motive"),
    "animal affinity": ("handle_animal", "ride"),
    "athletic": ("climb", "swim"),
    "deceitful": ("bluff", "disguise"),
    "deft hands": ("disable_device", "sleight_of_hand"),
    "magical aptitude": ("spellcraft", "use_magic_device"),
    "persuasive": ("diplomacy", "intimidate"),
    "self-sufficient": ("heal", "survival"),
    "stealthy": ("escape_artist", "stealth"),
}


_AUTOMATION: dict[str, dict] = {
    "extra spell points": _static(
        _effect("spell_points", 2),
        note="The spell pool maximum increases by 2. Multiple copies stack.",
    ),
    "sphere focus": _choice(
        "magic_sphere",
        "Magic sphere",
        _effect("sphere_save_dc:{choice_key}", 1),
        note="The selected sphere's saving throw DC increases by 1.",
    ),
    "great fortitude": _static(_effect("fortitude", 2)),
    "iron will": _static(_effect("will", 2)),
    "lightning reflexes": _static(_effect("reflex", 2)),
    "improved initiative": _static(_effect("initiative", 4)),
    "dodge": _static(
        _effect("ac", 1, "dodge"),
        _effect("touch_ac", 1, "dodge"),
    ),
    "toughness": _static(
        _effect("hp", 0, formula="character_level_min_3"),
        note="Maximum HP scales automatically with total character level.",
    ),
    "improved natural armor": _static(
        _effect("ac", 1),
        _effect("flat_footed_ac", 1),
    ),
    "shield focus": _static(
        _effect("ac", 1, formula="equipped_category", scope="Shield"),
        _effect(
            "flat_footed_ac",
            1,
            "untyped",
            formula="equipped_category",
            scope="Shield",
        ),
        note="The +1 shield bonus applies automatically while a shield is equipped.",
    ),
    "greater shield focus": _static(
        _effect("ac", 1, formula="equipped_category", scope="Shield"),
        _effect(
            "flat_footed_ac",
            1,
            "untyped",
            formula="equipped_category",
            scope="Shield",
        ),
        note="The additional shield bonus applies automatically while a shield is equipped.",
    ),
    "armor focus": _choice(
        "armor",
        "Armor",
        _effect("ac", 1, formula="equipped_item", scope="{choice_key}"),
        _effect(
            "flat_footed_ac",
            1,
            "untyped",
            formula="equipped_item",
            scope="{choice_key}",
        ),
        note="The +1 armor bonus applies automatically while the selected armor is equipped.",
    ),
    "skill focus": _choice(
        "skill",
        "Skill",
        _effect("skill:{choice_key}", 3, formula="rank_scaled_3_6"),
        note="The selected skill gains +3, increasing automatically to +6 at 10 ranks.",
    ),
    "weapon focus": _choice(
        "attack",
        "Saved attack",
        _effect("attack", 1, scope="name:{choice_key}"),
    ),
    "greater weapon focus": _choice(
        "attack",
        "Saved attack",
        _effect("attack", 1, scope="name:{choice_key}"),
    ),
    "weapon specialization": _choice(
        "attack",
        "Saved attack",
        _effect("damage", 2, scope="name:{choice_key}"),
    ),
    "greater weapon specialization": _choice(
        "attack",
        "Saved attack",
        _effect("damage", 2, scope="name:{choice_key}"),
    ),
    "point-blank shot": _toggle(
        _effect("attack", 1, scope="type:Ranged"),
        _effect("damage", 1, scope="type:Ranged"),
        note="Toggle active while making ranged attacks against targets within 30 feet.",
    ),
    "power attack": _toggle(
        _effect("attack", -1, formula="bab_step", scope="type:Melee"),
        _effect("damage", 0, formula="power_attack_damage", scope="type:Melee"),
        note="Toggle active when using Power Attack. Attack penalties and damage scale with BAB and the saved attack's damage multiplier.",
    ),
    "deadly aim": _toggle(
        _effect("attack", -1, formula="bab_step", scope="type:Ranged"),
        _effect("damage", 2, formula="bab_step", scope="type:Ranged"),
        note="Toggle active when using Deadly Aim. Its attack penalty and damage scale automatically with BAB.",
    ),
    "piranha strike": _toggle_choice(
        "attack",
        "Eligible saved attack",
        _effect("attack", -1, formula="bab_step", scope="name:{choice_key}"),
        _effect("damage", 2, formula="bab_step", scope="name:{choice_key}"),
        note="Toggle active when using Piranha Strike with the selected eligible weapon. Values scale automatically with BAB.",
    ),
    "combat expertise": _toggle(
        _effect("attack", -1, formula="bab_step", scope="type:Melee"),
        _effect("ac", 1, "dodge", formula="bab_step"),
        _effect("touch_ac", 1, "dodge", formula="bab_step"),
        note="Toggle active when using Combat Expertise. The melee attack penalty and dodge bonus scale automatically with BAB.",
    ),
    "advanced defensive combat training": _static(
        _effect("cmd", 4),
        note="The +4 bonus to CMD applies automatically.",
    ),
    "aquatic combatant": _static(
        _effect("skill:swim", 2),
        note="The +2 Swim bonus applies automatically. Its underwater attack and damage exceptions remain in the rules text.",
    ),
    "breadth of experience": _static(
        *(
            _effect(f"skill:{skill}", 2)
            for skill in (
                "knowledge_arcana",
                "knowledge_dungeoneering",
                "knowledge_engineering",
                "knowledge_geography",
                "knowledge_history",
                "knowledge_local",
                "knowledge_nature",
                "knowledge_nobility",
                "knowledge_planes",
                "knowledge_religion",
                "profession",
            )
        ),
        *(
            _effect(f"skill:{skill}", 0, formula="allow_untrained")
            for skill in (
                "knowledge_arcana",
                "knowledge_dungeoneering",
                "knowledge_engineering",
                "knowledge_geography",
                "knowledge_history",
                "knowledge_local",
                "knowledge_nature",
                "knowledge_nobility",
                "knowledge_planes",
                "knowledge_religion",
                "profession",
            )
        ),
        note="All Knowledge and Profession skills receive +2 and can be used untrained.",
    ),
    "steel skeleton": _static(
        _effect("ac", 1, "natural armor"),
        _effect("flat_footed_ac", 1, "natural armor"),
        _effect("cmb", 1, "racial"),
        _effect("cmd", 1, "racial"),
        note="Natural armor, CMB, and CMD bonuses apply automatically. Carrying-capacity and limited Strength-check rules remain in the description.",
    ),
    "tentacle master": _choice(
        "attack",
        "Saved tentacle attack",
        _effect("attack", 1, "racial", scope="name:{choice_key}"),
        _effect("damage", 1, "racial", scope="name:{choice_key}"),
    ),
    "realmwalker adept": _toggle(
        _effect("initiative", 2),
        _effect("skill:knowledge_planes", 2),
        _effect("skill:perception", 2),
        _effect("skill:stealth", 2),
        _effect("skill:survival", 2),
        note="Toggle active while on the currently attuned favored plane. Other planar-trait checks remain in the rules text.",
    ),
}

for feat_name, skills in _PAIR_SKILL_FEATS.items():
    _AUTOMATION[feat_name] = _static(
        *(
            _effect(f"skill:{skill}", 2, formula="rank_scaled_2_4")
            for skill in skills
        ),
        note="Each affected skill gains +2, increasing automatically to +4 at 10 ranks.",
    )


def feat_automation(name: str) -> dict:
    """Return a mutable copy of the safe automation definition for a feat."""
    return deepcopy(_AUTOMATION.get(name.casefold().strip(), {}))


def automated_feat_names() -> tuple[str, ...]:
    return tuple(sorted(_AUTOMATION))

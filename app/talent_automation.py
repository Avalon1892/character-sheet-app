from __future__ import annotations

from copy import deepcopy


def _effect(
    target: str,
    value: int = 0,
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
    choice_type: str,
    choice_label: str,
    *effects: dict,
    note: str,
) -> dict:
    return {
        "effects": list(effects),
        "choice_type": choice_type,
        "choice_label": choice_label,
        "activation": "toggle",
        "activation_note": note,
        "default_enabled": False,
    }


def _provider(
    provider: str,
    *,
    note: str,
    choice_type: str = "",
    choice_label: str = "",
    focus_usage: str = "none",
    repeatable: bool = False,
    repeat_limit: int = 0,
) -> dict:
    """Describe automation owned by a dedicated multi-stat rules provider."""

    return {
        "effects": [],
        "choice_type": choice_type,
        "choice_label": choice_label,
        "activation": "always",
        "activation_note": note,
        "default_enabled": True,
        "provider": provider,
        "focus_usage": focus_usage,
        "repeatable": repeatable,
        "repeat_limit": max(0, int(repeat_limit)),
    }


_MARTIAL_AUTOMATION: dict[str, dict] = {
    "animal companion": _provider(
        "beastmastery_companion",
        repeatable=True,
        repeat_limit=2,
        note=(
            "Grants the Beastmastery animal companion progression. Each copy "
            "uses one combat talent; the second removes the -3 effective-level "
            "penalty, and the provider stacks with another companion source."
        ),
    ),
    "pet": _provider(
        "beastmastery_pet",
        note=(
            "Grants the Beastmastery Pet familiar progression using the higher "
            "of BAB or Handle Animal ranks."
        ),
    ),
    "wild shooter": _static(
        _effect("attack", -1, scope="type:Ranged"),
        note="The drawback's -1 penalty is applied to all saved ranged attacks.",
    ),
    "blooded skeptic": _static(
        _effect("skill:sense_motive", 1, "competence", "bab_step"),
        note="Sense Motive receives +1, plus another +1 at BAB +4 and every +4 thereafter.",
    ),
    "marauder (adrenaline) [conq. hb]": _static(
        *(
            _effect(f"skill:{skill}", 0, "competence", "half_bab_min_1")
            for skill in ("acrobatics", "climb", "fly", "swim")
        ),
        note="The competence bonuses to Acrobatics, Climb, Fly, and Swim equal half BAB (minimum +1). Movement-speed changes remain in the rules text.",
    ),
    "rogue weapon training (discipline)": _static(
        _effect("skill:sleight_of_hand", 2, "competence", "bab_2_4_at_10"),
        note="Sleight of Hand receives +2, increasing to +4 at BAB +10.",
    ),
    "unarmored training": _toggle(
        _effect("ac", 3, "armor", "unarmored_bab_thirds"),
        _effect("touch_ac", 3, "armor", "unarmored_bab_thirds"),
        _effect("flat_footed_ac", 3, "armor", "unarmored_bab_thirds"),
        note="Activate only while unarmored, unencumbered, mobile, and not using an incompatible AC feature. The bonus scales with BAB and turns off automatically if armor is equipped.",
    ),
    "charming drunk [utility]": _toggle(
        _effect("skill:bluff", 1, "competence", "bab_step_5"),
        _effect("skill:diplomacy", 1, "competence", "bab_step_5"),
        note="Activate while you have the drunk status. Bluff and Diplomacy scale at every +5 BAB.",
    ),
    "liquid courage [drs]": _toggle(
        *(
            _effect(f"skill:{skill}", 1, "morale", "bab_step_7")
            for skill in (
                "acrobatics",
                "bluff",
                "diplomacy",
                "disable_device",
                "escape_artist",
                "fly",
                "intimidate",
                "perform",
                "ride",
                "sleight_of_hand",
                "stealth",
            )
        ),
        note="Activate while you have the drunk status. The listed skill bonuses scale at every +7 BAB.",
    ),
    "mobility": _toggle_choice(
        "skill",
        "Associated Athletics skill",
        _effect("ac", 2, "dodge", "skill_rank_base_2_step_4", "{choice_key}"),
        _effect(
            "touch_ac", 2, "dodge", "skill_rank_base_2_step_4", "{choice_key}"
        ),
        _effect("cmd", 2, "dodge", "skill_rank_base_2_step_4", "{choice_key}"),
        note="Activate only against attacks of opportunity caused by movement using the selected Athletics package. The bonus scales with that skill's ranks.",
    ),
    "expanded training": _provider(
        "athletics",
        choice_type="athletics_packages_two",
        choice_label="Two additional Athletics packages",
        repeatable=True,
        note="The two selected packages become available immediately. This talent may be selected again while two unowned packages remain.",
    ),
    "swift movement": _provider(
        "athletics",
        focus_usage="maintain",
        note="While martial focus is available, associated movement speeds gain +10 feet, plus +5 feet per 5 effective ranks in that package's skill.",
    ),
    "armored athlete [high. hb]": _provider(
        "athletics",
        note="Armor check penalty is reduced for the skills associated with possessed Athletics packages, scaling with effective ranks.",
    ),
    "mighty conditioning [utility]": _provider(
        "athletics",
        note="Associated package skills automatically include both Strength and Dexterity modifiers, respecting ability substitutions.",
    ),
    "sparrow’s path (fly)": _provider(
        "athletics",
        note="Grants a clumsy fly speed equal to half base speed; the movement panel updates automatically.",
    ),
    "eagle’s path (fly)": _provider(
        "athletics",
        note="Raises the granted fly speed to base speed and maneuverability to average.",
    ),
    "shark swim (swim)": _provider(
        "athletics",
        note="Swimming movement is displayed at full base speed.",
    ),
    "terrain glide (swim)": _provider(
        "athletics",
        note="Grants a 10-foot burrow speed, or adds 5 feet when a burrow speed already exists.",
    ),
    "earthswimmer (swim) [3pp]": _provider(
        "athletics",
        note="Burrow speed becomes the character's swim speed, or half base speed when no swim speed exists.",
    ),
}


_MAGIC_AUTOMATION: dict[str, dict] = {
    "adroitness (mandate)": _toggle(
        _effect("damage", 4, "morale"),
        note="Activate for the attack against the enemy that missed the other member of this mandate.",
    ),
    "resolve (mandate)": _toggle(
        _effect("ac", 4, "morale"),
        _effect("touch_ac", 4, "morale"),
        _effect("flat_footed_ac", 4, "morale"),
        _effect("cmd", 4, "morale"),
        _effect("fortitude", 4, "morale"),
        _effect("reflex", 4, "morale"),
        _effect("will", 4, "morale"),
        note="Activate only against the enemy hit by the other member of this mandate.",
    ),
    "vindictiveness (mandate)": _toggle(
        _effect("attack", 2, "morale"),
        _effect("cmb", 2, "morale"),
        note="Activate only against the enemy that hit the other member of this mandate.",
    ),
    "stabilize (aegis)": _toggle(
        _effect("ac", 4, "morale"),
        _effect("touch_ac", 4, "morale"),
        _effect("flat_footed_ac", 4, "morale"),
        _effect("fortitude", 4, "morale"),
        _effect("reflex", 4, "morale"),
        _effect("will", 4, "morale"),
        note="Activate only while bearing this aegis and resolving one of the listed teleportation, Time, Warp, telekinesis, or extraplanar effects.",
    ),
}


def martial_automation(name: str) -> dict:
    return deepcopy(_MARTIAL_AUTOMATION.get(name.casefold().strip(), {}))


def magic_automation(name: str) -> dict:
    return deepcopy(_MAGIC_AUTOMATION.get(name.casefold().strip(), {}))


def automated_martial_names() -> tuple[str, ...]:
    return tuple(sorted(_MARTIAL_AUTOMATION))


def automated_magic_names() -> tuple[str, ...]:
    return tuple(sorted(_MAGIC_AUTOMATION))

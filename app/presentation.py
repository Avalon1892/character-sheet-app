from __future__ import annotations

import html

from app.models import Feat, MartialTalent, SheetEffect, Spell, Trait
from app.text_cleanup import repair_mojibake


FEATURE_TARGET_LABELS = {
    "": "No automatic bonus",
    "strength": "Strength",
    "dexterity": "Dexterity",
    "constitution": "Constitution",
    "intelligence": "Intelligence",
    "wisdom": "Wisdom",
    "charisma": "Charisma",
    "initiative": "Initiative",
    "fortitude": "Fortitude",
    "reflex": "Reflex",
    "will": "Will",
    "ac": "Armor Class",
    "touch_ac": "Touch AC",
    "flat_footed_ac": "Flat-Footed AC",
    "cmb": "CMB",
    "cmd": "CMD",
    "attack": "All attacks",
    "damage": "All damage",
    "skills": "All skills",
    "hp": "Maximum HP",
    "land_speed": "Land Speed",
    "caster_level": "Caster Level",
    "save_dc": "Magic Save DC",
    "concentration": "Concentration",
    "magic_skill_bonus": "Magic Skill Bonus",
    "magic_skill_defense": "Magic Skill Defense",
    "spell_resistance": "Spell Resistance",
    "spell_points": "Spell Points",
}

RuleRecord = Feat | Trait | MartialTalent | Spell


def readable_tooltip(title: str, description: str) -> str:
    """Build the single rich-tooltip format used by every rules-bearing row."""
    title = repair_mojibake(title)
    description = repair_mojibake(description)
    return (
        "<div style='width:430px; padding:8px'>"
        f"<p style='font-size:13px; font-weight:700; margin:0 0 7px 0'>{html.escape(title)}</p>"
        f"<p style='font-size:11px; line-height:1.35; margin:0'>{html.escape(description)}</p>"
        "</div>"
    )


def feature_status(record: RuleRecord) -> str:
    if record.activation == "always":
        return "Permanent" if record.enabled else "Disabled"
    return "Active" if record.enabled else "Inactive"


def effect_target_label(target: str, skill_labels: dict[str, str] | None = None) -> str:
    if "{choice_key}" in target:
        return "Selected skill" if target.startswith("skill:") else "Selected option"
    if target.startswith("skill:"):
        skill_key = target.removeprefix("skill:")
        return (skill_labels or {}).get(skill_key, target)
    if target.startswith("sphere_save_dc:"):
        sphere = target.removeprefix("sphere_save_dc:").replace("-", " ").title()
        return f"{sphere} Sphere Save DC"
    return FEATURE_TARGET_LABELS.get(target, target.replace("_", " ").title())


def effect_display(
    effect: SheetEffect | dict, skill_labels: dict[str, str] | None = None
) -> str:
    target = str(effect.target if isinstance(effect, SheetEffect) else effect.get("target", ""))
    value = int(effect.value if isinstance(effect, SheetEffect) else effect.get("value", 0))
    formula = str(effect.formula if isinstance(effect, SheetEffect) else effect.get("formula", ""))
    scope = str(effect.scope if isinstance(effect, SheetEffect) else effect.get("scope", ""))
    label = effect_target_label(target, skill_labels)
    formula_labels = {
        "class_skill": "class skill",
        "allow_untrained": "usable untrained",
        "rank_scaled_2_4": "+2 / +4 at 10 ranks",
        "rank_scaled_3_6": "+3 / +6 at 10 ranks",
        "character_level_min_3": "+3, then +1 per level beyond 3",
        "half_level_round_up": "+1 per 2 levels (rounded up)",
        "half_bab_min_1": "half BAB (minimum +1)",
        "bab_2_4_at_10": "+2 / +4 at BAB +10",
        "skill_rank_base_2_step_4": "+2, +1 per 4 selected-skill ranks",
        "unarmored_bab_thirds": "+3, +1 per 3 BAB while unarmored",
        "power_attack_damage": "scales with BAB and handedness",
    }
    if formula in {"class_skill", "allow_untrained"}:
        return f"{label}: {formula_labels[formula]}"
    if formula in formula_labels:
        value_text = formula_labels[formula]
    elif formula == "bab_step_5":
        value_text = f"{value:+d}, +{abs(value)} per 5 BAB"
    elif formula == "bab_step_7":
        value_text = f"{value:+d}, +{abs(value)} per 7 BAB"
    elif formula == "bab_step":
        value_text = f"{value:+d}, scales with BAB"
    else:
        value_text = f"{value:+d}"
    condition = ""
    if formula == "equipped_category":
        condition = f" while {scope.lower()} is equipped"
    elif formula == "equipped_item":
        condition = f" while {scope} is equipped"
    elif scope.startswith("name:"):
        selected = scope.partition(":")[2]
        condition = f" for {'the selected option' if '{choice_key}' in selected else selected}"
    elif scope.startswith("type:"):
        condition = f" for {scope.partition(':')[2].lower()} attacks"
    return f"{label} {value_text}{condition}"


def effects_display(
    record: RuleRecord, skill_labels: dict[str, str] | None = None
) -> str:
    values = [effect_display(effect, skill_labels) for effect in record.effects]
    target = str(getattr(record, "target", ""))
    value = int(getattr(record, "value", 0))
    if target and value:
        values.insert(0, f"{FEATURE_TARGET_LABELS.get(target, target)} {value:+d}")
    return "; ".join(values) or "Rules only"


def feature_summary_text(
    kind: str, record: RuleRecord, skill_labels: dict[str, str] | None = None
) -> str:
    category = str(getattr(record, "catalog_category", "") or "Custom")
    sphere = str(getattr(record, "sphere", "") or "")
    parts = [f"Type: {category}", f"Status: {feature_status(record)}"]
    if sphere:
        parts.append(f"Sphere: {sphere}")
    if record.choice:
        parts.append(f"Choice: {record.choice}")
    parts.append(f"Automatic effects: {effects_display(record, skill_labels)}")
    if record.activation_note:
        parts.append(f"Activation: {record.activation_note}")
    if record.prerequisites:
        parts.append(f"Prerequisites: {record.prerequisites}")
    if record.notes:
        parts.append(record.notes)
    if record.source_url:
        parts.append(f"Source: {record.source_url}")
    return "\n\n".join(parts)


def feature_details_html(
    kind: str, record: RuleRecord, skill_labels: dict[str, str] | None = None
) -> str:
    name = repair_mojibake(record.name)
    notes = repair_mojibake(record.notes or "No description entered.")
    prerequisites = repair_mojibake(record.prerequisites or "None listed")
    source = (
        f"<p><b>Source:</b> <a href='{html.escape(record.source_url, quote=True)}'>Open rules page</a></p>"
        if record.source_url
        else "<p><b>Source:</b> Custom entry</p>"
    )
    sphere = str(getattr(record, "sphere", "") or "")
    sphere_line = f"<p><b>Sphere:</b> {html.escape(sphere)}</p>" if sphere else ""
    description = html.escape(notes).replace("\n", "<br>")
    activation = record.activation_note or (
        "Always applied" if record.activation == "always" else record.activation
    )
    return (
        f"<h2>{html.escape(name)}</h2>"
        f"<p>{description}</p><hr>"
        f"<p><i>{html.escape(kind)}</i></p>"
        f"<p><b>Type:</b> {html.escape(str(record.catalog_category or 'Custom'))}</p>"
        f"{sphere_line}"
        f"<p><b>Status:</b> {html.escape(feature_status(record))}</p>"
        f"<p><b>Choice:</b> {html.escape(record.choice or 'None')}</p>"
        f"<p><b>Automatic effects:</b> {html.escape(effects_display(record, skill_labels))}</p>"
        f"<p><b>Activation:</b> {html.escape(activation)}</p>"
        f"<p><b>Prerequisites:</b> {html.escape(prerequisites)}</p>"
        f"{source}"
    )

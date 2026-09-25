"""Read-only class-table projections, independent of Qt and character writes."""
from dataclasses import dataclass, replace
from functools import lru_cache
import json
import re

from app.catalog_versions import BUNDLED_CATALOG_ROOT
from app.content import DATA_ROOT, class_entry, archetype_entry
from app.class_feature_rules import resolve_class_features, feature_token
from app.class_modifications import resolve_class_profile
from app.archetype_rules import archetype_choice_selections_from_records
from app.advancement_rules import calculate_advancement_budgets, _progression_value
from app.rules import class_bab, class_save, automatic_sphere_casting


@dataclass(frozen=True)
class ClassProgression:
    name: str
    subtitle: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    descriptions: tuple[str, ...]
    source_url: str
    current_level: int


@lru_cache(maxsize=1)
def reference_tables():
    path = DATA_ROOT / "class_progression_tables.json"
    if not path.exists():
        path = BUNDLED_CATALOG_ROOT / path.name
    return json.loads(path.read_text(encoding="utf-8"))


def character_progressions(repository, character_id):
    selections = repository.list_class_feature_selections(character_id)
    archetype_keys = repository.list_class_archetype_keys(character_id)
    result = []
    for record in repository.list_class_levels(character_id):
        definition = class_entry(record.preset_key) or {}
        selected = tuple(a for key in archetype_keys.get(record.id, ())
                         if (a := archetype_entry(key)))
        choices = archetype_choice_selections_from_records(selections, record.id)
        optional = tuple(s.feature_key for s in selections if s.class_level_id == record.id
                         and (s.feature_key.startswith("archetype-option:")
                              or re.sub(r"[^a-z]+", " ", s.option_type.casefold()).strip()
                              in {"archetype exchange", "optional exchange"}))
        profile = resolve_class_profile(definition, selected, choices)
        reference = reference_tables().get(definition.get("key"), {})
        source_headers = reference.get("headers", ())
        extra = [(i, h) for i, h in enumerate(source_headers) if i >= 6]
        casting = profile.casting
        sphere = bool(casting.get("sphere_progression"))
        traditional = bool(casting.get("progression")) and casting.get("traditional") is not False
        if not traditional:
            extra = [(i, h) for i, h in extra if not any(x in h.lower() for x in ("spells", "extracts"))]
        if not sphere:
            extra = [(i, h) for i, h in extra if h.lower() != "caster level"]
        if selected and profile.advancement and sum("talent" in h.lower() for _, h in extra) == 1:
            extra = [(-1 if "talent" in h.lower() else i, h) for i, h in extra]
        if sphere:
            if selected and (profile.advancement or casting != definition.get("casting", {})):
                extra = [(-2 if h.lower()=="caster level" else i, h)
                         for i, h in extra]
            if not any("talent" in h.lower() for _, h in extra):
                label = "Blended Training Talents" if any("blended training" in str(f.get("name", "")).lower()
                         for f in definition.get("features", ())) else "Magic Talents"
                extra.append((-1, label))
            if not any(h.lower() == "caster level" for _, h in extra):
                extra.append((-2, "Caster Level"))
        headers = ("Level", "Base Attack Bonus", "Fort Save", "Ref Save", "Will Save", "Special",
                   *(h for _, h in extra))
        base_features = definition.get("features", ())
        if reference.get("features"):
            documented = {feature_token(f["name"]): f.get("description", "") for f in base_features}
            base_features = tuple({**f, "description": next((description for token, description in documented.items()
                                   if feature_token(f["name"]) == token or feature_token(f["name"]).startswith(token + "-")), "")}
                                  for f in reference["features"])
        features = resolve_class_features(base_features, selected, 20,
                                          record.class_name, optional, choices)
        if not traditional and definition.get("casting", {}).get("progression"):
            features = tuple(f for f in features if f.archetype or not (
                f.name.casefold() in {"spells", "spellcasting", "cantrips", "orisons", "knacks",
                                     f"{record.class_name.casefold()} spells"}
                or f.name.casefold().startswith("exchange spell")))
        rows, descriptions = [], []
        for level in range(1, 21):
            source_rows = reference.get("rows", ())
            source = source_rows[level - 1] if level <= len(source_rows) else ()
            if reference and level > len(source_rows):
                rows.append((str(level), *("—" for _ in headers[1:])))
                descriptions.append("This class has no documented progression at this level.")
                continue
            projected = replace(record, level=level, bab_progression=profile.bab_progression)
            bab = class_bab(projected)
            earned = [feature for feature in features if feature.level == level]
            values = [str(level), "/".join(f"+{n}" for n in range(bab, 0, -5)) or "+0",
                      f"+{class_save(level, profile.fort_progression)}",
                      f"+{class_save(level, profile.reflex_progression)}",
                      f"+{class_save(level, profile.will_progression)}",
                      ", ".join(f.name for f in earned) or "—"]
            for index, header in extra:
                if index == -1:
                    budgets = calculate_advancement_budgets(
                        classes=[projected], class_lookup=class_entry, intelligence_modifier=0,
                        race="", skill_ranks=0, favored_skill_points=0, feats=(),
                        martial_talents=(), spells=(), traditions=(), adjustments={},
                        archetype_lookup=archetype_entry,
                        archetype_keys_by_class_level={record.id: archetype_keys.get(record.id, ())},
                        feature_selections=selections)
                    total = next(b.total for b in budgets if b.key == "talents")
                    progression_total = max(0, total - (2 if sphere else 0))
                    value = f"{progression_total} (+2 magic)" if sphere and level == 1 else str(progression_total)
                elif index == -2:
                    calculated = automatic_sphere_casting([projected], {record.preset_key: definition},
                        {record.id: archetype_keys.get(record.id, ())},
                        {a["key"]: a for a in selected}, {record.id: choices})
                    raw = _progression_value(level, casting["sphere_progression"])
                    value = (f"{raw} ({calculated[1]})" if calculated and raw < calculated[1]
                             else str(raw))
                else:
                    value = source[index] if index < len(source) else "—"
                values.append(value)
            rows.append(tuple(values))
            descriptions.append("\n\n".join(f"{f.name}\n{f.description}" for f in earned))
        result.append(ClassProgression(record.class_name, ", ".join(a["name"] for a in selected),
                      headers, tuple(rows), tuple(descriptions), reference.get("source_url", ""), record.level))
    return tuple(result)

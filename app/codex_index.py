"""Catalog-to-Codex search projection, independent of Qt presentation."""

from __future__ import annotations

from collections.abc import Iterable
import re

from app.catalogs import RulesCatalog


def _record(
    name: object,
    category: object,
    description: object,
    source_url: object = "",
    target: object = "",
    hierarchy_rank: int | None = None,
) -> dict:
    record = {
        "name": str(name),
        "category": str(category),
        "description": str(description),
        "source_url": str(source_url or ""),
        "target": str(target or ""),
    }
    if hierarchy_rank is not None:
        record["hierarchy_rank"] = int(hierarchy_rank)
    return record


def codex_name_search_key(record: dict, query: str) -> tuple:
    """Rank direct parents before increasingly specific name matches.

    The Codex index remains presentation-independent.  Name-only search can
    therefore use this key without teaching the generic catalog search engine
    anything about spheres, classes, or the Codex tree.
    """

    needle = query.strip().casefold()
    name = str(record.get("name") or "").strip().casefold()
    # A base sphere's visible name is normally ``Alteration Sphere``. Treat
    # the suffix as presentation text so searching ``Alteration`` is an exact
    # parent match rather than a weaker prefix match.
    comparable = re.sub(r"\s+sphere$", "", name).strip()
    category = str(record.get("category") or "")
    category_parts = {
        part.strip().casefold() for part in category.split("·") if part.strip()
    }
    if comparable == needle or name == needle:
        match_rank = 0
    elif needle in category_parts:
        # A name hit that lives under the matching parent (for example Mass
        # Alteration inside the Alteration sphere) is more relevant than an
        # unrelated spell or feat which merely happens to contain the word.
        match_rank = 1
    elif comparable.startswith(needle) or name.startswith(needle):
        match_rank = 2
    elif re.search(rf"(?<![a-z0-9]){re.escape(needle)}", name):
        match_rank = 3
    else:
        match_rank = 4
    hierarchy_rank = int(record.get("hierarchy_rank", category.count(" · ") + 1))
    return (
        match_rank,
        hierarchy_rank,
        category.count(" · "),
        name.find(needle) if needle in name else 9999,
        len(name),
        name,
        category.casefold(),
    )


def build_codex_search_records(
    catalog: RulesCatalog,
    supplemental: Iterable[dict] = (),
) -> tuple[dict, ...]:
    """Project every rules family into one reusable search document shape."""

    records: list[dict] = []
    for entry in catalog.race_entries():
        traits = " ".join(
            f"{trait.get('name', '')} {trait.get('description', '')}"
            for trait in (
                *entry.get("racial_traits", ()),
                *entry.get("alternate_racial_traits", ()),
                *entry.get("variants", ()),
            )
        )
        records.append(_record(
            entry["name"],
            f"Races · {entry.get('category', 'Other')}",
            f"{entry.get('description', '')} {traits} {entry.get('rules_text', '')}",
            entry.get("source_url", ""),
            f"race:{entry['key']}",
            0,
        ))
    for entry in catalog.class_entries():
        features = " ".join(
            f"{feature.get('name', '')} {feature.get('description', '')}"
            for feature in entry.get("features", ())
        )
        ruleset = (
            "Spheres"
            if str(entry["key"]).startswith("spheres-class:") or entry["key"] == "prodigy"
            else "Pathfinder"
        )
        records.append(
            _record(
                entry["name"],
                f"Classes · {ruleset} · {entry['category']}",
                f"{entry.get('summary', '')} {entry.get('description', '')} "
                f"{entry.get('rules_text', '')} {features}",
                entry.get("source_url", ""),
                f"class:{entry['key']}",
                0,
            )
        )
    for entry in catalog.archetype_entries():
        records.append(
            _record(
                entry["name"],
                f"Classes · {entry['source_group']} Archetypes · {entry['class_name']}",
                f"{entry.get('summary', '')} {entry.get('replaces', '')} {entry.get('description', '')}",
                entry.get("source_url", ""),
                f"archetype:{entry['key']}",
                2,
            )
        )
    for entry in catalog.class_choice_entries():
        granted = " ".join(
            f"Level {feature.get('level', 1)} {feature.get('name', '')} "
            f"{feature.get('description', '')}"
            for feature in entry.get("granted_features", ())
        )
        records.append(
            _record(
                entry["name"],
                f"Classes · Feature Choices · {entry.get('family', 'General')} · "
                f"{entry.get('category', 'General')}",
                f"{entry.get('description', '')} {granted} {entry.get('source', '')}",
                entry.get("source_url", ""),
                f"class-choice:{entry['key']}",
                2,
            )
        )
    for entry in catalog.class_power_entries():
        requirements = ", ".join(entry.get("prerequisite_names", ()))
        records.append(
            _record(
                entry["name"],
                f"Classes · Powers · {catalog.class_power_family_label(str(entry.get('family', 'General')))} · "
                f"{entry.get('category', 'General')}",
                f"{entry.get('description', '')} Minimum level: {entry.get('minimum_level', 1)}. "
                f"Prerequisites: {requirements}. {entry.get('source', '')}",
                entry.get("source_url", ""),
                f"class-power:{entry['key']}",
                3,
            )
        )
    for entry in catalog.item_entries():
        automation = entry.get("item_automation") or {}
        automation_text = " ".join(
            str(effect.get("label") or effect.get("key") or "")
            for effect in automation.get("effects", ())
        )
        records.append(
            _record(
                entry["name"],
                f"Equipment & Items · {entry['source_group']} · {entry['family']} · {entry['category']}",
                f"{entry.get('description', '')} Sheet automation: "
                f"{automation.get('status', 'rules_only')} {automation_text}",
                entry.get("source_url", ""),
                f"item:{entry['key']}",
                2,
            )
        )
    for entry in catalog.enchantment_entries():
        records.append(
            _record(
                entry["name"],
                f"Enchantments · {entry['family']} · {entry['category']}",
                f"{entry.get('description', '')} Price: {entry.get('price_text', '')}. "
                f"Requirements: {entry.get('requirements', '')}. "
                f"Restrictions: {' '.join(entry.get('restrictions', ())) } "
                f"Source: {entry.get('source', '')}",
                entry.get("source_url", ""),
                f"enchantment:{entry['key']}",
                3,
            )
        )
    for family, label, feature_entries in (
        ("martial", "Talents · Martial", catalog.martial_entries()),
        ("magic", "Talents · Magical", catalog.magic_entries()),
    ):
        for entry in feature_entries:
            category = str(entry.get("category", "General"))
            records.append(
                _record(
                    entry["name"],
                    f"{label} · {entry.get('sphere', 'General')} · {category}",
                    f"{entry.get('description', '')} Prerequisites: {entry.get('prerequisites', '')}",
                    entry.get("source_url", ""),
                    f"feature:{family}:{entry['key']}",
                    0 if category == "Base Sphere" else 3,
                )
            )
    for entry in catalog.tradition_entries():
        records.append(
            _record(
                entry["name"],
                f"Traditions · {entry.get('kind', 'Spheres')}",
                f"{entry.get('description', '')} {entry.get('rules_text', '')} "
                f"Casting ability: {', '.join(entry.get('casting_ability_options', ()))}. "
                f"Drawbacks: {entry.get('drawbacks', '')}. Boons: {entry.get('boons', '')}.",
                entry.get("source_url", ""),
                f"tradition:{entry['key']}",
                1,
            )
        )
    for entry in catalog.tradition_rule_entries():
        sphere = str(entry.get("sphere") or "")
        records.append(
            _record(
                entry["name"],
                " · ".join(
                    value
                    for value in (
                        "Traditions",
                        str(entry.get("kind") or "Spheres"),
                        str(entry.get("category") or "Rule Option"),
                        sphere,
                    )
                    if value
                ),
                f"{entry.get('description', '')} "
                f"Prerequisites: {entry.get('prerequisites', '')}",
                entry.get("source_url", ""),
                f"tradition-rule:{entry['key']}",
                3,
            )
        )
    for family, label, feature_entries in (
        ("feat", "Feats", catalog.feat_entries()),
        ("trait", "Traits", catalog.trait_entries()),
    ):
        for entry in feature_entries:
            categories = ", ".join(entry.get("categories", ("General",)))
            records.append(
                _record(
                    entry["name"],
                    f"{label} · {entry.get('source_group', 'Pathfinder')} · {categories}",
                    f"{entry.get('description', '')} Prerequisites: {entry.get('prerequisites', '')}",
                    entry.get("source_url", ""),
                    f"feature:{family}:{entry['key']}",
                    2,
                )
            )
    for entry in catalog.spell_entries():
        levels = " ".join(
            f"{name} {level}" for name, level in (entry.get("class_levels") or {}).items()
        )
        records.append(
            _record(
                entry["name"],
                f"Spells · {entry.get('source_group', 'Pathfinder')} · "
                f"{entry.get('publisher', '')} · {entry.get('school', '')}",
                f"{entry.get('summary', '')} {entry.get('description', '')} "
                f"{levels} {entry.get('source', '')}",
                entry.get("source_url", ""),
                f"spell:{entry['key']}",
                2,
            )
        )
    records.extend(dict(entry) for entry in supplemental)
    return tuple(sorted(records, key=lambda entry: (entry["name"].casefold(), entry["category"].casefold())))

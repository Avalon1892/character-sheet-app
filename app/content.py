"""Compatibility facade for the centralized bundled-rules catalog gateway."""

from __future__ import annotations

from app.catalogs import DEFAULT_CATALOG, DATA_ROOT


def catalog() -> dict[str, tuple[dict, ...]]:
    return DEFAULT_CATALOG.core


def entries(category: str) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.entries(category)


def entry_by_key(category: str, key: str) -> dict | None:
    return DEFAULT_CATALOG.entry_by_key(category, key)


def entry_by_name(category: str, name: str) -> dict | None:
    return DEFAULT_CATALOG.entry_by_name(category, name)


def race_entries(category: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.race_entries(category)


def race_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.race_entry(key)


def race_categories() -> tuple[str, ...]:
    return DEFAULT_CATALOG.race_categories()


def martial_catalog() -> dict:
    return DEFAULT_CATALOG.martial_document


def martial_spheres() -> tuple[dict, ...]:
    return DEFAULT_CATALOG.martial_spheres()


def martial_sphere(name: str) -> dict | None:
    return DEFAULT_CATALOG.martial_sphere(name)


def martial_entries(sphere_name: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.martial_entries(sphere_name)


def martial_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.martial_entry(key)


def magic_catalog() -> dict:
    return DEFAULT_CATALOG.magic_document


def magic_spheres() -> tuple[dict, ...]:
    return DEFAULT_CATALOG.magic_spheres()


def magic_sphere(name: str) -> dict | None:
    return DEFAULT_CATALOG.magic_sphere(name)


def magic_entries(sphere_name: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.magic_entries(sphere_name)


def magic_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.magic_entry(key)


def tradition_entries(kind: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.tradition_entries(kind)


def tradition_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.tradition_entry(key)


def tradition_rule_entries(
    kind: str | None = None,
    category: str | None = None,
    sphere: str | None = None,
) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.tradition_rule_entries(kind, category, sphere)


def feat_catalog() -> dict:
    return DEFAULT_CATALOG.feat_document


def feat_entries(source_group: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.feat_entries(source_group)


def feat_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.feat_entry(key)


def feat_categories() -> tuple[str, ...]:
    return DEFAULT_CATALOG.feat_categories()


def trait_catalog() -> dict:
    return DEFAULT_CATALOG.trait_document


def trait_entries(source_group: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.trait_entries(source_group)


def trait_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.trait_entry(key)


def trait_categories() -> tuple[str, ...]:
    return DEFAULT_CATALOG.trait_categories()


def trait_sources() -> tuple[str, ...]:
    return DEFAULT_CATALOG.trait_sources()


def item_entries(source_group: str | None = None, family: str | None = None, category: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.item_entries(source_group, family, category)


def item_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.item_entry(key)


def item_sources() -> tuple[str, ...]:
    return DEFAULT_CATALOG.item_sources()


def item_families(source_group: str | None = None) -> tuple[str, ...]:
    return DEFAULT_CATALOG.item_families(source_group)


def item_categories(source_group: str | None = None, family: str | None = None) -> tuple[str, ...]:
    return DEFAULT_CATALOG.item_categories(source_group, family)


def pathfinder_class_entries(category: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.pathfinder_class_entries(category)


def pathfinder_class_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.pathfinder_class_entry(key)


def pathfinder_class_categories() -> tuple[str, ...]:
    return DEFAULT_CATALOG.pathfinder_class_categories()


def spheres_class_entries(category: str | None = None) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.spheres_class_entries(category)


def spheres_class_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.spheres_class_entry(key)


def spheres_class_categories() -> tuple[str, ...]:
    return DEFAULT_CATALOG.spheres_class_categories()


def class_entries(
    source_group: str | None = None, category: str | None = None
) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.class_entries(source_group, category)


def class_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.class_entry(key)


def class_power_entries(
    family: str | None = None,
    class_name: str | None = None,
    category: str | None = None,
) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.class_power_entries(family, class_name, category)


def class_power_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.class_power_entry(key)


def archetype_entries(
    class_key: str | None = None, source_group: str | None = None
) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.archetype_entries(class_key, source_group)


def archetype_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.archetype_entry(key)


def spell_entries(
    source_group: str | None = None,
    publisher: str | None = None,
    class_name: str | None = None,
) -> tuple[dict, ...]:
    return DEFAULT_CATALOG.spell_entries(source_group, publisher, class_name)


def spell_entry(key: str) -> dict | None:
    return DEFAULT_CATALOG.spell_entry(key)


def spell_sources() -> tuple[str, ...]:
    return DEFAULT_CATALOG.spell_sources()


def spell_publishers(source_group: str | None = None) -> tuple[str, ...]:
    return DEFAULT_CATALOG.spell_publishers(source_group)

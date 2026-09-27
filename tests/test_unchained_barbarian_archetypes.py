"""Unchained archetypes reuse the original imports without losing exchanges."""
from app.content import archetype_entries, archetype_entry, class_entry, class_power_entries
from app.class_feature_rules import resolve_class_features
from app.class_packages.loader import archetype_runtime_package
from app.archetype_rules import validate_archetype_selection
from app.database import CharacterRepository
from app.class_feature_context import resolved_class_features_for_level


def test_all_pathfinder_barbarian_archetypes_are_available_to_unchained():
    original = archetype_entries("pathfinder-class:barbarian", "Pathfinder")
    unchained = archetype_entries("pathfinder-class:barbarian-unchained", "Pathfinder")
    assert len(original) == len(unchained) == 42
    assert {entry["name"] for entry in original} == {entry["name"] for entry in unchained}
    for entry in unchained:
        source = archetype_entry(entry["inherited_from"])
        assert entry["description"] == source["description"]
        assert entry["features"] == source["features"]
        assert entry["source_url"] == source["source_url"]
        assert archetype_runtime_package(entry["key"]) == archetype_runtime_package(source["key"])
    assert len(archetype_entries("pathfinder-class:barbarian-unchained", "Spheres")) == 4


def test_trap_sense_exchange_removes_danger_sense_not_original_catalog():
    base = class_entry("pathfinder-class:barbarian-unchained")
    archetype = archetype_entry("pathfinder-archetype:pathfinder-class:barbarian-unchained:armored-hulk")
    features = resolve_class_features(base["features"], [archetype], 20, base["name"])
    names = {feature.name for feature in features}
    assert "Danger Sense" not in names
    assert "Fast Movement" not in names
    assert "Resilience of Steel" in names
    assert "Rage (UC)" in names
    original = archetype_entry(archetype["inherited_from"])
    assert "trap-sense" in original["removed_features"]
    assert "danger-sense" not in original["removed_features"]


def test_unchained_rules_and_power_descriptions_are_already_imported():
    base = class_entry("pathfinder-class:barbarian-unchained")
    assert len(base["features"]) == 11
    assert all(feature["description"] for feature in base["features"])
    powers = class_power_entries("rage_power", "Barbarian (Unchained)")
    assert any(entry["name"] == "Accurate Stance (UC)" for entry in powers)
    assert all(entry["description"] for entry in powers)


def test_selection_persists_and_conflicting_archetypes_are_rejected(tmp_path):
    definitions = {entry["key"]: entry for entry in archetype_entries("pathfinder-class:barbarian-unchained")}
    hulk = "pathfinder-archetype:pathfinder-class:barbarian-unchained:armored-hulk"
    breaker = "pathfinder-archetype:pathfinder-class:barbarian-unchained:breaker"
    assert not validate_archetype_selection((hulk, breaker), definitions).compatible
    path = tmp_path / "character.db"
    repository = CharacterRepository(path)
    character = repository.create_character("Unchained", "Pathfinder 1e")
    class_id = repository.add_class_level(character, "Barbarian (Unchained)", 8, "Full", "Good", "Poor", "Poor", "pathfinder-class:barbarian-unchained", 12, 61)
    repository.set_class_archetype_keys(character, class_id, (hulk,))
    repository.close()
    repository = CharacterRepository(path)
    try:
        level = repository.list_class_levels(character)[0]
        names = {feature.name for feature in resolved_class_features_for_level(repository, character, level)}
        assert "Resilience of Steel" in names
        assert "Danger Sense" not in names
    finally:
        repository.close()

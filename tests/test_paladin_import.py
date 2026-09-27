from pathlib import Path

from app.catalog_versions import inspect_catalog
from app.content import archetype_entries, archetype_entry, class_entry, class_power_entries
from app.archetype_rules import validate_archetype_selection
from app.class_feature_rules import resolve_class_features
from app.class_power_rules import resolve_class_power_sets, class_power_selection_record
from app.database import CharacterRepository


def test_complete_paladin_catalog_and_integrity():
    assert len(archetype_entries("paladin", "Pathfinder")) == 62
    assert len(archetype_entries("paladin", "Spheres")) == 12
    assert len(class_power_entries("paladin_mercy")) == 26
    assert len(class_power_entries("paladin_divine_bond")) == 3
    powers = class_power_entries(class_name="Paladin")
    assert all(entry["description"] and entry["source_url"] for entry in powers)
    assert not any("\ufffd" in entry["description"] for entry in powers)
    bond = next(feature for feature in class_entry("pathfinder-class:paladin")["features"] if feature["name"] == "Divine Bond")
    assert "30 days" in bond["description"] and "mount" in bond["description"]
    assert "\ufffd" not in bond["description"]
    result = inspect_catalog(Path(__file__).resolve().parents[1] / "data" / "pf1e", "Bundled")
    assert result.valid, result.errors


def test_mercies_have_native_slots_prerequisites_and_archetype_exchanges(tmp_path):
    repository = CharacterRepository(tmp_path / "paladin.db")
    try:
        character = repository.create_character("Paladin", "Pathfinder 1e")
        class_id = repository.add_class_level(character, "Paladin", 12, "Full", "Good", "Poor", "Good", "pathfinder-class:paladin", 10, 70)
        powers = next(value for value in resolve_class_power_sets(repository, character) if value.key == "paladin-mercies")
        assert powers.slot_levels == (3, 6, 9, 12)
        options = {value.name: value for value in powers.options}
        assert options["Exhausted"].prerequisite_names == ("Fatigued",)
        assert options["Amputated"].prerequisite_names == ("Injured",)
        assert options["Exhausted"].key in powers.unavailable_reasons
        chosen = tuple(options[name].key for name in ("Fatigued", "Diseased", "Exhausted", "Blinded"))
        repository.save_class_feature_selection(class_power_selection_record(character, powers, chosen))
        updated = next(value for value in resolve_class_power_sets(repository, character) if value.key == "paladin-mercies")
        assert updated.selected_keys == chosen
        repository.set_class_archetype_keys(character, class_id, ("pathfinder-archetype:pathfinder-class:paladin:holy-guide",))
        updated = next(value for value in resolve_class_power_sets(repository, character) if value.key == "paladin-mercies")
        assert updated.slot_levels == (9, 12)
        repository.set_class_archetype_keys(character, class_id, ("pathfinder-archetype:pathfinder-class:paladin:divine-defender",))
        assert not any(value.key == "paladin-mercies" for value in resolve_class_power_sets(repository, character))
    finally:
        repository.close()


def test_oaths_use_existing_replacement_and_compatibility_rules():
    prefix = "pathfinder-archetype:pathfinder-class:paladin:"
    oath = archetype_entry(prefix + "oath-of-vengeance")
    definition = class_entry("pathfinder-class:paladin")
    names = {feature.name for feature in resolve_class_features(definition["features"], (oath,), 20, "Paladin")}
    assert "Channel Positive Energy" not in names
    assert "Lay on Hands" in names
    assert "Powerful Justice" in names
    assert next(feature["level"] for feature in oath["features"] if feature["name"] == "Channel Wrath") == 4
    variant = archetype_entry(prefix + "oath-against-the-whispering-way")
    variant_names = {feature["name"] for feature in variant["features"]}
    assert {"Detect Undead", "Ghost Touch Aura", "Aura against Necromancy"} <= variant_names
    assert "Aura of Life" not in variant_names
    definitions = {entry["key"]: entry for entry in archetype_entries("paladin")}
    assert not validate_archetype_selection((prefix + "oath-of-vengeance", prefix + "oath-against-chaos"), definitions).compatible

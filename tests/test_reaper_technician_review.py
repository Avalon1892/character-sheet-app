import tempfile
from pathlib import Path

import pytest

from app.class_choice_rules import class_choice_selection_record, resolve_class_choice_slots
from app.class_feature_systems import resolve_class_feature_modules
from app.content import archetype_entries, class_entry
from app.database import CharacterRepository
from app.models import ClassFeatureState
from app.services.character_calculations import CharacterCalculationService


@pytest.fixture
def repository():
    with tempfile.TemporaryDirectory() as directory:
        repo = CharacterRepository(Path(directory) / "review.db")
        try:
            yield repo
        finally:
            repo.close()


def character(repo, family, level, archetype=""):
    entry = class_entry("spheres-class:" + family)
    character_id = repo.create_character(family, "Spheres")
    class_id = repo.add_class_level(
        character_id, entry["name"], level, entry["bab"], entry["fort"],
        entry["reflex"], entry["will"], entry["key"], entry["hit_die"], level * 6,
    )
    if archetype:
        repo.set_class_archetype_keys(character_id, class_id, (
            f"spheres-archetype:spheres-class:{family}:{archetype}",
        ))
    return character_id, class_id


def choices(repo, character_id):
    return {slot.key: slot for slot in resolve_class_choice_slots(repo, character_id)}


@pytest.mark.parametrize("level,bonus", [(3, 1), (7, 2), (11, 3), (15, 4), (19, 5)])
def test_prey_casting_changes_only_sphere_dc_and_penetration(repository, level, bonus):
    c, row = character(repository, "reaper", level)
    assert CharacterCalculationService(repository, c).sphere_dc_bonus("Destruction") == 0
    repository.save_class_feature_state(ClassFeatureState(c, row, "prey_casting_bonus", 0, active=True))
    calculator = CharacterCalculationService(repository, c)
    assert calculator.sphere_dc_bonus("Destruction") == bonus
    assert calculator.automatic_total("sphere_spell_penetration") == bonus
    assert calculator.automatic_total("caster_level") == 0
    assert calculator.automatic_total("save_dc") == 0
    assert calculator.automatic_total("magic_skill_bonus") == 0


def test_machine_insights_share_technique_slots_and_project_selected_rules(repository):
    c, _ = character(repository, "reaper", 4, "machine-cultist")
    slots = choices(repository, c)
    assert "reaper-cult" not in slots
    slot = slots["reaper-techniques"]
    assert slot.maximum == 2
    selected = next(o for o in slot.options if o.name == "Chemical Insight")
    assert selected.description
    assert not any(o.name == "Expert's Insight" for o in slot.options)
    repository.save_class_feature_selection(class_choice_selection_record(c, slot, (selected.key,)))
    assert choices(repository, c)[slot.key].selected_options[0].name == "Chemical Insight"


@pytest.mark.parametrize("level,count,dr", [(4, 0, 2), (5, 1, 2), (9, 2, 4), (13, 3, 6), (17, 4, 8), (20, 4, 10)])
def test_machine_invention_limits_and_replaced_resources(repository, level, count, dr):
    c, _ = character(repository, "reaper", level, "machine-cultist")
    slot = choices(repository, c).get("machine-integrated-invention")
    if count:
        assert slot.maximum == count
        assert len(slot.options) == 12
        assert all(option.description for option in slot.options)
        assert not {"Independent Invention", "Mechanical Arm", "Siege Engine", "Vehicle"}.intersection(
            option.name for option in slot.options
        )
    else:
        assert slot is None
    resources = {r.key: r for m in resolve_class_feature_modules(repository, c, {}) for r in m.resources}
    assert "prey_casting_bonus" not in resources
    assert resources["flesh_is_weak_dr"].maximum == dr


def test_technician_insight_catalog_and_passive_bonuses(repository):
    c, row = character(repository, "technician", 20)
    slot = choices(repository, c)["technician-technical-insights"]
    assert len(slot.options) == 29
    assert slot.minimum == slot.maximum == 10
    assert all(option.description for option in slot.options)
    calculator = CharacterCalculationService(repository, c)
    assert calculator.automatic_total("skill:knowledge_engineering") == 10
    assert all(calculator.automatic_total(ability) == 2 for ability in ("intelligence", "wisdom", "charisma"))
    assert calculator.automatic_total("skill:perception") == 0
    assert calculator.automatic_total("skill:disable_device") == 10
    repository.save_class_feature_state(ClassFeatureState(c, row, "trapfinding", 0, active=True))
    assert CharacterCalculationService(repository, c).automatic_total("skill:perception") == 10


def test_reaper_tracking_toggle_has_a_valid_progression(repository):
    c, row = character(repository, "reaper", 4)
    assert CharacterCalculationService(repository, c).automatic_total("skill:survival") == 0
    repository.save_class_feature_state(ClassFeatureState(c, row, "track", 0, active=True))
    assert CharacterCalculationService(repository, c).automatic_total("skill:survival") == 2


def test_insight_dependencies_are_checked_for_machine_and_technician(repository):
    for family, archetype, provider in (
        ("technician", "", "technician-technical-insights"),
        ("reaper", "machine-cultist", "reaper-techniques"),
    ):
        c, _ = character(repository, family, 4, archetype)
        slot = choices(repository, c)[provider]
        options = {option.name: option.key for option in slot.options}
        with pytest.raises(ValueError, match="requires Intuition"):
            class_choice_selection_record(c, slot, (options["Intuition, Combat"],))
        record = class_choice_selection_record(c, slot, (
            options["Intuition"], options["Intuition, Combat"],
        ))
        repository.save_class_feature_selection(record)
        assert len(choices(repository, c)[provider].selected_options) == 2


def test_all_reaper_and_technician_archetypes_resolve_at_progression_boundaries(repository):
    for family in ("reaper", "technician"):
        for archetype in archetype_entries("spheres-class:" + family):
            for level in (1, 4, 5, 17, 20):
                c, _ = character(repository, family, level, archetype["key"].rsplit(":", 1)[-1])
                calculator = CharacterCalculationService(repository, c)
                calculator.automatic_modifier_map()
                calculator.casting_statistics()
                calculator.resolved_class_skills()
                for slot in choices(repository, c).values():
                    assert slot.options, (archetype["name"], level, slot.key)

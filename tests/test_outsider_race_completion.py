import tempfile
from pathlib import Path

from app.database import CharacterRepository
from app.models import CharacterDetails, RaceTraitChoice
from app.race_rules import race_entry, race_modifier_map, synchronize_racial_trackers
from app.recovery import FullRestEngine
from app.services.character_calculations import CharacterCalculationService


def variant(character_id, race, number):
    key = f"race-alt-trait:{race}:variant-{race}-abilities"
    return CharacterDetails(character_id, race_key=race, race_alternate_trait_keys=(key,),
                            race_trait_choices=(RaceTraitChoice(key, "variant_abilities", (number,)),))


def test_reviewed_variant_bonuses_and_movement():
    with tempfile.TemporaryDirectory() as directory:
        repo = CharacterRepository(Path(directory) / "test.db")
        try:
            c = repo.create_character("Outsider", "Pathfinder 1e")
            repo.add_class_level(c, "Fighter", 5, "Full", "Good", "Poor", "Poor", hit_die=10, hp_gained=30)
            for race, number, field, expected in (
                ("tiefling", "19", "swim_speed", 30), ("tiefling", "31", "burrow_speed", 5),
                ("aasimar", "12", "swim_speed", 20), ("tiefling", "14", "land_speed", 35),
            ):
                repo.update_character_details(variant(c, race, number))
                assert CharacterCalculationService(repo, c).movement_results()[field] == expected
            repo.update_character_details(variant(c, "tiefling", "80"))
            assert CharacterCalculationService(repo, c).automatic_total("cmd") == 2
            repo.update_character_details(variant(c, "tiefling", "98"))
            maximum = CharacterCalculationService(repo, c).hit_point_maximum()
            repo.update_character_details(variant(c, "tiefling", "80"))
            assert maximum == CharacterCalculationService(repo, c).hit_point_maximum() + 5
        finally:
            repo.close()


def test_daily_uses_do_not_refill_on_refresh_and_recover_on_rest():
    with tempfile.TemporaryDirectory() as directory:
        repo = CharacterRepository(Path(directory) / "test.db")
        try:
            c = repo.create_character("Outsider", "Pathfinder 1e")
            repo.update_character_details(variant(c, "tiefling", "4"))
            synchronize_racial_trackers(repo, c)
            tracker, = repo.list_custom_trackers(c)
            assert tracker.current_value == tracker.manual_maximum == 3
            repo.set_custom_tracker_values(c, tracker.id, current_value=1)
            synchronize_racial_trackers(repo, c)
            assert repo.list_custom_trackers(c)[0].current_value == 1
            FullRestEngine(repo, c).perform()
            assert repo.list_custom_trackers(c)[0].current_value == 3
            repo.update_character_details(variant(c, "tiefling", "99"))
            synchronize_racial_trackers(repo, c)
            tracker, = repo.list_custom_trackers(c)
            assert tracker.recovery_event == "none"
            repo.set_custom_tracker_values(c, tracker.id, current_value=0)
            FullRestEngine(repo, c).perform()
            assert repo.list_custom_trackers(c)[0].current_value == 0
        finally:
            repo.close()


def test_cosmetic_tables_are_not_selectable_traits_and_heritage_skills_work():
    for race, erroneous in (("aasimar", "Summoner"), ("tiefling", "Wizard")):
        assert erroneous not in {trait["name"] for trait in race_entry(race)["alternate_racial_traits"]}
    entry = race_entry("aasimar")
    heritage = next(item for item in entry["variants"] if "Musetouched" in item["name"])
    modifiers = race_modifier_map(CharacterDetails(1, race_key="aasimar", race_variant_key=heritage["key"]))
    assert sum(item.value for item in modifiers["skill:perform"]) == 2


def test_every_heritage_replaces_default_spell_like_ability_pool():
    with tempfile.TemporaryDirectory() as directory:
        repo = CharacterRepository(Path(directory) / "test.db")
        try:
            c = repo.create_character("Heritages", "Pathfinder 1e")
            for race in ("aasimar", "tiefling"):
                for heritage in race_entry(race)["variants"]:
                    repo.update_character_details(CharacterDetails(
                        c, race_key=race, race_variant_key=heritage["key"]))
                    synchronize_racial_trackers(repo, c)
                    tracker, = repo.list_custom_trackers(c)
                    assert tracker.name == "Racial: " + heritage["resources"][0]["name"]
                    assert tracker.manual_maximum == 1
                    assert tracker.recovery_event == "full_rest"
        finally:
            repo.close()

import pytest
from app.marvelous_projects import start_project, work_on_project, finish_project
from app.marvelous_item_rules import MarvelousRequirements


def project():
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=1,
                uses=1, activation='standard', range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[])
    return start_project(plan, MarvelousRequirements((), (), 0))


def test_work_limits_distractions_and_no_mutation():
    original = project()
    worked = work_on_project(original, day='2026-10-13', hours=8, distracting=True)
    assert worked['worked_hours'] == 4 and original['worked_hours'] == 0
    with pytest.raises(ValueError, match='eight hours'):
        work_on_project(worked, day='2026-10-13', hours=4)
    with pytest.raises(ValueError, match='four-hour'):
        work_on_project(original, day='2026-10-13', hours=2)
    adventure = work_on_project(original, day='2026-10-13', hours=2, adventuring=True, distracting=True)
    assert adventure['worked_hours'] == 2


@pytest.mark.parametrize('check,status', [(11, 'complete'), (10, 'failed'), (6, 'cursed')])
def test_final_check_outcomes(check, status):
    p = work_on_project(project(), day='2026-10-13', hours=8)
    assert finish_project(p, check)['status'] == status
    assert p['status'] == 'crafting'


def test_incomplete_and_blocked_projects_are_rejected():
    with pytest.raises(ValueError, match='time is incomplete'): finish_project(project(), 20)
    from app.marvelous_item_rules import marvelous_crafting_quote, marvelous_item_price
    with pytest.raises(ValueError, match='requirements'):
        marvelous_crafting_quote(marvelous_item_price(1, 1), 1,
            requirements=MarvelousRequirements(('Missing sphere',), (), 0))

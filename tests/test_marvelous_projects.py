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


def test_project_uses_proportional_hours_not_rounded_calendar_days():
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=3,
                uses=1, activation='standard', range_steps=0, duration_steps=0,
                unique_changes=1, contributions=[])
    p = start_project(plan, MarvelousRequirements((), (), 0))
    assert p['required_hours'] == pytest.approx(19.2)
    for day, hours in [('2026-10-13', 8), ('2026-10-14', 8), ('2026-10-15', 4)]:
        p = work_on_project(p, day=day, hours=hours)
    assert finish_project(p, 13)['status'] == 'complete'


def test_persistent_project_pays_once_and_gates_activation(tmp_path, monkeypatch):
    from app.database import CharacterRepository
    from app.services.crafting import CraftingService
    from dataclasses import replace
    repo = CharacterRepository(tmp_path / 'project.db')
    cid = repo.create_character('Crafter', 'Spheres'); repo.add_feat(cid, 'Craft Marvelous Item')
    repo.update_currency_purse(replace(repo.get_currency_purse(cid), gold=1000))
    service = CraftingService(repo, cid)
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=1,
                uses=1, activation='standard', range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    iid = service.save_marvelous_design(plan, name='Project', slot='', description='')
    with pytest.raises(ValueError, match='requirements'): service.start_marvelous_construction(iid)
    assert repo.get_currency_purse(cid).gold == 1000
    monkeypatch.setattr(service, 'marvelous_plan_requirements', lambda p: MarvelousRequirements((), (), 0))
    service.start_marvelous_construction(iid)
    purse = repo.get_currency_purse(cid)
    assert purse.platinum * 10 + purse.gold == 800
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='already'): service.start_marvelous_construction(iid)
    assert repo._connection.total_changes == before
    with pytest.raises(ValueError, match='usable'): repo.consume_marvelous_item_use(cid, iid)
    repo.advance_marvelous_project(cid, iid, day='2026-10-13', hours=8)
    assert repo.advance_marvelous_project(cid, iid, check_total=11)['status'] == 'complete'
    repo.consume_marvelous_item_use(cid, iid)
    repo.close()


def test_project_ui_confirmations_and_progress(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app.ui.marvelous_crafting import MarvelousProjectDialog
    from app.database import CharacterRepository
    from app.services.crafting import CraftingService
    from dataclasses import replace
    app = QApplication.instance() or QApplication([])
    repo = CharacterRepository(tmp_path / 'ui.db')
    cid = repo.create_character('Crafter', 'Spheres'); repo.add_feat(cid, 'Craft Marvelous Item')
    repo.update_currency_purse(replace(repo.get_currency_purse(cid), gold=1000))
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=1,
                uses=1, activation='standard', range_steps=0, duration_steps=0, unique_changes=0, contributions=[])
    iid = CraftingService(repo, cid).save_marvelous_design(plan, name='Project', slot='', description='')
    monkeypatch.setattr(CraftingService, 'marvelous_plan_requirements', lambda self, p: MarvelousRequirements((), (), 0))
    dialog = MarvelousProjectDialog(repo, cid, iid)
    before = repo._connection.total_changes
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.No)
    dialog.start_construction()
    assert repo._connection.total_changes == before
    monkeypatch.setattr(QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes)
    dialog.start_construction()
    assert not dialog.start.isEnabled() and dialog.work.isEnabled()
    dialog.record_work()
    assert dialog.finish.isEnabled() and not dialog.work.isEnabled()
    dialog.check.setValue(11); dialog.finish_construction()
    assert dialog.project['status'] == 'complete' and dialog.changed
    dialog.close(); repo.close()


def test_work_calendar_is_shared_between_retained_projects(tmp_path, monkeypatch):
    from app.database import CharacterRepository
    from app.services.crafting import CraftingService
    from dataclasses import replace
    repo = CharacterRepository(tmp_path / 'calendar.db')
    cid = repo.create_character('Crafter', 'Spheres')
    repo.add_feat(cid, 'Craft Marvelous Item')
    repo.update_currency_purse(replace(repo.get_currency_purse(cid), gold=1000))
    service = CraftingService(repo, cid)
    monkeypatch.setattr(service, 'marvelous_plan_requirements', lambda p: MarvelousRequirements((), (), 0))
    plan = dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=1,
                uses=1, activation='standard', range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[])
    ids = [service.save_marvelous_design(plan, name=name, slot='', description='')
           for name in ('First', 'Second')]
    for iid in ids: service.start_marvelous_construction(iid)
    repo.advance_marvelous_project(cid, ids[0], day='2026-10-13', hours=4)
    repo.advance_marvelous_project(cid, ids[1], day='2026-10-13', hours=4)
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='across all projects'):
        repo.advance_marvelous_project(cid, ids[1], day='2026-10-13', hours=4)
    assert repo._connection.total_changes == before
    assert repo.advance_marvelous_project(cid, ids[1], day='2026-10-14', hours=4)['worked_hours'] == 8
    repo.advance_marvelous_project(cid, ids[0], day='2026-10-15', hours=4)
    repo.advance_marvelous_project(cid, ids[0], day='2026-10-15', check_total=11)
    before = repo._connection.total_changes
    with pytest.raises(ValueError, match='one item'):
        repo.advance_marvelous_project(cid, ids[1], day='2026-10-15', check_total=11)
    assert repo._connection.total_changes == before
    assert repo.advance_marvelous_project(cid, ids[1], day='2026-10-16', check_total=11)['completion_day'] == '2026-10-16'
    repo.delete_equipment(cid, ids[0])
    archived = {record['day']: record for record in repo.archived_crafting_days(cid)}
    assert archived['2026-10-13']['hours'] == 4 and archived['2026-10-15']['completions'] == 1
    third = service.save_marvelous_design(plan, name='Third', slot='', description='')
    service.start_marvelous_construction(third)
    with pytest.raises(ValueError, match='across all projects'):
        repo.advance_marvelous_project(cid, third, day='2026-10-13', hours=4)
    repo.advance_marvelous_project(cid, third, day='2026-10-14', hours=4)
    repo.advance_marvelous_project(cid, third, day='2026-10-15', hours=4)
    with pytest.raises(ValueError, match='one item'):
        repo.advance_marvelous_project(cid, third, day='2026-10-15', check_total=11)
    from app.transfer import export_character, import_character
    export = tmp_path / 'archived.character.json'
    export_character(repo, cid, export)
    imported = import_character(repo, export)
    assert repo.archived_crafting_days(imported) == repo.archived_crafting_days(cid)
    repo.close()

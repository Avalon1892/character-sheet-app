"""Pure construction progress; explicit calendar input, no UI or persistence."""
from copy import deepcopy
from datetime import date
from app.marvelous_item_rules import quote_marvelous_blueprint, marvelous_crafting_quote


def start_project(plan, requirements):
    _, price, _ = quote_marvelous_blueprint(plan)
    quote = marvelous_crafting_quote(price, plan['caster_level'], requirements=requirements)
    return dict(status='crafting', required_hours=quote.days * 8, worked_hours=0,
                materials_gp=str(quote.cost_gp), dc=quote.dc, calendar={})


def work_on_project(project, *, day, hours, distracting=False, adventuring=False):
    if project.get('status') != 'crafting': raise ValueError('This project is not in progress.')
    if not isinstance(day, str): raise ValueError('Work day must be an ISO date.')
    if not isinstance(distracting, bool) or not isinstance(adventuring, bool):
        raise ValueError('Work circumstances must be boolean.')
    date.fromisoformat(day)
    if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 8:
        raise ValueError('Work hours must be an integer from 1 to 8.')
    if not adventuring and hours < 4:
        raise ValueError('Ordinary crafting requires at least a four-hour block.')
    if adventuring and hours != 2:
        raise ValueError('An adventuring day grants two effective crafting hours.')
    updated = deepcopy(project)
    calendar = updated['calendar']
    if calendar and day < max(calendar): raise ValueError('Cannot record work before an already recorded day.')
    spent = calendar.get(day, 0)
    if spent + (8 if adventuring else hours) > 8:
        raise ValueError('No more than eight hours of crafting per day.')
    calendar[day] = spent + (8 if adventuring else hours)
    updated['worked_hours'] += 2 if adventuring else hours / 2 if distracting else hours
    return updated


def finish_project(project, check_total):
    if project.get('status') != 'crafting': raise ValueError('This project is not in progress.')
    if project['worked_hours'] < project['required_hours']: raise ValueError('Construction time is incomplete.')
    if isinstance(check_total, bool) or not isinstance(check_total, int): raise ValueError('Check total must be an integer.')
    updated = deepcopy(project)
    updated['check_total'] = check_total
    updated['status'] = 'complete' if check_total >= project['dc'] else 'cursed' if check_total <= project['dc'] - 5 else 'failed'
    return updated

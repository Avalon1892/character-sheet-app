from fractions import Fraction
import pytest
from app.marvelous_item_rules import quote_marvelous_blueprint
from app.marvelous_base_powers import resolve_base_power


def blueprint(**changes):
    return dict(schema_version=1, sphere='Life', base_power='life:temporary-hp',
                caster_level=10, uses=1, activation='standard', range_steps=0,
                duration_steps=0, unique_changes=0, contributions=[], **changes)


def test_slotless_is_a_mechanical_choice_not_a_slot_name():
    ordinary = quote_marvelous_blueprint(blueprint())[1]
    slotless = quote_marvelous_blueprint(blueprint(no_space_limitation=True))[1]
    assert slotless.market_price_gp == ordinary.market_price_gp * 2
    assert slotless.save_dc == ordinary.save_dc


def test_alternative_options_use_exact_half_costs():
    p = blueprint()
    p['contributions'] = [dict(complexity=1, alternative=True),
                          dict(complexity=2, alternative=True), dict(complexity=3)]
    complexity, price, quote = quote_marvelous_blueprint(p)
    assert complexity == Fraction(13, 2)
    assert price.market_price_gp == 26000
    assert quote.cost_gp == 13000


def test_permanency_requires_hours_and_level_ten_and_adds_complexity():
    p = blueprint(permanent=True)
    with pytest.raises(ValueError, match='hours'): quote_marvelous_blueprint(p)
    p['duration_steps'] = 2
    complexity, _, _ = quote_marvelous_blueprint(p)
    assert complexity == 7
    assert resolve_base_power(p)['duration'] == 'Permanent (dispellable)'
    p['caster_level'] = 9
    with pytest.raises(ValueError, match='level 10'): quote_marvelous_blueprint(p)


def test_old_blueprint_defaults_remain_unchanged():
    complexity, price, _ = quote_marvelous_blueprint(blueprint())
    assert complexity == 1 and price.market_price_gp == 4000


@pytest.mark.parametrize('changes', [dict(no_space_limitation='yes'), dict(permanent=1)])
def test_flags_are_not_silently_coerced(changes):
    with pytest.raises(ValueError): quote_marvelous_blueprint(blueprint(**changes))

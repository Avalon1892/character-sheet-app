import pytest
from fractions import Fraction

from app.marvelous_item_rules import effect_complexity, marvelous_crafting_quote, marvelous_item_price


def test_base_and_use_modes():
    quote = marvelous_item_price(3, 2)
    assert (quote.market_price_gp, quote.save_dc, quote.daily_uses) == (2400, 11, 1)
    assert marvelous_item_price(3, 2, daily_uses=4).market_price_gp == 9600
    unlimited = marvelous_item_price(3, 2, daily_uses=5)
    assert unlimited.market_price_gp == 12000
    assert unlimited.daily_uses is None and unlimited.total_uses is None
    limited = marvelous_item_price(3, 2, limited_uses=True)
    assert limited.market_price_gp == 6000
    assert limited.daily_uses is None and limited.total_uses == 50


@pytest.mark.parametrize("kwargs", [
    {"caster_level": 0}, {"complexity": -1}, {"complexity": 1.5},
    {"caster_level": True}, {"daily_uses": 0}, {"daily_uses": 6},
    {"daily_uses": 2, "limited_uses": True},
])
def test_invalid_construction(kwargs):
    values = {"caster_level": 1, "complexity": 1, **kwargs}
    with pytest.raises(ValueError):
        marvelous_item_price(**values)


def test_exact_variable_complexity_and_caster_level_gate():
    complexity = effect_complexity(talent_costs=(1,), alternative_costs=(1, 2))
    assert complexity == Fraction(9, 2)
    assert marvelous_item_price(5, complexity).market_price_gp == 9000
    with pytest.raises(ValueError, match="caster level"):
        marvelous_item_price(4, complexity)


def test_construction_adjustments_and_minimum():
    assert effect_complexity(range_steps=2, duration_steps=1, activation="move") == 8
    assert effect_complexity(range_steps=-2, duration_steps=-1, activation="full-round") == 1
    assert effect_complexity(talent_costs=(3,), unique_changes=-1) == 3


def test_spheres_crafting_dc_materials_and_work_conditions():
    price = marvelous_item_price(3, 2)
    normal = marvelous_crafting_quote(price, 3, missing_talents=2)
    assert (normal.cost_gp, normal.dc, normal.days) == (1200, 23, 3)
    assert marvelous_crafting_quote(price, 3, distracting=True).days == 6
    assert marvelous_crafting_quote(price, 3, adventuring=True, distracting=True).days == 12


@pytest.mark.parametrize("kwargs", [{"talent_costs": (-1,)}, {"alternative_costs": (0.5,)},
                                    {"activation": "free"}, {"range_steps": 1.5}])
def test_invalid_effect_contributions(kwargs):
    with pytest.raises(ValueError):
        effect_complexity(**kwargs)

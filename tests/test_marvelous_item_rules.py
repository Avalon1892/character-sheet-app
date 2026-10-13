import pytest

from app.marvelous_item_rules import marvelous_item_price


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

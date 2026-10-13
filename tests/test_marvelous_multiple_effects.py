import pytest
from app.marvelous_item_rules import quote_marvelous_effects


def effect(complexity=1, cl=10, uses=1):
    return dict(schema_version=1, sphere='Life', base_power='life:cure',
                caster_level=cl, uses=uses, activation='standard', range_steps=0,
                duration_steps=0, unique_changes=complexity - 1, contributions=[])


@pytest.mark.parametrize('mode,total', [('multiple', 18000), ('mixed', 20000)])
def test_independent_effects_keep_their_own_complexity_and_resources(mode, total):
    quote = quote_marvelous_effects([effect(1), effect(3)], mode=mode)
    assert quote['market_price_gp'] == total
    assert quote['crafting'].cost_gp == total / 2
    assert quote['crafting'].days == total / 1000
    assert [row[0] for row in quote['effects']] == [1, 3]
    assert all(row[1].daily_uses == 1 for row in quote['effects'])


def test_tied_most_expensive_effect_only_one_is_full_price():
    quote = quote_marvelous_effects([effect(), effect(), effect()])
    assert quote['market_price_gp'] == 16000


def test_highest_price_not_highest_complexity_is_full_price():
    quote = quote_marvelous_effects([effect(3), effect(1, uses=5)])
    assert quote['market_price_gp'] == 38000


def test_invalid_combinations_are_rejected():
    with pytest.raises(ValueError, match='same caster level'):
        quote_marvelous_effects([effect(cl=5), effect(cl=6)])
    with pytest.raises(ValueError, match='At least one'):
        quote_marvelous_effects([])
    with pytest.raises(ValueError, match='mode'):
        quote_marvelous_effects([effect()], mode='unknown')

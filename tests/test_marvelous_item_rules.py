import pytest
from fractions import Fraction

from app.marvelous_item_rules import effect_complexity, marvelous_crafting_quote, marvelous_item_price
from app.marvelous_item_rules import marvelous_requirements


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
    assert (normal.cost_gp, normal.dc, normal.days) == (1200, 23, 2.4)
    assert marvelous_crafting_quote(price, 3, distracting=True).days == 4.8
    assert marvelous_crafting_quote(price, 3, adventuring=True, distracting=True).days == 9.6
    assert marvelous_crafting_quote(marvelous_item_price(1, 1), 1).days == 1


def test_talent_construction_defaults_and_admixture_exception():
    from app.marvelous_item_rules import talent_construction_cost
    assert talent_construction_cost({'key': 'destruction:talent:admixture', 'category': 'Talent'}) == 0
    assert talent_construction_cost({'category': 'Talent'}, additional_spell_points=2) == 3
    assert talent_construction_cost({'category': 'Advanced Talent'}, additional_spell_points=1) == 3
    assert talent_construction_cost({'category': 'Advanced Talent'}, additional_spell_points=1, mythic_crafter=True) == 2
    with pytest.raises(ValueError): talent_construction_cost({}, mythic_crafter=1)
    assert talent_construction_cost({'key': 'alteration:talent:mass-alteration-mass', 'category': 'Talent'}) == 2
    assert talent_construction_cost({'key': 'illusion:talent:suppression-glamer', 'category': 'Talent'}) == 2
    with pytest.raises(ValueError): talent_construction_cost({}, additional_spell_points=True)


def test_mana_transfer_cannot_be_applied_to_crafted_manipulation():
    from app.marvelous_item_rules import quote_marvelous_blueprint
    plan = dict(schema_version=1, sphere='Mana', base_power='mana:manipulate', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[dict(
                    catalog_key='mana:manipulation-talent:transfer-manipulation', complexity=1)])
    with pytest.raises(ValueError, match='Mana Transfer'):
        quote_marvelous_blueprint(plan)


def test_crafting_tradition_costs_preserve_base_price_and_apply_floor():
    from app.marvelous_item_rules import tradition_costs
    assert tradition_costs(1000, cheap=True) == (450, 900)
    assert tradition_costs(1000, expensive=True) == (625, 1000)
    assert tradition_costs(1000, cheap=True, other_reduction=Fraction(1, 5)) == (400, 800)
    with pytest.raises(ValueError): tradition_costs(1000, cheap=True, expensive=True)


def test_explicit_feat_integration_costs_and_duplicate_validation():
    from app.marvelous_item_rules import feat_integration_complexity
    assert feat_integration_complexity([dict(name='Maximize Spell', metamagic=True, additional_spell_points=3)]) == 4
    assert feat_integration_complexity([dict(name='Example feat')]) == 1
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='A'), dict(name='a')])
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='A', additional_spell_points=1)])
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='Maximize Spell')])
    with pytest.raises(ValueError): feat_integration_complexity([dict(name='Maximize Spell', metamagic=True, additional_spell_points=2)])
    assert feat_integration_complexity([dict(name='Empower Spell', metamagic=True, additional_spell_points=2)]) == 3


@pytest.mark.parametrize("kwargs", [{"talent_costs": (-1,)}, {"alternative_costs": (0.5,)},
                                    {"activation": "free"}, {"range_steps": 1.5}])
def test_invalid_effect_contributions(kwargs):
    with pytest.raises(ValueError):
        effect_complexity(**kwargs)


def test_missing_ordinary_talent_is_bypassable_but_advanced_is_not():
    result = marvelous_requirements(caster_level=5, sphere_levels={"Life": 5},
        feats=("Craft Marvelous Item",), required_spheres=("Life",),
        required_talents=("Restore", "Resurrection"), advanced_talents=("Resurrection",))
    assert not result.eligible
    assert result.dc_increase == 5
    assert result.bypassed == ("Missing talent: Restore",)
    assert result.blockers == ("Missing talent: Resurrection",)


def test_versatile_crafter_waives_sphere_and_level_not_protected_features():
    result = marvelous_requirements(caster_level=3, sphere_levels={},
        feats=("Craft Wondrous Item", "Versatile Crafter"), required_spheres=("Life",),
        protected_requirements=("Mythic Crafter",), prohibited_abilities=("Healing",))
    assert result.dc_increase == 20
    assert len(result.blockers) == 2
    assert len(result.bypassed) == 2


def test_cooperative_access_and_case_insensitive_identity():
    result = marvelous_requirements(caster_level=3, sphere_levels={"life": 3},
        feats=("CRAFT MARVELOUS ITEM",), required_spheres=("Life",),
        required_talents=("Resurrection",), available_talents=("resurrection",),
        advanced_talents=("Resurrection",))
    assert result.eligible and not result.bypassed and result.dc_increase == 0


def test_missing_creation_feat_cannot_be_waived():
    result = marvelous_requirements(caster_level=1, sphere_levels={"Life": 1},
        feats=("Versatile Crafter",), required_spheres=("Life",))
    assert not result.eligible
    with pytest.raises(ValueError, match="not met"):
        marvelous_crafting_quote(marvelous_item_price(1, 1), 1, requirements=result)


def test_validated_versatile_dc_flows_into_quote_once():
    result = marvelous_requirements(caster_level=3, sphere_levels={"Life": 1},
        feats=("Craft Marvelous Item", "Versatile Crafter"), required_spheres=("Life", "life"))
    quote = marvelous_crafting_quote(marvelous_item_price(3, 1), 3, requirements=result)
    assert quote.dc == 23
    with pytest.raises(ValueError, match="second"):
        marvelous_crafting_quote(marvelous_item_price(3, 1), 3, requirements=result, missing_talents=1)

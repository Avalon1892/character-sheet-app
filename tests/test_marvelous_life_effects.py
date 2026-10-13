import pytest
from app.marvelous_base_powers import resolve_base_power, automatic_self_effect


def cure(keys, cl=10):
    return dict(base_power='life:cure', sphere='Life', caster_level=cl,
                range_steps=0, duration_steps=0, unique_changes=0,
                contributions=[dict(catalog_key=key, complexity=1) for key in keys])


@pytest.mark.parametrize('suffix', ['capacity', 'health', 'senses', 'spirit'])
def test_each_cure_talent_adds_one_hp_per_level(suffix):
    plan = cure([f'life:cure-talent:restore-{suffix}-cure'])
    assert resolve_base_power(plan)['healing'] == '1d8+20'
    assert automatic_self_effect(plan) == 'cure'


def test_deeper_healing_and_cure_talents_combine_without_averages():
    plan = cure(['life:talent:deeper-healing', 'life:cure-talent:restore-health-cure'])
    assert resolve_base_power(plan)['healing'] == '4d8+20'


def test_unknown_duplicate_and_alternative_contributions_stay_manual():
    for keys in [['unknown'], ['life:talent:deeper-healing'] * 2]:
        assert automatic_self_effect(cure(keys)) is None
    plan = cure(['life:talent:deeper-healing'])
    plan['contributions'][0]['alternative'] = True
    assert automatic_self_effect(plan) is None

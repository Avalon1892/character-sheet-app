from app.marvelous_item_presentation import ITEM_FIELDS, item_card_fields, item_card_html


def blueprint():
    return dict(schema_version=1, sphere='Life', base_power='life:cure', caster_level=5,
                activation='standard', uses=1, range_steps=0, duration_steps=0,
                unique_changes=0, contributions=[])


def test_item_block_descriptors_and_all_field_locks():
    plan = blueprint()
    fields = item_card_fields(plan, name='Healing gem', slot='Neck', description='A bright gem.')
    assert fields['price'] == '2,000.00 gp' and fields['construction_cost'] == '1,000.00 gp'
    assert fields['range'] == 'Touch' and fields['duration'] == 'Instantaneous'
    html = item_card_html(fields)
    assert all(label in html for label in ('Aura', 'CL', 'Slot', 'Price', 'Weight', 'Activation', 'Uses', 'DESCRIPTION', 'CONSTRUCTION'))
    plan['display_overrides'] = {key: dict(locked=True, value=f'Manual {key}') for key in ITEM_FIELDS}
    changed = item_card_fields(plan, name='Other', slot='', description='Changed')
    assert all(changed[key] == f'Manual {key}' for key in ITEM_FIELDS)
    plan['display_overrides']['range']['locked'] = False
    assert item_card_fields(plan, name='Other', slot='', description='Changed')['range'] == 'Touch'


def test_item_block_escapes_manual_html():
    fields = item_card_fields(blueprint(), name='<script>bad</script>', slot='', description='<img src=x>\nSecond line')
    html = item_card_html(fields)
    assert '<script>' not in html and '<img src=x>' not in html
    assert '&lt;script&gt;' in html and '&lt;img src=x&gt;<br>Second line' in html

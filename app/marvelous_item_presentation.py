"""Item-card projections and display locks; no mechanical overrides."""
from app.marvelous_item_rules import quote_marvelous_blueprint
from app.marvelous_base_powers import resolve_base_power

ITEM_FIELDS = ('name', 'slot', 'caster_level', 'save_dc', 'activation', 'uses', 'price', 'description')


def validate_display_overrides(records):
    if not isinstance(records, dict): raise ValueError('Item display overrides must be a mapping.')
    for key, record in records.items():
        if key not in ITEM_FIELDS or not isinstance(record, dict):
            raise ValueError('Unknown item display override.')
        if not isinstance(record.get('locked'), bool) or not isinstance(record.get('value'), str):
            raise ValueError('Item display overrides require text and a boolean lock.')


def item_card_fields(plan, *, name, slot, description):
    """Locked text changes the card, never the quoted price or activation rules."""
    _, price, _ = quote_marvelous_blueprint(plan)
    effect = resolve_base_power(plan)
    values = dict(name=name, slot=slot or 'Held / carried', caster_level=str(plan['caster_level']),
                  save_dc=str(price.save_dc), activation=plan['activation'].replace('-', ' ').title(),
                  uses='50 total activations' if plan['uses'] == 50 else 'At will' if plan['uses'] == 5 else f"{plan['uses']}/day",
                  price=f'{float(price.market_price_gp):,.2f} gp',
                  description=description or '\n'.join(f'{key.replace("_", " ").title()}: {value}'
                      for key, value in effect.items() if isinstance(value, (str, int))))
    from app.content import magic_entry
    for contribution in plan.get('contributions', []):
        entry = magic_entry(contribution['catalog_key'])
        if entry is None: continue
        label = f"Alternative group {contribution.get('alternative_group', 1)}" if contribution.get('alternative') else 'Effect'
        values['description'] += f"\n\n{label} — {entry['name']}\n{entry.get('description', '')}"
    records = plan.get('display_overrides', {})
    if plan.get('drawbacks'):
        values['description'] += '\n\nDrawbacks:\n' + '\n'.join(
            f"{record['name']}: {record.get('description', '')} (−{record['reduction']} complexity; {record['source']}, GM review)"
            for record in plan['drawbacks'])
    validate_display_overrides(records)
    values.update({key: record['value'] for key, record in records.items() if record['locked']})
    return values

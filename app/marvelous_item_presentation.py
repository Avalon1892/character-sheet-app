"""Item-card projections and display locks; no mechanical overrides."""
from app.marvelous_item_rules import quote_marvelous_blueprint
from app.marvelous_base_powers import resolve_base_power
from html import escape

ITEM_FIELDS = ('name', 'slot', 'aura', 'weight', 'caster_level', 'save_dc', 'activation', 'uses',
               'range', 'duration', 'price', 'construction_cost', 'construction_requirements', 'description')


def contribution_cost_details(plan):
    """Explain stored contribution costs without substituting catalog defaults."""
    from app.content import magic_entry
    lines = []
    for row in plan.get('contributions', []):
        entry = magic_entry(row['catalog_key'])
        name = entry['name'] if entry else row['catalog_key']
        points = row.get('additional_spell_points', 0)
        group = f" [alternative group {row.get('alternative_group', 1)}]" if row.get('alternative') else ''
        choice = f" ({row['effect_choice']})" if row.get('effect_choice') else ''
        lines.append(f"{name}{choice}{group}: {row['complexity'] - points} talent + {points} extra SP = {row['complexity']} complexity")
    for row in plan.get('drawbacks', []):
        lines.append(f"{row['name']}: −{row['reduction']} complexity")
    return '\n'.join(lines)


def validate_display_overrides(records):
    if not isinstance(records, dict): raise ValueError('Item display overrides must be a mapping.')
    for key, record in records.items():
        if key not in ITEM_FIELDS or not isinstance(record, dict):
            raise ValueError('Unknown item display override.')
        if not isinstance(record.get('locked'), bool) or not isinstance(record.get('value'), str):
            raise ValueError('Item display overrides require text and a boolean lock.')


def item_card_fields(plan, *, name, slot, description, quotation=None):
    """Locked text changes the card, never the quoted price or activation rules."""
    quotation = quotation if quotation is not None else quote_marvelous_blueprint(plan)
    _, price, quote = quotation
    effect = resolve_base_power(plan)
    from app.marvelous_item_rules import marvelous_item_weight, marvelous_aura_strength
    weight = marvelous_item_weight(plan)
    values = dict(name=name, slot=slot or 'Held / carried', caster_level=str(plan['caster_level']),
                  aura=marvelous_aura_strength(plan['caster_level']) + ' (school not specified)', weight='Not specified' if weight is None else f'{weight:g} lb.', range=effect['range'], duration=effect['duration'],
                  save_dc=str(price.save_dc), activation=plan['activation'].replace('-', ' ').title(),
                  uses='50 total activations' if plan['uses'] == 50 else 'At will' if plan['uses'] == 5 else f"{plan['uses']}/day",
                  price=f'{float(price.market_price_gp):,.2f} gp',
                  construction_cost=f'{float(quote.cost_gp):,.2f} gp',
                  construction_requirements=f"Craft Marvelous Item (or Craft Wondrous Item); {plan['sphere']} sphere; permanent CL {plan['caster_level']}",
                  description=(description + '\n\n' if description else '') + '\n'.join(
                      f'{key.replace("_", " ").title()}: {value}' for key, value in effect.items()
                      if isinstance(value, (str, int)) and key not in {'range', 'duration', 'caster_level', 'save_dc'}))
    from app.content import magic_entry
    for contribution in plan.get('contributions', []):
        entry = magic_entry(contribution['catalog_key'])
        if entry is None: continue
        values['construction_requirements'] += '; ' + entry['name']
        from app.marvelous_item_rules import talent_construction_spell_points
        if talent_construction_spell_points(entry, reviewed_only=True, base_power=plan.get('base_power')) is None:
            values['construction_requirements'] += ' (SP cost requires review; no registered automatic default)'
        from app.marvelous_item_rules import cross_sphere_construction_requirements, construction_package_requirements
        for package in construction_package_requirements(contribution):
            values['construction_requirements'] += '; prerequisite: ' + package
        for sphere, required_key in cross_sphere_construction_requirements(contribution):
            required = magic_entry(required_key) if required_key else None
            values['construction_requirements'] += '; prerequisite: ' + sphere + ' sphere'
            if entry['key'] == 'conjuration:form-talent:superior-senses-form':
                values['construction_requirements'] += ' (caster or companion)'
            if required_key: values['construction_requirements'] += ' / ' + (required['name'] if required else required_key)
        label = f"Alternative group {contribution.get('alternative_group', 1)}" if contribution.get('alternative') else 'Effect'
        if entry['sphere'].casefold() != plan['sphere'].casefold(): label = 'Required cross-sphere talent'
        selected = f"\nSelected option: {contribution['effect_choice']}" if contribution.get('effect_choice') else ''
        values['description'] += f"\n\n{label} — {entry['name']}{selected}\n{entry.get('description', '')}"
    records = plan.get('display_overrides', {})
    if tradition := plan.get('crafting_tradition'):
        values['description'] += '\n\nCrafting tradition — ' + tradition.get('name', tradition['key'])
        values['description'] += '\n' + tradition.get('description', '')
        if tradition.get('notes'): values['description'] += '\n' + tradition['notes']
        from app.marvelous_item_rules import crafting_boon_details
        for detail in crafting_boon_details(plan): values['description'] += '\n' + detail
    if plan.get('drawbacks'):
        values['description'] += '\n\nDrawbacks:\n' + '\n'.join(
            f"{record['name']}: {record.get('description', '')} (−{record['reduction']} complexity; {record['source']}, GM review)"
            for record in plan['drawbacks'])
    from app.marvelous_item_rules import crafting_limitation_details
    if limitations := crafting_limitation_details(plan, quotation=quotation):
        values['description'] += '\n\nActivation requirements:\n' + '\n'.join(limitations)
    if plan.get('extra_effects'):
        mixed = plan.get('combination_mode') == 'mixed'
        primary_uses = values['uses']
        values['uses'] = 'All component limits apply' if mixed else 'Independent per-power limits'
        for key in ('activation', 'range', 'duration'): values[key] += ' (primary)'
        values['description'] = (('Mixed simultaneous powers' if mixed else 'Separate selectable powers')
                                 + f'\nPrimary power — {effect["power"]}; {primary_uses}\n\n' + values['description'])
        from app.marvelous_item_rules import marvelous_effect_plan
        for index in range(2, len(plan['extra_effects']) + 2):
            extra = marvelous_effect_plan(plan, index - 1)
            effect_name = extra.get('effect_name', resolve_base_power(extra)['power'])
            effect_description = extra.get('effect_description', '')
            if not isinstance(effect_name, str) or not isinstance(effect_description, str):
                raise ValueError('Additional power name and description must be text.')
            child = item_card_fields(extra, name=effect_name, slot=slot, description=effect_description)
            values['description'] += (f'\n\nPower {index} — {child["name"]}\n'
                f'CL: {child["caster_level"]}; Activation: {child["activation"]}; Uses: {child["uses"]}; Range: {child["range"]}; '
                f'Duration: {child["duration"]}; Save DC: {child["save_dc"]}\n{child["description"]}')
            values['construction_requirements'] += f'\nPower {index}: {child["construction_requirements"]}'
    validate_display_overrides(records)
    values.update({key: record['value'] for key, record in records.items() if record['locked']})
    return values


def item_card_html(fields):
    """A theme-neutral PF-style item block; all manual/catalog text is escaped."""
    text = {key: escape(value).replace('\n', '<br>') for key, value in fields.items()}
    return (f'<h2>{text["name"]}</h2><hr>'
            f'<p><b>Aura</b> {text["aura"]}; <b>CL</b> {text["caster_level"]}<br>'
            f'<b>Slot</b> {text["slot"]}; <b>Price</b> {text["price"]}; <b>Weight</b> {text["weight"]}<br>'
            f'<b>Activation</b> {text["activation"]}; <b>Uses</b> {text["uses"]}<br>'
            f'<b>Range</b> {text["range"]}; <b>Duration</b> {text["duration"]}; <b>Save DC</b> {text["save_dc"]}</p>'
            f'<h3>DESCRIPTION</h3><hr><p>{text["description"]}</p>'
            f'<h3>CONSTRUCTION</h3><hr><p><b>Requirements</b> {text["construction_requirements"]}<br>'
            f'<b>Materials</b> {text["construction_cost"]}</p>')

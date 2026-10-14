"""Verified base Marvelous Item pricing; no catalog or persistence side effects.

Complexity is an already-resolved talent-based value, not a talent count.
Source: https://spheresofpower.wikidot.com/magical-items
"""
from dataclasses import dataclass, replace
from fractions import Fraction

from app.crafting_rules import CraftingQuote


@dataclass(frozen=True)
class MarvelousItemPrice:
    market_price_gp: Fraction
    save_dc: int
    daily_uses: int | None
    total_uses: int | None


@dataclass(frozen=True)
class MarvelousRequirements:
    blockers: tuple[str, ...]
    bypassed: tuple[str, ...]
    dc_increase: int

    @property
    def eligible(self):
        return not self.blockers


def marvelous_requirements(*, caster_level, sphere_levels, feats, required_spheres,
                            required_talents=(), available_talents=(),
                            advanced_talents=(), protected_requirements=(),
                            available_requirements=(), prohibited_abilities=()):
    """Evaluate explicitly supplied crafting access, independently of Qt.

    Sphere levels must exclude temporary bonuses. Cooperative sources must be
    available for the entire construction period. Advanced talents and protected
    class requirements are never waived. Versatile Crafter can waive base spheres
    and each missing caster level, but not a tradition's prohibited abilities.
    """
    if isinstance(caster_level, bool) or not isinstance(caster_level, int) or caster_level < 1:
        raise ValueError("Item caster level must be a positive integer.")
    levels = {name.casefold(): value for name, value in sphere_levels.items()}
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in levels.values()):
        raise ValueError("Permanent sphere levels must be nonnegative integers.")
    known_feats = {name.casefold() for name in feats}
    known_talents = {name.casefold() for name in available_talents}
    advanced = {name.casefold() for name in advanced_talents}
    requirements = {name.casefold() for name in available_requirements}
    versatile = "versatile crafter" in known_feats
    blockers, bypassed = [], []
    dc_increase = 0
    if not known_feats.intersection({"craft marvelous item", "craft wondrous item"}):
        blockers.append("Requires Craft Marvelous Item (or Craft Wondrous Item).")
    spheres = {name.casefold(): name for name in required_spheres}
    if not spheres or any(not name.strip() for name in spheres):
        raise ValueError("At least one base sphere is required.")
    for sphere in spheres.values():
        level = levels.get(sphere.casefold(), 0)
        if level == 0:
            message = f"Missing base sphere: {sphere}"
            (bypassed if versatile else blockers).append(message)
            if versatile:
                dc_increase += 5
        deficit = max(0, caster_level - level)
        if deficit:
            message = f"{sphere}: permanent caster level {level}, requires {caster_level}"
            (bypassed if versatile else blockers).append(message)
            if versatile:
                dc_increase += 5 * deficit
    for talent in {name.casefold(): name for name in required_talents}.values():
        if talent.casefold() in known_talents:
            continue
        message = f"Missing talent: {talent}"
        if talent.casefold() in advanced:
            blockers.append(message)
        else:
            bypassed.append(message)
            dc_increase += 5
    blockers.extend(f"Missing required feature: {name}" for name in protected_requirements
                    if name.casefold() not in requirements)
    blockers.extend(f"Casting tradition prohibits: {name}" for name in prohibited_abilities)
    return MarvelousRequirements(tuple(blockers), tuple(bypassed), dc_increase)


def marvelous_item_price(caster_level: int, complexity: int | Fraction, *, daily_uses: int = 1,
                         limited_uses: bool = False) -> MarvelousItemPrice:
    """Price the base effect, excluding optional traditions and costly components.

    Five daily uses means unlimited use; limited-use construction instead grants
    fifty total activations. Neither mode implies free spell-point resources.
    """
    for label, value in (("Caster level", caster_level), ("Daily uses", daily_uses)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{label} must be a positive integer.")
    if isinstance(complexity, bool) or not isinstance(complexity, (int, Fraction)) or complexity < 1:
        raise ValueError("Complexity must be an exact value of at least one.")
    if complexity > caster_level:
        raise ValueError("Item caster level must be at least its complexity.")
    if daily_uses > 5:
        raise ValueError("Use five daily uses for unlimited activation.")
    if limited_uses and daily_uses != 1:
        raise ValueError("Limited-total and daily-use construction cannot be combined.")
    base = Fraction(400 * caster_level * complexity)
    return MarvelousItemPrice(
        base * Fraction(5, 2) if limited_uses else base * daily_uses,
        10 + caster_level // 2,
        None if limited_uses or daily_uses == 5 else daily_uses,
        50 if limited_uses else None,
    )


# Reviewed construction prerequisites use catalog identities, never prose parsing.
ADVANCED_CONSTRUCTION_REQUIREMENTS = {
    'protection:advanced-talent:permanent-ward': (10, ('protection:talent:enduring-protection',)),
    'protection:advanced-talent:planar-refuge-aegis-ward-rw-hb': (5, ()),
    'protection:advanced-talent:preserve-integrity-aegis-alienist-hb': (10, ()),
    'protection:advanced-talent:rapid-glyph-3pp': (0, ('protection:talent:glyph',)),
    'protection:advanced-talent:spell-eater-aegis-3pp': (10, ('protection:succor-talent:negation-succor-3pp',)),
    'protection:advanced-talent:spell-selectivity-dbh': (10, ('protection:aegis-ward-talent:spell-ward-aegis-ward',)),
    'protection:advanced-talent:subtle-aegis': (5, ()),
    'protection:advanced-talent:true-protection': (10, ()),
    'protection:advanced-talent:undying-aegis': (7, ('protection:aegis-ward-talent:deathless-aegis',)),
    'protection:advanced-talent:unplottable-aegis': (15, ('protection:aegis-ward-talent:resistance-aegis',)),
    'protection:advanced-talent:adaptation-aegis': (10, ('protection:aegis-ward-talent:energy-resistance-aegis-ward',)),
    'protection:advanced-talent:antimagic-aura': (10, ('protection:aegis-ward-talent:spell-ward-aegis-ward',)),
    'protection:advanced-talent:automatic-fortification-3pp': (5, ('protection:talent:fortifier-3pp',)),
    'protection:advanced-talent:complex-glyph': (5, ('protection:talent:glyph',)),
    'protection:advanced-talent:improved-negation-3pp': (10, ('protection:succor-talent:negation-succor-3pp',)),
    'protection:advanced-talent:layered-glyph-3pp': (0, ('protection:talent:glyph',)),
    'protection:advanced-talent:mobile-ward-alienist-hb': (5, ()),
    'warp:advanced-talent:true-teleport': (10, ('warp:talent:distant-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:flawless-teleport-utility': (15, ('warp:talent:distant-teleport',
        'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:planeshift': (10, ('warp:talent:distant-teleport',
        'warp:advanced-talent:true-teleport', 'warp:talent:unseeing-teleport')),
    'warp:advanced-talent:portal': (5, ('warp:talent:mass-teleport-mass', 'warp:space-talent:wormhole-space')),
    'warp:advanced-talent:enduring-portal': (15, ('warp:talent:mass-teleport-mass', 'warp:advanced-talent:portal',
        'warp:space-talent:teleport-beacon-space', 'warp:talent:unwilling-teleport', 'warp:space-talent:wormhole-space')),
    'warp:advanced-talent:portal-network-dbh': (15, ('warp:advanced-talent:enduring-portal',
        'warp:talent:mass-teleport-mass', 'warp:advanced-talent:portal', 'warp:space-talent:teleport-beacon-space',
        'warp:talent:unwilling-teleport', 'warp:space-talent:wormhole-space')),
    'life:advanced-talent:feline-good-catgirl-hb': (5, ('life:talent:lingering-resilience',)),
    'life:advanced-talent:hypervitalize': (15, ('life:cure-talent:restore-health-cure', 'life:talent:revitalize')),
    'life:advanced-talent:make-whole': (10, ('life:talent:break-enchantment',
        'life:cure-talent:restore-senses-cure', 'life:cure-talent:restore-spirit-cure')),
    'life:advanced-talent:resurrection': (10, ('life:talent:resuscitate',)),
    'life:advanced-talent:resurrection-greater': (15, ('life:talent:break-enchantment',
        'life:advanced-talent:make-whole', 'life:cure-talent:restore-senses-cure',
        'life:cure-talent:restore-spirit-cure', 'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:resurrection-supreme-warden': (20, ('life:talent:break-enchantment',
        'life:advanced-talent:resurrection-greater', 'life:advanced-talent:make-whole',
        'life:cure-talent:restore-senses-cure', 'life:cure-talent:restore-spirit-cure',
        'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:transfiguration': (10, ('life:cure-talent:restore-health-cure',)),
    'life:advanced-talent:reincarnation-utility-3pp': (10, ('life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:reincarnation-instant-3pp': (15, ('life:advanced-talent:reincarnation-utility-3pp',
        'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
    'life:advanced-talent:reincarnation-manipulated-utility-3pp': (20, ('life:advanced-talent:reincarnation-utility-3pp',
        'life:advanced-talent:resurrection', 'life:talent:resuscitate')),
}


def missing_construction_prerequisites(contributions):
    """Reviewed transitive additions in deterministic dependency order."""
    owned = {row['catalog_key'] for row in contributions}
    seen, missing = set(owned), []
    def visit(key):
        for required in ADVANCED_CONSTRUCTION_REQUIREMENTS.get(key, (0, ()))[1]:
            if required in seen: continue
            seen.add(required); visit(required); missing.append(required)
    for key in sorted(owned): visit(key)
    return tuple(missing)


def advanced_construction_blockers(contributions, caster_level, *, display_names=None):
    keys = {row['catalog_key'] for row in contributions}
    blockers = []
    names = display_names or {}
    if {'protection:advanced-talent:mobile-ward-alienist-hb',
            'protection:advanced-talent:permanent-ward'} <= keys:
        blockers.append('Mobile Ward cannot benefit from Permanent Ward in the same effect.')
    for key in sorted(keys):
        requirement = ADVANCED_CONSTRUCTION_REQUIREMENTS.get(key)
        if requirement is None: continue
        minimum, required = requirement
        if caster_level < minimum:
            blockers.append(f'{names.get(key, key)}: item caster level must be at least {minimum}.')
        blockers.extend(f'{names.get(key, key)}: prerequisite talent must be included in this effect: {names.get(talent, talent)}.'
                        for talent in required if talent not in keys)
    return tuple(blockers)


REVIEWED_METAMAGIC_SP_COSTS = {'maximize spell': 3, 'empower spell': 2}


def feat_integration_defaults(name):
    points = REVIEWED_METAMAGIC_SP_COSTS.get(name.casefold())
    return dict(name=name, metamagic=points is not None, additional_spell_points=points or 0)


def feat_integration_complexity(integrations):
    """Explicit reviewed feat integration; metamagic adds its extra SP cost."""
    seen, total = set(), 0
    for feat in integrations:
        name = feat.get('name', '').strip()
        metamagic, points = feat.get('metamagic', False), feat.get('additional_spell_points', 0)
        if not name or name.casefold() in seen: raise ValueError('Integrated feats must have unique names.')
        if not isinstance(metamagic, bool) or isinstance(points, bool) or not isinstance(points, int) or points < 0:
            raise ValueError('Invalid metamagic integration cost.')
        if not metamagic and points: raise ValueError('Only metamagic feats add spell-point integration costs.')
        minimum = REVIEWED_METAMAGIC_SP_COSTS.get(name.casefold())
        if minimum is not None and (not metamagic or points < minimum):
            raise ValueError(f'{name} requires metamagic integration and at least {minimum} additional spell points.')
        seen.add(name.casefold()); total += 1 + points
    return total


def tradition_costs(base_price, *, cheap=False, expensive=False, other_reduction=Fraction(0)):
    """Reviewed material/resale adjustments, separate from base work pricing.

    Cheap reduces original materials by 10%, stacks additively with reductions,
    and floors materials at 40% of base price. Expensive changes materials only.
    Other reduction is a fraction of original material cost, not market value.
    """
    if not isinstance(cheap, bool) or not isinstance(expensive, bool) or (cheap and expensive):
        raise ValueError('Cheap and Expensive are mutually exclusive boolean options.')
    if isinstance(base_price, bool) or not isinstance(base_price, (int, Fraction)) or base_price <= 0:
        raise ValueError('Base price must be a positive exact value.')
    if isinstance(other_reduction, bool) or not isinstance(other_reduction, (int, Fraction)) or not 0 <= other_reduction <= 1:
        raise ValueError('Other reduction must be an exact fraction from zero to one.')
    base = Fraction(base_price)
    fraction = max(Fraction(4, 5), 1 - Fraction(1, 10) - other_reduction) if cheap else 1 - other_reduction
    materials = base / 2 * fraction * (Fraction(5, 4) if expensive else 1)
    return materials, base * fraction if cheap else base


def talent_construction_spell_points(entry):
    """Reviewed mandatory default, not optional SP inferred from catalog prose.

    Ultimate Teleport Beacon spends one SP to place or use a beacon. These are
    separate activations, not two SP charged together. Basic Teleport comes
    from the Warp base power and is not another talent contribution.
    Ultimate basic teleport is free; True Teleport therefore adds two SP.
    Planeshift adds two, Portal adds one, and sustained Enduring Portal adds
    one beyond its integrated prerequisites. Optional variants remain explicit.
    """
    return {
        'warp:space-talent:teleport-beacon-space': 1,
        'warp:advanced-talent:true-teleport': 2,
        'warp:advanced-talent:planeshift': 2,
        'warp:advanced-talent:portal': 1,
        'warp:advanced-talent:enduring-portal': 1,
        'protection:advanced-talent:antimagic-aura': 1,
        'protection:advanced-talent:automatic-fortification-3pp': 1,
        # Adaptation's two-SP aegis adds one beyond the ordinary one-SP aegis.
        'protection:advanced-talent:adaptation-aegis': 1,
        'protection:aegis-ward-talent:spell-ward-aegis-ward': 1,
        'protection:advanced-talent:spell-eater-aegis-3pp': 2,
        'protection:advanced-talent:spell-selectivity-dbh': 1,
        'protection:advanced-talent:undying-aegis': 1,
        'protection:succor-talent:negation-succor-3pp': 1,
        'protection:succor-talent:reflection-succor': 1,
    }.get(entry.get('key'), 0)


def talent_construction_cost(entry, *, additional_spell_points=0, mythic_crafter=False):
    """Default reviewed contribution; never extract spell-point rules from prose.

    Published Admixture construction is free; its blast types are paid separately.
    Other talents use the general ordinary/advanced rule until mapped explicitly.
    """
    if isinstance(additional_spell_points, bool) or not isinstance(additional_spell_points, int) or additional_spell_points < 0:
        raise ValueError('Additional spell points must be a nonnegative integer.')
    if not isinstance(mythic_crafter, bool): raise ValueError('Mythic Crafter access must be boolean.')
    if entry.get('key') == 'destruction:talent:admixture':
        return 0
    if entry.get('key') in {'alteration:talent:mass-alteration-mass', 'illusion:talent:suppression-glamer'}:
        return 2 + additional_spell_points
    return (2 if 'advanced' in str(entry.get('category', '')).casefold() and not mythic_crafter else 1) + additional_spell_points


ACTIVATION_COMPLEXITY = {"standard": 0, "full-round": -1, "move": 3, "swift": 5}


def simple_tradition_reduction(plan):
    """Reviewed sample traditions; never infer boons from user/catalog prose."""
    tradition = plan.get('crafting_tradition')
    if tradition is None: return 0
    if not isinstance(tradition, dict) or not isinstance(tradition.get('key'), str):
        raise ValueError('Crafting tradition requires a catalog identity.')
    return int(tradition['key'] in {
        'crafting:evil-artifice', 'crafting:sacred-artifice'})


def crafting_item_limitations(plan):
    """Reviewed identities, independent of editable tradition/drawback prose."""
    keys = {row.get('catalog_key') for row in plan.get('drawbacks', []) if row.get('source') == 'published'}
    tradition = (plan.get('crafting_tradition') or {}).get('key')
    if tradition == 'crafting:evil-artifice': keys.add('crafting:sacrificing')
    if tradition == 'crafting:ley-linked': keys.add('crafting:taxing')
    return keys


def spell_selectivity_options(plan):
    """Reviewed DbH sphere-selection mode; source-type variants remain separate."""
    rows = [row for row in plan.get('contributions', [])
            if row.get('catalog_key') == 'protection:advanced-talent:spell-selectivity-dbh']
    if not rows: return None
    row = rows[0]
    mode, spheres = row.get('effect_choice', ''), row.get('effect_spheres', [])
    if mode not in {'', 'only', 'except'} or not isinstance(spheres, list) or any(
            not isinstance(name, str) or not name.strip() for name in spheres):
        raise ValueError('Spell Selectivity requires a valid mode and sphere list.')
    if len({name.casefold() for name in spheres}) != len(spheres) or len(spheres) > 1 + plan['caster_level'] // 5:
        raise ValueError('Spell Selectivity sphere choices exceed the limit or contain duplicates.')
    if mode == 'except' and any(item.get('catalog_key') == 'protection:advanced-talent:antimagic-aura'
                               for item in plan['contributions']):
        raise ValueError('Spell Selectivity except-mode cannot be combined with Antimagic Aura.')
    return dict(mode=mode, spheres=tuple(spheres), maximum=1 + plan['caster_level'] // 5)


def crafting_limitation_details(plan):
    """Concrete item requirements; no location, clock or sacrifice simulation."""
    keys = crafting_item_limitations(plan)
    lines = []
    if 'crafting:charged' in keys:
        complexity, _, _ = quote_marvelous_blueprint(plan)
        points = sum(row.get('additional_spell_points', 0) for row in plan['contributions'])
        points += sum(row.get('additional_spell_points', 0) for row in plan.get('feat_integrations', []))
        if any(row.get('alternative') for row in plan['contributions']):
            lines.append(f'Charged: {complexity} base charges per activation, plus the additional SP of the selected alternative; charge supply is manual.')
        else:
            lines.append(f'Charged: {complexity + points} charges per activation; charge supply is manual.')
    if 'crafting:sacrificing' in keys:
        lines.append(f'Sacrificing: recharge requires a qualifying sacrifice of at least {(plan["caster_level"] + 1) // 2} HD; once per day, manually verified.')
    if 'crafting:taxing' in keys:
        lines.append('Taxing: concentration is required when applicable; use normal concentration or half HD (rounded down, minimum 1), whichever is higher.')
    tradition = (plan.get('crafting_tradition') or {}).get('key')
    skills = {'crafting:fey-touched': ('Knowledge (nature)',),
              'crafting:ridiculously-complicated': ('Acrobatics', 'Disable Device', 'Linguistics', 'Use Magic Device')}.get(tradition, ())
    if skills:
        lines.append(f'Complex: DC {5 + plan["caster_level"]} {", ".join(skills)} checks to activate; crafter must be trained in each skill.')
    if tradition == 'crafting:diviner-s-sight':
        lines.append('Educated: user must be trained in the Divination sphere; Use Magic Device cannot bypass this requirement.')
    return tuple(lines)


def marvelous_manual_recharge_requirements(plan):
    """Only reviewed replacement recovery contracts; no inferred clock state."""
    if 'crafting:sacrificing' in crafting_item_limitations(plan):
        return (f'Qualifying sacrifice of at least {(plan["caster_level"] + 1) // 2} HD, killed by coup de grace with the item within 5 feet; at most once per day. Verify any tradition-specific exceptions with the GM.',)
    return ()


def effect_complexity(*, talent_costs=(), alternative_costs=(), range_steps=0,
                      duration_steps=0, activation="standard", unique_changes=0):
    """Resolve explicit construction contributions, never infer them from prose.

    Talent costs include the talent's own complexity and extra spell points.
    Alternative costs represent mutually exclusive options: the largest is paid
    in full and the others at half cost. Sphere-specific exceptions must supply
    their published costs rather than the general one-point talent default.
    """
    activation_cost = ACTIVATION_COMPLEXITY
    if activation not in activation_cost:
        raise ValueError("Unsupported activation time.")
    for value in (range_steps, duration_steps, unique_changes):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("Construction steps must be integers.")
    costs = tuple(talent_costs)
    alternatives = tuple(alternative_costs)
    for value in (*costs, *alternatives):
        if isinstance(value, bool) or not isinstance(value, (int, Fraction)) or value < 0:
            raise ValueError("Effect contributions must be nonnegative exact values.")
    variable = (sum(alternatives) + max(alternatives)) / Fraction(2) if alternatives else 0
    return max(Fraction(1), Fraction(1 + sum(costs) + variable + range_steps
                                   + 2 * duration_steps + activation_cost[activation]
                                   + unique_changes))


def drawback_complexity(records):
    """Explicit reviewed reductions; published text alone never implies a price."""
    if not isinstance(records, list): raise ValueError('Drawbacks must be a list.')
    seen, total = set(), 0
    for record in records:
        if not isinstance(record, dict) or record.get('source') not in {'published', 'custom'}:
            raise ValueError('Each drawback needs a published/custom source.')
        name, reduction = record.get('name'), record.get('reduction')
        if not isinstance(name, str) or not name.strip() or not isinstance(record.get('description', ''), str):
            raise ValueError('Drawbacks require a name and text description.')
        identity = record.get('catalog_key') if record['source'] == 'published' else name.strip().casefold()
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError('Duplicate or missing drawback identity.')
        seen.add(identity)
        if isinstance(reduction, bool) or not isinstance(reduction, int) or not 0 <= reduction <= 100:
            raise ValueError('Drawback reduction must be an integer from 0 to 100.')
        total += reduction
    return total


def quote_marvelous_blueprint(plan):
    """Price the persisted composer blueprint using the same pure rules."""
    if plan.get('schema_version') != 1:
        raise ValueError('Unsupported Marvelous blueprint version.')
    spell_selectivity_options(plan)
    if plan.get('base_power'):
        from app.marvelous_base_powers import resolve_base_power
        resolve_base_power(plan)
    elif plan.get('effect_range_steps', 0):
        raise ValueError('Effect range adjustments require a structured base power.')
    for option in ('permanent', 'no_space_limitation', 'full_blast_damage'):
        if not isinstance(plan.get(option, False), bool):
            raise ValueError('Construction flags must be boolean.')
    if plan.get('permanent') and not plan.get('base_power'):
        raise ValueError('Permanency requires a structured base power.')
    if any(not isinstance(x.get('alternative', False), bool) for x in plan['contributions']):
        raise ValueError('Alternative-effect flags must be boolean.')
    groups = {}
    for contribution in plan['contributions']:
        if (plan.get('base_power') == 'mana:manipulate'
                and contribution.get('catalog_key') == 'mana:manipulation-talent:transfer-manipulation'):
            raise ValueError('Mana Transfer cannot be applied to a crafted manipulate effect.')
        extra_sp = contribution.get('additional_spell_points', 0)
        if isinstance(extra_sp, bool) or not isinstance(extra_sp, int) or extra_sp < 0 or extra_sp > contribution['complexity']:
            raise ValueError('Additional spell points must be included in the contribution complexity.')
        group = contribution.get('alternative_group', 1)
        if isinstance(group, bool) or not isinstance(group, int) or group < 1:
            raise ValueError('Alternative groups must be positive integers.')
        if contribution.get('alternative', False):
            groups.setdefault(group, []).append(contribution['complexity'])
    # Resolve each independent choice set separately; legacy alternatives use group 1.
    grouped_costs = [effect_complexity(alternative_costs=costs) - 1 for costs in groups.values()]
    feat_cost = feat_integration_complexity(plan.get('feat_integrations', []))
    simple = simple_tradition_reduction(plan)
    limitations = crafting_item_limitations(plan)
    for power in [plan, *plan.get('extra_effects', [])]:
        if 'crafting:charged' in limitations and power['uses'] != 5:
            raise ValueError('Charged requires an unlimited-use Marvelous Item.')
        if 'crafting:sacrificing' in limitations and power['uses'] not in (1, 2, 3, 4):
            raise ValueError('Sacrificing requires limited daily uses, not unlimited or fifty-total uses.')
        if 'crafting:taxing' in limitations and power.get('permanent'):
            raise ValueError('Taxing cannot restrict an effect usable for an unlimited duration.')
    complexity = effect_complexity(talent_costs=[x['complexity'] for x in plan['contributions'] if not x.get('alternative', False)] + grouped_costs,
        range_steps=plan['range_steps'], duration_steps=plan['duration_steps'],
        activation=plan['activation'], unique_changes=plan['unique_changes'] - drawback_complexity(plan.get('drawbacks', [])) - simple + (2 if plan.get('permanent') else 0) + int(plan.get('full_blast_damage', False)) + 2 * plan.get('effect_range_steps', 0) + feat_cost)
    price = marvelous_item_price(plan['caster_level'], complexity,
                                daily_uses=1 if plan['uses'] == 50 else plan['uses'], limited_uses=plan['uses'] == 50)
    if plan.get('no_space_limitation'):
        price = replace(price, market_price_gp=price.market_price_gp * 2)
    if plan.get('extra_effects'):
        if any(row.get('source') == 'published' and row.get('catalog_key', '').startswith('crafting:')
               for extra in plan['extra_effects'] for row in extra.get('drawbacks', [])):
            raise ValueError('Crafting-specific drawbacks belong to the whole item, not individual powers.')
        if any(extra.get('extra_effects') for extra in plan['extra_effects']):
            raise ValueError('Nested effect combinations are not supported.')
        combined = quote_marvelous_effects(marvelous_pricing_powers(plan), mode=plan.get('combination_mode', 'multiple'))
        price = replace(price, market_price_gp=combined['market_price_gp'])
    quote = marvelous_crafting_quote(price, plan['caster_level'])
    tradition = plan.get('crafting_tradition')
    cheap = False
    if tradition is not None:
        cheap = tradition['key'] in {'crafting:city-construction', 'crafting:diviner-s-sight'}
        if tradition['key'] in {'crafting:city-construction', 'crafting:evil-artifice'} and any(
                row.get('source') == 'published' and row.get('catalog_key') == 'crafting:fragile'
                for row in plan.get('drawbacks', [])):
            raise ValueError('Fragile is incompatible with the Resilient boon of this crafting tradition.')
    expensive = any(record['source'] == 'published' and record.get('catalog_key') == 'crafting:expensive'
                    for record in plan.get('drawbacks', []))
    if cheap or expensive:
        materials, selling = tradition_costs(price.market_price_gp, cheap=cheap, expensive=expensive)
        price = replace(price, market_price_gp=selling)
        quote = replace(quote, cost_gp=float(materials))
    return complexity, price, quote


def marvelous_remaining_uses(metadata, effect_index=0):
    """None means unlimited; limited-total charges never recover on rest."""
    plan = marvelous_effect_plan(metadata['marvelous_blueprint'], effect_index)
    _, price, _ = quote_marvelous_blueprint(plan)
    used = metadata.get('marvelous_uses_used', 0) if effect_index == 0 else metadata.get('marvelous_extra_uses_used', {}).get(str(effect_index), 0)
    if isinstance(used, bool) or not isinstance(used, int) or used < 0:
        raise ValueError('Invalid saved Marvelous Item usage.')
    maximum = price.daily_uses if price.daily_uses is not None else price.total_uses
    return None if maximum is None else max(0, maximum - used)


def marvelous_effect_plan(plan, effect_index=0):
    if isinstance(effect_index, bool) or not isinstance(effect_index, int) or effect_index < 0:
        raise ValueError('Invalid effect index.')
    if effect_index == 0:
        return {key: value for key, value in plan.items() if key not in {'extra_effects', 'combination_mode'}}
    extras = plan.get('extra_effects', [])
    if effect_index > len(extras): raise ValueError('Unknown item effect.')
    result = dict(extras[effect_index - 1])
    if simple_tradition_reduction(plan):
        result['crafting_tradition'] = plan['crafting_tradition']
    return result


def marvelous_pricing_powers(plan):
    """Apply per-effect Simple before combining, whole-item Cheap afterwards."""
    powers = [marvelous_effect_plan(plan, index) for index in range(1 + len(plan.get('extra_effects', [])))]
    if not simple_tradition_reduction(plan):
        powers = [{key: value for key, value in power.items() if key != 'crafting_tradition'} for power in powers]
    return powers


def quote_marvelous_effects(plans, *, mode='multiple'):
    """Quote independent or mixed powers without flattening their mechanics.

    Each entry is an ordinary single-effect blueprint. One most expensive
    effect is paid in full; the others cost 3/2 (multiple) or 2 (mixed).
    Creation eligibility and individual activation resources remain separate.
    """
    if mode not in {'multiple', 'mixed'}:
        raise ValueError('Unsupported effect combination mode.')
    plans = tuple(plans)
    if not plans:
        raise ValueError('At least one effect is required.')
    levels = {plan['caster_level'] for plan in plans}
    if len(levels) != 1:
        raise ValueError('All item effects must have the same caster level.')
    quoted = tuple(quote_marvelous_blueprint(plan) for plan in plans)
    prices = tuple(result[1].market_price_gp for result in quoted)
    multiplier = Fraction(3, 2) if mode == 'multiple' else Fraction(2)
    highest = max(prices)
    total = highest + (sum(prices) - highest) * multiplier
    cl = plans[0]['caster_level']
    # This aggregate is only a construction quote, not a shared usage pool.
    combined = MarvelousItemPrice(total, 10 + cl // 2, None, None)
    return dict(effects=quoted, market_price_gp=total,
                crafting=marvelous_crafting_quote(combined, cl), mode=mode)


def marvelous_complexity_formula(plan):
    """Explain every primary-effect term; use the quote for the final result."""
    complexity, _, _ = quote_marvelous_blueprint(plan)
    ordinary = [row for row in plan['contributions'] if not row.get('alternative')]
    groups = {}
    for row in plan['contributions']:
        if row.get('alternative'):
            groups.setdefault(row.get('alternative_group', 1), []).append(row['complexity'])
    terms = [('base', 1), ('talents', sum(row['complexity'] - row.get('additional_spell_points', 0) for row in ordinary)),
             ('extra SP', sum(row.get('additional_spell_points', 0) for row in ordinary)),
             ('choices', sum(effect_complexity(alternative_costs=costs) - 1 for costs in groups.values())),
             ('range', plan['range_steps']), ('duration', 2 * plan['duration_steps']),
             ('activation', ACTIVATION_COMPLEXITY[plan['activation']]), ('unique changes', plan['unique_changes']),
             ('permanency', 2 if plan.get('permanent') else 0), ('full blast', int(plan.get('full_blast_damage', False))),
             ('distance/area', 2 * plan.get('effect_range_steps', 0)),
             ('feats', feat_integration_complexity(plan.get('feat_integrations', []))),
             ('drawbacks', -drawback_complexity(plan.get('drawbacks', []))),
             ('Simple boon', -simple_tradition_reduction(plan))]
    rendered = '1 base' + ''.join(f" {'+' if value > 0 else '−'} {abs(value)} {label}" for label, value in terms[1:] if value)
    return f'max(1, {rendered}) = {complexity}'


def marvelous_materials_formula(plan):
    """Explain the construction materials separately from selling price."""
    _, price, quote = quote_marvelous_blueprint(plan)
    expensive = any(row.get('source') == 'published' and row.get('catalog_key') == 'crafting:expensive'
                    for row in plan.get('drawbacks', []))
    factor = ' × 1.25 (Expensive)' if expensive else ''
    return f'{price.market_price_gp} gp ÷ 2{factor} = {float(quote.cost_gp):g} gp'


def marvelous_price_formula(plan):
    """Readable live formula from the authoritative quote, not a second calculator."""
    complexity, price, _ = quote_marvelous_blueprint(plan)
    tradition = plan.get('crafting_tradition') or {}
    if tradition.get('key') in {'crafting:city-construction', 'crafting:diviner-s-sight'}:
        base = {key: value for key, value in plan.items() if key != 'crafting_tradition'}
        return marvelous_price_formula(base) + f' → × 0.9 (Cheap) = {price.market_price_gp} gp'
    if plan.get('extra_effects'):
        amounts = [quote_marvelous_blueprint(power)[1].market_price_gp for power in marvelous_pricing_powers(plan)]
        highest = max(amounts)
        factor = '2' if plan.get('combination_mode') == 'mixed' else '1.5'
        return f'{highest} + ({sum(amounts)} − {highest}) × {factor} = {price.market_price_gp} gp'
    usage = '2.5 (50 total uses)' if plan['uses'] == 50 else f"{plan['uses']}" + (' (unlimited)' if plan['uses'] == 5 else ' (daily uses)')
    slot = ' × 2 (slotless)' if plan.get('no_space_limitation') else ''
    return f"400 gp × {plan['caster_level']} (CL) × {complexity} (complexity) × {usage}{slot} = {price.market_price_gp} gp"


def marvelous_crafting_quote(price: MarvelousItemPrice, caster_level: int, *,
                              missing_talents=0, adventuring=False,
                              distracting=False, requirements=None) -> CraftingQuote:
    """Spheres construction estimate; prerequisite eligibility is checked separately.

    Missing ordinary talents can raise the DC. Base spheres, advanced talents,
    creation feats and protected class requirements cannot use this bypass.
    Adventuring already includes distractions; do not apply both penalties.
    """
    for value in (caster_level, missing_talents):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("Crafting values must be nonnegative integers.")
    if caster_level < 1 or price.market_price_gp <= 0:
        raise ValueError("Caster level and price must be positive.")
    if requirements is not None:
        if missing_talents:
            raise ValueError("Use the validated requirements, not a second missing-talent count.")
        if not requirements.eligible:
            raise ValueError("Construction requirements are not met: " + "; ".join(requirements.blockers))
    dc_increase = requirements.dc_increase if requirements is not None else 5 * missing_talents
    # Work is proportional to price; whole calendar days are a presentation
    # estimate, not extra required crafting time.
    days = float(max(Fraction(1), price.market_price_gp / 1000))
    days *= 4 if adventuring else 2 if distracting else 1
    return CraftingQuote(price.market_price_gp / 2, 10 + caster_level + dc_increase,
                         days, "One item per day; materials paid at the start. Missing base spheres and advanced talents cannot be bypassed.")

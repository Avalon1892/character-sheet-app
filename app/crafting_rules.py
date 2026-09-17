"""Pure PF1 crafting estimates. No widgets, database writes, or prose parsing."""
from dataclasses import dataclass
from math import ceil


def magical_base_price(market_price, construction_cost):
    """P = B + extras; C = B/2 + extras. Unknown/special pricing stays unknown."""
    if market_price is None or construction_cost is None:
        return None
    if market_price <= 0 or not market_price / 2 <= construction_cost < market_price:
        return None
    return 2 * (market_price - construction_cost)


def crafting_calendar_days(quote, *, adventuring=False, quantity=1, magical=True):
    if quote.days is None: return None
    if quantity < 1: raise ValueError('Quantity must be positive.')
    days = quote.days * (4 if adventuring and magical else 1)
    return max(1, ceil(days)) * quantity if magical else days * quantity


def recommended_craft_specialties(entry):
    name = entry.get('name', '').casefold()
    family = entry.get('family', '')
    category = entry.get('subcategory', '').casefold()
    if 'alchemical' in category or name in {'acid', 'antitoxin', 'sunrod', 'thunderstone', 'tindertwig', 'smokestick', 'tanglefoot bag', "alchemist's fire"}:
        return ('alchemy',)
    if family == 'Armor & Shields': return ('armor', 'armorsmithing')
    if family == 'Weapons & Ammunition':
        return ('bows', 'bowmaking') if any(s in name for s in ('bow', 'arrow', 'bolt')) else ('weapons', 'weaponsmithing')
    if category == 'clothing': return ('clothing', 'cloth', 'tailoring')
    return ()


def composite_bow_price(entry, strength_rating):
    surcharge = {'composite longbow':100, 'composite shortbow':75}.get(entry.get('name','').casefold())
    return entry.get('price_gp',0) + surcharge * max(0,strength_rating) if surcharge else None


@dataclass(frozen=True)
class CraftingQuote:
    cost_gp: float
    dc: int
    days: float | None
    note: str = ''


def mundane_dc(entry, *, strength_rating=0):
    """Published standard categories; None means a GM-selected complexity DC."""
    name = entry['name'].casefold()
    alchemy = {'acid': 15, "alchemist's fire": 20, 'smokestick': 20, 'tindertwig': 20,
               'antitoxin': 25, 'sunrod': 25, 'tanglefoot bag': 25, 'thunderstone': 25}
    if name in alchemy:
        return alchemy[name]
    if entry.get('family') == 'Armor & Shields':
        bonus = entry.get('automation', {}).get('ac_bonus', 0)
        return 10 + bonus if bonus else None
    if entry.get('family') == 'Weapons & Ammunition':
        if 'composite' in name:
            return 15 + 2 * max(0, strength_rating)
        if 'crossbow' in name or 'bolt' in name:
            return 15
        if name in {'longbow', 'shortbow'} or name.startswith('arrow'):
            return 12
        return {'Simple': 12, 'Martial': 15, 'Exotic': 18}.get(entry.get('subcategory'))
    return None


def mundane_quote(price_gp: float, dc: int, check: int, *, masterwork_gp=0, faster=False) -> CraftingQuote:
    if price_gp < 0 or dc <= 0 or masterwork_gp < 0:
        raise ValueError('Price must be nonnegative and DC positive.')
    cost = (price_gp + masterwork_gp) / 3
    dc += 10 if faster else 0
    masterwork_dc = 30 if faster else 20
    if check < dc or (masterwork_gp and check < masterwork_dc):
        return CraftingQuote(cost, dc, None, 'No progress at this check result. Failure by 5 or more ruins half the raw materials for that component.')
    days = price_gp * 10 / (check * dc) * 7
    if masterwork_gp:
        days += masterwork_gp * 10 / (check * masterwork_dc) * 7
    return CraftingQuote(cost, dc, days, f'Estimate assumes successful checks at the chosen result; masterwork is a separate DC {masterwork_dc} component.' if masterwork_gp else 'Estimate assumes successful checks at the chosen result.')


def magic_quote(base_price: float, cost: float, caster_level: int, *, missing=0, accelerated=False, consumable=False) -> CraftingQuote:
    if min(base_price, cost, caster_level, missing) < 0:
        raise ValueError('Crafting values cannot be negative.')
    hours = 2 if consumable and base_price <= 250 else max(1, ceil(base_price / 1000)) * (4 if accelerated else 8)
    return CraftingQuote(cost, 5 + caster_level + 5 * missing + (5 if accelerated else 0), hours / 8,
                         'At most one magic item per day. Time uses magical base price, excluding independent item and costly component costs.')

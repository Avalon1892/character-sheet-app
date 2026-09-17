"""Cached crafting metadata referring to shared item identities."""
import json
from functools import lru_cache
from pathlib import Path
from app.catalog_versions import active_catalog_root


@lru_cache(maxsize=4)
def crafting_document(root=None):
    path = Path(root or active_catalog_root()) / 'crafting_catalog.json'
    if not path.exists():
        path = Path(__file__).resolve().parents[1] / 'data/pf1e/crafting_catalog.json'
    document = json.loads(path.read_text(encoding='utf-8'))
    overrides = path.with_name('crafting_automation.json')
    if overrides.exists():
        patches = json.loads(overrides.read_text(encoding='utf-8')).get('entries',{})
        document['recipes'] = [{**recipe, **patches.get(recipe['key'],{})} for recipe in document['recipes']]
    return document


@lru_cache(maxsize=1)
def creation_feats():
    return frozenset(f for r in crafting_document()['recipes'] for f in r['feats']) - {'Master Craftsman'}


@lru_cache(maxsize=4)
def spell_recipes(feat):
    """Spell-derived items retain spell keys; do not create a second spell catalog.

    A class-list level is explicit. Caster level and costly components still
    require confirmation in the planner, rather than guessing from spell prose.
    """
    factors = {'Scribe Scroll': 25, 'Craft Wand': 750, 'Brew Potion': 50}
    if feat not in factors: return ()
    root = Path(active_catalog_root())
    spells = json.loads((root / 'spells.json').read_text(encoding='utf-8'))['entries']
    result = []
    for spell in spells:
        if spell.get('third_party') or spell.get('source_group') != 'Pathfinder': continue
        for level in sorted(set(spell.get('class_levels', {}).values())):
            if not isinstance(level, int) or not 0 <= level <= 9: continue
            if feat == 'Craft Wand' and level > 4: continue
            if feat == 'Brew Potion':
                if level > 3 or spell.get('range', '').casefold() == 'personal': continue
                if not spell.get('target'): continue
                if spell.get('casting_time', '').casefold() not in {'1 standard action', '1 swift action', '1 immediate action', '1 full-round action', '1 round'}: continue
            classes = ', '.join(k for k, v in spell.get('class_levels', {}).items() if v == level)
            result.append(dict(key=f'craft:{feat}:{spell["key"]}:{level}', item_key=spell['key'],
                name=f'{spell["name"]} — level {level}', kind='magic', feats=[feat], spells=[spell['name']],
                requirements=f'{feat}; {spell["name"]} (level {level}: {classes})',
                review='Confirm the creator’s class-list level, legal caster level, spell access and costly components.' +
                    (' Confirm potion target eligibility; target must be a creature or object.' if feat == 'Brew Potion' else ''),
                caster_level=1, creation_cost_gp=max(.5, level)*factors[feat]/2,
                spell_level=level, spell_classes=[k for k,v in spell.get('class_levels',{}).items() if v==level],
                price_gp=max(.5, level)*factors[feat], price_per_cl=max(.5, level)*factors[feat],
                description=spell.get('description', ''), source_url=spell.get('source_url', ''),
                category=feat))
    return tuple(result)


def mundane_entries(catalog):
    return tuple(e for e in catalog.all_item_entries if e.get('source_group') == 'Pathfinder'
                 and e.get('family') in {'Mundane Equipment', 'Weapons & Ammunition', 'Armor & Shields', 'Alchemical Items'}
                 and e.get('subcategory') not in {'Animal', 'Class Kits', 'Herb', 'Wondrous', 'Potion', 'Dungeon Guides', 'Black Market', 'Poison'})

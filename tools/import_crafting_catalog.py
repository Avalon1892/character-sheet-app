"""Import official construction metadata at build time, never while browsing.

Existing item identities are reused. Additional published magic items supplement
the shared item catalog; recipes refer to those same keys. Unknown requirements
remain explicit review conditions rather than being guessed as satisfied.
"""
import json, re, sys, hashlib, time
from pathlib import Path
from urllib.parse import urljoin, urlsplit, quote, unquote
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor, as_completed
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.import_reference_catalog import BeautifulSoup
from tools.catalog_import_common import slug

CACHE = ROOT / '.crafting-source'
OUTPUT = ROOT / 'data/pf1e/crafting_catalog.json'
BASE = 'https://aonprd.com/'


def fetch(url):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest() + '.html')
    if path.exists():
        raw = path.read_bytes()
    else:
        for attempt in range(3):
            try:
                request = Request(quote(url, safe=':/?=&%'), headers={'User-Agent': 'Character Sheet App crafting reference importer'})
                raw = urlopen(request, timeout=45).read()
                path.write_bytes(raw)
                time.sleep(.15)
                break
            except Exception:
                if attempt == 2: raise
                time.sleep(1 + attempt)
    return BeautifulSoup(raw, 'html.parser')


def money(text):
    match = re.search(r'([\d,]+(?:\.\d+)?)\s*gp\b', text, re.I)
    return float(match[1].replace(',', '')) if match else None


def field(node, label):
    tag = next((b for b in node.find_all('b') if b.get_text(' ', strip=True).strip(' :').casefold() == label.casefold()), None)
    if tag is None: return ''
    parts = []
    for sibling in tag.next_siblings:
        if getattr(sibling, 'name', '') in ('b', 'h1', 'h2', 'h3', 'br'): break
        parts.append(sibling.get_text(' ', strip=True) if hasattr(sibling, 'get_text') else str(sibling))
    return re.sub(r'\s+', ' ', ' '.join(parts)).strip(' ;\n')


def discover():
    queue = [BASE + 'MagicItems.aspx']
    visited = set(); records = {}
    while queue:
        url = queue.pop(0)
        if url in visited: continue
        visited.add(url)
        soup = fetch(url)
        for anchor in soup.select('a[href]'):
            href = urljoin(BASE, anchor['href']).replace(' ', '%20')
            path = urlsplit(href).path.rsplit('/', 1)[-1]
            if urlsplit(href).netloc not in ('aonprd.com', 'www.aonprd.com'): continue
            if not path.startswith('Magic') or not path.endswith('.aspx'): continue
            if any(word in path for word in ('Artifact', 'Cursed', 'Intelligent')): continue
            if 'Display' in path:
                row = anchor.find_parent('tr')
                if row is None: continue
                cells = row.find_all('td', recursive=False)
                price = money(cells[-1].get_text(' ', strip=True)) if cells else None
                records[href] = dict(url=href, name=anchor.get_text(' ', strip=True), price_gp=price)
            elif href not in visited and href not in queue:
                queue.append(href)
        print('Index', len(visited), 'items', len(records), flush=True)
        if len(visited) > 100: raise ValueError('Unexpected index expansion')
    return list(records.values())


def parse_record(record, existing, feat_names):
    soup = fetch(record['url'])
    node = soup.find(id='MainContent_DataListTypes_LabelName_0')
    if node is None: return None
    requirements = field(node, 'Requirements')
    if not requirements: return None
    feats = [name for name in feat_names if re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', requirements, re.I)]
    if not feats: return None
    price = record['price_gp']
    prices = [float(x.replace(',', '')) for x in re.findall(r'([\d,]+(?:\.\d+)?)\s*gp', field(node, 'Price'))]
    costs = [float(x.replace(',', '')) for x in re.findall(r'([\d,]+(?:\.\d+)?)\s*gp', field(node, 'Cost'))]
    if price is None and len(prices) == 1: price = prices[0]
    cost = costs[0] if len(costs) == 1 else None
    if price in prices and len(costs) == len(prices): cost = costs[prices.index(price)]
    cl = re.search(r'\d+', field(node, 'CL'))
    construction = next((h for h in node.find_all(['h3', 'h2']) if h.get_text(strip=True) == 'Construction'), None)
    spells = []
    if construction:
        for sibling in construction.next_siblings:
            if getattr(sibling, 'name', '') == 'i': spells.append(sibling.get_text(' ', strip=True))
            elif getattr(sibling, 'name', '') == 'a' and 'SpellDisplay' in sibling.get('href', ''): spells.append(sibling.get_text(' ', strip=True))
    remainder = requirements
    for name in sorted([*feats, *spells], key=len, reverse=True):
        remainder = re.sub(re.escape(name), '', remainder, flags=re.I)
    remainder = re.sub(r'^[\s,;]+|[\s,;]+$', '', remainder)
    remainder = re.sub(r'[\s,;]+', ' ', remainder).strip()
    # Alternatives, quantities, and creator restrictions must not be silently
    # reduced to a flat list of spells. Preserve them for explicit confirmation.
    review = remainder if remainder else ''
    name = record['name']
    matched = existing.get(slug(name))
    key = matched['key'] if matched else 'aon:item:' + slug(name)
    category = next((label for token, label in (('Wondrous', 'Wondrous Items'), ('Rings', 'Rings'), ('Rods', 'Rods'), ('Staves', 'Staves'), ('Weapons', 'Weapons'), ('Armor', 'Armor & Shields')) if token in record['url']), 'Magic Items')
    description_header = node.find(lambda tag: tag.name in {'h2', 'h3'} and tag.get_text(strip=True) == 'Description')
    description_parts = []
    if description_header:
        for sibling in description_header.next_siblings:
            if sibling is construction: break
            description_parts.append(sibling.get_text(' ', strip=True) if hasattr(sibling, 'get_text') else str(sibling).strip())
    description = ' '.join(part for part in description_parts if part).strip()
    entry = dict(key=key, name=name, source_group='Pathfinder', family='Magic Items', category='Magic Items', subcategory=category,
                 description=description or node.get_text(' ', strip=True), source=field(node, 'Source'), source_url=record['url'],
                 price_gp=price or 0, weight_lb=0, slot=field(node, 'Slot'), item_type='equipment', weapon={}, automation={})
    recipe = dict(key='craft:' + key, item_key=key, name=name, kind='magic', feats=feats, spells=list(dict.fromkeys(spells)),
                  requirements=requirements, review=review, caster_level=int(cl[0]) if cl else None,
                  creation_cost_gp=cost, price_gp=price, cost_text=field(node, 'Cost'), category=category, source_url=record['url'],
                  construction_skill=field(node, 'Skill'))
    return entry, recipe


def main():
    original = json.loads((ROOT / 'data/pf1e/items.json').read_text(encoding='utf-8'))['entries']
    existing = {slug(e['name']): e for e in original if e.get('source_group') == 'Pathfinder'}
    feats = json.loads((ROOT / 'data/pf1e/item_creation_rules.json').read_text(encoding='utf-8'))['feats']
    feat_names = tuple(e['name'] for e in feats if e.get('source_group') == 'Pathfinder')
    records = discover()
    entries = {}; recipes = {}; failures = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(parse_record, r, existing, feat_names): r for r in records}
        for count, future in enumerate(as_completed(futures), 1):
            try:
                result = future.result()
                if result:
                    entry, recipe = result
                    entries[entry['key']] = entry
                    recipes[recipe['key']] = recipe
            except Exception as error:
                failures.append(dict(url=futures[future]['url'], error=str(error)))
            if count % 100 == 0: print('Imported', count, '/', len(records), 'recipes', len(recipes), flush=True)
    document = dict(schema_version=1, sources=[BASE + 'MagicItems.aspx'], discovered=len(records), failures=failures,
                    entries=sorted(entries.values(), key=lambda e:e['name'].casefold()), recipes=sorted(recipes.values(), key=lambda e:e['name'].casefold()))
    OUTPUT.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Saved', len(entries), 'items;', len(recipes), 'recipes; failures', len(failures), flush=True)


if __name__ == '__main__': main()

"""Refresh full crafting-feat text by stable catalog key; import supporting rules."""
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote, urljoin
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.import_reference_catalog import BeautifulSoup, clean


def fetch(url):
    raw = urlopen(Request(url, headers={'User-Agent': 'Character Sheet reference importer'}), timeout=60).read()
    return BeautifulSoup(raw.decode('utf-8'), 'html.parser')


def full_feat(entry):
    url = entry['source_url'].replace(' ', '%20')
    node = fetch(url).find(id='MainContent_DataListTypes_LabelName_0')
    if node is None or 'Benefit' not in node.get_text():
        raise ValueError('Incomplete feat: ' + entry['name'])
    for heading in node.find_all('h1'):
        heading.decompose()
    result = dict(entry)
    result.update(description=node.get_text(' ', strip=True), rules_html=clean(node, url), full_rules=True)
    return result


def rule_page(rule_id, title):
    url = 'https://aonprd.com/Rules.aspx?ID=' + str(rule_id)
    node = fetch(url).find(id='MainContent_DetailedOutput')
    if node is None or len(node.get_text()) < 300:
        raise ValueError('Missing rules: ' + title)
    return dict(key='pf-' + str(rule_id), name=title, sphere='Pathfinder', kind='Rules',
                html=clean(node, url), description=node.get_text(' ', strip=True), source_url=url)


def main():
    original = json.loads((ROOT / 'data/pf1e/feats.json').read_text(encoding='utf-8'))['entries']
    index = fetch('https://aonprd.com/Feats.aspx?Category=Item%20Creation')
    names = {row.find('td').get_text(' ', strip=True) for row in index.select('tr')
             if row.find('td') and row.find('td').select('a[href*=FeatDisplay]')}
    names.update(('Craft Technological Arms and Armor', 'Craft Technological Item',
                  'Craft Cybernetics', 'Craft Pharmaceutical', 'Master Craftsman'))
    selected = [e for e in original if e.get('source_group') == 'Pathfinder' and e['name'] in names]
    missing = names - {e['name'] for e in selected}
    for name in missing:
        selected.append(dict(key='aon:' + re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-'),
                             name=name, categories=['Item Creation'], source_group='Pathfinder',
                             source_name='Archives of Nethys', prerequisites='', source_tags=[],
                             source_url='https://aonprd.com/FeatDisplay.aspx?ItemName=' + quote(name),
                             sphere='', repeatable=False))
    with ThreadPoolExecutor(max_workers=4) as pool:
        feats = list(pool.map(full_feat, selected))
    rules = [rule_page(401, 'Magic Item Creation — Core Rules'),
             rule_page(1426, 'Magic Item Creation — Campaign Guidance'),
             rule_page(1983, 'Dynamic Magic Item Creation — Optional Rules'),
             rule_page(974, 'Building and Modifying Constructs')]
    flesh_url = 'https://aonprd.com/Rules.aspx?Name=Fleshwarping&Category=Horror%20Rules'
    flesh = fetch(flesh_url).find(id='MainContent_DetailedOutput')
    if flesh is None:
        raise ValueError('Missing Fleshwarping rules')
    rules.append(dict(key='pf-fleshwarping', name='Fleshwarping', sphere='Pathfinder', kind='Rules',
                      html=clean(flesh, flesh_url), description=flesh.get_text(' ', strip=True), source_url=flesh_url))
    url = 'https://spheresofpower.wikidot.com/magical-items'
    root = fetch(url).select_one('#page-content')
    headings = root.find_all(['h1', 'h2', 'h3', 'h4'])
    crafting_feats = False
    for h in headings:
        if not h.get('id', '').startswith('toc'):
            continue
        number = int(h['id'][3:])
        # These traditions were imported separately; do not duplicate them.
        if 44 <= number <= 108:
            continue
        name = h.get_text(' ', strip=True)
        if h.name == 'h1':
            crafting_feats = name == 'New Crafting Feats'
        parts = []
        for node in h.next_siblings:
            if getattr(node, 'name', '') in ('h1', 'h2', 'h3', 'h4'):
                break
            if getattr(node, 'name', '') in ('p', 'ul', 'ol', 'table'):
                parts.append(str(node))
        body = clean(''.join(parts), url)
        text = BeautifulSoup(body, 'html.parser').get_text(' ', strip=True)
        if not text:
            continue
        if crafting_feats and h.name == 'h3':
            base = name.split('(')[0].split('[')[0].strip().casefold()
            entry = next((dict(e) for e in original if e.get('source_group') == 'Spheres'
                          and e['name'].split('(')[0].split('[')[0].strip().casefold() == base), None)
            if entry is None:
                entry = dict(key='spheres:' + re.sub(r'[^a-z0-9]+', '-', base).strip('-'),
                             name=name, categories=['Item Creation'], source_group='Spheres',
                             source_name='Spheres of Power Wiki', prerequisites='', source_tags=[],
                             repeatable=False, sphere='')
            entry.update(description=text, rules_html=body, full_rules=True, source_url=url + '#' + h['id'])
            feats.append(entry)
        else:
            rules.append(dict(key='spheres-' + h['id'], name=name, sphere='Spheres', kind='Rules',
                              html=body, description=text, source_url=url + '#' + h['id']))
    document = dict(schema_version=1, feats=feats, entries=rules,
                    attribution='Paizo Inc. via Archives of Nethys; Drop Dead Studios and credited '
                    'contributors via Spheres of Power Wiki. See reference_rules_LICENSE.txt.')
    (ROOT / 'data/pf1e/item_creation_rules.json').write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(len(feats), 'full feat records;', len(rules), 'supporting rule references;', len(missing), 'new Pathfinder feats')


if __name__ == '__main__':
    main()

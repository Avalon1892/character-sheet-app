"""Offline-only import of Spheres crafting and Tinker tradition references."""
from __future__ import annotations
import json
import re
import sys
from urllib.request import Request, urlopen
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.import_reference_catalog import BeautifulSoup, clean


def import_page(kind, page):
    url = 'https://spheresofpower.wikidot.com/' + page
    raw = urlopen(Request(url, headers={'User-Agent': 'Character Sheet reference importer'}), timeout=60).read()
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    root = soup.select_one('#page-content')
    headings = root.find_all(re.compile('^h[1-4]$'))
    entries, rules = [], []
    active = kind == 'Tinker'
    category = 'Rules'
    for h in headings:
        name = h.get_text(' ', strip=True)
        if kind == 'Crafting':
            if name.startswith('Crafting Traditions'):
                active = True
            if name == 'Intelligent Items':
                break
        if not active:
            continue
        if name in ('Drawbacks', 'Tinker Drawbacks'):
            category = 'Drawback'
        elif name in ('Boons', 'Tinker Boons'):
            category = 'Boon'
        elif name == 'Qualities':
            category = 'Quality'
        elif name in ('Sample Crafting Traditions', 'Sample Tinker Traditions'):
            category = 'Tradition'
        parts = []
        for sibling in h.next_siblings:
            if getattr(sibling, 'name', '') in ('h1', 'h2', 'h3', 'h4'):
                break
            if getattr(sibling, 'name', None) in ('p', 'ul', 'ol', 'table', 'div'):
                # Wiki navigation and advertisements are not rules.
                if getattr(sibling, 'get', lambda *_: None)('class') and any(
                    word in str(sibling.get('class')) for word in ('footer', 'ad-')):
                    continue
                parts.append(str(sibling))
        body = clean(''.join(parts), url)
        text = BeautifulSoup(body, 'html.parser').get_text(' ', strip=True)
        if not text:
            continue
        is_sample = category == 'Tradition' and h.name == ('h3' if kind == 'Crafting' else 'h4')
        key = kind.lower() + ':' + re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        entry = dict(key=key, name=name, kind=kind, category='Tradition' if is_sample else category,
                     html=body, description=text, source_url=url + '#' + h.get('id', ''),
                     fixed_grants=[], choice_groups=[])
        (entries if is_sample else rules).append(entry)
    return entries, rules


def main():
    document = {'schema_version': 1, 'entries': [], 'rules': [],
                'attribution': 'Spheres of Power wiki; Drop Dead Studios and credited third-party authors. '
                'See reference_rules_LICENSE.txt for Open Game License notices.'}
    for kind, page in (('Crafting', 'magical-items'), ('Tinker', 'tinker-traditions')):
        entries, rules = import_page(kind, page)
        if len(entries) < 10:
            raise ValueError(f'Incomplete {kind} import: {len(entries)} traditions')
        document['entries'].extend(entries)
        document['rules'].extend(rules)
        print(kind, len(entries), 'traditions,', len(rules), 'rule sections')
    (ROOT / 'data/pf1e/optional_traditions.json').write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

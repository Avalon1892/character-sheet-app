"""Offline import of the Ultimate Engineering gizmo reference corpus."""
import json
import sys
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.import_reference_catalog import BeautifulSoup, clean

PAGES = (
    ('using-tinker-sphere', 'Using Tinker Sphere'),
    ('tinker', 'Tinker Sphere & Talents'),
    ('skill-rules', 'Skill Rules'),
    ('mastering-gizmos', 'Mastering Gizmos'),
    ('ai-and-mechanoids', 'AI & Mechanoids'),
    ('gizmo-feats', 'Gizmo Feats'),
    ('tinker-optional-and-variant-rules', 'Optional & Variant Rules'),
    ('inventioneering', 'Inventioneering'),
    ('tinker-bestiary', 'Tinker Bestiary'),
)


def import_page(pair):
    slug, title = pair
    url = 'https://spheresofpower.wikidot.com/' + slug
    data = urlopen(Request(url, headers={'User-Agent': 'Character Sheet reference importer'}), timeout=60).read()
    soup = BeautifulSoup(data.decode('utf-8'), 'html.parser')
    root = soup.select_one('#page-content')
    if root is None:
        raise ValueError('Missing rules page: ' + slug)
    for node in root.select('#toc, .redtext, .yui-nav, script, style, iframe'):
        node.decompose()
    for node in root.find_all(['p', 'div']):
        if node.parent is None:
            continue
        text = node.get_text(' ', strip=True)
        if len(text) < 150 and '$' in text and node.select('a[href*="drivethrurpg"]'):
            node.decompose()
    # Navigation outside the article is removed above, not mixed into reference text.
    rendered = clean(root, url)
    cleaned = BeautifulSoup(rendered, 'html.parser')
    for table in cleaned.find_all('table'):
        if not table.get_text(' ', strip=True):
            table.decompose()
        else:
            table['width'] = '98%'
    rendered = '<h1>' + escape(title) + '</h1>' + str(cleaned)
    text = BeautifulSoup(rendered, 'html.parser').get_text(' ', strip=True)
    if len(text) < 500 or '\ufffd' in text:
        raise ValueError('Incomplete or misdecoded page: ' + slug)
    entries = [dict(key=slug, name=title, sphere=title, kind='Overview',
                    html=rendered, description=text, source_url=url)]
    for heading in root.find_all(['h1', 'h2', 'h3', 'h4', 'h5']):
        anchor = heading.get('id')
        if not anchor:
            continue
        parts = []
        for node in heading.next_siblings:
            if getattr(node, 'name', None) in ('h1', 'h2', 'h3', 'h4', 'h5'):
                break
            parts.append(str(node))
        body = clean(''.join(parts), url)
        description = BeautifulSoup(body, 'html.parser').get_text(' ', strip=True)
        if not description:
            continue
        entries.append(dict(key=slug + '-' + anchor, name=heading.get_text(' ', strip=True),
                            sphere=title, kind='Rule', html=body, description=description,
                            source_url=url + '#' + anchor))
    print(title, len(entries) - 1, 'sections', flush=True)
    return entries


def main():
    with ThreadPoolExecutor(max_workers=4) as pool:
        entries = [e for page in pool.map(import_page, PAGES) for e in page]
    keys = {e['key'] for e in entries}
    pages = {p[0] for p in PAGES}
    for entry in entries:
        body = BeautifulSoup(entry['html'], 'html.parser')
        for link in body.select('a[href]'):
            target = urlsplit(link['href'])
            slug = target.path.strip('/')
            if target.netloc == 'spheresofpower.wikidot.com' and slug in pages:
                key = slug + '-' + target.fragment if target.fragment else slug
                link['href'] = 'codex:gizmo-reference:' + (key if key in keys else slug)
        entry['html'] = str(body)
    document = {'schema_version': 1, 'sources': [p[0] for p in PAGES], 'entries': entries,
                'attribution': 'Spheres of Power wiki; Ultimate Engineering by Drop Dead Studios, '
                'Diamond Recreational Studios and credited contributors. '
                'See reference_rules_LICENSE.txt for Open Game License notices.'}
    (ROOT / 'data/pf1e/gizmo_rules.json').write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

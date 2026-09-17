"""Shared, read-only rules reference for Codex and character Details.

New reference families belong in the versioned JSON catalog; presentation and
runtime calculations never scrape web pages or reinterpret rules prose.
"""
from functools import lru_cache
from html import escape
import json
import re
from app.catalog_versions import active_catalog_root, BUNDLED_CATALOG_ROOT

@lru_cache(maxsize=1)
def reference_catalog():
    path = active_catalog_root() / "reference_rules.json"
    if not path.exists():
        path = BUNDLED_CATALOG_ROOT / "reference_rules.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    gizmos = active_catalog_root() / 'gizmo_rules.json'
    if not gizmos.exists():
        gizmos = BUNDLED_CATALOG_ROOT / 'gizmo_rules.json'
    document['gizmos'] = json.loads(gizmos.read_text(encoding='utf-8'))['entries']
    from app.item_creation_rules import item_creation_catalog
    document['crafting'] = item_creation_catalog()['entries']
    return document


REFERENCE_FAMILIES = (
    ('skills', 'Skills', 'skill'),
    ('prodigy', 'Prodigy Sequence Reference', 'sequence-reference'),
    ('gizmos', 'Gizmos & Tinker Rules', 'gizmo-reference'),
    ('crafting', 'Item Creation Rules', 'crafting-reference'),
)

def skill_reference(key):
    key = str(key).split("__", 1)[0]
    if key.startswith("knowledge_"):
        key = "knowledge"
    return next((e for e in reference_catalog()["skills"] if e["key"] == key), None)

def normalized(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())

def sequence_reference(name, sphere=""):
    return next((e for e in reference_catalog()["prodigy"]
                 if normalized(e["name"]) == normalized(name)
                 and normalized(e["sphere"]) == normalized(sphere)), None)

def reference_html(entry, *, title="", summary="", show_heading=True, link_color=""):
    if not entry:
        return "<p>No imported reference available.</p>"
    body = entry["html"]
    if body.lstrip().startswith("<li>") and body.rstrip().endswith("</li>"):
        body = body.replace("<li>", "<p>", 1).rsplit("</li>", 1)[0] + "</p>"
    if "kind" in entry:
        # Separate threshold clauses without summarizing or changing any words.
        body = re.sub(r"(?<=[.!?])\s+(?=(?:As a \d+ link finisher|If the sequence))", "</p><p>", body)
    # Skill titles already exist in the imported source; use the specialization
    # label in their place while retaining the original ability/restrictions.
    if title and "<h1" in body:
        body = re.sub(r"<h1[^>]*>.*?</h1>", "", body, count=1, flags=re.S)
    heading = f"<h2>{escape(title or entry['name'])}</h2>" if show_heading and (title or "<h1" not in body) else ""
    optional = ""
    if "Unchained" in body or "Occult" in body:
        optional = ("<p><b>Optional rules:</b> Skill unlocks require an ability such as "
                    "Signature Skill or rogue’s edge. Occult uses require their stated "
                    "access conditions. Ranks alone do not grant these options.</p>")
        match = re.search(r"<h[234][^>]*>.*?(?:Unchained|Occult).*?</h[234]>", body, flags=re.S)
        if match:
            body = body[:match.start()] + optional + body[match.start():]
            optional = ""
    rendered = (heading + summary + "<hr>" + body + optional
                + f"<hr><p><a href='{escape(entry['source_url'], quote=True)}'>Complete rules source</a></p>")
    if link_color:
        rendered = rendered.replace("<a ", f'<a style="color:{escape(link_color, quote=True)}" ')
    return '<div style="font-size:11pt">' + rendered + '</div>'

def reference_index_html(family):
    _, title, prefix = next(row for row in REFERENCE_FAMILIES if row[0] == family)
    entries = sorted(reference_catalog()[family], key=lambda e: (e.get("sphere", ""), e["name"]))
    groups = {}
    for entry in entries:
        groups.setdefault(entry.get("sphere") or ("Skills" if family == "skills" else "Universal"), []).append(entry)
    extra = ''
    if family == 'crafting':
        from app.catalogs import DEFAULT_CATALOG
        from app.item_creation_rules import item_creation_catalog
        keys = {e['key'] for e in item_creation_catalog()['feats']}
        feats = [e for e in DEFAULT_CATALOG.feat_entries() if e['key'] in keys or 'Item Creation' in e.get('categories', ())]
        extra = '<p><a href="codex:skill:craft">Craft skill: mundane crafting, repairs, and salvage</a></p><h2>Item Creation Feats</h2><ul>' + ''.join(
            f"<li><a href='codex:feature:feat:{escape(e['key'], quote=True)}'>{escape(e['name'])}</a> · {escape(e['source_group'])}</li>" for e in feats) + '</ul>'
    return f"<h1>{escape(title)}</h1>" + extra + "".join(
        f"<h2>{escape(group)}</h2><ul>" + "".join(
            f"<li><a href='codex:{prefix}:{e['key']}'>{escape(e['name'])}</a>"
            + (f" · {escape(e['kind'])}" if "kind" in e else "") + "</li>" for e in entries
        ) + "</ul>" for group, entries in groups.items())

def reference_search_records():
    return tuple({"name": e["name"], "category": title + (" · " + e.get('sphere', '') if family != 'skills' else ''),
                  "description": e["description"], "source_url": e["source_url"],
                  "target": prefix + ':' + e["key"]}
                 for family, title, prefix in REFERENCE_FAMILIES for e in reference_catalog()[family])

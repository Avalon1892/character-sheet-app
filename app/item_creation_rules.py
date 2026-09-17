"""Read-only crafting references and stable-key feat enrichment."""
import json
from functools import lru_cache
from app.catalog_versions import active_catalog_root, BUNDLED_CATALOG_ROOT


@lru_cache(maxsize=8)
def item_creation_catalog(root=None):
    path = (root or active_catalog_root()) / 'item_creation_rules.json'
    if not path.exists():
        path = BUNDLED_CATALOG_ROOT / path.name
    return json.loads(path.read_text(encoding='utf-8'))


def enriched_feats(entries, root=None):
    # Preserve stable identities, automation metadata, and saved character links.
    result = {e['key']: dict(e) for e in entries}
    for supplement in item_creation_catalog(root)['feats']:
        result[supplement['key']] = {**result.get(supplement['key'], {}), **supplement}
    return tuple(result.values())

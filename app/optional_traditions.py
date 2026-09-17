"""Optional tradition selection; deliberately independent of advancement/audit grants."""
from __future__ import annotations
import json
from functools import lru_cache
from app.catalog_versions import active_catalog_root, BUNDLED_CATALOG_ROOT

KINDS = ('Crafting', 'Tinker')


@lru_cache(maxsize=1)
def catalog():
    path = active_catalog_root() / 'optional_traditions.json'
    if not path.exists():
        path = BUNDLED_CATALOG_ROOT / path.name
    return json.loads(path.read_text(encoding='utf-8'))


class OptionalTraditionService:
    def __init__(self, repository, character_id):
        self.repository, self.character_id = repository, character_id

    def selections(self):
        return tuple(t for t in self.repository.list_character_traditions(self.character_id)
                     if t.kind in KINDS)

    def add(self, key, notes=''):
        entry = next((e for e in catalog()['entries'] if e['key'] == key), None)
        if entry is None:
            raise ValueError('Unknown optional tradition.')
        if any(t.catalog_key == key for t in self.selections()):
            raise ValueError('This tradition is already selected.')
        return self.repository.add_character_tradition(
            self.character_id, key, entry['name'], entry['kind'],
            choices_json=json.dumps({'Notes': [notes]} if notes else {}),
            definition_json=json.dumps(entry))

    def remove(self, tradition_id):
        if not any(t.id == tradition_id for t in self.selections()):
            raise ValueError('Tradition does not belong to this character.')
        self.repository.delete_character_tradition(self.character_id, tradition_id)

    def edit(self, tradition_id, notes):
        if not any(t.id == tradition_id for t in self.selections()):
            raise ValueError('Tradition does not belong to this character.')
        self.repository.update_optional_tradition_notes(self.character_id, tradition_id, notes)

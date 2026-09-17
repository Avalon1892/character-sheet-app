"""Style-local presentation persistence; never stores gameplay values."""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from app.building_blocks.persistence import BuildingBlockRepository


class SheetStyleStore:
    def __init__(self, repository):
        self.connection = repository.sqlite_connection
        self.connection.execute("""CREATE TABLE IF NOT EXISTS sheet_style_preferences (
            character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
            style_key TEXT NOT NULL, state_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY(character_id, style_key))""")
        self.connection.commit()

    def get(self, character_id, style_key):
        row = self.connection.execute("SELECT state_json FROM sheet_style_preferences WHERE character_id=? AND style_key=?", (character_id, style_key)).fetchone()
        return json.loads(row[0]) if row else {}

    def save(self, character_id, style_key, state):
        if self.get(character_id, style_key) == state:
            return
        self.connection.execute("INSERT INTO sheet_style_preferences VALUES (?, ?, ?) ON CONFLICT(character_id,style_key) DO UPDATE SET state_json=excluded.state_json", (character_id, style_key, json.dumps(state)))
        self.connection.commit()

    def export(self, character_id):
        return {row[0]: json.loads(row[1]) for row in self.connection.execute("SELECT style_key,state_json FROM sheet_style_preferences WHERE character_id=?", (character_id,))}


class MemorySettings:
    """QSettings-compatible ephemeral workspace for one presentation controller."""
    def __init__(self):
        self.values = {}
    def value(self, key, default=None, **kwargs):
        value = self.values.get(key, default)
        convert = kwargs.get("type")
        return convert(value) if convert else value
    def setValue(self, key, value):
        self.values[key] = value
    def allKeys(self):
        return list(self.values)
    def remove(self, key):
        for existing in list(self.values):
            if existing == key or existing.startswith(key + "/"):
                del self.values[existing]


class _PresentationConnection:
    """Alias only the closed set of presentation tables, not SQL values.

    This lets the mature block repository retain its transaction/validation
    behavior while a new style gets independent tabs, instances and cells.
    Templates deliberately remain shared across styles.
    """
    _names = ("sheet_tabs", "sheet_block_instances", "sheet_cell_overrides",
              "sheet_presentation_migrations", "idx_sheet_blocks_character_tab")
    def __init__(self, connection, namespace):
        if not re.fullmatch(r"[a-z][a-z0-9_]*", namespace):
            raise ValueError("Invalid presentation namespace")
        self.raw = connection
        self.namespace = namespace
        self._batch_depth = 0
    @property
    def row_factory(self):
        return self.raw.row_factory
    @row_factory.setter
    def row_factory(self, value):
        self.raw.row_factory = value
    def _sql(self, sql):
        return re.sub(r"\b(" + "|".join(self._names) + r")\b", lambda m: self.namespace + "_" + m[0], sql)
    def execute(self, sql, *args):
        return self.raw.execute(self._sql(sql), *args)
    def executemany(self, sql, *args):
        return self.raw.executemany(self._sql(sql), *args)
    def executescript(self, sql):
        return self.raw.executescript(self._sql(sql))
    def commit(self):
        if not self._batch_depth:
            return self.raw.commit()
    def rollback(self):
        return self.raw.rollback()

    @contextmanager
    def batch(self):
        """One atomic presentation update, preserving any outer transaction."""
        name = f"{self.namespace}_batch_{self._batch_depth}"
        self.raw.execute(f"SAVEPOINT {name}")
        self._batch_depth += 1
        try:
            yield
        except BaseException:
            self.raw.execute(f"ROLLBACK TO SAVEPOINT {name}")
            self.raw.execute(f"RELEASE SAVEPOINT {name}")
            raise
        else:
            self.raw.execute(f"RELEASE SAVEPOINT {name}")
        finally:
            self._batch_depth -= 1


class StyleBlockRepository(BuildingBlockRepository):
    def __init__(self, repository, namespace, default_tabs):
        self.default_tabs = default_tabs
        super().__init__(repository.database_path,
                         connection=_PresentationConnection(repository.sqlite_connection, namespace))

    def ensure_character(self, character_id, registry):
        # No legacy-layout migrations belong in a new presentation namespace.
        tabs = {tab.key for tab in self.list_tabs(character_id)}
        existing = {row[0] for row in self.connection.execute(
            "SELECT template_key FROM sheet_block_instances WHERE character_id=?", (character_id,))}
        missing_tabs = [(order, key, name) for order, (key, name) in enumerate(self.default_tabs) if key not in tabs]
        missing_blocks = [definition for definition in registry.all()
                          if definition.builtin and definition.key not in existing]
        if not missing_tabs and not missing_blocks:
            return
        with self.connection.batch():
            for order, key, name in missing_tabs:
                self.connection.execute("INSERT INTO sheet_tabs (character_id,tab_key,name,display_order,visible,builtin) VALUES (?,?,?,?,1,1)", (character_id,key,name,order))
            for definition in missing_blocks:
                instance = self.add_instance(character_id, definition, definition.default_tab)
                self.set_instance_visible(instance, definition.default_visible)

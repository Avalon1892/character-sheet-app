from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path

from app.building_blocks.registry import BlockRegistry
from app.building_blocks.schemas import (
    BlockDefinition,
    BlockInstance,
    CellOverride,
    SheetTab,
)


DEFAULT_TABS = (
    ("crafting", "Crafting", 5),
    ("build", "0   CHARACTER BUILD", 0),
    ("core", "1   CORE", 1),
    ("inventory", "2   INVENTORY & FEATURES", 2),
    ("magic", "3   MAGIC & SPHERES", 3),
    ("companion", "4   ANIMAL COMPANION", 4),
)


class BuildingBlockRepository:
    """Additive presentation persistence kept separate from character rules tables."""

    def __init__(
        self,
        database_path: Path,
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self._owns_connection = connection is None
        self.connection = connection or sqlite3.connect(self.database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def close(self) -> None:
        if self._owns_connection:
            self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS building_block_templates (
                template_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                definition_json TEXT NOT NULL,
                schema_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sheet_tabs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                tab_key TEXT NOT NULL,
                name TEXT NOT NULL,
                display_order INTEGER NOT NULL,
                visible INTEGER NOT NULL DEFAULT 1 CHECK (visible IN (0, 1)),
                builtin INTEGER NOT NULL DEFAULT 0 CHECK (builtin IN (0, 1)),
                UNIQUE(character_id, tab_key)
            );
            CREATE TABLE IF NOT EXISTS sheet_block_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                instance_key TEXT NOT NULL,
                template_key TEXT NOT NULL,
                tab_key TEXT NOT NULL,
                x INTEGER NOT NULL DEFAULT 12,
                y INTEGER NOT NULL DEFAULT 12,
                width INTEGER NOT NULL DEFAULT 520,
                height INTEGER NOT NULL DEFAULT 300,
                z_order INTEGER NOT NULL DEFAULT 0,
                visible INTEGER NOT NULL DEFAULT 1 CHECK (visible IN (0, 1)),
                style_json TEXT NOT NULL DEFAULT '{}',
                template_snapshot_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(character_id, instance_key)
            );
            CREATE TABLE IF NOT EXISTS sheet_cell_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                block_instance_id INTEGER NOT NULL
                    REFERENCES sheet_block_instances(id) ON DELETE CASCADE,
                cell_key TEXT NOT NULL,
                x INTEGER NOT NULL,
                y INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                visible INTEGER NOT NULL DEFAULT 1 CHECK (visible IN (0, 1)),
                anchored INTEGER NOT NULL DEFAULT 1 CHECK (anchored IN (0, 1)),
                group_id TEXT NOT NULL DEFAULT '',
                binding TEXT NOT NULL DEFAULT '',
                formula TEXT NOT NULL DEFAULT '',
                action TEXT NOT NULL DEFAULT '',
                config_json TEXT NOT NULL DEFAULT '{}',
                style_json TEXT NOT NULL DEFAULT '{}',
                UNIQUE(block_instance_id, cell_key)
            );
            CREATE INDEX IF NOT EXISTS idx_sheet_blocks_character_tab
                ON sheet_block_instances(character_id, tab_key, z_order);
            CREATE TABLE IF NOT EXISTS sheet_presentation_migrations (
                character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
                migration_key TEXT NOT NULL,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (character_id, migration_key)
            );
            """
        )
        self.connection.commit()

    @staticmethod
    def _clean_key(value: str, prefix: str = "item") -> str:
        clean = re.sub(r"[^a-z0-9:_-]+", "_", value.casefold()).strip("_")
        return clean or f"{prefix}:{uuid.uuid4().hex}"

    def ensure_character(self, character_id: int, registry: BlockRegistry) -> None:
        existing_rows = self.connection.execute(
            """
            SELECT instance_key, x, y, width, height, visible, style_json
            FROM sheet_block_instances WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        existing = {str(row["instance_key"]): row for row in existing_rows}
        introducing_classic_default = bool(existing) and "builtin:classic_statistics" not in existing
        for key, name, order in DEFAULT_TABS:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO sheet_tabs
                    (character_id, tab_key, name, display_order, visible, builtin)
                VALUES (?, ?, ?, ?, 1, 1)
                """,
                (character_id, key, name, order),
            )
        for order, definition in enumerate(registry.all()):
            if not definition.builtin:
                continue
            instance_key = definition.key
            visible = definition.default_visible
            # Do not place a replacement panel on top of a deliberately
            # customized legacy sheet.  A one-time migration below enables it
            # only when the prior Ability/Combat blocks were still untouched.
            if introducing_classic_default and definition.key == "builtin:classic_statistics":
                visible = False
            self.connection.execute(
                """
                INSERT OR IGNORE INTO sheet_block_instances
                    (character_id, instance_key, template_key, tab_key, x, y,
                     width, height, z_order, visible, style_json,
                     template_snapshot_json)
                VALUES (?, ?, ?, ?, 12, 12, ?, ?, ?, ?, '{}', ?)
                """,
                (
                    character_id,
                    instance_key,
                    definition.key,
                    definition.default_tab,
                    definition.width,
                    definition.height,
                    order,
                    int(visible),
                    json.dumps(definition.to_dict(), ensure_ascii=False),
                ),
            )
        if introducing_classic_default and self._legacy_core_is_unmodified(character_id, existing):
            self.connection.execute(
                """
                UPDATE sheet_block_instances
                SET visible = CASE
                    WHEN instance_key = 'builtin:classic_statistics' THEN 1
                    WHEN instance_key IN ('builtin:abilities', 'builtin:combat_defense') THEN 0
                    ELSE visible
                END
                WHERE character_id = ?
                """,
                (character_id,),
            )
        self._apply_classic_statistics_default_migration(character_id)
        self.connection.commit()

    def _apply_classic_statistics_default_migration(self, character_id: int) -> None:
        """Upgrade untouched legacy Core pages once, preserving real customization."""

        migration_key = "classic-statistics-default-v2"
        if self.connection.execute(
            """
            SELECT 1 FROM sheet_presentation_migrations
            WHERE character_id = ? AND migration_key = ?
            """,
            (character_id, migration_key),
        ).fetchone() is not None:
            return
        rows = self.connection.execute(
            """
            SELECT instance_key, x, y, width, height, visible, style_json
            FROM sheet_block_instances WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        existing = {str(row["instance_key"]): row for row in rows}
        if "builtin:classic_statistics" not in existing:
            return
        if self._legacy_core_is_unmodified(character_id, existing):
            self.connection.execute(
                """
                UPDATE sheet_block_instances
                SET visible = CASE
                    WHEN instance_key = 'builtin:classic_statistics' THEN 1
                    WHEN instance_key IN ('builtin:abilities', 'builtin:combat_defense') THEN 0
                    ELSE visible
                END
                WHERE character_id = ?
                """,
                (character_id,),
            )
        self.connection.execute(
            """
            INSERT INTO sheet_presentation_migrations (character_id, migration_key)
            VALUES (?, ?)
            """,
            (character_id, migration_key),
        )

    def _legacy_core_is_unmodified(self, character_id: int, existing: dict) -> bool:
        """Recognize the old responsive default without overwriting custom layouts."""

        for key in ("builtin:abilities", "builtin:combat_defense"):
            row = existing.get(key)
            if row is None or not bool(row["visible"]):
                return False
            if (int(row["x"]), int(row["y"]), int(row["width"]), int(row["height"])) != (
                12, 12, 520, 300
            ):
                return False
            if str(row["style_json"] or "{}").strip() not in {"", "{}"}:
                return False
        overrides = self.connection.execute(
            """
            SELECT 1 FROM sheet_cell_overrides AS override
            JOIN sheet_block_instances AS block ON block.id = override.block_instance_id
            WHERE block.character_id = ? LIMIT 1
            """,
            (character_id,),
        ).fetchone()
        if overrides is not None:
            return False
        row = self.connection.execute(
            "SELECT state_json FROM character_sheet_layouts WHERE character_id = ?",
            (character_id,),
        ).fetchone()
        if row is None:
            return True
        try:
            state = json.loads(str(row["state_json"] or "{}"))
        except json.JSONDecodeError:
            return False
        raw_freeform = state.get("freeform")
        if not raw_freeform:
            return True
        try:
            freeform = (
                json.loads(raw_freeform)
                if isinstance(raw_freeform, str)
                else dict(raw_freeform)
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return not any(
            isinstance(placement, dict) and placement.get("page") == "core"
            for placement in freeform.values()
        )

    def reset_character_presentation(
        self, character_id: int, registry: BlockRegistry
    ) -> None:
        """Restore default tabs/blocks while preserving every rules-data table."""
        self.connection.execute(
            """
            DELETE FROM sheet_cell_overrides
            WHERE block_instance_id IN (
                SELECT id FROM sheet_block_instances WHERE character_id = ?
            )
            """,
            (character_id,),
        )
        self.connection.execute(
            "DELETE FROM sheet_block_instances WHERE character_id = ?",
            (character_id,),
        )
        self.connection.execute(
            "DELETE FROM sheet_tabs WHERE character_id = ?",
            (character_id,),
        )
        self.connection.commit()
        self.ensure_character(character_id, registry)

    # Templates ---------------------------------------------------------
    def list_user_templates(self) -> tuple[BlockDefinition, ...]:
        rows = self.connection.execute(
            "SELECT definition_json FROM building_block_templates ORDER BY category, name"
        ).fetchall()
        result = []
        for row in rows:
            try:
                result.append(BlockDefinition.from_dict(json.loads(row["definition_json"])))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return tuple(result)

    def save_user_template(self, definition: BlockDefinition) -> None:
        if definition.builtin:
            raise ValueError("Built-in templates are registered by the application.")
        if not definition.key.strip() or not definition.name.strip():
            raise ValueError("Template key and name are required.")
        payload = json.dumps(definition.to_dict(), ensure_ascii=False)
        self.connection.execute(
            """
            INSERT INTO building_block_templates
                (template_key, name, category, description, definition_json,
                 schema_version)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(template_key) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                description=excluded.description,
                definition_json=excluded.definition_json,
                schema_version=excluded.schema_version,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                definition.key,
                definition.name.strip(),
                definition.category.strip() or "Custom",
                definition.description.strip(),
                payload,
                definition.version,
            ),
        )
        self.connection.commit()

    def delete_user_template(self, template_key: str) -> None:
        # Instances retain template_snapshot_json and deliberately have no FK.
        self.connection.execute(
            "DELETE FROM building_block_templates WHERE template_key = ?",
            (template_key,),
        )
        self.connection.commit()

    def unique_template_key(self, name: str) -> str:
        base = self._clean_key(name, "block")
        if not base.startswith("user:"):
            base = f"user:{base}"
        candidate = base
        counter = 2
        while self.connection.execute(
            "SELECT 1 FROM building_block_templates WHERE template_key = ?", (candidate,)
        ).fetchone():
            candidate = f"{base}_{counter}"
            counter += 1
        return candidate

    # Tabs --------------------------------------------------------------
    def list_tabs(self, character_id: int) -> tuple[SheetTab, ...]:
        rows = self.connection.execute(
            """
            SELECT id, character_id, tab_key, name, display_order, visible, builtin
            FROM sheet_tabs WHERE character_id = ? ORDER BY display_order, id
            """,
            (character_id,),
        ).fetchall()
        return tuple(
            SheetTab(
                int(row["id"]), int(row["character_id"]), str(row["tab_key"]),
                str(row["name"]), int(row["display_order"]), bool(row["visible"]),
                bool(row["builtin"]),
            )
            for row in rows
        )

    def add_tab(self, character_id: int, name: str, *, source_key: str = "") -> str:
        clean_name = name.strip() or "New Page"
        tab_key = f"tab:{uuid.uuid4().hex}"
        order = int(
            self.connection.execute(
                "SELECT COALESCE(MAX(display_order), -1) + 1 FROM sheet_tabs WHERE character_id = ?",
                (character_id,),
            ).fetchone()[0]
        )
        self.connection.execute(
            "INSERT INTO sheet_tabs (character_id, tab_key, name, display_order) VALUES (?, ?, ?, ?)",
            (character_id, tab_key, clean_name, order),
        )
        if source_key:
            source = self.connection.execute(
                "SELECT tab_key FROM sheet_tabs WHERE character_id = ? AND tab_key = ?",
                (character_id, source_key),
            ).fetchone()
            if source:
                for block in self.list_instances(character_id, source_key):
                    snapshot = block.template_snapshot
                    if bool(snapshot.get("builtin", False)):
                        # Built-in sections are one live view over rules data. Do
                        # not steal that view from the source when duplicating.
                        continue
                    self.add_instance(
                        character_id,
                        BlockDefinition.from_dict(snapshot),
                        tab_key,
                        x=block.x + 18,
                        y=block.y + 18,
                    )
        self.connection.commit()
        return tab_key

    def rename_tab(self, character_id: int, tab_key: str, name: str) -> None:
        clean = name.strip()
        if not clean:
            raise ValueError("Tab name cannot be empty.")
        self.connection.execute(
            "UPDATE sheet_tabs SET name = ? WHERE character_id = ? AND tab_key = ?",
            (clean, character_id, tab_key),
        )
        self.connection.commit()

    def set_tab_visible(self, character_id: int, tab_key: str, visible: bool) -> None:
        self.connection.execute(
            "UPDATE sheet_tabs SET visible = ? WHERE character_id = ? AND tab_key = ?",
            (int(visible), character_id, tab_key),
        )
        self.connection.commit()

    def reorder_tabs(self, character_id: int, ordered_keys: list[str]) -> None:
        for order, key in enumerate(ordered_keys):
            self.connection.execute(
                "UPDATE sheet_tabs SET display_order = ? WHERE character_id = ? AND tab_key = ?",
                (order, character_id, key),
            )
        self.connection.commit()

    def remove_tab(
        self,
        character_id: int,
        tab_key: str,
        *,
        move_to: str = "",
        hide: bool = False,
    ) -> None:
        if hide:
            self.set_tab_visible(character_id, tab_key, False)
            return
        if not move_to:
            raise ValueError("Choose a destination tab or hide the tab.")
        self.connection.execute(
            "UPDATE sheet_block_instances SET tab_key = ? WHERE character_id = ? AND tab_key = ?",
            (move_to, character_id, tab_key),
        )
        self.connection.execute(
            "DELETE FROM sheet_tabs WHERE character_id = ? AND tab_key = ?",
            (character_id, tab_key),
        )
        self.connection.commit()

    # Instances ---------------------------------------------------------
    def list_instances(
        self, character_id: int, tab_key: str | None = None
    ) -> tuple[BlockInstance, ...]:
        sql = """
            SELECT id, character_id, instance_key, template_key, tab_key, x, y,
                   width, height, z_order, visible, style_json,
                   template_snapshot_json
            FROM sheet_block_instances WHERE character_id = ?
        """
        values: tuple = (character_id,)
        if tab_key is not None:
            sql += " AND tab_key = ?"
            values = (character_id, tab_key)
        sql += " ORDER BY z_order, id"
        return tuple(self._instance(row) for row in self.connection.execute(sql, values))

    @staticmethod
    def _instance(row: sqlite3.Row) -> BlockInstance:
        def loaded(name: str) -> dict:
            try:
                value = json.loads(str(row[name] or "{}"))
                return dict(value) if isinstance(value, dict) else {}
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        return BlockInstance(
            int(row["id"]), int(row["character_id"]), str(row["instance_key"]),
            str(row["template_key"]), str(row["tab_key"]), int(row["x"]),
            int(row["y"]), int(row["width"]), int(row["height"]),
            int(row["z_order"]), bool(row["visible"]), loaded("style_json"),
            loaded("template_snapshot_json"),
        )

    def add_instance(
        self,
        character_id: int,
        definition: BlockDefinition,
        tab_key: str,
        *,
        x: int = 24,
        y: int = 24,
    ) -> int:
        if not self.connection.execute(
            "SELECT 1 FROM sheet_tabs WHERE character_id = ? AND tab_key = ?",
            (character_id, tab_key),
        ).fetchone():
            raise ValueError("Unknown destination tab.")
        if definition.builtin:
            existing = self.connection.execute(
                "SELECT id FROM sheet_block_instances WHERE character_id = ? AND template_key = ?",
                (character_id, definition.key),
            ).fetchone()
            if existing:
                self.connection.execute(
                    "UPDATE sheet_block_instances SET tab_key = ?, visible = 1 WHERE id = ?",
                    (tab_key, int(existing["id"])),
                )
                self.connection.commit()
                return int(existing["id"])
        instance_key = f"instance:{uuid.uuid4().hex}"
        z_order = int(
            self.connection.execute(
                "SELECT COALESCE(MAX(z_order), -1) + 1 FROM sheet_block_instances WHERE character_id = ? AND tab_key = ?",
                (character_id, tab_key),
            ).fetchone()[0]
        )
        cursor = self.connection.execute(
            """
            INSERT INTO sheet_block_instances
                (character_id, instance_key, template_key, tab_key, x, y, width,
                 height, z_order, visible, style_json, template_snapshot_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                character_id, instance_key, definition.key, tab_key, int(x), int(y),
                definition.width, definition.height, z_order,
                json.dumps(definition.style, ensure_ascii=False),
                json.dumps(definition.to_dict(), ensure_ascii=False),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def update_instance_geometry(
        self, instance_id: int, x: int, y: int, width: int, height: int
    ) -> None:
        self.connection.execute(
            "UPDATE sheet_block_instances SET x=?, y=?, width=?, height=? WHERE id=?",
            (int(x), int(y), max(160, int(width)), max(90, int(height)), instance_id),
        )
        self.connection.commit()

    def update_instance_snapshot(
        self, instance_id: int, definition: BlockDefinition
    ) -> None:
        self.connection.execute(
            """
            UPDATE sheet_block_instances
            SET template_snapshot_json = ?, width = ?, height = ?
            WHERE id = ?
            """,
            (
                json.dumps(definition.to_dict(), ensure_ascii=False),
                definition.width,
                definition.height,
                instance_id,
            ),
        )
        self.connection.commit()

    def move_instance(self, instance_id: int, tab_key: str) -> None:
        self.connection.execute(
            "UPDATE sheet_block_instances SET tab_key = ?, visible = 1 WHERE id = ?",
            (tab_key, instance_id),
        )
        self.connection.commit()

    def set_instance_visible(self, instance_id: int, visible: bool) -> None:
        self.connection.execute(
            "UPDATE sheet_block_instances SET visible = ? WHERE id = ?",
            (int(visible), instance_id),
        )
        self.connection.commit()

    def delete_custom_instance(self, instance_id: int) -> None:
        self.connection.execute(
            "DELETE FROM sheet_block_instances WHERE id = ?", (instance_id,)
        )
        self.connection.commit()

    # Cell overrides ----------------------------------------------------
    def list_cell_overrides(self, block_instance_id: int) -> tuple[CellOverride, ...]:
        rows = self.connection.execute(
            """
            SELECT id, block_instance_id, cell_key, x, y, width, height, visible,
                   anchored, group_id, binding, formula, action, config_json,
                   style_json
            FROM sheet_cell_overrides WHERE block_instance_id = ? ORDER BY id
            """,
            (block_instance_id,),
        ).fetchall()
        return tuple(self._override(row) for row in rows)

    @staticmethod
    def _override(row: sqlite3.Row) -> CellOverride:
        def loaded(name: str) -> dict:
            try:
                value = json.loads(str(row[name] or "{}"))
                return dict(value) if isinstance(value, dict) else {}
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
        return CellOverride(
            int(row["id"]), int(row["block_instance_id"]), str(row["cell_key"]),
            int(row["x"]), int(row["y"]), int(row["width"]), int(row["height"]),
            bool(row["visible"]), bool(row["anchored"]), str(row["group_id"]),
            str(row["binding"]), str(row["formula"]), str(row["action"]),
            loaded("config_json"), loaded("style_json"),
        )

    def save_cell_override(self, override: CellOverride) -> None:
        self.connection.execute(
            """
            INSERT INTO sheet_cell_overrides
                (block_instance_id, cell_key, x, y, width, height, visible,
                 anchored, group_id, binding, formula, action, config_json,
                 style_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(block_instance_id, cell_key) DO UPDATE SET
                x=excluded.x, y=excluded.y, width=excluded.width,
                height=excluded.height, visible=excluded.visible,
                anchored=excluded.anchored, group_id=excluded.group_id,
                binding=excluded.binding, formula=excluded.formula,
                action=excluded.action, config_json=excluded.config_json,
                style_json=excluded.style_json
            """,
            (
                override.block_instance_id, override.cell_key, override.x, override.y,
                max(20, override.width), max(18, override.height), int(override.visible),
                int(override.anchored), override.group_id, override.binding,
                override.formula, override.action,
                json.dumps(override.config, ensure_ascii=False),
                json.dumps(override.style, ensure_ascii=False),
            ),
        )
        self.connection.commit()

    def delete_cell_override(self, block_instance_id: int, cell_key: str) -> None:
        self.connection.execute(
            "DELETE FROM sheet_cell_overrides WHERE block_instance_id=? AND cell_key=?",
            (block_instance_id, cell_key),
        )
        self.connection.commit()

    # Portable state ----------------------------------------------------
    def export_character_state(self, character_id: int) -> dict:
        tabs = [
            {
                "key": tab.key,
                "name": tab.name,
                "order": tab.order,
                "visible": tab.visible,
                "builtin": tab.builtin,
            }
            for tab in self.list_tabs(character_id)
        ]
        blocks = []
        for block in self.list_instances(character_id):
            blocks.append(
                {
                    "instance_key": block.instance_key,
                    "template_key": block.template_key,
                    "tab_key": block.tab_key,
                    "x": block.x, "y": block.y, "width": block.width,
                    "height": block.height, "z_order": block.z_order,
                    "visible": block.visible, "style": block.style,
                    "template_snapshot": block.template_snapshot,
                    "cell_overrides": [
                        {
                            "cell_key": item.cell_key, "x": item.x, "y": item.y,
                            "width": item.width, "height": item.height,
                            "visible": item.visible, "anchored": item.anchored,
                            "group_id": item.group_id, "binding": item.binding,
                            "formula": item.formula, "action": item.action,
                            "config": item.config, "style": item.style,
                        }
                        for item in self.list_cell_overrides(block.id)
                    ],
                }
            )
        return {"schema_version": 1, "tabs": tabs, "blocks": blocks}

    def import_character_state(self, character_id: int, state: dict) -> None:
        if int(state.get("schema_version", 1)) > 1:
            raise ValueError("This sheet layout uses a newer unsupported schema.")
        self.connection.execute("DELETE FROM sheet_cell_overrides WHERE block_instance_id IN (SELECT id FROM sheet_block_instances WHERE character_id=?)", (character_id,))
        self.connection.execute("DELETE FROM sheet_block_instances WHERE character_id=?", (character_id,))
        self.connection.execute("DELETE FROM sheet_tabs WHERE character_id=?", (character_id,))
        for order, tab in enumerate(state.get("tabs", ())):
            self.connection.execute(
                "INSERT INTO sheet_tabs (character_id, tab_key, name, display_order, visible, builtin) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    character_id, str(tab.get("key") or f"tab:{uuid.uuid4().hex}"),
                    str(tab.get("name") or "Page"), int(tab.get("order", order)),
                    int(bool(tab.get("visible", True))), int(bool(tab.get("builtin", False))),
                ),
            )
        if not state.get("tabs"):
            for key, name, order in DEFAULT_TABS:
                self.connection.execute(
                    "INSERT INTO sheet_tabs (character_id, tab_key, name, display_order, visible, builtin) VALUES (?, ?, ?, ?, 1, 1)",
                    (character_id, key, name, order),
                )
        self.connection.commit()
        for order, block in enumerate(state.get("blocks", ())):
            snapshot = dict(block.get("template_snapshot") or {})
            definition = BlockDefinition.from_dict(snapshot or {
                "key": str(block.get("template_key") or f"imported:{uuid.uuid4().hex}"),
                "name": "Imported Block", "category": "Imported",
            })
            cursor = self.connection.execute(
                """
                INSERT INTO sheet_block_instances
                    (character_id, instance_key, template_key, tab_key, x, y,
                     width, height, z_order, visible, style_json,
                     template_snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    character_id, str(block.get("instance_key") or f"instance:{uuid.uuid4().hex}"),
                    definition.key, str(block.get("tab_key") or "build"),
                    int(block.get("x", 12)), int(block.get("y", 12)),
                    max(160, int(block.get("width", definition.width))),
                    max(90, int(block.get("height", definition.height))),
                    int(block.get("z_order", order)), int(bool(block.get("visible", True))),
                    json.dumps(dict(block.get("style") or {}), ensure_ascii=False),
                    json.dumps(definition.to_dict(), ensure_ascii=False),
                ),
            )
            instance_id = int(cursor.lastrowid)
            for cell in block.get("cell_overrides", ()):
                self.save_cell_override(CellOverride(
                    0, instance_id, str(cell.get("cell_key", "")),
                    int(cell.get("x", 0)), int(cell.get("y", 0)),
                    int(cell.get("width", 80)), int(cell.get("height", 28)),
                    bool(cell.get("visible", True)), bool(cell.get("anchored", True)),
                    str(cell.get("group_id", "")), str(cell.get("binding", "")),
                    str(cell.get("formula", "")), str(cell.get("action", "")),
                    dict(cell.get("config") or {}), dict(cell.get("style") or {}),
                ))
        self.connection.commit()

    def replace_character_cell_overrides(
        self, character_id: int, state: dict
    ) -> None:
        """Apply only cell presentation state without rebuilding tabs or blocks.

        Undo/redo uses this fast path when stable tab and block structure did not
        change. Keeping instance IDs intact avoids recreating every sheet widget
        for a single cell move or resize.
        """
        instance_ids = {
            str(row["instance_key"]): int(row["id"])
            for row in self.connection.execute(
                "SELECT id, instance_key FROM sheet_block_instances WHERE character_id=?",
                (character_id,),
            ).fetchall()
        }
        blocks = list(state.get("blocks", ()))
        if any(
            str(block.get("instance_key") or "") not in instance_ids
            for block in blocks
        ):
            raise ValueError("Sheet block structure changed during cell-only restore.")
        self.connection.execute(
            """
            DELETE FROM sheet_cell_overrides
            WHERE block_instance_id IN (
                SELECT id FROM sheet_block_instances WHERE character_id=?
            )
            """,
            (character_id,),
        )
        for block in blocks:
            instance_id = instance_ids[str(block.get("instance_key") or "")]
            for cell in block.get("cell_overrides", ()):
                self.connection.execute(
                    """
                    INSERT INTO sheet_cell_overrides
                        (block_instance_id, cell_key, x, y, width, height,
                         visible, anchored, group_id, binding, formula, action,
                         config_json, style_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        instance_id,
                        str(cell.get("cell_key", "")),
                        int(cell.get("x", 0)),
                        int(cell.get("y", 0)),
                        max(20, int(cell.get("width", 80))),
                        max(18, int(cell.get("height", 28))),
                        int(bool(cell.get("visible", True))),
                        int(bool(cell.get("anchored", True))),
                        str(cell.get("group_id", "")),
                        str(cell.get("binding", "")),
                        str(cell.get("formula", "")),
                        str(cell.get("action", "")),
                        json.dumps(dict(cell.get("config") or {}), ensure_ascii=False),
                        json.dumps(dict(cell.get("style") or {}), ensure_ascii=False),
                    ),
                )
        self.connection.commit()

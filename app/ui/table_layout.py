from __future__ import annotations

import json
import uuid
from shiboken6 import isValid as qt_object_is_valid

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QInputDialog,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)


class TableLayoutController(QObject):
    """Persistent, structural table presentation controlled through Build Mode."""

    SETTINGS_KEY = "customization/tableLayouts"
    COLUMN_KEY_ROLE = Qt.ItemDataRole.UserRole + 41

    def __init__(self, settings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.tables: dict[str, QTableWidget] = {}
        self._builtin_counts: dict[str, int] = {}
        self._defaults: dict[str, dict] = {}
        self._restoring = False
        self._editing = False
        self._active_table_id = ""
        self.history = None
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(120)
        self._save_timer.timeout.connect(self._save_active_table)
        self._state = self._read_state()

    def set_history(self, history) -> None:
        self.history = history

    def register(self, table_id: str, table: QTableWidget) -> None:
        if table_id in self.tables:
            return
        self.tables[table_id] = table
        self._builtin_counts[table_id] = table.columnCount()
        table.setProperty("tableLayoutId", table_id)
        header = table.horizontalHeader()
        header.setSectionsMovable(False)
        header.setMinimumSectionSize(28)
        for logical in range(table.columnCount()):
            item = table.horizontalHeaderItem(logical) or QTableWidgetItem(
                f"Column {logical + 1}"
            )
            item.setData(self.COLUMN_KEY_ROLE, self._builtin_key(logical))
            table.setHorizontalHeaderItem(logical, item)
        self._defaults[table_id] = {
            "order": [self._builtin_key(index) for index in range(table.columnCount())],
            "widths": {
                self._builtin_key(index): header.sectionSize(index)
                for index in range(table.columnCount())
            },
            "modes": {
                self._builtin_key(index): header.sectionResizeMode(index)
                for index in range(table.columnCount())
            },
        }
        header.sectionResized.connect(self._changed)
        header.sectionMoved.connect(self._changed)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(
            lambda position, key=table_id: self._show_column_menu(key, position)
        )
        header.installEventFilter(self)
        header.viewport().installEventFilter(self)
        table.itemChanged.connect(
            lambda item, key=table_id: self._item_changed(key, item)
        )
        table.cellDoubleClicked.connect(
            lambda row, column, key=table_id: self._edit_custom_cell(key, row, column)
        )
        table.model().rowsInserted.connect(
            lambda *_args, key=table_id: QTimer.singleShot(
                0, lambda: self._apply_custom_cells(key)
            )
        )
        table.itemDelegate().closeEditor.connect(
            lambda *_args: self._finish_interaction()
        )
        QTimer.singleShot(0, lambda key=table_id: self._restore_table(key))

    def set_editing(self, enabled: bool) -> None:
        if not enabled and self._save_timer.isActive():
            self._save_timer.stop()
            self._save()
        self._editing = enabled
        self._restoring = True
        try:
            for table_id, table in self.tables.items():
                header = table.horizontalHeader()
                header.setSectionsMovable(enabled)
                if enabled or table_id in self._state:
                    for logical in range(header.count()):
                        header.setSectionResizeMode(
                            logical, QHeaderView.ResizeMode.Interactive
                        )
                else:
                    self._restore_table(table_id)
        finally:
            self._restoring = False

    def reset(self) -> None:
        self._state = {}
        self.settings.remove(self.SETTINGS_KEY)
        for table_id in self.tables:
            self._restore_table(table_id)

    def flush(self) -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
        self._save()

    def dispose(self) -> None:
        """Stop deferred work and detach filters from tables owned by a closing sheet."""

        self._save_timer.stop()
        self._editing = False
        self.history = None
        for table in tuple(self.tables.values()):
            try:
                header = table.horizontalHeader()
                header.removeEventFilter(self)
                header.viewport().removeEventFilter(self)
            except RuntimeError:
                # A table may already have been deleted by Qt during shutdown.
                pass
        self.tables.clear()
        self._builtin_counts.clear()
        self._defaults.clear()

    def reload(self) -> None:
        self._state = self._read_state()
        for table_id in self.tables:
            self._restore_table(table_id)

    def eventFilter(self, watched, event) -> bool:
        if not self._editing:
            return False
        table_id = next(
            (
                key
                for key, table in self.tables.items()
                if qt_object_is_valid(table) and watched in {table.horizontalHeader(), table.horizontalHeader().viewport()}
            ),
            "",
        )
        if not table_id or not self._editing:
            return False
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._active_table_id = table_id
            if self.history is not None:
                self.history.begin("Adjust table columns")
        elif (
            event.type() == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
        ):
            active = self._active_table_id or table_id
            self._active_table_id = ""
            QTimer.singleShot(0, lambda key=active: self._finish_interaction(key))
        return False

    def _finish_interaction(self, table_id: str = "") -> None:
        if self._save_timer.isActive():
            self._save_timer.stop()
        if table_id:
            self._capture_table(table_id)
        self._save()
        if self.history is not None:
            self.history.commit()

    def _changed(self, *_args) -> None:
        if self._restoring:
            return
        header = self.sender()
        table_id = next(
            (
                key
                for key, table in self.tables.items()
                if table.horizontalHeader() is header
            ),
            "",
        )
        if self._editing and table_id == self._active_table_id:
            self._save_timer.start()

    def _save_active_table(self) -> None:
        if self._active_table_id:
            self._capture_table(self._active_table_id)
        self._save()

    def _read_state(self) -> dict:
        raw = str(self.settings.value(self.SETTINGS_KEY, "{}") or "{}")
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _builtin_key(logical: int) -> str:
        return f"builtin:{logical}"

    @staticmethod
    def _serialized_key(key: str):
        """Keep the original numeric format for built-in columns.

        Custom columns need stable string IDs, while older installations and
        extensions already consume numeric built-in order/width keys.
        """
        if key.startswith("builtin:") and key[8:].isdigit():
            return int(key[8:])
        return key

    def _column_key(self, table: QTableWidget, logical: int) -> str:
        item = table.horizontalHeaderItem(logical)
        key = str(item.data(self.COLUMN_KEY_ROLE) or "") if item else ""
        return key or self._builtin_key(logical)

    def _logical_for_key(self, table: QTableWidget, key: str) -> int:
        return next(
            (
                logical
                for logical in range(table.columnCount())
                if self._column_key(table, logical) == key
            ),
            -1,
        )

    def _remove_custom_columns(self, table_id: str) -> None:
        table = self.tables[table_id]
        for logical in reversed(range(table.columnCount())):
            if self._column_key(table, logical).startswith("custom:"):
                table.removeColumn(logical)

    def _restore_table(self, table_id: str) -> None:
        table = self.tables.get(table_id)
        if table is None or not qt_object_is_valid(table):
            return
        state = self._state.get(table_id)
        state = state if isinstance(state, dict) else {}
        if state and not self._meaningful_state(table_id, state):
            # Older versions persisted every table merely by entering Build
            # Mode. Width-only legacy snapshots are indistinguishable from Qt's
            # transient layout widths and caused responsive columns to drift.
            self._state.pop(table_id, None)
            state = {}
        header = table.horizontalHeader()
        self._restoring = True
        table.blockSignals(True)
        try:
            self._remove_custom_columns(table_id)
            custom_columns = [
                value for value in state.get("custom", ()) if isinstance(value, dict)
            ]
            for custom in custom_columns:
                logical = table.columnCount()
                table.insertColumn(logical)
                item = QTableWidgetItem(str(custom.get("title") or "Custom"))
                item.setData(
                    self.COLUMN_KEY_ROLE,
                    str(custom.get("key") or f"custom:{uuid.uuid4().hex}"),
                )
                table.setHorizontalHeaderItem(logical, item)
            default_modes = self._defaults.get(table_id, {}).get("modes", {})
            customized = bool(state)
            for logical in range(header.count()):
                key = self._column_key(table, logical)
                mode = (
                    QHeaderView.ResizeMode.Interactive
                    if self._editing or customized or key.startswith("custom:")
                    else default_modes.get(key, QHeaderView.ResizeMode.Interactive)
                )
                header.setSectionResizeMode(logical, mode)
                table.setColumnHidden(logical, False)

            keys = [self._column_key(table, logical) for logical in range(header.count())]
            # Presentation styles may opt into a different initial visual
            # order. Logical columns and explicit saved arrangements stay put.
            raw_order = list(state.get("order", table.property("defaultColumnOrder") or ()))
            order = []
            for value in raw_order:
                if isinstance(value, int) or str(value).isdigit():
                    index = int(value)
                    if 0 <= index < len(keys):
                        order.append(keys[index])
                else:
                    order.append(str(value))
            if set(order) == set(keys) and len(order) == len(keys):
                for visual, key in enumerate(order):
                    logical = self._logical_for_key(table, key)
                    current_visual = header.visualIndex(logical)
                    if logical >= 0 and current_visual != visual:
                        header.moveSection(current_visual, visual)
            else:
                for visual, key in enumerate(keys):
                    current_visual = header.visualIndex(self._logical_for_key(table, key))
                    if current_visual != visual:
                        header.moveSection(current_visual, visual)

            widths = state.get("widths", {})
            defaults = self._defaults.get(table_id, {}).get("widths", {})
            for logical in range(header.count()):
                key = self._column_key(table, logical)
                width = int(
                    widths.get(key, widths.get(str(logical), defaults.get(key, 100)))
                    or 100
                )
                header.resizeSection(
                    logical, max(header.minimumSectionSize(), width)
                )
            # Style-specific defaults are opt-in. Explicit user layouts win.
            default_hidden = table.property("defaultHiddenColumns") or ()
            for key in state.get("hidden", default_hidden):
                logical = self._logical_for_key(table, str(key))
                if logical >= 0:
                    table.setColumnHidden(logical, True)
        finally:
            table.blockSignals(False)
            self._restoring = False
        self._apply_custom_cells(table_id)
        header.setSectionsMovable(self._editing)

    def _meaningful_state(self, table_id: str, state: dict) -> bool:
        if state.get("user_modified") or state.get("custom") or state.get("hidden"):
            return True
        raw_order = list(state.get("order", ()))
        expected = list(range(self._builtin_counts.get(table_id, 0)))
        normalized = []
        for value in raw_order:
            if isinstance(value, int) or str(value).isdigit():
                normalized.append(int(value))
            elif str(value).startswith("builtin:") and str(value)[8:].isdigit():
                normalized.append(int(str(value)[8:]))
            else:
                return True
        return bool(normalized and normalized != expected)

    def _custom_definition(self, table_id: str, key: str) -> dict | None:
        state = self._state.get(table_id, {})
        return next(
            (
                value
                for value in state.get("custom", ())
                if isinstance(value, dict) and str(value.get("key")) == key
            ),
            None,
        )

    def _row_key(self, table: QTableWidget, row: int) -> str:
        for logical in range(min(self._builtin_counts.get(str(table.property("tableLayoutId")), 0), table.columnCount())):
            item = table.item(row, logical)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) is not None:
                return f"record:{item.data(Qt.ItemDataRole.UserRole)}"
        return f"row:{row}"

    def _apply_custom_cells(self, table_id: str) -> None:
        table = self.tables.get(table_id)
        if table is None:
            return
        state = self._state.get(table_id, {})
        custom = [value for value in state.get("custom", ()) if isinstance(value, dict)]
        table.blockSignals(True)
        try:
            for definition in custom:
                key = str(definition.get("key") or "")
                logical = self._logical_for_key(table, key)
                if logical < 0:
                    continue
                cells = dict(definition.get("cells") or {})
                for row in range(table.rowCount()):
                    item = table.item(row, logical) or QTableWidgetItem()
                    item.setText(str(cells.get(self._row_key(table, row), "")))
                    item.setToolTip("Custom sheet column — double-click in Build Mode to edit")
                    table.setItem(row, logical, item)
        finally:
            table.blockSignals(False)

    def _edit_custom_cell(self, table_id: str, row: int, logical: int) -> None:
        if not self._editing:
            return
        table = self.tables[table_id]
        key = self._column_key(table, logical)
        if not key.startswith("custom:"):
            return
        if self.history is not None:
            self.history.begin("Edit custom table cell")
        item = table.item(row, logical) or QTableWidgetItem()
        table.setItem(row, logical, item)
        table.editItem(item)

    def _item_changed(self, table_id: str, item: QTableWidgetItem) -> None:
        if self._restoring:
            return
        table = self.tables[table_id]
        key = self._column_key(table, item.column())
        definition = self._custom_definition(table_id, key)
        if definition is None:
            return
        cells = dict(definition.get("cells") or {})
        cells[self._row_key(table, item.row())] = item.text()
        definition["cells"] = cells
        self._save_timer.start()

    def _show_column_menu(self, table_id: str, position) -> None:
        if not self._editing:
            return
        table = self.tables[table_id]
        header = table.horizontalHeader()
        logical = header.logicalIndexAt(position)
        menu = QMenu(table.window())
        menu.addAction("Add custom column…", lambda: self.add_custom_column(table_id))
        if logical >= 0:
            key = self._column_key(table, logical)
            title_item = table.horizontalHeaderItem(logical)
            title = title_item.text() if title_item else "Column"
            menu.addSeparator()
            if key.startswith("custom:"):
                menu.addAction(
                    f'Rename “{title}”…',
                    lambda: self.rename_custom_column(table_id, key),
                )
                menu.addAction(
                    f'Delete “{title}”',
                    lambda: self.remove_column(table_id, key),
                )
            else:
                menu.addAction(
                    f'Remove “{title}” from sheet',
                    lambda: self.remove_column(table_id, key),
                )
        hidden = [
            self._column_key(table, logical)
            for logical in range(table.columnCount())
            if table.isColumnHidden(logical)
        ]
        if hidden:
            restore = menu.addMenu("Restore removed column")
            for key in hidden:
                logical = self._logical_for_key(table, key)
                item = table.horizontalHeaderItem(logical)
                restore.addAction(
                    item.text() if item else key,
                    lambda checked=False, column_key=key: self.restore_column(
                        table_id, column_key
                    ),
                )
        menu.exec(header.mapToGlobal(position))

    def _record(self, description: str, operation) -> object:
        if self.history is None:
            return operation()
        return self.history.record(description, operation)

    def _mark_modified(self, table_id: str) -> dict:
        state = self._state.setdefault(table_id, {})
        defaults = self.tables[table_id].property("defaultHiddenColumns")
        if defaults and "hidden" not in state:
            state["hidden"] = list(defaults)
        state["user_modified"] = True
        return state

    def add_custom_column(self, table_id: str, title: str = "") -> str:
        table = self.tables[table_id]
        if not title:
            title, accepted = QInputDialog.getText(
                table.window(), "Add table column", "Column name"
            )
            if not accepted or not title.strip():
                return ""
        key = f"custom:{uuid.uuid4().hex}"

        def operation() -> None:
            state = self._mark_modified(table_id)
            state.setdefault("custom", []).append(
                {"key": key, "title": title.strip(), "cells": {}}
            )
            self._restore_table(table_id)
            self._save()

        self._record("Add table column", operation)
        return key

    def rename_custom_column(self, table_id: str, key: str, title: str = "") -> None:
        table = self.tables[table_id]
        definition = self._custom_definition(table_id, key)
        if definition is None:
            return
        if not title:
            title, accepted = QInputDialog.getText(
                table.window(), "Rename table column", "Column name",
                text=str(definition.get("title") or "Custom"),
            )
            if not accepted or not title.strip():
                return

        def operation() -> None:
            definition["title"] = title.strip()
            self._mark_modified(table_id)
            logical = self._logical_for_key(table, key)
            if logical >= 0:
                table.horizontalHeaderItem(logical).setText(title.strip())
            self._save()

        self._record("Rename table column", operation)

    def remove_column(self, table_id: str, key: str) -> None:
        def operation() -> None:
            state = self._mark_modified(table_id)
            if key.startswith("custom:"):
                state["custom"] = [
                    item for item in state.get("custom", ())
                    if str(item.get("key")) != key
                ]
                self._restore_table(table_id)
            else:
                hidden = list(state.get("hidden", ()))
                if key not in hidden:
                    hidden.append(key)
                state["hidden"] = hidden
                logical = self._logical_for_key(self.tables[table_id], key)
                if logical >= 0:
                    self.tables[table_id].setColumnHidden(logical, True)
            self._save()

        self._record("Remove table column", operation)

    def restore_column(self, table_id: str, key: str) -> None:
        def operation() -> None:
            state = self._mark_modified(table_id)
            state["hidden"] = [
                value for value in state.get("hidden", ()) if str(value) != key
            ]
            logical = self._logical_for_key(self.tables[table_id], key)
            if logical >= 0:
                self.tables[table_id].setColumnHidden(logical, False)
            self._save()

        self._record("Restore table column", operation)

    def _save(self) -> None:
        if self._restoring:
            return
        self.settings.setValue(self.SETTINGS_KEY, json.dumps(self._state))

    def _capture_table(self, table_id: str) -> None:
        table = self.tables.get(table_id)
        if table is None:
            return
        header = table.horizontalHeader()
        existing = self._mark_modified(table_id)
        existing["order"] = [
            self._serialized_key(self._column_key(table, header.logicalIndex(visual)))
            for visual in range(header.count())
        ]
        existing["widths"] = {
            str(self._serialized_key(self._column_key(table, logical))):
                header.sectionSize(logical)
            for logical in range(header.count())
        }
        existing["hidden"] = [
            self._column_key(table, logical)
            for logical in range(header.count())
            if table.isColumnHidden(logical)
        ]
        existing.setdefault("custom", [])

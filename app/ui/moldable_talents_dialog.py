"""Neutral editor for ordered talent slots supplied by class features."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.content import magic_entries, martial_entries
from app.exploitant_rules import validate_moldable_entries
from app.sphere_rules import base_sphere_choice_label, base_sphere_choice_options
from app.talent_sorting import talent_entry_sort_key


class MoldableTalentsDialog(QDialog):
    """Edit all Moldable slots as one atomic ordered build."""

    def __init__(
        self,
        repository,
        character_id: int,
        capacity: int,
        parent=None,
        *,
        locked_count: int = 0,
        source_key: str = "exploitant:moldable-talents",
        validator: Callable | None = None,
        feature_name: str = "Moldable Talents",
        instructions: str = "",
        allowed_kinds: tuple[str, ...] = ("martial", "magic"),
        allow_base_spheres: bool = True,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id = character_id
        self.capacity = max(0, int(capacity))
        self.locked_count = max(0, int(locked_count))
        self.source_key = str(source_key)
        self.validator = validator or validate_moldable_entries
        self.feature_name = str(feature_name)
        self.allowed_kinds = frozenset(str(value) for value in allowed_kinds)
        self.allow_base_spheres = bool(allow_base_spheres)
        self._match_count = 0
        self.selections = [
            {
                "talent_kind": item.talent_kind,
                "catalog_key": item.catalog_key,
                "name": item.name,
                "sphere": item.sphere,
                "category": item.category,
                "description": item.description,
                "choice": item.choice,
                "choice_key": item.choice_key,
            }
            for item in repository.list_flexible_talent_selections(
                character_id, self.source_key
            )[: self.capacity]
        ]
        self._entries = tuple(sorted(
            (
                *(
                    {**entry, "talent_kind": "martial"}
                    for entry in martial_entries()
                    if "martial" in self.allowed_kinds
                ),
                *(
                    {**entry, "talent_kind": "magic"}
                    for entry in magic_entries()
                    if "magic" in self.allowed_kinds
                ),
            ),
            key=talent_entry_sort_key,
        ))
        self._by_key = {
            (str(entry["talent_kind"]), str(entry["key"])): entry
            for entry in self._entries
        }
        self._search_text={key:" ".join(str(entry.get(field) or "") for field in
            ("name","sphere","category","description","prerequisites")).casefold()
            for key,entry in self._by_key.items()}
        self.setWindowTitle(f"Choose {self.feature_name}")
        self.resize(1560, 840)
        layout = QVBoxLayout(self)
        title = QLabel(self.feature_name.upper())
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        summary = QLabel(instructions or (
            "Slots are resolved from top to bottom. A temporary base sphere chosen "
            "in one slot unlocks that sphere's talents in later slots."
        ))
        summary.setObjectName("mutedText")
        summary.setWordWrap(True)
        layout.addWidget(summary)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        slots_panel = QWidget()
        slots_layout = QVBoxLayout(slots_panel)
        slots_layout.setContentsMargins(0, 0, 0, 0)
        slots_layout.addWidget(QLabel(f"CURRENT SLOTS · {self.capacity} AVAILABLE"))
        self.slots = QTableWidget(self.capacity, 4)
        self.slots.setHorizontalHeaderLabels(("#", "Talent", "Sphere", "Type"))
        self.slots.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.slots.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.slots.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.slots.verticalHeader().setVisible(False)
        self.slots.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.slots.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.slots.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.slots.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        slots_layout.addWidget(self.slots, 1)
        slot_actions = QHBoxLayout()
        self.clear_button = QPushButton("Clear selected slot")
        self.clear_button.clicked.connect(self._clear_slot)
        self.clear_all_button = QPushButton("Clear unlocked slots")
        self.clear_all_button.clicked.connect(self._clear_all)
        slot_actions.addWidget(self.clear_button)
        slot_actions.addWidget(self.clear_all_button)
        slots_layout.addLayout(slot_actions)
        split.addWidget(slots_panel)

        catalog = QWidget()
        catalog_layout = QVBoxLayout(catalog)
        catalog_layout.setContentsMargins(0, 0, 0, 0)
        filters = QGridLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search talent names, spheres, types, and descriptions…")
        self.kind = QComboBox()
        if len(self.allowed_kinds) > 1:
            self.kind.addItem("Martial and magic", "")
        if "martial" in self.allowed_kinds:
            self.kind.addItem("Martial", "martial")
        if "magic" in self.allowed_kinds:
            self.kind.addItem("Magic", "magic")
        self.sphere = QComboBox()
        self.sphere.addItem("All spheres", "")
        for value in sorted(
            {str(entry.get("sphere") or "") for entry in self._entries if entry.get("sphere")},
            key=str.casefold,
        ):
            self.sphere.addItem(value, value)
        filters.addWidget(QLabel("Find"), 0, 0)
        filters.addWidget(self.search, 0, 1)
        filters.addWidget(QLabel("Kind"), 0, 2)
        filters.addWidget(self.kind, 0, 3)
        filters.addWidget(QLabel("Sphere"), 0, 4)
        filters.addWidget(self.sphere, 0, 5)
        filters.setColumnStretch(1, 1)
        catalog_layout.addLayout(filters)
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(("Talent", "Sphere", "Type", "Kind"))
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results.setAlternatingRowColors(True)
        self.results.setWordWrap(True)
        self.results.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.slots.setWordWrap(True)
        self.slots.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.results.verticalHeader().setVisible(False)
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.results.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        catalog_split = QSplitter(Qt.Orientation.Vertical)
        catalog_split.addWidget(self.results)
        catalog_split.addWidget(self.details)
        catalog_split.setSizes([560, 220])
        catalog_layout.addWidget(catalog_split, 1)
        self.use_button = QPushButton("Place in selected / next slot")
        self.use_button.setObjectName("primaryButton")
        self.use_button.setAutoDefault(False)
        self.use_button.clicked.connect(self._place_current)
        catalog_layout.addWidget(self.use_button)
        self.status=QLabel()
        self.status.setObjectName("mutedText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        split.addWidget(catalog)
        split.setSizes([520, 1000])
        layout.addWidget(split, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.search_timer=QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(400)
        self.search_timer.timeout.connect(self._refresh_results)
        self.search.textChanged.connect(lambda:self.search_timer.start())
        self.kind.currentIndexChanged.connect(self._refresh_results)
        self.sphere.currentIndexChanged.connect(self._refresh_results)
        self.results.itemSelectionChanged.connect(self._show_details)
        self.results.itemDoubleClicked.connect(self._place_current)
        self.results.installEventFilter(self)
        self.slots.installEventFilter(self)
        self.slots.itemSelectionChanged.connect(self._update_controls)
        self._refresh_slots()
        self._refresh_results()

    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.KeyPress:
            if watched is self.results and event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
                self._place_current()
                return True
            if watched is self.slots and event.key()==Qt.Key.Key_Delete:
                self._clear_slot()
                return True
        return super().eventFilter(watched,event)

    def _target_slot(self) -> int | None:
        selected = self.slots.currentRow()
        if selected >= 0:
            if selected < self.locked_count:
                return None
            return min(selected,len(self.selections)) if len(self.selections)<self.capacity else selected
        if len(self.selections) < self.capacity:
            return len(self.selections)
        return None

    def _refresh_slots(self) -> None:
        self.slots.clearContents()
        for row in range(self.capacity):
            selection = self.selections[row] if row < len(self.selections) else None
            values = (
                str(row + 1),
                (str(selection.get("name") or "") +
                 (f" — {selection['choice']}" if selection.get("choice") else "")) if selection else "Empty",
                str(selection.get("sphere") or "") if selection else "—",
                str(selection.get("talent_kind") or "").title() if selection else "—",
            )
            background = None
            if selection:
                background = QColor(
                    "#FBE2D5" if selection["talent_kind"] == "martial" else "#DAE9F8"
                )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if background is not None:
                    item.setBackground(background)
                    item.setForeground(QColor("#252C35"))
                if row < self.locked_count:
                    item.setForeground(QColor("#59616B"))
                    item.setToolTip("This slot can be replaced after a full rest.")
                elif selection:
                    item.setToolTip(str(selection.get("description") or ""))
                self.slots.setItem(row, column, item)
        self.slots.resizeRowsToContents()
        self._update_controls()

    def _update_controls(self):
        target=self._target_slot()
        self.use_button.setEnabled(target is not None and self._current_entry() is not None)
        row=self.slots.currentRow()
        self.clear_button.setEnabled(self.locked_count<=row<len(self.selections))
        self.clear_all_button.setEnabled(len(self.selections)>self.locked_count)
        self.status.setText(f"{len(self.selections)} / {self.capacity} slots filled · {self.locked_count} locked until rest")
        self.status.setText(self.status.text() +
                            f" · {self._match_count} matches, showing {self.results.rowCount()}")

    def _refresh_results(self, *_args) -> None:
        query = self.search.text().strip().casefold()
        kind = str(self.kind.currentData() or "")
        sphere = str(self.sphere.currentData() or "")
        self.results.setRowCount(0)
        matches=[]
        for entry in self._entries:
            if "drawback" in str(entry.get("category") or "").casefold():
                continue
            if not self.allow_base_spheres and entry.get("category") == "Base Sphere":
                continue
            if kind and entry["talent_kind"] != kind:
                continue
            if sphere and entry.get("sphere") != sphere:
                continue
            haystack=self._search_text[(str(entry["talent_kind"]),str(entry["key"]))]
            if query and query not in haystack:
                continue
            matches.append(entry)
        # Bound row-widget work; filtering still searches the complete catalog.
        visible=matches[:350]
        self._match_count = len(matches)
        self.results.setUpdatesEnabled(False)
        self.results.setRowCount(len(visible))
        for row,entry in enumerate(visible):
            values = (
                str(entry.get("name") or ""),
                str(entry.get("sphere") or ""),
                str(entry.get("category") or "Talent"),
                str(entry["talent_kind"]).title(),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    (str(entry["talent_kind"]), str(entry["key"])),
                )
                self.results.setItem(row, column, item)
                item.setToolTip(str(entry.get("description") or ""))
        self.results.resizeRowsToContents()
        self.results.setUpdatesEnabled(True)
        self.results.clearSelection()
        self.results.setCurrentCell(-1, -1)
        self.details.clear()
        self._update_controls()

    def _current_entry(self):
        row = self.results.currentRow()
        item = self.results.item(row, 0) if row >= 0 else None
        return self._by_key.get(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _show_details(self) -> None:
        self._update_controls()
        entry = self._current_entry()
        if entry is None:
            self.details.clear()
            return
        self.details.setPlainText(
            f"{entry['name']}\n{str(entry['talent_kind']).title()} · "
            f"{entry.get('sphere', '')} · {entry.get('category', '')}\n\n"
            f"{entry.get('description', '')}\n\nPrerequisites: {entry.get('prerequisites') or 'None listed'}"
        )

    def _selection_record(self, entry: dict) -> dict | None:
        record = {
            "talent_kind": str(entry["talent_kind"]),
            "catalog_key": str(entry["key"]),
            "name": str(entry.get("name") or ""),
            "sphere": str(entry.get("sphere") or ""),
            "category": str(entry.get("category") or "Talent"),
            "description": str(entry.get("description") or ""),
            "choice": "",
            "choice_key": "",
        }
        if self.allow_base_spheres and record["category"] == "Base Sphere":
            options = base_sphere_choice_options(record["sphere"], record["talent_kind"])
            if options:
                value, accepted = QInputDialog.getItem(
                    self,
                    "Choose base-sphere option",
                    base_sphere_choice_label(record["sphere"], record["talent_kind"]),
                    list(options),
                    0,
                    False,
                )
                if not accepted:
                    return None
                record["choice"] = str(value)
                record["choice_key"] = str(value).strip().casefold().replace(" ", "_")
        automation = entry.get("automation") or {}
        choice_type = str(automation.get("choice_type") or "")
        if choice_type and not record["choice"]:
            # Import locally to keep the reusable rules dialog independent from
            # the large catalog module's import graph.
            from app.ui.dialogs import FeatChoiceDialog

            picker = FeatChoiceDialog(
                choice_type,
                str(automation.get("choice_label") or "Choice"),
                self.repository.list_attacks(self.character_id),
                self.repository.list_equipment(self.character_id),
                self,
            )
            if picker.exec() != QDialog.DialogCode.Accepted:
                return None
            record["choice"] = picker.choice
            record["choice_key"] = picker.choice_key
        return record

    def _place_current(self, *_args) -> None:
        entry = self._current_entry()
        target = self._target_slot()
        if entry is None or target is None:
            return
        record = self._selection_record(entry)
        if record is None:
            return
        proposed = list(self.selections)
        if target<len(proposed):proposed[target]=record
        else:proposed.append(record)
        try:
            validated = list(self.validator(
                self.repository, self.character_id, proposed
            ))
        except ValueError as error:
            QMessageBox.information(self, "Talent unavailable", str(error))
            return
        # Preserve unrelated later slots. If a dependency becomes invalid,
        # reject the whole staged change rather than silently deleting talents.
        self.selections = validated
        self._refresh_slots()
        if len(self.selections) < self.capacity:
            self.slots.setCurrentCell(len(self.selections), 1)
        else:
            self.slots.clearSelection()
            self.slots.setCurrentCell(-1,-1)
        self._update_controls()

    def _clear_slot(self) -> None:
        row = self.slots.currentRow()
        if not self.locked_count <= row < len(self.selections):
            return
        proposed=self.selections[:row]+self.selections[row+1:]
        try:
            self.selections=list(self.validator(self.repository,self.character_id,proposed))
        except ValueError as error:
            QMessageBox.information(self,"Dependent talent",f"Nothing was removed. Remove or replace the dependent talent first.\n\n{error}")
            return
        self._refresh_slots()

    def _clear_all(self) -> None:
        self.selections = self.selections[: self.locked_count]
        self._refresh_slots()

    def _accept(self) -> None:
        try:
            self.selections = list(self.validator(
                self.repository, self.character_id, self.selections
            ))
        except ValueError as error:
            QMessageBox.warning(self, f"Invalid {self.feature_name}", str(error))
            return
        self.accept()

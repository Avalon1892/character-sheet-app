"""A bounded catalog browser beside an explicitly saved encounter draft."""
from __future__ import annotations

import sqlite3
from html import escape

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.bestiary import BestiaryFilters, BestiaryIndex, creature_html, filter_options
from app.catalogs import DEFAULT_CATALOG
from app.encounters import DIFFICULTIES, ENCOUNTER_RULES_URL, EncounterRepository, encounter_budget, parse_party_levels
from app.ui.components import DebouncedCallback
from app.ui.reference_details import reference_document_html
from app.ui.filter_controls import CapabilityFilter, MultiChoiceFilter


class BestiaryDialog(QDialog):
    open_codex = Signal(str)

    def __init__(self, repository: EncounterRepository, parent=None, *, catalog=DEFAULT_CATALOG):
        super().__init__(parent)
        self.setWindowTitle("Bestiary & Encounters")
        self.resize(1540, 900)
        self.setMinimumSize(1060, 650)
        self.repository = repository
        self.catalog = catalog
        self.index = BestiaryIndex(catalog.bestiary_entries())
        self.entries = {entry["key"]: entry for entry in self.index.entries}
        self.members: dict[str, int] = {}
        self.encounter_id = None
        self._dirty = False
        layout = QVBoxLayout(self)
        heading = QLabel("BESTIARY & ENCOUNTERS")
        heading.setObjectName("heroTitle")
        layout.addWidget(heading)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search creatures… (use ; for alternatives)")
        self.search_mode = QComboBox()
        for title, key in (("Name", "name"), ("Rules text", "description"), ("Name & rules", "both")):
            self.search_mode.addItem(title, key)
        self.sort = QComboBox()
        for title, key in (("Name A–Z", "name"), ("CR: low to high", "cr"), ("CR: high to low", "cr_desc")):
            self.sort.addItem(title, key)
        self.minimum_cr = self._cr_combo("Min CR")
        self.maximum_cr = self._cr_combo("Max CR")
        cr_values = {entry["cr"]: entry.get("cr_value") for entry in self.index.entries}
        self.cr_choices = MultiChoiceFilter(sorted(cr_values, key=lambda value: (cr_values[value] is None, cr_values[value] or 0)), empty_text="Any CR")
        self.more_filters = QPushButton("More filters")
        self.more_filters.setCheckable(True)
        reset = QPushButton("Reset filters")
        search_row.addWidget(self.search, 1)
        for widget in (self.search_mode, self.minimum_cr, self.maximum_cr, self.cr_choices, self.sort, self.more_filters, reset):
            search_row.addWidget(widget)
        layout.addLayout(search_row)
        self.filter_box = QGroupBox("Any selected option within each filter · all filters must match · separate text alternatives with ;")
        grid = QGridLayout(self.filter_box)
        self.combos = {}
        for index, (field, label) in enumerate((
            ("kinds", "Entry kind"), ("type", "Creature type"), ("subtypes", "Subtype"),
            ("size", "Size"), ("alignment", "Alignment"), ("movement", "Movement"),
        )):
            combo = MultiChoiceFilter(self.index.values(field))
            combo.setProperty("filterLabel", label)
            combo.setMinimumWidth(130)
            self.combos[field] = combo
            row, column = divmod(index, 3)
            grid.addWidget(QLabel(label), row, column * 2)
            grid.addWidget(combo, row, column * 2 + 1)
        self.text_filters = {}
        for index, (field, label, example) in enumerate((
            ("environment", "Location / environment", "forest; desert; underground"),
            ("abilities", "Special abilities", "poison; pounce; regeneration"),
            ("defenses", "Defenses", "fire; DR; spell resistance"),
            ("source", "Publication", "Bestiary 2; NPC Codex"),
        )):
            edit = QLineEdit()
            edit.setProperty("filterLabel", label)
            edit.setPlaceholderText(example)
            edit.setToolTip("Separate alternatives with ;. Matching any one is enough. Leave empty for no restriction.")
            self.text_filters[field] = edit
            row, column = divmod(index, 2)
            grid.addWidget(QLabel(label), row + 2, column * 3)
            grid.addWidget(edit, row + 2, column * 3 + 1, 1, 2)
        role_row = QHBoxLayout()
        role_row.addWidget(QLabel("Capabilities:"))
        self.roles = {}
        for role in ("Melee", "Ranged", "Caster"):
            check = CapabilityFilter(role)
            self.roles[role] = check
            role_row.addWidget(check)
        self.roles["Caster"].setStatusTip("Published spells, extracts, psychic magic, or spell-like abilities.")
        role_row.addWidget(QLabel("— any   ✓ must have   ✕ must not have"))
        self.legacy = QCheckBox("Include legacy 3.5 entries")
        self.legacy.setChecked(True)
        role_row.addStretch()
        role_row.addWidget(self.legacy)
        grid.addLayout(role_row, 4, 0, 1, 6)
        layout.addWidget(self.filter_box)
        self.filter_box.hide()
        self.more_filters.toggled.connect(self.filter_box.setVisible)
        self.active_filters = QLabel()
        self.active_filters.setWordWrap(True)
        self.active_filters.setTextFormat(Qt.TextFormat.RichText)
        self.active_filters.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.active_filters.setToolTip("Activate a filter link to remove only that value.")
        self.active_filters.linkActivated.connect(self._remove_active_filter)
        self._filter_removals = {}
        layout.addWidget(self.active_filters)
        self.result_count = QLabel()
        self.result_count.setWordWrap(True)
        layout.addWidget(self.result_count)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter = splitter
        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        results_layout.setContentsMargins(0, 0, 0, 0)
        self.results = self._table(("Creature", "CR", "Type"))
        self.results.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.results.setColumnWidth(2, 125)
        results_layout.addWidget(self.results, 1)
        add_row = QHBoxLayout()
        self.add_quantity = QSpinBox()
        self.add_quantity.setRange(1, 999)
        self.add_quantity.setPrefix("Qty ")
        self.add_button = QPushButton("Add to encounter")
        self.add_button.setObjectName("primaryButton")
        self.add_button.setEnabled(False)
        add_row.addWidget(self.add_quantity)
        add_row.addWidget(self.add_button, 1)
        results_layout.addLayout(add_row)
        details_panel = QWidget()
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(0, 0, 0, 0)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        details_layout.addWidget(self.details, 1)
        self.codex_button = QPushButton("Open in Codex")
        self.codex_button.setEnabled(False)
        details_layout.addWidget(self.codex_button)
        encounter_panel = QWidget()
        encounter_layout = QVBoxLayout(encounter_panel)
        encounter_layout.setContentsMargins(0, 0, 0, 0)
        encounter_layout.addWidget(QLabel("ENCOUNTER"))
        form = QFormLayout()
        self.encounter_name = QLineEdit("New encounter")
        self.party_levels = QLineEdit("1, 1, 1, 1")
        self.party_levels.setToolTip("One character level per party member, separated by commas.")
        self.difficulty = QComboBox()
        self.difficulty.addItems(DIFFICULTIES)
        self.difficulty.setCurrentText("Average")
        form.addRow("Name", self.encounter_name)
        form.addRow("Party levels", self.party_levels)
        form.addRow("Target", self.difficulty)
        encounter_layout.addLayout(form)
        self.encounter_table = self._table(("Creature", "Qty", "XP"))
        self.encounter_table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2):
            self.encounter_table.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        encounter_layout.addWidget(self.encounter_table, 1)
        edit_row = QHBoxLayout()
        self.member_quantity = QSpinBox()
        self.member_quantity.setRange(1, 999)
        self.member_quantity.setPrefix("Qty ")
        self.member_quantity.setEnabled(False)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setEnabled(False)
        clear = QPushButton("Clear")
        for widget in (self.member_quantity, self.remove_button, clear):
            edit_row.addWidget(widget)
        encounter_layout.addLayout(edit_row)
        self.budget = QLabel()
        self.budget.setWordWrap(True)
        self.budget.setTextFormat(Qt.TextFormat.PlainText)
        encounter_layout.addWidget(self.budget)
        rules = QPushButton("Encounter guidelines ↗")
        rules.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(ENCOUNTER_RULES_URL)))
        encounter_layout.addWidget(rules)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Encounter notes…")
        self.notes.setMaximumHeight(90)
        encounter_layout.addWidget(self.notes)
        save_row = QHBoxLayout()
        for title, callback in (("Save", self._save), ("Save copy", lambda: self._save(copy=True)), ("Load", self._load)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            save_row.addWidget(button)
        encounter_layout.addLayout(save_row)
        manage_row = QHBoxLayout()
        for title, callback in (("New", self._new), ("Delete saved…", self._delete)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            manage_row.addWidget(button)
        encounter_layout.addLayout(manage_row)
        self.save_status = QLabel()
        self.save_status.setWordWrap(True)
        encounter_layout.addWidget(self.save_status)
        for panel in (results_panel, details_panel, encounter_panel):
            splitter.addWidget(panel)
        splitter.setChildrenCollapsible(False)
        splitter.setSizes([470, 600, 380])
        layout.addWidget(splitter, 1)
        self.debounce = DebouncedCallback(self.refresh_results, 400, self)
        for edit in (self.search, *self.text_filters.values()):
            edit.textChanged.connect(self.debounce.schedule)
        for combo in (self.search_mode, self.sort, self.minimum_cr, self.maximum_cr):
            combo.currentIndexChanged.connect(self.debounce.schedule)
        for combo in (*self.combos.values(), self.cr_choices):
            combo.selectionChanged.connect(self.debounce.schedule)
        for check in self.roles.values():
            check.stateChanged.connect(self.debounce.schedule)
        self.legacy.toggled.connect(self.debounce.schedule)
        reset.clicked.connect(self._reset_filters)
        self.results.currentItemChanged.connect(self._preview_result)
        self.results.itemActivated.connect(lambda *_: self._add())
        self.add_button.clicked.connect(self._add)
        self.codex_button.clicked.connect(self._codex)
        self.encounter_table.currentItemChanged.connect(self._select_member)
        self.member_quantity.valueChanged.connect(self._change_quantity)
        self.remove_button.clicked.connect(self._remove)
        clear.clicked.connect(self._clear)
        self.encounter_name.textChanged.connect(self._mark_dirty)
        self.party_levels.textChanged.connect(self._draft_changed)
        self.difficulty.currentIndexChanged.connect(self._draft_changed)
        self.notes.textChanged.connect(self._mark_dirty)
        self.refresh_results()
        self._refresh_encounter()

    @staticmethod
    def _cr_combo(title):
        from fractions import Fraction
        combo = QComboBox()
        combo.addItem(title, None)
        for value in ("1/8", "1/6", "1/4", "1/3", "1/2", *(str(n) for n in range(0, 41))):
            combo.addItem(value, float(Fraction(value)))
        return combo

    @staticmethod
    def _table(headers):
        table = QTreeWidget()
        table.setObjectName("bestiaryTable")
        table.setHeaderLabels(headers)
        table.setRootIsDecorated(False)
        table.header().setStretchLastSection(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setWordWrap(True)
        return table

    def refresh_results(self):
        filters = BestiaryFilters(
            minimum_cr=self.minimum_cr.currentData(), maximum_cr=self.maximum_cr.currentData(),
            kind=self.combos["kinds"].selected_values(), creature_type=self.combos["type"].selected_values(),
            subtype=self.combos["subtypes"].selected_values(), size=self.combos["size"].selected_values(),
            alignment=self.combos["alignment"].selected_values(), movement=self.combos["movement"].selected_values(),
            challenge_ratings=self.cr_choices.selected_values(),
            roles=tuple(role for role, check in self.roles.items() if check.state == 1),
            excluded_roles=tuple(role for role, check in self.roles.items() if check.state == -1),
            include_legacy=self.legacy.isChecked(), **{field: edit.text() for field, edit in self.text_filters.items()},
        )
        result = self.index.search(self.search.text(), self.search_mode.currentData(), filters, self.sort.currentData())
        self.results.clear()
        for entry in result.records:
            row = QTreeWidgetItem((entry["name"], entry["cr"], entry["type"]))
            row.setData(0, Qt.ItemDataRole.UserRole, entry["key"])
            row.setToolTip(0, f'{entry["name"]}\n{entry["environment"]}\n{entry["source"]}')
            self.results.addTopLevelItem(row)
        suffix = " · showing first 300; narrow your search" if result.limited else ""
        if filters.minimum_cr is not None and filters.maximum_cr is not None and filters.minimum_cr > filters.maximum_cr:
            suffix = " · Minimum CR exceeds maximum CR. Remove or adjust either limit."
        elif not result.total:
            suffix = " · Remove an active filter below the search bar, or reset filters to broaden your search."
        self.result_count.setText(f"{result.total:,} matching creatures{suffix}")
        self._refresh_active_filters()
        self._preview_result(None)

    def _refresh_active_filters(self):
        self._filter_removals = {}
        links = []
        color = self.active_filters.palette().color(self.active_filters.foregroundRole()).name()

        def add(label, callback):
            key = str(len(links))
            self._filter_removals[key] = callback
            links.append(f'<a href="{key}" style="color:{color}">{escape(label)} ×</a>')

        for control in (*self.combos.values(), self.cr_choices):
            for value in control.selected_values():
                add(f'{control.property("filterLabel") or "CR"}: {value}',
                    lambda control=control, value=value: control.set_selected_values(
                        tuple(item for item in control.selected_values() if item != value)))
        for edit in (self.search, *self.text_filters.values()):
            for value in dict.fromkeys(filter_options(edit.text())):
                label = edit.property("filterLabel") or f"Search ({self.search_mode.currentText()})"
                add(f"{label}: {value}", lambda edit=edit, value=value: edit.setText(
                    "; ".join(item for item in filter_options(edit.text()) if item != value)))
        for title, combo in (("Min CR", self.minimum_cr), ("Max CR", self.maximum_cr)):
            if combo.currentData() is not None:
                add(f"{title}: {combo.currentText()}", lambda combo=combo: combo.setCurrentIndex(0))
        for role, control in self.roles.items():
            if control.state:
                add(f'{"Required" if control.state == 1 else "Excluded"}: {role}',
                    lambda control=control: control.set_state(0))
        if not self.legacy.isChecked():
            add("Exclude legacy 3.5", lambda: self.legacy.setChecked(True))
        self.active_filters.setText("<b>Active filters — click to remove:</b> " + " &nbsp; · &nbsp; ".join(links))
        self.active_filters.setVisible(bool(links))

    def _remove_active_filter(self, key):
        callback = self._filter_removals.get(key)
        if callback is not None:
            callback()
            self.debounce.flush()

    def _reset_filters(self):
        for edit in (self.search, *self.text_filters.values()):
            edit.clear()
        for combo in (self.search_mode, self.sort, self.minimum_cr, self.maximum_cr):
            combo.setCurrentIndex(0)
        for combo in (*self.combos.values(), self.cr_choices):
            combo.clear()
        for check in self.roles.values():
            check.set_state(0)
        self.legacy.setChecked(True)
        self.debounce.flush()

    def _preview_result(self, item, _previous=None):
        key = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.details.setHtml(reference_document_html(self, creature_html(self.entries.get(key))))
        self.add_button.setEnabled(key in self.entries)
        self.codex_button.setEnabled(key in self.entries)

    def _codex(self):
        item = self.results.currentItem()
        if item:
            self.open_codex.emit(item.data(0, Qt.ItemDataRole.UserRole))

    def _add(self):
        item = self.results.currentItem()
        if not item:
            return
        key = item.data(0, Qt.ItemDataRole.UserRole)
        quantity = self.members.get(key, 0) + self.add_quantity.value()
        if quantity > 999:
            self.save_status.setText("Maximum 999 of each creature per encounter.")
            return
        self.members[key] = quantity
        self._mark_dirty()
        self._refresh_encounter(key)

    def _select_member(self, item, _previous=None):
        key = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.member_quantity.setEnabled(key in self.members)
        self.remove_button.setEnabled(key in self.members)
        self.member_quantity.blockSignals(True)
        self.member_quantity.setValue(self.members.get(key, 1))
        self.member_quantity.blockSignals(False)
        if key:
            self.details.setHtml(reference_document_html(self, creature_html(self.entries.get(key))))

    def _change_quantity(self, value):
        item = self.encounter_table.currentItem()
        if item:
            key = item.data(0, Qt.ItemDataRole.UserRole)
            self.members[key] = value
            self._mark_dirty()
            self._refresh_encounter(key)

    def _remove(self):
        item = self.encounter_table.currentItem()
        if item:
            self.members.pop(item.data(0, Qt.ItemDataRole.UserRole), None)
            self._mark_dirty()
            self._refresh_encounter()

    def _clear(self):
        if self.members and QMessageBox.question(self, "Clear encounter", "Remove every creature from this encounter draft?") == QMessageBox.StandardButton.Yes:
            self.members.clear()
            self._mark_dirty()
            self._refresh_encounter()

    def _refresh_encounter(self, selected_key=None):
        self.encounter_table.clear()
        for key, quantity in self.members.items():
            entry = self.entries.get(key, {})
            xp = entry.get("xp")
            item = QTreeWidgetItem((entry.get("name", "Missing: " + key), str(quantity), f"{xp * quantity:,}" if xp is not None else "Unknown"))
            item.setData(0, Qt.ItemDataRole.UserRole, key)
            self.encounter_table.addTopLevelItem(item)
            if key == selected_key:
                self.encounter_table.setCurrentItem(item)
        self._update_budget()

    def _update_budget(self):
        try:
            budget = encounter_budget(self.entries, self.members, parse_party_levels(self.party_levels.text()), self.difficulty.currentText())
            target = f"{budget.target_xp:,} XP" if budget.target_xp is not None else "outside the reference table"
            count = sum(self.members.values())
            text = (f"{count} {'creature' if count == 1 else 'creatures'} · {budget.xp:,} {'known ' if budget.unknown else ''}XP\n"
                    f"{budget.equivalent_cr}\nAPL {budget.apl} · Target CR {budget.target_cr}: {target}")
            if budget.unknown:
                text += "\nXP missing: " + ", ".join(budget.unknown)
            self.budget.setText(text)
        except ValueError as exc:
            self.budget.setText(str(exc))

    def _mark_dirty(self, *_args):
        self._dirty = True
        self.save_status.setText("Unsaved changes")

    def _draft_changed(self, *_args):
        self._mark_dirty()
        self._update_budget()

    def _save(self, _checked=False, *, copy=False):
        try:
            self.encounter_id = self.repository.save(
                self.encounter_name.text(), self.members, parse_party_levels(self.party_levels.text()),
                self.difficulty.currentText(), self.notes.toPlainText(), None if copy else self.encounter_id)
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Encounter not saved", str(exc))
            return False
        self._dirty = False
        self.save_status.setText("Encounter saved")
        return True

    def _can_discard(self):
        if not self._dirty:
            return True
        answer = QMessageBox.question(self, "Unsaved encounter", "Save changes to this encounter?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        return self._save() if answer == QMessageBox.StandardButton.Save else answer == QMessageBox.StandardButton.Discard

    def _load(self):
        rows = self.repository.list()
        if not rows:
            self.save_status.setText("No saved encounters yet.")
            return
        labels = [f"{name} (#{key})" for key, name in rows]
        value, ok = QInputDialog.getItem(self, "Load encounter", "Encounter", labels, 0, False)
        if not ok or not self._can_discard():
            return
        key = rows[labels.index(value)][0]
        try:
            data = self.repository.load(key)
        except (ValueError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Encounter not loaded", str(exc))
            return
        self.encounter_id = key
        self.members = dict(data["members"])
        self.encounter_name.setText(data["name"])
        self.party_levels.setText(", ".join(map(str, data["levels"])))
        self.difficulty.setCurrentText(data["difficulty"])
        self.notes.setPlainText(data["notes"])
        self._refresh_encounter()
        self._dirty = False
        self.save_status.setText("Encounter loaded")

    def _new(self):
        if not self._can_discard():
            return
        self.encounter_id = None
        self.members.clear()
        self.encounter_name.setText("New encounter")
        self.notes.clear()
        self._refresh_encounter()
        self._dirty = False
        self.save_status.clear()

    def _delete(self):
        if self.encounter_id is None:
            self.save_status.setText("This draft has not been saved.")
            return
        if QMessageBox.question(self, "Delete saved encounter", "Delete this saved encounter? The current draft will remain open.") == QMessageBox.StandardButton.Yes:
            try:
                self.repository.delete(self.encounter_id)
            except sqlite3.Error as exc:
                QMessageBox.warning(self, "Encounter not deleted", str(exc))
                return
            self.encounter_id = None
            self._dirty = True
            self.save_status.setText("Saved encounter deleted; draft retained")

    def reject(self):
        if self._can_discard():
            super().reject()

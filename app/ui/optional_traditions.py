"""Reusable optional-tradition picker and movable sheet section."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QDialog, QDialogButtonBox,
    QLineEdit, QListWidget, QTextBrowser, QSplitter, QPlainTextEdit, QInputDialog,
)
from app.optional_traditions import OptionalTraditionService, catalog
from app.ui.reference_details import reference_details_html


class OptionalTraditionDialog(QDialog):
    def __init__(self, kind, selected_keys=(), parent=None):
        super().__init__(parent)
        self.selected_entry = None
        self.entries = tuple(e for e in catalog()['entries']
                             if e['kind'] == kind and e['key'] not in selected_keys)
        self.setWindowTitle(f'{kind} Traditions')
        self.resize(1120, 740)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search names and descriptions…')
        layout.addWidget(self.search)
        split = QSplitter()
        self.list = QListWidget()
        self.list.setWordWrap(True)
        self.details = QTextBrowser()
        self.details.setOpenExternalLinks(True)
        split.addWidget(self.list)
        split.addWidget(self.details)
        split.setSizes([330, 750])
        layout.addWidget(split, 1)
        layout.addWidget(QLabel('Choices / GM-approved adjustments (optional)'))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText('Record associated-skill choices, chosen plane, dominant tradition, or other decisions here.')
        self.notes.setMaximumHeight(85)
        layout.addWidget(self.notes)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.confirm = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm.setText('Add tradition')
        buttons.accepted.connect(self.accept_selected)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self.refresh)
        self.list.currentRowChanged.connect(self.show_entry)
        self.list.itemDoubleClicked.connect(lambda *_: self.accept_selected())
        self.refresh()

    def refresh(self):
        query = self.search.text().strip().casefold()
        self.filtered = tuple(e for e in self.entries if not query or
                              query in (e['name'] + ' ' + e['description']).casefold())
        self.list.clear()
        self.list.addItems([e['name'] for e in self.filtered])
        self.details.clear()
        self.confirm.setEnabled(False)

    def show_entry(self, row):
        valid = 0 <= row < len(self.filtered)
        self.confirm.setEnabled(valid)
        if valid:
            self.details.setHtml(reference_details_html(self, self.filtered[row]))
        else:
            self.details.clear()

    def accept_selected(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.filtered):
            self.selected_entry = self.filtered[row]
            self.accept()


class OptionalTraditionsSection(QWidget):
    def __init__(self, sheet):
        super().__init__()
        self.sheet = sheet
        self.setObjectName('sheetSection')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.addWidget(sheet._section_title('CRAFTING & TINKER TRADITIONS'))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Name', 'Type', 'Choices / Notes'])
        self.table.setProperty('contentStretchColumns', [0, 2])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        self.table.setMinimumHeight(95)
        layout.addWidget(self.table)
        actions = QHBoxLayout()
        for kind in ('Crafting', 'Tinker'):
            button = QPushButton(f'+ {kind} tradition')
            button.setProperty('prominentAction', True)
            button.clicked.connect(lambda _=False, k=kind: self.add(k))
            actions.addWidget(button)
        self.edit_button = QPushButton('Edit choices')
        self.remove_button = QPushButton('Remove')
        self.edit_button.clicked.connect(self.edit)
        self.remove_button.clicked.connect(self.remove)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.remove_button)
        actions.addStretch()
        layout.addLayout(actions)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        self.table.cellDoubleClicked.connect(lambda *_: self.edit())
        self.update_buttons()

    def service(self):
        return OptionalTraditionService(self.sheet.repository, self.sheet.character_id)

    def current_id(self):
        item = self.table.item(self.table.currentRow(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def update_buttons(self):
        selected = self.current_id() is not None
        self.edit_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)

    def refresh(self):
        self.table.setRowCount(0)
        if self.sheet.character_id is None:
            return
        for t in self.service().selections():
            row = self.table.rowCount()
            self.table.insertRow(row)
            entry = json.loads(t.definition_json or '{}')
            notes = '\n'.join(json.loads(t.choices_json or '{}').get('Notes', []))
            for column, value in enumerate((t.name, t.kind, notes)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, t.id)
                item.setToolTip(reference_details_html(self, entry) if entry else t.name)
                self.table.setItem(row, column, item)
        self.table.resizeRowsToContents()
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.update_buttons()

    def add(self, kind):
        if self.sheet.character_id is None:
            return
        service = self.service()
        dialog = OptionalTraditionDialog(kind, {t.catalog_key for t in service.selections()}, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_entry:
            service.add(dialog.selected_entry['key'], dialog.notes.toPlainText())
            self.refresh()

    def edit(self):
        selected = next((t for t in self.service().selections() if t.id == self.current_id()), None)
        if selected is None:
            return
        previous = '\n'.join(json.loads(selected.choices_json or '{}').get('Notes', []))
        notes, accepted = QInputDialog.getMultiLineText(self, selected.name, 'Choices / GM-approved adjustments', previous)
        if accepted:
            self.service().edit(selected.id, notes)
            self.refresh()

    def remove(self):
        if self.current_id() is not None:
            self.service().remove(self.current_id())
            self.refresh()

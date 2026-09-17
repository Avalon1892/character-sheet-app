from __future__ import annotations

import html
from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.building_blocks.designer import BlockDesignerDialog
from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.registry import BlockRegistry
from app.building_blocks.schemas import BlockDefinition, SheetTab
from app.database import CharacterRepository


class BuildingBlocksDialog(QDialog):
    def __init__(
        self,
        character_repository: CharacterRepository,
        presentation: BuildingBlockRepository,
        registry: BlockRegistry,
        character_id: int,
        tabs: tuple[SheetTab, ...],
        add_block,
        parent=None,
        *,
        remove_block=None,
        current_tab_key: str = "",
    ) -> None:
        super().__init__(parent)
        self.character_repository = character_repository
        self.presentation = presentation
        self.registry = registry
        self.character_id = character_id
        self.add_block_callback = add_block
        self.remove_block_callback = remove_block
        self.setWindowTitle("Building Blocks")
        self.resize(1180, 760)
        root = QVBoxLayout(self)
        heading = QLabel("BUILDING BLOCKS")
        heading.setObjectName("heroTitle")
        root.addWidget(heading)
        subtitle = QLabel("Add built-in sheet sections or create reusable custom boxes and cells.")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)
        filters = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search names and descriptions…")
        self.category = QComboBox(); self.category.addItem("All categories", "")
        self.source = QComboBox(); self.source.addItem("Built-in and custom", ""); self.source.addItem("Built-in", "builtin"); self.source.addItem("My blocks", "custom")
        self.destination = QComboBox()
        for tab in tabs:
            if tab.visible:
                self.destination.addItem(tab.name, tab.key)
        current_index = self.destination.findData(current_tab_key)
        if current_index >= 0:
            self.destination.setCurrentIndex(current_index)
        filters.addWidget(self.search, 1); filters.addWidget(self.category); filters.addWidget(self.source); filters.addWidget(QLabel("Add to")); filters.addWidget(self.destination)
        root.addLayout(filters)
        splitter = QSplitter()
        self.results = QListWidget()
        self.preview = QTextBrowser(); self.preview.setOpenExternalLinks(False)
        splitter.addWidget(self.results); splitter.addWidget(self.preview); splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)
        actions = QHBoxLayout()
        add = QPushButton("Add / restore on selected tab"); add.setObjectName("primaryButton"); add.clicked.connect(self._add)
        self.remove_from_page = QPushButton("Remove from selected tab")
        self.remove_from_page.setObjectName("dangerButton")
        self.remove_from_page.clicked.connect(self._remove_from_page)
        create = QPushButton("Create new block…"); create.clicked.connect(self._create)
        edit = QPushButton("Edit selected…"); edit.clicked.connect(self._edit)
        duplicate = QPushButton("Duplicate as my block…"); duplicate.clicked.connect(self._duplicate)
        delete = QPushButton("Delete my template"); delete.setObjectName("dangerButton"); delete.clicked.connect(self._delete)
        for button in (add, self.remove_from_page, create, edit, duplicate, delete): actions.addWidget(button)
        actions.addStretch(); root.addLayout(actions)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); close.rejected.connect(self.reject); root.addWidget(close)
        self.search.textChanged.connect(self._refresh)
        self.category.currentIndexChanged.connect(self._refresh)
        self.source.currentIndexChanged.connect(self._refresh)
        self.destination.currentIndexChanged.connect(self._update_page_actions)
        self.results.currentItemChanged.connect(self._preview)
        self._reload_categories()
        self._refresh()

    def _definitions(self) -> tuple[BlockDefinition, ...]:
        return (*self.registry.all(), *self.presentation.list_user_templates())

    def _reload_categories(self) -> None:
        current = str(self.category.currentData() or "")
        categories = sorted({item.category for item in self._definitions()}, key=str.casefold)
        self.category.blockSignals(True); self.category.clear(); self.category.addItem("All categories", "")
        for value in categories: self.category.addItem(value, value)
        self.category.setCurrentIndex(max(0, self.category.findData(current)))
        self.category.blockSignals(False)

    def _refresh(self) -> None:
        query = self.search.text().strip().casefold()
        category = str(self.category.currentData() or "")
        source = str(self.source.currentData() or "")
        self.results.clear()
        for definition in self._definitions():
            if category and definition.category != category: continue
            if source == "builtin" and not definition.builtin: continue
            if source == "custom" and definition.builtin: continue
            haystack = f"{definition.name} {definition.description} {definition.category}".casefold()
            if query and query not in haystack: continue
            item = QListWidgetItem(f"{definition.name}\n{definition.category} · {'Built-in' if definition.builtin else 'My block'}")
            item.setData(Qt.ItemDataRole.UserRole, definition)
            self.results.addItem(item)
        if self.results.count(): self.results.setCurrentRow(0)
        else: self.preview.setHtml("<h2>No building blocks found</h2>")
        self._update_page_actions()

    def _selected(self) -> BlockDefinition | None:
        item = self.results.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _preview(self, item: QListWidgetItem | None, _previous=None) -> None:
        definition = item.data(Qt.ItemDataRole.UserRole) if item else None
        if definition is None:
            self._update_page_actions()
            return
        cells = "".join(f"<li><b>{html.escape(cell.label or cell.key)}</b> — {html.escape(cell.cell_type)}" + (f" · {html.escape(cell.binding)}" if cell.binding else "") + "</li>" for cell in definition.cells)
        self.preview.setHtml(
            f"<h1>{html.escape(definition.name)}</h1><p><b>{html.escape(definition.category)}</b> · {'Built-in' if definition.builtin else 'User-created'}</p>"
            f"<p>{html.escape(definition.description or 'No description.')}</p><p><b>Default size:</b> {definition.width} × {definition.height}</p>"
            f"<h2>Cells</h2><ul>{cells or '<li>Existing live sheet content</li>'}</ul>"
        )
        self._update_page_actions()

    def _placed_on_selected_page(self) -> tuple:
        definition = self._selected()
        tab_key = str(self.destination.currentData() or "")
        if definition is None or not tab_key:
            return ()
        return tuple(
            instance
            for instance in self.presentation.list_instances(
                self.character_id, tab_key
            )
            if instance.template_key == definition.key and instance.visible
        )

    def _update_page_actions(self, *_args) -> None:
        self.remove_from_page.setEnabled(bool(self._placed_on_selected_page()))

    def _add(self) -> None:
        definition = self._selected()
        if definition is None: return
        tab_key = str(self.destination.currentData() or "build")
        try: self.add_block_callback(definition, tab_key)
        except ValueError as error: QMessageBox.warning(self, "Cannot add block", str(error)); return
        self._update_page_actions()
        QMessageBox.information(self, "Building block added", f"{definition.name} is available on the selected tab.")

    def _remove_from_page(self) -> None:
        definition = self._selected()
        if definition is None:
            return
        tab_key = str(self.destination.currentData() or "")
        try:
            if self.remove_block_callback is not None:
                self.remove_block_callback(definition, tab_key)
            else:
                placed = self._placed_on_selected_page()
                if not placed:
                    raise ValueError("This block is not on the selected tab.")
                self.presentation.set_instance_visible(placed[-1].id, False)
        except ValueError as error:
            QMessageBox.warning(self, "Cannot remove block", str(error))
            return
        self._update_page_actions()

    def _create(self) -> None:
        dialog = BlockDesignerDialog(self.character_repository, self.character_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        key = self.presentation.unique_template_key(dialog.name.text())
        self.presentation.save_user_template(dialog.definition(key))
        self._reload_categories(); self._refresh()

    def _edit(self) -> None:
        definition = self._selected()
        if definition is None: return
        if definition.builtin:
            QMessageBox.information(self, "Built-in template", "Duplicate this built-in block to create an editable custom template.")
            return
        dialog = BlockDesignerDialog(self.character_repository, self.character_id, definition, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        self.presentation.save_user_template(dialog.definition(definition.key))
        self._reload_categories(); self._refresh()

    def _duplicate(self) -> None:
        definition = self._selected()
        if definition is None: return
        dialog = BlockDesignerDialog(self.character_repository, self.character_id, replace(definition, builtin=False, name=f"{definition.name} Copy", section_key=""), self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        key = self.presentation.unique_template_key(dialog.name.text())
        self.presentation.save_user_template(dialog.definition(key))
        self._reload_categories(); self._refresh()

    def _delete(self) -> None:
        definition = self._selected()
        if definition is None: return
        if definition.builtin:
            QMessageBox.information(self, "Built-in template", "Built-in templates cannot be deleted from the catalogue.")
            return
        answer = QMessageBox.question(self, "Delete template?", "Remove this reusable template from the catalogue? Existing placed blocks keep an embedded copy and character data is never deleted.")
        if answer != QMessageBox.StandardButton.Yes: return
        self.presentation.delete_user_template(definition.key)
        self._reload_categories(); self._refresh()

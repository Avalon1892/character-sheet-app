"""Wide drag-and-drop organizer for one character's existing inventory."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QMimeData, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QFontMetrics, QKeySequence, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.inventory_organization import (
    DEFAULT_SUBCATEGORY,
    InventoryOrganizationService,
    InventoryOrganizationSnapshot,
    OrganizedInventoryItem,
)
from app.item_enchantments import (
    enchantment_summary,
    item_display_name,
    item_market_price,
)
from app.presentation import readable_tooltip
from app.ui.components import DebouncedCallback


from app.ui.equipment_drag import INVENTORY_ITEM_MIME, WORN_MIME, SCOPE_MIME, item_mime, dropped_item
from app.equipment_wearing import EquipmentWearService
from app.item_effects import effective_item_state

def _inventory_owner(widget):
    while widget is not None and not hasattr(widget, "service"):
        widget = widget.parentWidget()
    return widget

def _foreign_equipment_drag(widget, mime):
    owner = _inventory_owner(widget)
    return (owner is not None and mime.hasFormat(SCOPE_MIME)
            and dropped_item(mime, EquipmentWearService(owner.service.repository, owner.service.character_id).scope) is None)


class InventoryDropList(QListWidget):
    item_dropped = Signal(int, str, str, int)
    worn_item_dropped = Signal(int, str, str, int)

    def __init__(
        self,
        category: str,
        subcategory: str,
        parent=None,
        *,
        container_equipment_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.category = category
        self.subcategory = subcategory
        self.container_equipment_id = container_equipment_id
        self.setObjectName("inventoryOrganizerList")
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setWordWrap(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        if item is None:
            return
        item_id = item.data(Qt.ItemDataRole.UserRole)
        if item_id is None:
            return
        owner = _inventory_owner(self)
        if owner is None:
            return
        scope = EquipmentWearService(owner.service.repository, owner.service.character_id).scope
        mime = item_mime(item_id, scope)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event) -> None:
        if _foreign_equipment_drag(self, event.mimeData()):
            event.ignore(); return
        if event.mimeData().hasFormat(INVENTORY_ITEM_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        if _foreign_equipment_drag(self, event.mimeData()):
            event.ignore(); return
        if event.mimeData().hasFormat(INVENTORY_ITEM_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:
        if _foreign_equipment_drag(self, event.mimeData()):
            event.ignore(); return
        if not event.mimeData().hasFormat(INVENTORY_ITEM_MIME):
            event.ignore()
            return
        try:
            item_id = int(bytes(event.mimeData().data(INVENTORY_ITEM_MIME)).decode("ascii"))
        except (TypeError, ValueError, UnicodeError):
            event.ignore()
            return
        signal = self.worn_item_dropped if event.mimeData().hasFormat(WORN_MIME) else self.item_dropped
        signal.emit(
            item_id,
            self.category,
            self.subcategory,
            self.container_equipment_id if self.container_equipment_id is not None else -1,
        )
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class InventoryOrganizerCanvas(QWidget):
    """Whitespace drop target that returns one item to automatic placement."""

    item_reset_requested = Signal(int)
    worn_item_reset_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if _foreign_equipment_drag(self, event.mimeData()):
            event.ignore(); return
        if event.mimeData().hasFormat(INVENTORY_ITEM_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if _foreign_equipment_drag(self, event.mimeData()):
            event.ignore(); return
        if event.mimeData().hasFormat(INVENTORY_ITEM_MIME):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if _foreign_equipment_drag(self, event.mimeData()):
            event.ignore(); return
        if not event.mimeData().hasFormat(INVENTORY_ITEM_MIME):
            event.ignore()
            return
        try:
            item_id = int(bytes(event.mimeData().data(INVENTORY_ITEM_MIME)).decode("ascii"))
        except (TypeError, ValueError, UnicodeError):
            event.ignore()
            return
        signal = self.worn_item_reset_requested if event.mimeData().hasFormat(WORN_MIME) else self.item_reset_requested
        signal.emit(item_id)
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()


class _InventorySnapshotCommand(QUndoCommand):
    def __init__(
        self,
        label: str,
        service: InventoryOrganizationService,
        before: InventoryOrganizationSnapshot,
        after: InventoryOrganizationSnapshot,
        refresh: Callable[[], None],
        usage_before=None,
        usage_after=None,
    ) -> None:
        super().__init__(label)
        self.service = service
        self.before = before
        self.after = after
        self.refresh = refresh
        self._already_applied = True
        self.usage_before = usage_before or {}
        self.usage_after = usage_after or {}

    def redo(self) -> None:
        if self._already_applied:
            self._already_applied = False
        else:
            self.service.apply_snapshot(self.after)
            for item_id, state in self.usage_after.items():
                self.service.repository.set_equipment_state(self.service.character_id, item_id, state)
        self.refresh()

    def undo(self) -> None:
        self.service.apply_snapshot(self.before)
        for item_id, state in self.usage_before.items():
            self.service.repository.set_equipment_state(self.service.character_id, item_id, state)
        self.refresh()


class InventoryOrganizerDialog(QDialog):
    """Show only occupied automatic groups plus persistent custom drop targets."""

    organization_changed = Signal()

    def __init__(
        self,
        service: InventoryOrganizationService,
        parent: QWidget | None = None,
        *,
        edit_item: Callable[[int], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.edit_item = edit_item
        self.setWindowTitle("Inventory")
        self.resize(1480, 860)
        self.setMinimumSize(1080, 620)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.group_columns: dict[str, QFrame] = {}
        self.drop_lists: dict[tuple[str, str], InventoryDropList] = {}
        self.container_drop_lists: dict[tuple[int, str, str], InventoryDropList] = {}
        self.container_columns: dict[int, QFrame] = {}
        self.undo_stack = QUndoStack(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        heading = QHBoxLayout()
        title = QLabel("INVENTORY")
        title.setObjectName("sectionTitle")
        heading.addWidget(title, 1)
        self.undo_button = QPushButton("Undo")
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undo_stack.undo)
        add_category = QPushButton("+ Custom category")
        add_category.setObjectName("primaryButton")
        add_category.clicked.connect(self._add_custom_group)
        reset = QPushButton("Reset categories")
        reset.setObjectName("dangerButton")
        reset.setToolTip("Return every item to its automatic catalog category.")
        reset.clicked.connect(self._reset_categories)
        heading.addWidget(self.undo_button)
        heading.addWidget(add_category)
        heading.addWidget(reset)
        layout.addLayout(heading)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Search this inventory"))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Search item names and details…")
        search_row.addWidget(self.search, 1)
        layout.addLayout(search_row)
        self.status = QLabel()
        self.status.setObjectName("mutedText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("inventoryOrganizerScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.canvas = InventoryOrganizerCanvas()
        self.canvas.setObjectName("inventoryOrganizerCanvas")
        self.canvas.setToolTip(
            "Drop an item on empty space to return it to its automatic category."
        )
        self.canvas.item_reset_requested.connect(self._reset_item)
        self.canvas.worn_item_reset_requested.connect(lambda item_id: self._move_unequipped_item(item_id, "", DEFAULT_SUBCATEGORY, -1))
        self.columns = QHBoxLayout(self.canvas)
        self.columns.setContentsMargins(8, 8, 8, 14)
        self.columns.setSpacing(9)
        self.columns.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        close_row.addWidget(close)
        layout.addLayout(close_row)

        self.search_debounce = DebouncedCallback(self.refresh, 300, self)
        self.search.textChanged.connect(self.search_debounce.schedule)
        self.undo_stack.canUndoChanged.connect(self.undo_button.setEnabled)
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo_stack.undo)
        self.refresh()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                InventoryOrganizerDialog._clear_layout(item.layout())

    def refresh(self) -> None:
        query = self.search.text().strip()
        groups = self.service.groups(query)
        container_groups = self.service.container_groups(query)
        self._clear_layout(self.columns)
        self.group_columns.clear()
        self.drop_lists.clear()
        self.container_drop_lists.clear()
        self.container_columns.clear()
        item_count = 0
        enchantments = self.service.repository.list_item_enchantments(
            self.service.character_id
        )
        for group in groups:
            category = QFrame()
            category.setObjectName("inventoryOrganizerCategory")
            category.setMinimumWidth(270)
            category.setMaximumWidth(320)
            category.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
            )
            category_layout = QVBoxLayout(category)
            category_layout.setContentsMargins(8, 7, 8, 8)
            category_layout.setSpacing(6)
            heading = QLabel(group.category.upper())
            heading.setObjectName("inventoryOrganizerCategoryTitle")
            heading.setWordWrap(True)
            category_layout.addWidget(heading)
            for subcategory, items in group.subcategories:
                subheading = QLabel(subcategory)
                subheading.setObjectName("inventoryOrganizerSubcategory")
                subheading.setWordWrap(True)
                category_layout.addWidget(subheading)
                drop_list = InventoryDropList(group.category, subcategory)
                drop_list.item_dropped.connect(self._move_item)
                drop_list.worn_item_dropped.connect(self._move_unequipped_item)
                drop_list.itemDoubleClicked.connect(self._item_double_clicked)
                for organized in items:
                    self._add_item(drop_list, organized, enchantments)
                    item_count += 1
                row_height = sum(
                    drop_list.item(index).sizeHint().height()
                    for index in range(drop_list.count())
                )
                drop_list.setFixedHeight(max(58, min(430, row_height + 8)))
                category_layout.addWidget(drop_list)
                self.drop_lists[(group.category, subcategory)] = drop_list
            category_layout.addStretch()
            self.columns.addWidget(category, 0, Qt.AlignmentFlag.AlignTop)
            self.group_columns[group.category] = category
        for container_group in container_groups:
            organized_container = container_group.container
            container = organized_container.item
            frame = QFrame()
            frame.setObjectName("inventoryOrganizerContainer")
            frame.setMinimumWidth(290)
            frame.setMaximumWidth(350)
            frame.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
            )
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(8, 7, 8, 8)
            frame_layout.setSpacing(6)
            heading = QLabel(container.name.upper())
            heading.setObjectName("inventoryOrganizerCategoryTitle")
            heading.setWordWrap(True)
            frame_layout.addWidget(heading)
            capacity = (
                f" / {container_group.capacity_lb:g} lb capacity"
                if container_group.capacity_lb is not None else ""
            )
            summary = QLabel(
                f"Container · {container_group.contents_weight:g} lb inside{capacity}"
            )
            summary.setObjectName("mutedText")
            summary.setWordWrap(True)
            frame_layout.addWidget(summary)
            inbox_label = QLabel("DROP ITEMS INTO THIS CONTAINER")
            inbox_label.setObjectName("inventoryOrganizerSubcategory")
            frame_layout.addWidget(inbox_label)
            inbox = InventoryDropList(
                "", DEFAULT_SUBCATEGORY, container_equipment_id=container.id
            )
            inbox.item_dropped.connect(self._move_item)
            inbox.worn_item_dropped.connect(self._move_unequipped_item)
            inbox.itemDoubleClicked.connect(self._item_double_clicked)
            inbox.setFixedHeight(58)
            frame_layout.addWidget(inbox)
            self.container_drop_lists[(container.id, "", DEFAULT_SUBCATEGORY)] = inbox
            for category_group in container_group.categories:
                category_heading = QLabel(category_group.category.upper())
                category_heading.setObjectName("inventoryOrganizerContainerCategory")
                category_heading.setWordWrap(True)
                frame_layout.addWidget(category_heading)
                for subcategory, children in category_group.subcategories:
                    subheading = QLabel(subcategory)
                    subheading.setObjectName("inventoryOrganizerSubcategory")
                    subheading.setWordWrap(True)
                    frame_layout.addWidget(subheading)
                    drop_list = InventoryDropList(
                        category_group.category,
                        subcategory,
                        container_equipment_id=container.id,
                    )
                    drop_list.item_dropped.connect(self._move_item)
                    drop_list.worn_item_dropped.connect(self._move_unequipped_item)
                    drop_list.itemDoubleClicked.connect(self._item_double_clicked)
                    for child in children:
                        self._add_item(drop_list, child, enchantments)
                        item_count += 1
                    row_height = sum(
                        drop_list.item(index).sizeHint().height()
                        for index in range(drop_list.count())
                    )
                    drop_list.setFixedHeight(max(58, min(430, row_height + 8)))
                    frame_layout.addWidget(drop_list)
                    self.container_drop_lists[
                        (container.id, category_group.category, subcategory)
                    ] = drop_list
            frame_layout.addStretch()
            self.columns.addWidget(frame, 0, Qt.AlignmentFlag.AlignTop)
            self.container_columns[container.id] = frame
        if not groups and not container_groups:
            empty = QLabel(
                "No inventory items match this search."
                if query else "This character's inventory is empty."
            )
            empty.setObjectName("mutedText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.columns.addWidget(empty)
        self.columns.addStretch()
        self.status.setText(
            f"{item_count} item entr{'y' if item_count == 1 else 'ies'} shown. "
            "Drag an item into another visible group or item container to organize it; "
            "double-click edits it and Ctrl+Z undoes changes."
        )

    def _add_item(self, target: QListWidget, organized: OrganizedInventoryItem, enchantments) -> None:
        item = organized.item
        display_name = item_display_name(item, enchantments)
        market_price = item_market_price(item, enchantments)
        text = f"{display_name}    ×{item.quantity}"
        row = QListWidgetItem(text)
        row.setData(Qt.ItemDataRole.UserRole, item.id)
        details = "\n\n".join(
            value
            for value in (
                f"{organized.category} · {organized.subcategory}",
                (
                    f"Quantity: {item.quantity}; Weight: {item.weight * item.quantity:g} lb; "
                    f"Market value: {market_price * item.quantity:g} gp"
                ),
                f"State: {item.state.replace('_', ' ').title()}; Slot: {item.slot or 'None'}",
                f"Enchantments: {enchantment_summary(item, enchantments)}",
                organized.description,
                item.notes,
            )
            if value
        )
        row.setToolTip(readable_tooltip(display_name, details))
        metrics = QFontMetrics(target.font())
        bounds = metrics.boundingRect(
            0, 0, 232, 1000, int(Qt.TextFlag.TextWordWrap), text
        )
        row.setSizeHint(QSize(244, max(36, bounds.height() + 14)))
        target.addItem(row)

    def _perform_change(self, label: str, mutation: Callable[[], None]) -> None:
        before = self.service.snapshot()
        usage_before = {item.id: effective_item_state(item) for item in self.service.repository.list_equipment(self.service.character_id)}
        mutation()
        after = self.service.snapshot()
        usage_after = {item.id: effective_item_state(item) for item in self.service.repository.list_equipment(self.service.character_id)}
        changed = {key for key in usage_before if key in usage_after and usage_before[key] != usage_after[key]}
        if before == after and not changed:
            return
        self.undo_stack.push(
            _InventorySnapshotCommand(
                label, self.service, before, after, self._refresh_after_change,
                {key: usage_before[key] for key in changed},
                {key: usage_after[key] for key in changed},
            )
        )

    def _refresh_after_change(self) -> None:
        self.refresh()
        self.organization_changed.emit()

    def _move_item(
        self, item_id: int, category: str, subcategory: str, container_id: int = -1
    ) -> None:
        parent_id = None if int(container_id) < 0 else int(container_id)
        destination = (
            f"container {parent_id}" if parent_id is not None
            else f"{category} / {subcategory}"
        )
        try:
            self._perform_change(
                f"Move inventory item to {destination}",
                lambda: self.service.move_item(
                    item_id, category, subcategory, parent_id
                ),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot move item", str(error))

    def _move_unequipped_item(self, item_id, category, subcategory, container_id=-1):
        def mutation():
            self.service.move_item(item_id, category, subcategory, None if container_id < 0 else container_id)
            EquipmentWearService(self.service.repository, self.service.character_id).unequip(item_id)
        try:
            self._perform_change("Unequip inventory item", mutation)
        except ValueError as error:
            self.setToolTip(str(error))

    def _reset_item(self, item_id: int) -> None:
        self._perform_change(
            "Return inventory item to its automatic category",
            lambda: self.service.reset_item(item_id),
        )

    def _item_double_clicked(self, row: QListWidgetItem) -> None:
        item_id = row.data(Qt.ItemDataRole.UserRole)
        if item_id is None or self.edit_item is None:
            return
        self.edit_item(int(item_id))
        self.refresh()
        container = self.container_columns.get(int(item_id))
        if container is not None:
            self.scroll.ensureWidgetVisible(container)

    def _add_custom_group(self) -> None:
        category, accepted = QInputDialog.getText(
            self, "Custom inventory category", "Category name"
        )
        if not accepted or not category.strip():
            return
        subcategory, accepted = QInputDialog.getText(
            self,
            "Custom inventory subcategory",
            "Subcategory name",
            text=DEFAULT_SUBCATEGORY,
        )
        if not accepted:
            return
        try:
            self._perform_change(
                f"Add inventory category {category.strip()}",
                lambda: self.service.add_custom_group(category, subcategory),
            )
        except ValueError as error:
            QMessageBox.warning(self, "Cannot add category", str(error))

    def _reset_categories(self) -> None:
        before = self.service.snapshot()
        if not before.placements and not before.custom_groups:
            return
        answer = QMessageBox.question(
            self,
            "Reset inventory categories",
            "Return every item to its automatic catalog category and remove custom categories?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._perform_change("Reset inventory categories", self.service.reset)

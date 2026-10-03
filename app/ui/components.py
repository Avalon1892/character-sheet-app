from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPoint, QRectF, QObject, QSize, QTimer, Qt, QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QDrag, QPainter, QPainterPath, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QProgressBar,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid as qt_object_is_valid
from app.character_formulas import FormulaSuggestion
from app.formulas import FormulaError


@dataclass(frozen=True, slots=True)
class TableColumn:
    heading: str
    width: int | None = None
    stretch: bool = False


class SortableTableItem(QTableWidgetItem):
    """A table cell with a presentation-independent sort value."""

    def __init__(self, text: str, sort_value=None) -> None:
        super().__init__(text)
        self.sort_value = text.casefold() if sort_value is None else sort_value

    def __lt__(self, other) -> bool:
        if isinstance(other, SortableTableItem):
            try:
                return self.sort_value < other.sort_value
            except TypeError:
                return str(self.sort_value).casefold() < str(other.sort_value).casefold()
        return super().__lt__(other)


class OptionalNumericRangeFilter(QWidget):
    """Reusable inclusive min/max filter whose zero values mean “unbounded”."""

    changed = Signal()

    def __init__(
        self,
        minimum_label: str,
        maximum_label: str,
        *,
        suffix: str = "",
        maximum: float = 1_000_000_000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.minimum = self._field(suffix, maximum)
        self.maximum = self._field(suffix, maximum)
        layout.addWidget(QLabel(minimum_label))
        layout.addWidget(self.minimum)
        layout.addWidget(QLabel(maximum_label))
        layout.addWidget(self.maximum)
        self.minimum.valueChanged.connect(self.changed)
        self.maximum.valueChanged.connect(self.changed)

    @staticmethod
    def _field(suffix: str, maximum: float) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(0, maximum)
        field.setDecimals(2)
        field.setSpecialValueText("Any")
        field.setSuffix(suffix)
        field.setMaximumWidth(125)
        return field

    def matches(self, value: float) -> bool:
        lower = self.minimum.value()
        upper = self.maximum.value()
        return (not lower or value >= lower) and (not upper or value <= upper)

class CatalogSelectionBasket(QFrame):
    """Persistent, reusable batch-selection queue for catalog dialogs.

    Catalog tables remain responsible for searching and previewing entries;
    this component owns only the explicit set of entries the user intends to
    add.  Keeping those concerns separate prevents result refreshes from
    changing or clearing the batch.
    """

    changed = Signal()

    def __init__(
        self,
        singular: str,
        plural: str,
        *,
        meta_provider: Callable[[dict], str] | None = None,
        quantity_mode: bool = False,
        maximum_entries: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._singular = singular
        self._plural = plural
        self._meta_provider = meta_provider or (lambda _entry: "")
        self._quantity_mode = quantity_mode
        self._maximum_entries = max(0, int(maximum_entries))
        self._compact = False
        self._entries: dict[str, dict] = {}
        self._quantities: dict[str, int] = {}
        self.setObjectName("catalogSelectionBasket")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(290)
        self.setMaximumWidth(430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.title_label = QLabel("SELECTED FOR ADDITION")
        self.title_label.setObjectName("sectionTitle")
        layout.addWidget(self.title_label)

        self.count_label = QLabel()
        self.count_label.setObjectName("mutedText")
        layout.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("catalogSelectionQueue")
        self.list_widget.setWordWrap(True)
        self.list_widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.installEventFilter(self)
        layout.addWidget(self.list_widget, 1)
        self.empty_label = None

        actions = QHBoxLayout()
        self.remove_button = QPushButton("Remove")
        self.clear_button = QPushButton("Clear All")
        actions.addWidget(self.remove_button)
        actions.addWidget(self.clear_button)
        layout.addLayout(actions)

        self.list_widget.itemSelectionChanged.connect(self._update_controls)
        self.list_widget.itemClicked.connect(self._modified_remove_click)
        self.list_widget.itemDoubleClicked.connect(self._double_click_remove)
        self.remove_button.clicked.connect(lambda: self.remove_current(1))
        self.clear_button.clicked.connect(self.clear_entries)
        self._update_controls()

    def set_compact(self, compact: bool) -> None:
        """Opt-in presentation; other catalog baskets retain their layout."""
        self._compact = compact
        if compact and self.empty_label is None:
            self.empty_label = QLabel("Double-click a talent or press Enter to add it here.")
            self.empty_label.setObjectName("mutedText")
            self.empty_label.setWordWrap(True)
            self.layout().insertWidget(3, self.empty_label)
            self.list_widget.viewport().installEventFilter(self)
        self.setProperty("compactBasket", compact)
        self.title_label.setObjectName("catalogBasketTitle" if compact else "sectionTitle")
        self.count_label.setVisible(not compact)
        self.setMaximumWidth(16777215 if compact else 430)
        self._update_controls()

    def set_entity_labels(self, singular: str, plural: str) -> None:
        self._singular = singular
        self._plural = plural
        self._update_controls()

    @property
    def entries(self) -> tuple[dict, ...]:
        return tuple(self._entries.values())

    @property
    def selection_entries(self) -> tuple[dict, ...]:
        if not self._quantity_mode:
            return self.entries
        return tuple(
            {**entry, "_selection_quantity": self._quantities.get(key, 1)}
            for key, entry in self._entries.items()
        )

    @property
    def count(self) -> int:
        if self._quantity_mode:
            return sum(self._quantities.values())
        return len(self._entries)

    def add_entry(self, entry: dict, quantity: int = 1) -> bool:
        key = str(entry.get("key") or entry.get("name") or "")
        quantity = max(0, int(quantity))
        if not key or not quantity:
            return False
        if (
            key not in self._entries
            and self._maximum_entries
            and len(self._entries) >= self._maximum_entries
        ):
            return False
        if key in self._entries:
            if not self._quantity_mode:
                return False
            self._quantities[key] += quantity
            self._render_item(key)
            self._update_controls()
            self.changed.emit()
            return True
        self._entries[key] = entry
        self._quantities[key] = quantity
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, key)
        description = str(entry.get("description") or entry.get("summary") or "").strip()
        if description:
            item.setToolTip(description)
        self.list_widget.addItem(item)
        self._render_item(key)
        self.list_widget.setCurrentItem(item)
        self._update_controls()
        self.changed.emit()
        return True

    def remove_current(self, quantity: int = 1) -> bool:
        row = self.list_widget.currentRow()
        if row < 0:
            return False
        item = self.list_widget.item(row)
        key = str(item.data(Qt.ItemDataRole.UserRole) or "")
        quantity = max(0, int(quantity))
        if not quantity:
            return False
        if self._quantity_mode and self._quantities.get(key, 0) > quantity:
            self._quantities[key] -= quantity
            self._render_item(key)
            self._update_controls()
            self.changed.emit()
            return True
        self.list_widget.takeItem(row)
        self._entries.pop(key, None)
        self._quantities.pop(key, None)
        self._update_controls()
        self.changed.emit()
        return True

    def clear_entries(self) -> None:
        if not self._entries:
            return
        self._entries.clear()
        self._quantities.clear()
        self.list_widget.clear()
        self._update_controls()
        self.changed.emit()

    def _update_controls(self) -> None:
        count = self.count
        label = self._singular if count == 1 else self._plural
        self.count_label.setText(f"{count} {label} selected")
        if self._compact:
            self.title_label.setText(f"Selected · {count}")
            self.empty_label.setVisible(count == 0)
        self.remove_button.setEnabled(self.list_widget.currentRow() >= 0)
        self.clear_button.setEnabled(count > 0)

    def _render_item(self, key: str) -> None:
        entry = self._entries[key]
        name = str(entry.get("name") or key)
        if self._quantity_mode:
            name = f"{name}  ×{self._quantities.get(key, 1)}"
        meta = str(self._meta_provider(entry) or "").strip()
        text = name if not meta else f"{name}\n{meta}"
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == key:
                if not self._compact:
                    item.setText(text)
                    return
                item.setText("")
                item.setData(Qt.ItemDataRole.AccessibleTextRole, text)
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.setContentsMargins(4, 4, 4, 4)
                label = QLabel(text)
                label.setWordWrap(True)
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                remove = QPushButton("×")
                remove.setObjectName("catalogQueueRemove")
                remove.setFixedWidth(28)
                remove.setToolTip(f"Remove {name}")
                remove.clicked.connect(lambda _checked=False, selected=key: self._remove_key(selected))
                layout.addWidget(label, 1)
                layout.addWidget(remove)
                self.list_widget.setItemWidget(item, widget)
                self._fit_compact_items()
                return

    def _remove_key(self, key: str) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                self.list_widget.setCurrentItem(item)
                self.remove_current()
                return

    def _fit_compact_items(self) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            widget = self.list_widget.itemWidget(item)
            if widget:
                label = widget.findChild(QLabel)
                width = max(90, self.list_widget.viewport().width() - 54)
                label.setMaximumWidth(width)
                height = max(widget.minimumSizeHint().height(), label.heightForWidth(width)) + 20
                item.setSizeHint(QSize(self.list_widget.viewport().width(), height))

    @staticmethod
    def prompt_quantity(parent: QWidget, action: str) -> int | None:
        text, accepted = QInputDialog.getText(
            parent,
            f"{action} quantity",
            "Quantity",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if not accepted:
            return None
        try:
            quantity = int(text.strip())
        except ValueError:
            return None
        return quantity if quantity > 0 else None

    def _double_click_remove(self, _item: QListWidgetItem) -> None:
        if QApplication.keyboardModifiers() & (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            return
        self.remove_current(1)

    def _modified_remove_click(self, item: QListWidgetItem) -> None:
        if not self._quantity_mode:
            return
        self.list_widget.setCurrentItem(item)
        modifiers = QApplication.keyboardModifiers()
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self.remove_current(10)
        elif modifiers & Qt.KeyboardModifier.ShiftModifier:
            quantity = self.prompt_quantity(self, "Remove")
            if quantity is not None:
                self.remove_current(quantity)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self._compact and watched is self.list_widget.viewport() and event.type() == QEvent.Type.Resize:
            self._fit_compact_items()
        if watched is self.list_widget and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                modifiers = event.modifiers()
                if self._quantity_mode and modifiers & Qt.KeyboardModifier.ControlModifier:
                    self.remove_current(10)
                elif self._quantity_mode and modifiers & Qt.KeyboardModifier.ShiftModifier:
                    quantity = self.prompt_quantity(self, "Remove")
                    if quantity is not None:
                        self.remove_current(quantity)
                else:
                    self.remove_current(1)
                return True
        return super().eventFilter(watched, event)


class TranslucentReorderListWidget(QListWidget):
    """An internal-move list with a readable translucent drag preview."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, _supported_actions) -> None:
        indexes = self.selectedIndexes()
        item = self.currentItem()
        if not indexes or item is None:
            return
        rect = self.visualItemRect(item)
        source = self.viewport().grab(rect)
        preview = QPixmap(source.size())
        preview.fill(Qt.GlobalColor.transparent)
        painter = QPainter(preview)
        painter.setOpacity(0.58)
        painter.drawPixmap(0, 0, source)
        painter.end()
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData(indexes))
        drag.setPixmap(preview)
        drag.setHotSpot(preview.rect().center())
        drag.exec(Qt.DropAction.MoveAction)


class LayeredHealthBar(QProgressBar):
    """Animated HP bar with independent temporary and nonlethal overlays."""

    TRANSITION_MS = 250

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._display = (0.0, 0.0, 0.0, 0.0)
        self._target = self._display
        self._initialized = False
        self._animation = QVariantAnimation(self)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setDuration(self.TRANSITION_MS)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._animate)

    @property
    def temporary_hit_points(self) -> int:
        return round(self._target[2])

    @property
    def nonlethal_damage(self) -> int:
        return round(self._target[3])

    def set_health(
        self,
        current: int,
        maximum: int,
        temporary: int = 0,
        nonlethal: int = 0,
        *,
        animate: bool = True,
    ) -> None:
        maximum = max(0, int(maximum))
        current = int(current)
        temporary = max(0, int(temporary))
        nonlethal = max(0, int(nonlethal))
        target = (float(current), float(maximum), float(temporary), float(nonlethal))
        if self._initialized and target == self._target:
            # Unrelated rule refreshes often revisit the HP presenters.  Do
            # not restart two 250 ms animations when no health value changed.
            return
        super().setRange(0, max(1, maximum))
        super().setValue(max(0, min(current, maximum)))
        super().setFormat("No HP" if maximum <= 0 else f"{current} / {maximum} HP")
        ratio = current / maximum if maximum else 0.0
        state = (
            "empty" if maximum <= 0 else
            "critical" if ratio < 0.25 else
            "warning" if ratio < 0.5 else
            "healthy"
        )
        self.setProperty("healthState", state)
        self._target = target
        if not self._initialized or not animate:
            self._animation.stop()
            self._display = target
            self._initialized = True
            self.update()
            return
        self._start = self._display
        self._animation.stop()
        self._animation.start()

    def _animate(self, progress) -> None:
        value = float(progress)
        self._display = tuple(
            start + (target - start) * value
            for start, target in zip(self._start, self._target)
        )
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        inner = outer.adjusted(3.0, 3.0, -3.0, -3.0)
        palette = self.palette()
        background = palette.color(QPalette.ColorRole.Base)
        border = palette.color(QPalette.ColorRole.Mid)
        painter.setPen(border)
        painter.setBrush(background)
        painter.drawRoundedRect(outer, 7.0, 7.0)

        path = QPainterPath()
        path.addRoundedRect(inner, 4.0, 4.0)
        painter.save()
        painter.setClipPath(path)
        current, maximum, temporary, nonlethal = self._display
        if maximum > 0:
            current_ratio = max(0.0, min(1.0, current / maximum))
            health_width = inner.width() * current_ratio
            health_color = (
                QColor("#b6423d") if current / maximum < 0.25 else
                QColor("#c89b2c") if current / maximum < 0.5 else
                QColor("#4f8f5b")
            )
            painter.fillRect(
                QRectF(inner.left(), inner.top(), health_width, inner.height()),
                health_color,
            )

            nonlethal_amount = min(max(0.0, nonlethal), max(0.0, current))
            if nonlethal_amount:
                nonlethal_width = inner.width() * min(1.0, nonlethal_amount / maximum)
                painter.fillRect(
                    QRectF(
                        inner.left() + max(0.0, health_width - nonlethal_width),
                        inner.top(),
                        nonlethal_width,
                        inner.height(),
                    ),
                    QColor("#df789d"),
                )

            if temporary > 0:
                temporary_width = inner.width() * min(1.0, temporary / maximum)
                painter.fillRect(
                    QRectF(inner.left(), inner.top(), temporary_width, inner.height()),
                    QColor(26, 178, 188, 115),
                )
        painter.restore()

        painter.setPen(palette.color(QPalette.ColorRole.Text))
        painter.setFont(self.font())
        if maximum <= 0:
            text = "No HP"
        else:
            text = f"{round(current)} / {round(maximum)} HP"
        painter.drawText(outer, Qt.AlignmentFlag.AlignCenter, text)


class ReplaceMinimumOnFocusSpinBox(QSpinBox):
    """Select a sentinel minimum value when the user starts editing.

    This keeps compact action inputs convenient without changing the editing
    behavior of ordinary numeric fields whose existing value is meaningful.
    """

    def _select_minimum_value(self) -> None:
        if self.value() == self.minimum():
            self.selectAll()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if self.value() == self.minimum():
            QTimer.singleShot(0, self._select_minimum_value)

    def mousePressEvent(self, event) -> None:
        replace_minimum = self.value() == self.minimum()
        super().mousePressEvent(event)
        if replace_minimum:
            QTimer.singleShot(0, self._select_minimum_value)


def section_title(text: str) -> QLabel:
    title = QLabel(text)
    title.setObjectName("sectionTitle")
    title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return title


def section_shell(
    title: str, *, margins: int = 9, spacing: int = 7
) -> tuple[QWidget, QVBoxLayout, QLabel]:
    section = QWidget()
    section.setObjectName("sheetSection")
    layout = QVBoxLayout(section)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(spacing)
    heading = section_title(title)
    layout.addWidget(heading)
    return section, layout, heading


def configure_record_table(table: QTableWidget, stretch_column: int = 0) -> None:
    if not table.objectName():
        table.setObjectName("recordTable")
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(30)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setSectionResizeMode(
        stretch_column, QHeaderView.ResizeMode.Stretch
    )


def configure_columns(table: QTableWidget, columns: Sequence[TableColumn]) -> None:
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(tuple(column.heading for column in columns))
    stretch_column = next(
        (index for index, column in enumerate(columns) if column.stretch), 0
    )
    configure_record_table(table, stretch_column)
    for index, column in enumerate(columns):
        if index == stretch_column:
            continue
        mode = (
            QHeaderView.ResizeMode.Interactive
            if column.width is not None
            else QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(index, mode)
        if column.width is not None:
            table.setColumnWidth(index, column.width)


def fit_table_rows(
    table: QTableWidget, row_count: int, minimum_rows: int, maximum_rows: int
) -> None:
    if bool(table.property("fillAvailableHeight")):
        table.setMinimumHeight(44)
        table.setMaximumHeight(16777215)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return
    visible_rows = max(minimum_rows, min(maximum_rows, row_count))
    height = (
        table.horizontalHeader().sizeHint().height()
        + visible_rows * table.verticalHeader().defaultSectionSize()
        + 5
    )
    table.setFixedHeight(height)
    table.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
        if row_count > maximum_rows
        else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )


def populate_record_table(
    table: QTableWidget,
    records: Iterable,
    values: Callable[[object], Sequence[str]],
    tooltip: Callable[[object], str],
    *,
    record_id: Callable[[object], object] = lambda record: record.id,
    enabled: Callable[[object], bool] = lambda record: bool(
        getattr(record, "enabled", True)
    ),
) -> list:
    materialized = list(records)
    table.setRowCount(0)
    for record in materialized:
        row = table.rowCount()
        table.insertRow(row)
        row_tooltip = tooltip(record)
        for column, value in enumerate(values(record)):
            cell = QTableWidgetItem(str(value))
            cell.setData(Qt.ItemDataRole.UserRole, record_id(record))
            cell.setToolTip(row_tooltip)
            if not enabled(record):
                cell.setForeground(Qt.GlobalColor.gray)
            table.setItem(row, column, cell)
    if materialized and table.currentRow() < 0:
        table.setCurrentCell(0, 0)
    return materialized


def action_menu_button(
    actions: Sequence[tuple[str, Callable | None]], label: str = "⋯  Actions"
) -> QPushButton:
    button = QPushButton(label)
    menu = QMenu(button)
    for text, callback in actions:
        if callback is None:
            menu.addSeparator()
        else:
            menu.addAction(text).triggered.connect(callback)
    button.setMenu(menu)
    return button


def numeric_field(
    minimum: int,
    maximum: int,
    *,
    width: int | None = None,
    replace_minimum_on_focus: bool = False,
) -> QSpinBox:
    field = ReplaceMinimumOnFocusSpinBox() if replace_minimum_on_focus else QSpinBox()
    field.setRange(minimum, maximum)
    field.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    field.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if width is not None:
        field.setFixedWidth(width)
    return field


def forward_editor_wheel_to_page(
    root: QWidget, watched: QObject, event: QEvent
) -> bool:
    """Prevent accidental wheel edits and keep the enclosing sheet scrolling.

    Installed once on the application by the character sheet.  The ancestry
    checks keep dialogs and other windows independent, while covering internal
    line edits owned by spin boxes and every closed combo box on all pages.
    """

    if event.type() != QEvent.Type.Wheel or not isinstance(watched, QWidget):
        return False
    cursor: QWidget | None = watched
    editor: QWidget | None = None
    scroll: QScrollArea | None = None
    inside_sheet = False
    while cursor is not None:
        if cursor is root:
            inside_sheet = True
            break
        if editor is None and isinstance(cursor, (QAbstractSpinBox, QComboBox)):
            editor = cursor
        if scroll is None and isinstance(cursor, QScrollArea):
            scroll = cursor
        cursor = cursor.parentWidget()
    if not inside_sheet or editor is None:
        return False
    if isinstance(editor, QComboBox) and editor.view().isVisible():
        return False
    if scroll is not None and hasattr(event, "angleDelta"):
        pixel = event.pixelDelta().y()
        angle = event.angleDelta().y()
        bar = scroll.verticalScrollBar()
        amount = pixel or int((angle / 120) * max(1, bar.singleStep()) * 3)
        if amount:
            bar.setValue(bar.value() - amount)
    event.accept()
    return True


class FormulaLineEdit(QLineEdit):
    """Line edit with an Excel-style, character-aware formula suggestion popup."""

    MAX_VISIBLE_SUGGESTIONS = 12
    MAX_RESULTS = 60

    def __init__(
        self,
        *args,
        suggestion_provider: Callable[[], Sequence[FormulaSuggestion]] | None = None,
        require_equals: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.suggestion_provider = suggestion_provider
        self.require_equals = require_equals
        self._completion_span = (0, 0)
        self._completion_disposed = False
        self._completion_hide_timer = QTimer(self)
        self._completion_hide_timer.setSingleShot(True)
        self._completion_hide_timer.timeout.connect(
            self._hide_completion_if_inactive
        )
        self.completion_popup = QTreeWidget(self)
        self.completion_popup.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.completion_popup.setAttribute(
            Qt.WidgetAttribute.WA_ShowWithoutActivating, True
        )
        self.completion_popup.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.completion_popup.setObjectName("formulaCompletionPopup")
        self.completion_popup.setColumnCount(3)
        self.completion_popup.setHeaderLabels(("Formula value", "Current", "Meaning"))
        self.completion_popup.setRootIsDecorated(False)
        self.completion_popup.setUniformRowHeights(True)
        self.completion_popup.setAlternatingRowColors(True)
        self.completion_popup.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.completion_popup.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        header = self.completion_popup.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.completion_popup.itemClicked.connect(self._insert_selected_completion)
        self.textEdited.connect(self._update_formula_completions)
        self.cursorPositionChanged.connect(self._update_formula_completions)
        self.installEventFilter(self)

    def event(self, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.DeferredDelete
            and not getattr(self, "_completion_disposed", True)
        ):
            self._dispose_formula_completion()
        return super().event(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            # Formula-number fields normally contain a literal such as ``0``.
            # Starting a formula should replace that literal, just as typing
            # into a selected spreadsheet cell does, instead of producing the
            # invalid text ``0=...`` and suppressing autocomplete.
            if (
                key == Qt.Key.Key_Equal
                and self.require_equals
                and not self.hasSelectedText()
                and self.text().strip()
                and not self.text().lstrip().startswith("=")
            ):
                try:
                    float(self.text().strip())
                except ValueError:
                    pass
                else:
                    self.clear()
            if key == Qt.Key.Key_Down and not self.completion_popup.isVisible():
                self._update_formula_completions(force=True)
                return self.completion_popup.isVisible()
            if self.completion_popup.isVisible():
                if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    self._move_completion(1 if key == Qt.Key.Key_Down else -1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                    self._insert_selected_completion()
                    return True
                if key == Qt.Key.Key_Escape:
                    self.completion_popup.hide()
                    return True
        if watched is self and event.type() == QEvent.Type.FocusOut:
            if not self._completion_disposed:
                self._completion_hide_timer.start(0)
        return super().eventFilter(watched, event)

    def _hide_completion_if_inactive(self) -> None:
        """Hide a stale popup without dereferencing deleted Qt wrappers."""

        if self._completion_disposed or not qt_object_is_valid(self):
            return
        popup = getattr(self, "completion_popup", None)
        if popup is None or not qt_object_is_valid(popup):
            return
        try:
            if not self.hasFocus() and not popup.hasFocus():
                popup.hide()
        except RuntimeError:
            # Direct C++ parent destruction can invalidate children between
            # validity checks.  There is nothing left to hide in that case.
            self._completion_disposed = True

    def _dispose_formula_completion(self) -> None:
        """Stop deferred work and detach completion-only signal connections."""

        if self._completion_disposed:
            return
        self._completion_disposed = True
        timer = getattr(self, "_completion_hide_timer", None)
        popup = getattr(self, "completion_popup", None)
        if timer is not None and qt_object_is_valid(timer):
            timer.stop()
            try:
                timer.timeout.disconnect(self._hide_completion_if_inactive)
            except (RuntimeError, TypeError):
                pass
        if popup is not None and qt_object_is_valid(popup):
            popup.hide()
            try:
                popup.itemClicked.disconnect(self._insert_selected_completion)
            except (RuntimeError, TypeError):
                pass
        for signal, slot in (
            (self.textEdited, self._update_formula_completions),
            (self.cursorPositionChanged, self._update_formula_completions),
        ):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self.suggestion_provider = None

    def _formula_token(self) -> tuple[str, int, int] | None:
        import re

        text = self.text()
        cursor = self.cursorPosition()
        if self.require_equals and not text.lstrip().startswith("="):
            return None
        before = text[:cursor]
        match = re.search(r"[A-Za-z_][A-Za-z0-9_.]*$", before)
        start = match.start() if match else cursor
        query = match.group(0) if match else ""
        tail = re.match(r"[A-Za-z0-9_.]*", text[cursor:])
        end = cursor + (len(tail.group(0)) if tail else 0)
        return query, start, end

    def _update_formula_completions(self, *_args, force: bool = False) -> None:
        if not self.hasFocus() and not force:
            self.completion_popup.hide()
            return
        token = self._formula_token()
        if token is None or self.suggestion_provider is None:
            self.completion_popup.hide()
            return
        query, start, end = token
        if not force and not query and self.text().strip() not in {"=", ""}:
            self.completion_popup.hide()
            return
        query_folded = query.casefold()
        candidates = []
        for suggestion in self.suggestion_provider():
            reference = suggestion.reference.casefold()
            segments = reference.replace("()", "").split(".")
            if query_folded and query_folded not in reference:
                continue
            priority = (
                0 if reference.startswith(query_folded) else
                1 if any(segment.startswith(query_folded) for segment in segments) else 2
            )
            candidates.append((priority, len(reference), reference, suggestion))
        candidates.sort(key=lambda item: item[:3])
        candidates = candidates[: self.MAX_RESULTS]
        self.completion_popup.clear()
        self._completion_span = (start, end)
        for _priority, _length, _reference, suggestion in candidates:
            item = QTreeWidgetItem(
                (suggestion.reference, suggestion.value, suggestion.description)
            )
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                suggestion.insertion or suggestion.reference,
            )
            item.setToolTip(0, suggestion.description)
            item.setToolTip(1, suggestion.description)
            item.setToolTip(2, suggestion.description)
            self.completion_popup.addTopLevelItem(item)
        if not candidates:
            self.completion_popup.hide()
            return
        self.completion_popup.setCurrentItem(self.completion_popup.topLevelItem(0))
        self._show_completion_popup()

    def _show_completion_popup(self) -> None:
        rows = min(self.completion_popup.topLevelItemCount(), self.MAX_VISIBLE_SUGGESTIONS)
        row_height = self.completion_popup.sizeHintForRow(0)
        row_height = row_height if row_height > 0 else 26
        header_height = self.completion_popup.header().sizeHint().height()
        width = max(620, self.width())
        height = header_height + rows * row_height + 6
        origin = self.mapToGlobal(QPoint(0, self.height()))
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            width = min(width, screen.width())
            x = min(origin.x(), screen.right() - width + 1)
            y = origin.y()
            if y + height > screen.bottom():
                y = self.mapToGlobal(QPoint(0, 0)).y() - height
            origin = QPoint(max(screen.left(), x), max(screen.top(), y))
        self.completion_popup.setGeometry(origin.x(), origin.y(), width, height)
        self.completion_popup.show()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _move_completion(self, direction: int) -> None:
        count = self.completion_popup.topLevelItemCount()
        if not count:
            return
        current = self.completion_popup.indexOfTopLevelItem(
            self.completion_popup.currentItem()
        )
        row = (max(0, current) + direction) % count
        item = self.completion_popup.topLevelItem(row)
        self.completion_popup.setCurrentItem(item)
        self.completion_popup.scrollToItem(item)

    def _insert_selected_completion(self, *_args) -> None:
        item = self.completion_popup.currentItem()
        if item is None:
            return
        insertion = str(item.data(0, Qt.ItemDataRole.UserRole) or item.text(0))
        start, end = self._completion_span
        text = self.text()
        self.setText(f"{text[:start]}{insertion}{text[end:]}")
        cursor = start + len(insertion) - (1 if insertion.endswith("()") else 0)
        self.setCursorPosition(cursor)
        self.completion_popup.hide()
        self.setFocus(Qt.FocusReason.OtherFocusReason)


class FormulaNumberEdit(QWidget):
    """Reusable literal-or-formula editor with a focus-aware resolved display.

    Formula source is an editing concern: at rest the sheet shows only its
    resolved number. Clicking that number restores the expression for editing.
    This behavior lives here so every current and future numeric rule field is
    consistent without page-specific code.
    """

    def __init__(
        self,
        minimum: float,
        maximum: float,
        *,
        integer: bool = True,
        evaluator: Callable[[str], float] | None = None,
        symbolic_evaluator: Callable[[str], object] | None = None,
        suggestion_provider: Callable[[], Sequence[FormulaSuggestion]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.integer = integer
        self.evaluator = evaluator
        self.symbolic_evaluator = symbolic_evaluator
        layout = QStackedLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self.editor = FormulaLineEdit(
            "0", suggestion_provider=suggestion_provider, require_equals=True
        )
        self.editor.setObjectName("formulaNumberEditor")
        self.editor.setPlaceholderText("Number or =formula")
        self.preview = QLabel("0")
        self.preview.setObjectName("formulaResult")
        self.preview.setMinimumWidth(70)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.editor)
        layout.addWidget(self.preview)
        self._display_stack = layout
        self.editor.installEventFilter(self)
        self.preview.installEventFilter(self)
        self.preview.setCursor(Qt.CursorShape.IBeamCursor)
        self.editor.textChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.preview and event.type() == QEvent.Type.MouseButtonPress:
            self._display_stack.setCurrentWidget(self.editor)
            self.editor.setFocus(Qt.FocusReason.MouseFocusReason)
            self.editor.selectAll()
            return True
        if watched is self.editor:
            if event.type() == QEvent.Type.FocusIn:
                self._display_stack.setCurrentWidget(self.editor)
            elif event.type() == QEvent.Type.FocusOut:
                QTimer.singleShot(0, self._show_formula_result_if_idle)
        return super().eventFilter(watched, event)

    def _show_formula_result_if_idle(self) -> None:
        # Focus-out is deferred so completion-popup clicks can finish first.
        # The containing dialog may be destroyed during that turn of the event
        # loop, so never dereference wrappers whose C++ objects are gone.
        if not qt_object_is_valid(self):
            return
        editor = getattr(self, "editor", None)
        preview = getattr(self, "preview", None)
        display_stack = getattr(self, "_display_stack", None)
        if (
            editor is None
            or preview is None
            or display_stack is None
            or not qt_object_is_valid(editor)
            or not qt_object_is_valid(preview)
        ):
            return
        text = editor.text().strip()
        if text.startswith("=") and not editor.hasFocus():
            display_stack.setCurrentWidget(preview)

    @property
    def expression(self) -> str:
        text = self.editor.text().strip()
        return text if text.startswith("=") else ""

    def set_expression(self, expression: str, fallback: int | float = 0) -> None:
        self.editor.setText(expression.strip() if expression.strip() else str(fallback))
        self._show_formula_result_if_idle()

    def set_value(self, value: int | float) -> None:
        self.editor.setText(str(value))
        self._display_stack.setCurrentWidget(self.editor)

    def value(self) -> int | float:
        text = self.editor.text().strip()
        if text.startswith("="):
            if self.symbolic_evaluator is not None:
                value = float(self.symbolic_evaluator(text).constant)
            elif self.evaluator is None:
                raise FormulaError("This field has no character formula context.")
            else:
                value = float(self.evaluator(text))
        else:
            try:
                value = float(text)
            except ValueError:
                raise FormulaError("Enter a number or start a formula with =.") from None
        if self.integer:
            rounded = round(value)
            if abs(value - rounded) > 1e-9:
                raise FormulaError("This field must resolve to a whole number.")
            value = int(rounded)
        if not self.minimum <= float(value) <= self.maximum:
            raise FormulaError(
                f"Result must be between {self.minimum:g} and {self.maximum:g}."
            )
        return value

    def _refresh_preview(self) -> None:
        try:
            value = self.value()
            if self.expression and self.symbolic_evaluator is not None:
                self.preview.setText(self.symbolic_evaluator(self.expression).format())
            else:
                self.preview.setText(f"{value:g}" if isinstance(value, float) else str(value))
            if self.expression and self.property("showFormulaIndicator"):
                self.preview.setText("ƒ  " + self.preview.text())
                self.preview.setToolTip("Calculated from a formula. Click to edit: " + self.expression)
            self.preview.setProperty("formulaError", False)
            self.editor.setToolTip("Formula result is valid." if self.expression else "Literal number.")
        except FormulaError as error:
            self.preview.setText("Invalid")
            self.preview.setProperty("formulaError", True)
            self.editor.setToolTip(str(error))
        self.preview.style().unpolish(self.preview)
        self.preview.style().polish(self.preview)
        if self.expression and not self.editor.hasFocus():
            self._display_stack.setCurrentWidget(self.preview)
        elif not self.expression:
            self._display_stack.setCurrentWidget(self.editor)


def sheet_page(object_name: str) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setObjectName("sheetScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    canvas = QWidget()
    canvas.setObjectName(object_name)
    canvas.setMinimumWidth(1120)
    layout = QVBoxLayout(canvas)
    layout.setContentsMargins(12, 12, 12, 22)
    layout.setSpacing(10)
    scroll.setWidget(canvas)
    return scroll, canvas, layout


class DetailsPanel(QTextBrowser):
    def __init__(self, empty_html: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._empty_html = empty_html
        self.setObjectName("featureDetails")
        self.setOpenExternalLinks(True)
        self.setMinimumHeight(150)
        self.clear_details()

    def clear_details(self) -> None:
        self.setHtml(self._empty_html)


class DebouncedCallback(QObject):
    """Reusable UI-thread debounce with explicit flush support for tests/actions."""

    def __init__(
        self, callback: Callable[[], None], delay_ms: int = 200,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._callback = callback
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay_ms)
        self.timer.timeout.connect(callback)

    def schedule(self, *_args) -> None:
        self.timer.start()

    def flush(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
        self._callback()

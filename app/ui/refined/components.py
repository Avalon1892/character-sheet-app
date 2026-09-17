"""Reusable, rules-free Refined presentation controls."""
from PySide6.QtCore import Qt, QTimer, QEvent, QObject, QSize, Signal
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout,
    QBoxLayout, QSizePolicy, QTableWidget, QHeaderView, QLineEdit, QLayout, QPushButton)


def card(title=""):
    widget = QFrame()
    widget.setObjectName("refinedCard")
    root = QVBoxLayout(widget)
    root.setContentsMargins(12, 10, 12, 10)
    root.setSpacing(8)
    if title:
        label = QLabel(title)
        label.setObjectName("refinedSectionTitle")
        root.addWidget(label)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
    return widget


class ResponsiveRow(QWidget):
    geometry_changed = Signal()

    def __init__(self, *widgets, breakpoint=950, stretches=None):
        super().__init__()
        self._content_height=None
        self.breakpoint = breakpoint
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(12)
        self.row.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        weights=tuple(stretches) if stretches is not None else (1,)*len(widgets)
        if len(weights)!=len(widgets) or any(weight<=0 for weight in weights):
            raise ValueError("Each responsive column needs a positive stretch weight")
        self.column_stretches=dict(zip(widgets,weights))
        for widget in widgets:
            self.row.addWidget(widget, self.column_stretches[widget], Qt.AlignmentFlag.AlignTop)

    def restore_column_layout(self):
        for index in range(self.row.count()):
            widget=self.row.itemAt(index).widget()
            if widget is not None:
                self.row.setStretch(index,self.column_stretches.get(widget,1))
                self.row.setAlignment(widget,Qt.AlignmentFlag.AlignTop)
    def resizeEvent(self, event):
        direction = QBoxLayout.Direction.TopToBottom if self.width() < self.breakpoint else QBoxLayout.Direction.LeftToRight
        if self.row.direction() != direction:
            self.row.setDirection(direction)
        super().resizeEvent(event)
    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def event(self,event):
        result=super().event(event)
        if event.type()==QEvent.Type.LayoutRequest and hasattr(self,"row"):
            height=self.row.minimumSize().height()
            if height!=self._content_height:
                self._content_height=height
                self.updateGeometry()
                self.geometry_changed.emit()
        return result


class TablePresentation(QObject):
    """Opt-in readable widths, bounded content height, and debounced filtering."""
    fitted = Signal(int, int)
    geometry_changed = Signal()

    def __init__(self, table, parent, name_column=0, max_rows=22, *, balanced=False, sortable=True, row_visible=None):
        super().__init__(parent)
        self.table = table
        self.max_rows = max_rows
        self.name_column = name_column
        self.query = ""
        self.row_filters = {}
        self.matching_count = 0
        self.row_visible = row_visible
        self.sortable = sortable
        self.sort_column = None
        self.sort_order = Qt.SortOrder.AscendingOrder
        self.preview_rows = None
        self.expanded = False
        self._fitting = False
        self.empty_label = QLabel(table.viewport())
        self.empty_label.setObjectName("refinedMuted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.empty_label.hide()
        if sortable and not table.isSortingEnabled():
            table.horizontalHeader().setSectionsClickable(True)
            table.horizontalHeader().sectionClicked.connect(self.sort)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(80)
        self.timer.timeout.connect(self._fit_visible)
        table.setShowGrid(False)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        table.setMinimumWidth(0)
        table.setMaximumWidth(16777215)
        table.verticalHeader().hide()
        table.horizontalHeader().setStretchLastSection(False)
        for column in range(table.columnCount()):
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(column, 100)
        if balanced:
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            table.horizontalHeader().setSectionResizeMode(name_column, QHeaderView.ResizeMode.Stretch)
        for column in table.property('contentStretchColumns') or ():
            if 0 <= column < table.columnCount():
                table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setMinimumSectionSize(36)
        for signal in (table.model().modelReset, table.model().rowsInserted,
                       table.model().rowsRemoved, table.model().dataChanged):
            signal.connect(self.schedule)
        table.installEventFilter(self)
        self.schedule()
    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.schedule()
        return False
    def schedule(self, *_):
        if not self._fitting and not self.timer.isActive():
            self.timer.start()
    def _fit_visible(self):
        # Hidden pages will receive a Show event before they are used. Do not
        # measure every off-screen table after each character-value change.
        if self.table.isVisible():
            self.fit()
    def filter(self, text):
        self.query = text.casefold().strip()
        self.schedule()
    def set_row_filter(self, key, predicate=None):
        """Combine optional presentation filters without changing any records."""
        if predicate is None:
            self.row_filters.pop(key,None)
        else:
            self.row_filters[key]=predicate
        self.schedule()
    def sort(self,column):
        # Keep the shared row-population routines unsorted while they write.
        # Allocation grids with embedded editors retain their semantic order.
        if not self.sortable or any(self.table.cellWidget(r,c) for r in range(self.table.rowCount()) for c in range(self.table.columnCount())):
            return
        self.sort_order = Qt.SortOrder.DescendingOrder if column==self.sort_column and self.sort_order==Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
        self.sort_column=column
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().setSortIndicator(column,self.sort_order)
        self.table.sortItems(column,self.sort_order)
        self.schedule()
    def fit(self):
        if self._fitting:
            return
        self.timer.stop()
        self._fitting = True
        try:
            self._fit()
        finally:
            self._fitting = False

    def _fit(self):
        t = self.table
        managed_size = bool(t.property("freeformManaged") or t.property("fillAvailableHeight"))
        if self.sort_column is not None:
            t.sortItems(self.sort_column,self.sort_order)
        visible = []
        matching = 0
        for row in range(t.rowCount()):
            match = not self.query or any(self.query in t.item(row,c).text().casefold() for c in range(t.columnCount()) if t.item(row,c))
            if self.row_visible is not None:
                match = match and self.row_visible(t, row)
            match = match and all(predicate(t,row) for predicate in self.row_filters.values())
            if match:
                matching += 1
                if self.preview_rows and not self.expanded and not self.query and not self.row_filters:
                    match = matching <= self.preview_rows
            if t.isRowHidden(row) == match:
                t.setRowHidden(row, not match)
            if match:
                visible.append(row)
        t.resizeRowsToContents()
        heights = [max(32, min(180, t.rowHeight(r)),
            # The item delegate's vertical padding also surrounds embedded
            # editors; their minimum height must fit inside that padded cell.
            max((t.cellWidget(r,c).sizeHint().height()+22 for c in range(t.columnCount())
                 if t.cellWidget(r,c) and not t.isColumnHidden(c)),default=0)) for r in visible]
        for r,h in zip(visible, heights):
            t.setRowHeight(r,h)
        # An expanded reference list uses the page scroll, never a second
        # scrollbar. Searching reveals every match without changing its fold.
        limit = len(heights) if self.preview_rows else self.max_rows
        height = t.horizontalHeader().height() + sum(heights[:limit]) + 5
        if not visible:
            height += 36
        # Do not reserve rows which do not exist; bound huge lists to one scroll.
        if not managed_size:
            if t.minimumHeight() != height or t.maximumHeight() != height:
                t.setFixedHeight(height)
                self.geometry_changed.emit()
        # Manual sizing affects geometry, never which records can be revealed.
        # In a fixed-size box the normal scrollbar exposes the expanded rows.
        if t.currentRow()>=0 and t.isRowHidden(t.currentRow()):
            t.setCurrentCell(-1,-1)
            t.clearSelection()
        self.empty_label.setText("No matching entries" if self.query or self.row_filters else "No entries yet")
        self.empty_label.setGeometry(t.viewport().rect())
        self.empty_label.setVisible(not visible)
        self.matching_count=matching
        self.fitted.emit(len(visible), matching)


class TableDisclosure(QPushButton):
    """Non-destructive, searchable preview for long reference sections."""
    def __init__(self, adapter, section, *, preview_rows=6, noun="entries"):
        super().__init__(section)
        self.adapter = adapter
        self.noun = noun
        self.setObjectName("refinedDisclosure")
        self.setAccessibleName("Expand or collapse " + noun)
        adapter.preview_rows = preview_rows
        adapter.fitted.connect(self._updated)
        self.clicked.connect(lambda: self.set_expanded(not adapter.expanded))
        section.layout().insertWidget(section.layout().indexOf(adapter.table) + 1, self)
        self.hide()

    def set_expanded(self, expanded):
        self.adapter.expanded = bool(expanded)
        self.adapter.fit()

    def _updated(self, visible, matching):
        self.setVisible(matching > self.adapter.preview_rows and not self.adapter.query and not self.adapter.row_filters)
        self.setText(f"Show fewer {self.noun}" if self.adapter.expanded
                     else f"Show all {matching} {self.noun}")
        # Text uses the theme foreground; platform arrow icons can remain
        # black and become invisible on a dark surface.
        self.setText(("− " if self.adapter.expanded else "+ ") + self.text())


def search_field(controllers):
    """Compatibility factory; page search and feedback live in table_tools."""
    from .table_tools import PageSearchBar
    return PageSearchBar(controllers)

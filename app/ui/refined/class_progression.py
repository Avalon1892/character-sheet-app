"""Refined-only, read-only class reference pages and grouped navigation."""
import html
from PySide6.QtCore import QSize, Qt, QRect
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTabWidget, QTabBar,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QStylePainter, QStyleOptionTab, QStyle)
from app.services.class_progression import character_progressions


class ProgressionHeader(QHeaderView):
    def __init__(self, headers, parent):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.groups = {}
        for column, text in enumerate(headers):
            if " · " in text:
                self.groups.setdefault(text.split(" · ")[0], []).append(column)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        for label, columns in self.groups.items():
            rectangle = QRect(self.sectionViewportPosition(columns[0]), 0,
                              sum(self.sectionSize(c) for c in columns), self.height() // 2)
            painter.drawText(rectangle, Qt.AlignmentFlag.AlignCenter, label)


class ProgressionTable(QTableWidget):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.columnCount() > 5:
            other = sum(self.columnWidth(c) for c in range(self.columnCount()) if c != 5)
            self.setColumnWidth(5, max(350, self.viewport().width() - other))
            self.resizeRowsToContents()


class GroupedTabBar(QTabBar):
    gap = 28

    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        if self.tabData(index) in ("build", "crafting"):
            size += QSize(self.gap, 0)
        return size

    def paintEvent(self, event):
        painter = QStylePainter(self)
        for index in range(self.count()):
            if not self.isTabVisible(index):
                continue
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            option.text = option.text.replace("&", "&&")
            if self.tabData(index) in ("build", "crafting"):
                option.rect.adjust(self.gap, 0, 0, 0)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTab, option)


class ClassProgressionPage(QWidget):
    def __init__(self, sheet):
        super().__init__(sheet)
        self.sheet = sheet
        self.signature = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.empty = QLabel("Add a class to view its progression.")
        layout.addWidget(self.empty)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

    def refresh(self):
        repository, character_id = self.sheet.repository, self.sheet.character_id
        if character_id is None:
            return
        signature = repr((character_id, repository.list_class_levels(character_id),
                          repository.list_class_archetype_keys(character_id),
                          repository.list_class_feature_selections(character_id)))
        if signature == self.signature:
            return
        self.signature = signature
        selected = self.tabs.currentIndex()
        while self.tabs.count():
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.deleteLater()
        for projection in character_progressions(repository, character_id):
            page = QWidget()
            layout = QVBoxLayout(page)
            if projection.subtitle:
                label = QLabel(projection.subtitle)
                label.setWordWrap(True)
                layout.addWidget(label)
            table = ProgressionTable(20, len(projection.headers))
            table.setObjectName("classProgressionTable")
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setAlternatingRowColors(True)
            table.setWordWrap(True)
            table.verticalHeader().hide()
            table.setHorizontalHeader(ProgressionHeader(projection.headers, table))
            table.setHorizontalHeaderLabels(["\n"+h.split(" · ")[-1] if " · " in h else h
                                             for h in projection.headers])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            for row, values in enumerate(projection.rows):
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column != 5:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if column == 5:
                        description = projection.descriptions[row]
                        item.setToolTip("<div style='white-space:pre-wrap'>" + html.escape(description) + "</div>")
                    if row + 1 == projection.current_level:
                        font = item.font(); font.setBold(True); item.setFont(font)
                    table.setItem(row, column, item)
            table.resizeColumnsToContents()
            for column in range(table.columnCount()):
                table.setColumnWidth(column,48 if " · " in projection.headers[column]
                                     else max(74,table.columnWidth(column)))
            table.setColumnWidth(0,55)
            table.setColumnWidth(5,430)
            table.verticalHeader().setMinimumSectionSize(32)
            table.resizeRowsToContents()
            table.horizontalHeader().sectionResized.connect(table.resizeRowsToContents)
            table.setMinimumHeight(720)
            layout.addWidget(table)
            self.tabs.addTab(page, projection.name)
        self.empty.setVisible(not self.tabs.count())
        self.tabs.setCurrentIndex(min(max(0, selected), self.tabs.count() - 1))

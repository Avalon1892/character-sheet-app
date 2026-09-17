"""Wide sphere-grouped play interface for owned martial talents."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.martial_book import FOCUS_EXPEND, FOCUS_NONE, MartialBookEntry, MartialBookService
from app.presentation import readable_tooltip
from app.ui.components import DebouncedCallback
from app.ui.sphere_colors import style_sphere_group


class MartialBookDialog(QDialog):
    resources_changed = Signal()
    CARDS_PER_ROW = 4

    def __init__(self, service: MartialBookService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Martial Book")
        self.resize(1420, 840)
        self.setMinimumSize(1080, 620)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._entries: tuple[MartialBookEntry, ...] = ()
        self.entry_cards: dict[str, QFrame] = {}
        self.use_buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        title = QLabel("MARTIAL BOOK")
        title.setObjectName("sectionTitle")
        self.focus_summary = QLabel()
        self.focus_summary.setObjectName("resourceTotalSmall")
        title_row.addWidget(title, 1)
        title_row.addWidget(self.focus_summary)
        layout.addLayout(title_row)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Find in this character's martial talents"))
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Search talent name, description, sphere, or type…")
        search_row.addWidget(self.search, 1)
        layout.addLayout(search_row)
        self.status = QLabel()
        self.status.setObjectName("mutedText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("martialBookScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.canvas = QWidget()
        self.canvas.setObjectName("martialBookPage")
        self.book_layout = QVBoxLayout(self.canvas)
        self.book_layout.setContentsMargins(8, 8, 8, 14)
        self.book_layout.setSpacing(9)
        self.book_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        close_row.addWidget(close)
        layout.addLayout(close_row)

        self.search_debounce = DebouncedCallback(self._render, 400, self)
        self.search.textChanged.connect(self.search_debounce.schedule)
        from app.ui.search_navigation import install_search_shortcut
        self.search_shortcut = install_search_shortcut(self, self.search)
        self.refresh()

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                MartialBookDialog._clear_layout(item.layout())

    def refresh(self) -> None:
        self._entries = self.service.entries()
        focus = self.service.focus()
        self.focus_summary.setText(f"Martial Focus  {focus.current} / {focus.maximum}")
        self._render()

    def _render(self) -> None:
        query = self.search.text().strip().casefold()
        focus = self.service.focus()
        self._clear_layout(self.book_layout)
        self.entry_cards.clear()
        self.use_buttons.clear()
        shown = 0
        spheres = sorted({entry.sphere for entry in self._entries}, key=str.casefold)
        for sphere in spheres:
            entries = tuple(
                entry for entry in self._entries
                if entry.sphere == sphere
                and (not query or query in entry.searchable_text)
            )
            if not entries:
                continue
            shown += len(entries)
            section = QFrame()
            section.setObjectName("martialBookSection")
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(8, 7, 8, 8)
            section_layout.setSpacing(6)
            heading = QLabel(f"{sphere.upper()} SPHERE")
            heading.setObjectName("martialBookSectionTitle")
            style_sphere_group(heading, sphere, 'martial', self)
            section_layout.addWidget(heading)
            grid = QGridLayout()
            grid.setHorizontalSpacing(7)
            grid.setVerticalSpacing(7)
            for column in range(self.CARDS_PER_ROW):
                grid.setColumnStretch(column, 1)
            for index, entry in enumerate(entries):
                grid.addWidget(
                    self._card(entry, focus.current),
                    index // self.CARDS_PER_ROW,
                    index % self.CARDS_PER_ROW,
                )
            section_layout.addLayout(grid)
            self.book_layout.addWidget(section)
        if not shown:
            empty = QLabel(
                "No owned martial talents match this search."
                if query else "This character currently has no martial talents."
            )
            empty.setObjectName("mutedText")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.book_layout.addWidget(empty)
        self.book_layout.addStretch()
        total = len(self._entries)
        self.status.setText(
            f"{shown} of {total} owned talents match the search."
            if query else f"{total} owned martial talents are grouped by sphere."
        )

    def _card(self, entry: MartialBookEntry, focus_current: int) -> QFrame:
        focus_available = entry.focus_usage == FOCUS_NONE or focus_current > 0
        available = entry.enabled and focus_available
        card = QFrame()
        card.setObjectName("martialBookEntry")
        card.setProperty("available", available)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        card.setMinimumWidth(235)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(5)
        name = QLabel(entry.name)
        name.setObjectName("martialBookEntryName")
        name.setWordWrap(True)
        layout.addWidget(name)
        tooltip = readable_tooltip(
            entry.name,
            "\n\n".join((f"Sphere: {entry.sphere}", f"Type: {entry.category}", entry.focus_label, entry.description)),
        )
        for widget in (card, name):
            widget.setToolTip(tooltip)
        focus_label = QLabel(entry.focus_label)
        focus_label.setObjectName(
            "martialFocusRequirement" if entry.focus_usage != FOCUS_NONE else "mutedText"
        )
        focus_label.setToolTip(tooltip)
        layout.addWidget(focus_label)
        if entry.focus_usage == FOCUS_EXPEND:
            use = QPushButton("Use · Expend Focus")
            use.setObjectName("primaryButton")
            use.setEnabled(available)
            use.clicked.connect(partial(self._use_talent, entry.key))
            layout.addWidget(use)
            self.use_buttons[entry.key] = use
        self.entry_cards[entry.key] = card
        return card

    def _use_talent(self, key: str) -> None:
        result = self.service.use_talent(key)
        self.status.setText(result.message)
        if result.changed:
            self.resources_changed.emit()
            self.refresh()

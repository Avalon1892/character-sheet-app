"""Persistent screen-floating rich-text notes for character sheets."""
from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Callable

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import (
    QAction, QFont, QKeySequence, QMouseEvent, QTextCharFormat, QTextCursor,
    QTextDocument, QTextFormat,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import SheetNote


FORMULA_PROPERTY = int(QTextFormat.Property.UserProperty) + 41


def _formula_expression(fmt: QTextCharFormat) -> str:
    value = fmt.property(FORMULA_PROPERTY)
    if value:
        return str(value)
    href = fmt.anchorHref()
    if href.startswith("formula:"):
        return urllib.parse.unquote(href.partition(":")[2])
    return ""


def _number_text(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


class FormulaNoteEditor(QTextEdit):
    changed_for_save = Signal()
    page_undo_requested = Signal()
    page_redo_requested = Signal()

    def __init__(
        self,
        evaluator: Callable[[str], object],
        suggestion_provider: Callable[[], tuple] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.evaluator = evaluator
        self.suggestion_provider = suggestion_provider
        self._completion_span = (0, 0)
        self.setAcceptRichText(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.textChanged.connect(self.changed_for_save)
        self._install_shortcut("Ctrl+B", self.toggle_bold)
        self._install_shortcut("Ctrl+U", self.toggle_underline)
        self._install_shortcut("Ctrl+K", self.toggle_italic)
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
        header = self.completion_popup.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.completion_popup.itemClicked.connect(self._insert_selected_completion)
        self.textChanged.connect(self._update_formula_completions)
        self.cursorPositionChanged.connect(self._update_formula_completions)

    def _install_shortcut(self, sequence: str, callback: Callable[[], None]) -> None:
        action = QAction(self)
        action.setShortcut(QKeySequence(sequence))
        action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        action.triggered.connect(callback)
        self.addAction(action)

    def _merge_format(self, fmt: QTextCharFormat) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(fmt)
        self.mergeCurrentCharFormat(fmt)
        self.setFocus()

    def toggle_bold(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontWeight(
            QFont.Weight.Normal
            if self.fontWeight() >= QFont.Weight.Bold else QFont.Weight.Bold
        )
        self._merge_format(fmt)

    def toggle_underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.fontUnderline())
        self._merge_format(fmt)

    def toggle_italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.fontItalic())
        self._merge_format(fmt)

    def set_note_font(self, family: str) -> None:
        fmt = QTextCharFormat(); fmt.setFontFamily(family); self._merge_format(fmt)

    def set_note_size(self, size: int) -> None:
        fmt = QTextCharFormat(); fmt.setFontPointSize(float(size)); self._merge_format(fmt)

    def insert_formula_template(self) -> None:
        cursor = self.textCursor()
        cursor.insertText("{}")
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)
        self.setFocus()
        self._update_formula_completions(force=True)

    def _formula_token(self) -> tuple[str, int, int] | None:
        text = self.toPlainText()
        cursor = self.textCursor().position()
        left = text.rfind("{", 0, cursor + 1)
        if left < 0 or text.rfind("}", 0, cursor) > left:
            return None
        right = text.find("}", cursor)
        if right < 0:
            return None
        before = text[left + 1:cursor]
        match = re.search(r"[A-Za-z_][A-Za-z0-9_.]*$", before)
        start = left + 1 + (match.start() if match else len(before))
        query = match.group(0) if match else ""
        tail = re.match(r"[A-Za-z0-9_.]*", text[cursor:right])
        end = cursor + (len(tail.group(0)) if tail else 0)
        return query, start, end

    def _update_formula_completions(self, *_args, force: bool = False) -> None:
        token = self._formula_token()
        if token is None or self.suggestion_provider is None or not self.hasFocus():
            self.completion_popup.hide()
            return
        query, start, end = token
        if not force and not query:
            self.completion_popup.hide()
            return
        folded = query.casefold()
        candidates = []
        for suggestion in self.suggestion_provider():
            reference = str(suggestion.reference)
            reference_folded = reference.casefold()
            if folded and folded not in reference_folded:
                continue
            segments = reference_folded.replace("()", "").split(".")
            priority = (
                0 if reference_folded.startswith(folded) else
                1 if any(value.startswith(folded) for value in segments) else 2
            )
            candidates.append((priority, len(reference), reference_folded, suggestion))
        candidates.sort(key=lambda value: value[:3])
        self.completion_popup.clear()
        self._completion_span = (start, end)
        for _priority, _length, _reference, suggestion in candidates[:60]:
            item = QTreeWidgetItem(
                (str(suggestion.reference), str(suggestion.value), str(suggestion.description))
            )
            item.setData(
                0, Qt.ItemDataRole.UserRole,
                str(suggestion.insertion or suggestion.reference),
            )
            self.completion_popup.addTopLevelItem(item)
        if not self.completion_popup.topLevelItemCount():
            self.completion_popup.hide()
            return
        self.completion_popup.setCurrentItem(self.completion_popup.topLevelItem(0))
        rows = min(10, self.completion_popup.topLevelItemCount())
        row_height = max(24, self.completion_popup.sizeHintForRow(0))
        width = max(620, self.width())
        height = self.completion_popup.header().sizeHint().height() + rows * row_height + 6
        origin = self.mapToGlobal(self.cursorRect().bottomLeft())
        self.completion_popup.setGeometry(origin.x(), origin.y(), width, height)
        self.completion_popup.show()

    def _insert_selected_completion(self, *_args) -> None:
        item = self.completion_popup.currentItem()
        if item is None:
            return
        insertion = str(item.data(0, Qt.ItemDataRole.UserRole) or item.text(0))
        start, end = self._completion_span
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(insertion)
        if insertion.endswith("()"):
            cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)
        self.completion_popup.hide()
        self.setFocus()

    def keyPressEvent(self, event) -> None:
        if self.completion_popup.isVisible():
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                count = self.completion_popup.topLevelItemCount()
                current = self.completion_popup.indexOfTopLevelItem(
                    self.completion_popup.currentItem()
                )
                row = (max(0, current) + (1 if event.key() == Qt.Key.Key_Down else -1)) % count
                self.completion_popup.setCurrentItem(self.completion_popup.topLevelItem(row))
                return
            if event.key() == Qt.Key.Key_Tab:
                self._insert_selected_completion()
                return
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.completion_popup.hide()
                self.finalize_formulas()
                return
            if event.key() == Qt.Key.Key_Escape:
                self.completion_popup.hide()
                return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z and not self.document().isUndoAvailable():
                self.page_undo_requested.emit()
                return
            if event.key() == Qt.Key.Key_Y and not self.document().isRedoAvailable():
                self.page_redo_requested.emit()
                return
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and self._formula_token() is not None
        ):
            self.completion_popup.hide()
            self.finalize_formulas()
            return
        super().keyPressEvent(event)
        self._update_formula_completions()

    def _show_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        formula_span = self._formula_span_at_position(
            self.cursorForPosition(position).position()
        )
        if formula_span is not None:
            open_formula = menu.addAction("Open Formula")
            open_formula.triggered.connect(
                lambda: self._open_formula_span(formula_span)
            )
            menu.addSeparator()
        for label, callback, enabled in (
            ("Cut", self.cut, self.textCursor().hasSelection()),
            ("Copy", self.copy, self.textCursor().hasSelection()),
            ("Paste", self.paste, self.canPaste()),
            ("Delete", self._delete_selection, self.textCursor().hasSelection()),
        ):
            action = menu.addAction(label)
            action.setEnabled(enabled)
            action.triggered.connect(callback)
        menu.addSeparator()
        formula = menu.addAction("Write Formula")
        formula.triggered.connect(self.insert_formula_template)
        menu.exec(self.mapToGlobal(position))

    def _delete_selection(self) -> None:
        cursor = self.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()

    def focusOutEvent(self, event) -> None:
        self.completion_popup.hide()
        if event.reason() == Qt.FocusReason.MouseFocusReason:
            self.finalize_formulas()
        super().focusOutEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        current = self.textCursor().position()
        target = self.cursorForPosition(event.position().toPoint()).position()
        text = self.toPlainText()
        left = text.rfind("{", 0, current + 1)
        right = text.find("}", current)
        if left >= 0 and right >= current and not (left <= target <= right):
            self.finalize_formulas()
        super().mousePressEvent(event)

    def finalize_formulas(self) -> None:
        text = self.toPlainText()
        ranges: list[tuple[int, int, str]] = []
        start = 0
        while True:
            left = text.find("{", start)
            if left < 0:
                break
            right = text.find("}", left + 1)
            if right < 0:
                break
            expression = text[left + 1:right].strip()
            if expression:
                ranges.append((left, right + 1, expression))
            start = right + 1
        for left, right, expression in reversed(ranges):
            try:
                result = _number_text(self.evaluator(expression))
            except Exception:
                continue
            cursor = QTextCursor(self.document())
            cursor.setPosition(left)
            cursor.setPosition(right, QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setProperty(FORMULA_PROPERTY, expression)
            fmt.setAnchor(True)
            fmt.setAnchorHref("formula:" + urllib.parse.quote(expression, safe=""))
            fmt.setFontWeight(QFont.Weight.DemiBold)
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DotLine)
            fmt.setToolTip(f"Formula: {expression} · double-click to edit")
            cursor.insertText(result, fmt)
        if ranges:
            self.changed_for_save.emit()

    def refresh_formula_results(self) -> None:
        fragments: list[tuple[int, int, str, QTextCharFormat]] = []
        block = self.document().begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    expression = _formula_expression(fragment.charFormat())
                    if expression:
                        fragments.append(
                            (
                                fragment.position(), fragment.length(),
                                str(expression), fragment.charFormat(),
                            )
                        )
                iterator += 1
            block = block.next()
        for position, length, expression, fmt in reversed(fragments):
            try:
                result = _number_text(self.evaluator(expression))
            except Exception:
                continue
            cursor = QTextCursor(self.document())
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(result, fmt)

    def _formula_span_at_position(
        self, position: int
    ) -> tuple[int, int, str] | None:
        maximum = max(0, self.document().characterCount() - 1)
        expression = ""
        character_position = -1
        for candidate in (position, position - 1):
            if not 0 <= candidate < maximum:
                continue
            probe = QTextCursor(self.document())
            probe.setPosition(candidate)
            probe.setPosition(candidate + 1, QTextCursor.MoveMode.KeepAnchor)
            expression = _formula_expression(probe.charFormat())
            if expression:
                character_position = candidate
                break
        if not expression:
            return None
        start = character_position
        end = character_position + 1
        while start > 0:
            check = QTextCursor(self.document())
            check.setPosition(start - 1); check.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
            if _formula_expression(check.charFormat()) != expression:
                break
            start -= 1
        while end < maximum:
            check = QTextCursor(self.document())
            check.setPosition(end); check.setPosition(end + 1, QTextCursor.MoveMode.KeepAnchor)
            if _formula_expression(check.charFormat()) != expression:
                break
            end += 1
        return start, end, str(expression)

    def _open_formula_span(self, span: tuple[int, int, str]) -> None:
        start, end, expression = span
        cursor = QTextCursor(self.document())
        cursor.setPosition(start); cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText("{" + str(expression) + "}", QTextCharFormat())
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self.setTextCursor(cursor)
        self.setFocus()
        self._update_formula_completions()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        span = self._formula_span_at_position(
            self.cursorForPosition(event.position().toPoint()).position()
        )
        if span is None:
            super().mouseDoubleClickEvent(event)
            return
        self._open_formula_span(span)


class FloatingNoteWidget(QFrame):
    save_requested = Signal()
    pin_changed = Signal(bool)

    def __init__(
        self,
        note: SheetNote,
        evaluator: Callable[[str], object],
        suggestion_provider: Callable[[], tuple] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.note_id = note.id
        self.character_id = note.character_id
        self.page_key = note.page_key
        self.pinned = note.pinned
        self.user_visible = note.visible
        self._drag_origin: QPoint | None = None
        self._resize_origin: QPoint | None = None
        self._resize_size = None
        self.resize_handle = None
        try:
            loaded_pages = json.loads(note.pages_json or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            loaded_pages = []
        self.pages = [str(value) for value in loaded_pages if isinstance(value, str)]
        if not self.pages:
            self.pages = [note.content_html or ""]
        self.current_page = min(max(0, note.current_page), len(self.pages) - 1)
        self._page_undo: list[tuple[list[str], int]] = []
        self._page_redo: list[tuple[list[str], int]] = []
        self.page_buttons: list[QToolButton] = []
        self.setObjectName("floatingNoteOverlay")
        self.setMinimumSize(250, 150)
        self.setGeometry(note.x, note.y, note.width, note.height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.page_rail = QFrame()
        self.page_rail.setObjectName("floatingNotePageRail")
        self.page_rail.setFixedWidth(34)
        self.page_rail_layout = QVBoxLayout(self.page_rail)
        self.page_rail_layout.setContentsMargins(0, 10, 0, 4)
        self.page_rail_layout.setSpacing(3)
        outer.addWidget(self.page_rail)
        self.note_body = QFrame()
        self.note_body.setObjectName("floatingSheetNote")
        outer.addWidget(self.note_body, 1)

        layout = QVBoxLayout(self.note_body)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.title_bar = QFrame()
        self.title_bar.setObjectName("floatingNoteTitleBar")
        self.title_bar.setFixedHeight(28)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(4, 1, 3, 1)
        self.pin_button = QToolButton()
        self.pin_button.setObjectName("floatingNotePin")
        self.pin_button.setText("📌")
        self.pin_button.setCheckable(True)
        self.pin_button.setChecked(self.pinned)
        self.pin_button.setToolTip(
            "Unpin this note" if self.pinned
            else "Pin this note to the current sheet page"
        )
        self.pin_button.clicked.connect(self._toggle_pin)
        title_layout.addWidget(self.pin_button)
        title_layout.addStretch()
        close = QToolButton(); close.setObjectName("floatingNoteClose"); close.setText("×")
        close.setToolTip("Close note (content is preserved)")
        close.clicked.connect(self._close_preserving)
        title_layout.addWidget(close)
        self.title_bar.installEventFilter(self)
        layout.addWidget(self.title_bar)

        self.toolbar_toggle = QToolButton()
        self.toolbar_toggle.setObjectName("floatingNoteToolbarToggle")
        self.toolbar_toggle.setText("▲" if note.toolbar_expanded else "▼")
        self.toolbar_toggle.clicked.connect(self._toggle_toolbar)
        layout.addWidget(self.toolbar_toggle, 0, Qt.AlignmentFlag.AlignHCenter)

        self.toolbar = QFrame(); self.toolbar.setObjectName("floatingNoteToolbar")
        tools = QGridLayout(self.toolbar); tools.setContentsMargins(4, 2, 4, 3)
        self.font_choice = QComboBox()
        self.font_choice.addItems(("Georgia", "Segoe UI", "Arial", "Times New Roman", "Verdana", "Courier New"))
        self.font_choice.currentTextChanged.connect(lambda value: self.editor.set_note_font(value))
        self.font_size = QSpinBox(); self.font_size.setRange(7, 48); self.font_size.setValue(11)
        self.font_size.valueChanged.connect(lambda value: self.editor.set_note_size(value))
        self.bold = QPushButton("Bold")
        self.underline = QPushButton("Underline")
        self.italic = QPushButton("Cursive")
        self.bold.clicked.connect(self.editor_toggle_bold)
        self.underline.clicked.connect(self.editor_toggle_underline)
        self.italic.clicked.connect(self.editor_toggle_italic)
        tools.addWidget(self.font_choice, 0, 0, 1, 2)
        tools.addWidget(self.font_size, 0, 2)
        tools.addWidget(self.bold, 1, 0)
        tools.addWidget(self.underline, 1, 1)
        tools.addWidget(self.italic, 1, 2)
        self.toolbar.setVisible(note.toolbar_expanded)
        layout.addWidget(self.toolbar)

        self.editor = FormulaNoteEditor(evaluator, suggestion_provider)
        self.editor.setObjectName("floatingNoteEditor")
        self.editor.setHtml(self.pages[self.current_page])
        self.editor.changed_for_save.connect(self.save_requested)
        self.editor.page_undo_requested.connect(self._undo_page_change)
        self.editor.page_redo_requested.connect(self._redo_page_change)
        layout.addWidget(self.editor, 1)
        self._rebuild_page_rail()

        self.resize_handle = QLabel("●", self)
        self.resize_handle.setObjectName("floatingNoteResizeHandle")
        self.resize_handle.setFixedSize(18, 18)
        self.resize_handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resize_handle.installEventFilter(self)
        self.resize_handle.raise_()
        self._place_resize_handle()

    def editor_toggle_bold(self) -> None: self.editor.toggle_bold()
    def editor_toggle_underline(self) -> None: self.editor.toggle_underline()
    def editor_toggle_italic(self) -> None: self.editor.toggle_italic()

    def _sync_current_page(self) -> None:
        self.pages[self.current_page] = self.editor.toHtml()

    def _rebuild_page_rail(self) -> None:
        while self.page_rail_layout.count():
            item = self.page_rail_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.page_buttons = []
        for index in range(len(self.pages)):
            button = QToolButton()
            button.setObjectName("floatingNotePageTab")
            button.setText(str(index + 1))
            button.setCheckable(True)
            button.setChecked(index == self.current_page)
            button.setToolTip(
                f"Note page {index + 1} · right-click for page options"
            )
            button.clicked.connect(lambda _checked=False, page=index: self._switch_page(page))
            button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            button.customContextMenuRequested.connect(
                lambda position, page=index, source=button:
                self._show_page_menu(page, source, position)
            )
            self.page_rail_layout.addWidget(button)
            self.page_buttons.append(button)
        add_page = QToolButton()
        add_page.setObjectName("floatingNoteAddPage")
        add_page.setText("+")
        add_page.setToolTip("Add a note page")
        add_page.clicked.connect(self._add_page)
        self.page_rail_layout.addWidget(add_page)
        self.page_rail_layout.addStretch()

    def _switch_page(self, index: int) -> None:
        if index == self.current_page or not 0 <= index < len(self.pages):
            return
        self.editor.finalize_formulas()
        self._sync_current_page()
        self.current_page = index
        self.editor.blockSignals(True)
        self.editor.setHtml(self.pages[index])
        self.editor.blockSignals(False)
        self.editor.refresh_formula_results()
        self._rebuild_page_rail()
        self.editor.setFocus()
        self.save_requested.emit()

    def _add_page(self) -> None:
        self._record_page_change()
        self.pages.append("")
        self.current_page = len(self.pages) - 1
        self.editor.blockSignals(True)
        self.editor.clear()
        self.editor.blockSignals(False)
        self._rebuild_page_rail()
        self.editor.setFocus()
        self.save_requested.emit()

    def _page_state(self) -> tuple[list[str], int]:
        self.editor.finalize_formulas()
        self._sync_current_page()
        return (list(self.pages), self.current_page)

    def _record_page_change(self) -> None:
        self._page_undo.append(self._page_state())
        self._page_undo = self._page_undo[-50:]
        self._page_redo.clear()

    def _restore_page_state(self, state: tuple[list[str], int]) -> None:
        pages, current = state
        self.pages = list(pages) or [""]
        self.current_page = min(max(0, int(current)), len(self.pages) - 1)
        self.editor.blockSignals(True)
        self.editor.setHtml(self.pages[self.current_page])
        self.editor.blockSignals(False)
        self.editor.refresh_formula_results()
        self._rebuild_page_rail()
        self.editor.setFocus()
        self.save_requested.emit()

    def _undo_page_change(self) -> None:
        if not self._page_undo:
            return
        self._page_redo.append(self._page_state())
        self._restore_page_state(self._page_undo.pop())

    def _redo_page_change(self) -> None:
        if not self._page_redo:
            return
        self._page_undo.append(self._page_state())
        self._restore_page_state(self._page_redo.pop())

    def _page_has_content(self, index: int) -> bool:
        document = QTextDocument()
        document.setHtml(self.pages[index])
        return bool(document.toPlainText().strip())

    def _show_page_menu(
        self, index: int, source: QWidget, position: QPoint
    ) -> None:
        self.editor.finalize_formulas()
        self._sync_current_page()
        menu = QMenu(self)
        remove = menu.addAction(f"Delete Page {index + 1}")
        remove.setEnabled(len(self.pages) > 1)
        remove.triggered.connect(lambda: self._delete_page(index))
        menu.addSeparator()
        undo = menu.addAction("Undo Page Change")
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        undo.setEnabled(bool(self._page_undo))
        undo.triggered.connect(self._undo_page_change)
        redo = menu.addAction("Redo Page Change")
        redo.setShortcut(QKeySequence.StandardKey.Redo)
        redo.setEnabled(bool(self._page_redo))
        redo.triggered.connect(self._redo_page_change)
        menu.exec(source.mapToGlobal(position))

    def _delete_page(self, index: int) -> None:
        if len(self.pages) <= 1 or not 0 <= index < len(self.pages):
            return
        self.editor.finalize_formulas()
        self._sync_current_page()
        if self._page_has_content(index):
            answer = QMessageBox.question(
                self,
                f"Delete Note Page {index + 1}",
                f"Page {index + 1} contains content. Delete it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._record_page_change()
        del self.pages[index]
        if index < self.current_page:
            self.current_page -= 1
        elif index == self.current_page:
            self.current_page = min(index, len(self.pages) - 1)
        self._restore_page_state((self.pages, self.current_page))

    def _toggle_toolbar(self) -> None:
        visible = not self.toolbar.isVisible()
        self.toolbar.setVisible(visible)
        self.toolbar_toggle.setText("▲" if visible else "▼")
        self.save_requested.emit()

    def _toggle_pin(self) -> None:
        self.pinned = self.pin_button.isChecked()
        self.pin_button.setToolTip(
            "Unpin this note" if self.pinned
            else "Pin this note to the current sheet page"
        )
        self.pin_changed.emit(self.pinned)
        self.save_requested.emit()

    def _close_preserving(self) -> None:
        self.editor.finalize_formulas()
        self.user_visible = False
        self.hide()
        self.save_requested.emit()

    def _place_resize_handle(self) -> None:
        if self.resize_handle is not None:
            self.resize_handle.move(self.width() - 19, self.height() - 19)

    def resizeEvent(self, event) -> None:
        self._place_resize_handle()
        super().resizeEvent(event)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.title_bar:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_origin = event.globalPosition().toPoint() - self.pos()
                self.raise_(); return True
            if event.type() == QEvent.Type.MouseMove and self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
                target = event.globalPosition().toPoint() - self._drag_origin
                if self.parentWidget() is not None:
                    target.setX(max(0, min(target.x(), self.parentWidget().width() - self.width())))
                    target.setY(max(0, min(target.y(), self.parentWidget().height() - self.height())))
                self.move(target); return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_origin = None; self.save_requested.emit(); return True
        if self.resize_handle is not None and watched is self.resize_handle:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._resize_origin = event.globalPosition().toPoint(); self._resize_size = self.size(); return True
            if event.type() == QEvent.Type.MouseMove and self._resize_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
                delta = event.globalPosition().toPoint() - self._resize_origin
                self.resize(max(220, self._resize_size.width() + delta.x()), max(150, self._resize_size.height() + delta.y()))
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._resize_origin = None; self._resize_size = None; self.save_requested.emit(); return True
        return super().eventFilter(watched, event)

    def snapshot(self) -> dict:
        # Autosave must preserve an actively edited ``{formula}``.  Committing
        # is an explicit editor interaction (Enter or a mouse-focus departure),
        # not a persistence side effect.
        self._sync_current_page()
        return {
            "page_key": self.page_key,
            "x": self.x(), "y": self.y(), "width": self.width(), "height": self.height(),
            "pinned": self.pinned,
            "content_html": self.pages[0],
            "toolbar_expanded": self.toolbar.isVisible(),
            "visible": self.user_visible,
            "pages_json": json.dumps(self.pages, ensure_ascii=False),
            "current_page": self.current_page,
        }


class FloatingNoteManager:
    def __init__(
        self,
        repository,
        host: QWidget,
        page_key: Callable[[], str],
        evaluator: Callable[[str], object],
        suggestion_provider: Callable[[], tuple] | None = None,
    ) -> None:
        self.repository = repository
        self.host = host
        self.page_key = page_key
        self.evaluator = evaluator
        self.suggestion_provider = suggestion_provider
        self.character_id: int | None = None
        self.notes: list[FloatingNoteWidget] = []
        self.save_timer = QTimer(host); self.save_timer.setSingleShot(True); self.save_timer.setInterval(250)
        self.save_timer.timeout.connect(self.save_all)

    def load_character(self, character_id: int) -> None:
        self.clear()
        self.character_id = character_id
        for record in self.repository.list_sheet_notes(character_id):
            self._make_widget(record)
        self.page_changed()

    def clear(self) -> None:
        self.save_all()
        for note in self.notes:
            note.deleteLater()
        self.notes.clear(); self.character_id = None

    def create_or_show(self, global_position: QPoint, *, formula: bool = False) -> None:
        if self.character_id is None:
            return
        hidden = next((note for note in self.notes if not note.isVisible()), None)
        if hidden is not None:
            hidden.user_visible = True
            hidden.show(); hidden.raise_(); hidden.editor.setFocus()
            if formula: hidden.editor.insert_formula_template()
            self.schedule_save()
            return
        local = self.host.mapFromGlobal(global_position)
        x = max(0, min(local.x(), max(0, self.host.width() - 360)))
        y = max(0, min(local.y(), max(0, self.host.height() - 260)))
        note_id = self.repository.add_sheet_note(
            self.character_id, x=x, y=y, page_key=self.page_key()
        )
        record = next(
            value for value in self.repository.list_sheet_notes(self.character_id)
            if value.id == note_id
        )
        widget = self._make_widget(record)
        widget.show(); widget.raise_(); widget.editor.setFocus()
        if formula: widget.editor.insert_formula_template()

    def _make_widget(self, record: SheetNote) -> FloatingNoteWidget:
        widget = FloatingNoteWidget(
            record, self.evaluator, self.suggestion_provider, self.host
        )
        widget.save_requested.connect(self.schedule_save)
        widget.pin_changed.connect(lambda pinned, widget=widget: self._pin(widget, pinned))
        self.notes.append(widget)
        widget.setVisible(record.visible)
        if record.visible:
            widget.raise_()
        return widget

    def _pin(self, widget: FloatingNoteWidget, pinned: bool) -> None:
        if pinned:
            widget.page_key = self.page_key()
        self.page_changed()

    def schedule_save(self) -> None:
        self.save_timer.start()

    def save_all(self) -> None:
        if self.character_id is None:
            return
        for note in self.notes:
            self.repository.update_sheet_note(
                self.character_id, note.note_id, **note.snapshot()
            )

    def page_changed(self) -> None:
        current = self.page_key()
        for note in self.notes:
            visible = note.user_visible and (
                not note.pinned or note.page_key == current
            )
            note.setVisible(visible)
            if visible:
                note.raise_(); note.editor.refresh_formula_results()

    def refresh_formulas(self) -> None:
        for note in self.notes:
            note.editor.refresh_formula_results()
            note._sync_current_page()

    def set_host_visible(self, visible: bool) -> None:
        if not visible:
            for note in self.notes: note.hide()
        else:
            self.page_changed()

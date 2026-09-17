"""A theme boundary prevents sheet-local styles leaking into child dialogs."""
from functools import lru_cache
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPalette, QTextCursor, QTextCharFormat
from PySide6.QtWidgets import QDialog, QAbstractItemView, QStyledItemDelegate, QTextBrowser
from app.ui.theme import style_sheet


@lru_cache(maxsize=3)
def dialog_stylesheet(theme):
    from app.ui.refined.theme import PALETTES
    p=PALETTES.get(theme,PALETTES['classic'])
    return style_sheet(theme) + f'''
        QDialog {{ background: {p.page}; color: {p.text}; font: 10pt 'Segoe UI'; }}
        QDialog QLineEdit, QDialog QComboBox, QDialog QAbstractSpinBox {{
            background: {p.surface}; color: {p.text}; border: 1px solid {p.line};
            border-radius: 5px; padding: 5px 8px; min-height: 22px; font: 11pt 'Segoe UI';
        }}
        QDialog QPushButton {{ min-height: 24px; padding: 5px 12px; border-radius: 5px; }}
        QDialog QTextEdit, QDialog QPlainTextEdit, QDialog QTextBrowser {{
            background: {p.surface}; color: {p.text}; border: 1px solid {p.line};
            border-radius: 6px; font: 11pt 'Segoe UI'; selection-background-color: {p.selection};
        }}
        QDialog QTableView, QDialog QListView {{ background: {p.surface}; color: {p.text};
            alternate-background-color: {p.page}; border: 1px solid {p.line};
            selection-background-color: {p.selection}; selection-color: {p.text}; font: 10pt 'Segoe UI'; }}
        QDialog QListView::item {{ padding: 6px 8px; color: {p.text}; }}
        QDialog QListView::item:selected {{ background: {p.selection}; color: {p.text}; }}
        QDialog QListWidget#catalogSphereList {{ background: {p.surface}; color: {p.text};
            border: 1px solid {p.line}; }}
        QDialog QListWidget::item {{ background: transparent; color: {p.text}; border-color: {p.line}; }}
        QDialog QListWidget::item:hover {{ background: {p.page}; }}
        QDialog QListWidget::item:selected {{ background: {p.selection}; color: {p.text}; }}
        QDialog QScrollArea#dialogFormScroll, QDialog QScrollArea#dialogFormScroll > QWidget > QWidget {{
            background: {p.page}; }}
        QDialog QHeaderView::section {{ background: {p.selection}; color: {p.text};
            padding: 7px 8px; border: none; border-bottom: 1px solid {p.line}; font: 600 9pt 'Segoe UI'; }}
        QDialog QLabel#catalogTalentTitle {{ color: {p.text}; font: 600 17pt 'Segoe UI'; padding: 2px 0; }}
        QDialog QLabel#sectionTitle, QDialog QLabel#heroTitle {{ background: transparent;
            color: {p.text}; font: 600 16pt 'Segoe UI'; padding: 4px 0; }}
        QDialog QSplitter::handle {{ background: {p.page}; }}
        QDialog QLabel {{ background: transparent; }}
        QFrame#inventoryOrganizerCategory, QFrame#inventoryOrganizerContainer {{
            background: {p.surface}; border: 1px solid {p.line}; border-radius: 5px;
        }}
        QWidget#inventoryOrganizerCanvas, QScrollArea#inventoryOrganizerScroll {{
            background: {p.page};
        }}
        QLabel#inventoryOrganizerCategoryTitle {{
            background: {p.selection}; color: {p.text};
        }}
        QLabel#inventoryOrganizerContainerCategory, QLabel#inventoryOrganizerSubcategory {{
            color: {p.text}; border-color: {p.line};
        }}
        QListWidget#inventoryOrganizerList {{
            background: {p.surface}; color: {p.text}; border-color: {p.line};
        }}
        QListWidget#inventoryOrganizerList::item {{ color: {p.text}; background: transparent; }}
        QListWidget#inventoryOrganizerList::item:selected {{ background: {p.selection}; color: {p.text}; }}
        QLabel#catalogBehaviorNote {{ background: {p.surface}; color: {p.muted};
            border: 1px solid {p.line}; padding: 4px 7px; font: 9pt 'Segoe UI'; }}
    '''


class DialogItemDelegate(QStyledItemDelegate):
    """Translate legacy status ink without changing catalog data or selection."""
    def __init__(self, view, theme):
        super().__init__(view)
        self.theme = theme

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        if not isinstance(brush, QBrush):
            return
        dark = self.theme() == 'dark'
        colors = {
            '#008000': '#A4DEB3' if dark else '#245E35',
            '#808000': '#E9CD87' if dark else '#69520F',
            '#800000': '#FFB4AA' if dark else '#9E302B',
            '#ff0000': '#FFB4AA' if dark else '#9E302B',
            '#808080': '#BAC4CC' if dark else '#555B5F',
            '#a0a0a4': '#BAC4CC' if dark else '#555B5F',
        }
        color = colors.get(brush.color().name())
        if color:
            option.palette.setColor(QPalette.ColorRole.Text, QColor(color))


class DialogThemeBoundary:
    def __init__(self, owner):
        self.owner = owner

    def apply(self, dialog):
        if not isinstance(dialog, QDialog):
            return
        ancestor = dialog.parentWidget()
        while ancestor is not None and ancestor is not self.owner:
            ancestor = ancestor.parentWidget()
        if ancestor is None:
            return
        if dialog.property("originalDialogStyle") is None:
            dialog.setProperty("originalDialogStyle", dialog.styleSheet())
        value = dialog_stylesheet(self.owner.theme) + str(dialog.property("originalDialogStyle") or "")
        if dialog.styleSheet() != value:
            dialog.setStyleSheet(value)
        from app.ui.refined.theme import PALETTES
        p=PALETTES.get(self.owner.theme,PALETTES['classic'])
        palette=dialog.palette()
        palette.setColor(QPalette.ColorRole.Link,QColor(p.accent))
        palette.setColor(QPalette.ColorRole.LinkVisited,QColor(p.accent))
        dialog.setPalette(palette)
        style_dialog_links(dialog, p.accent)
        for view in dialog.findChildren(QAbstractItemView):
            # Custom editors and specialised delegates retain their behavior.
            if type(view.itemDelegate()) is QStyledItemDelegate:
                view.setItemDelegate(DialogItemDelegate(view, lambda: self.owner.theme))
        from app.ui.sphere_colors import refresh_sphere_colors
        refresh_sphere_colors(dialog, self.owner.theme)
        from app.ui.dialog_layout import apply_dialog_layout
        apply_dialog_layout(dialog)
        if hasattr(dialog,'catalog_presentation'):
            dialog.catalog_presentation.schedule()

    def refresh(self):
        for dialog in self.owner.findChildren(QDialog):
            self.apply(dialog)


def style_dialog_links(dialog, color):
    """Keep existing and subsequently rendered rules links legible in each theme."""
    for browser in dialog.findChildren(QTextBrowser):
        document = browser.document()
        original = browser.property('dialogDocumentStyle')
        if original is None:
            original = document.defaultStyleSheet()
            browser.setProperty('dialogDocumentStyle', original)
        document.setDefaultStyleSheet(str(original) + f'\na {{ color: {color}; }}')
        # Existing rich text is already parsed. Recolor anchors without replacing
        # the document, losing its scroll position, or touching editable notes.
        if browser.property('dialogLinkColor') == color:
            continue
        browser.setProperty('dialogLinkColor', color)
        ranges = []
        block = document.begin()
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid() and fragment.charFormat().isAnchor():
                    ranges.append((fragment.position(), fragment.length()))
                iterator += 1
            block = block.next()
        formatting = QTextCharFormat()
        formatting.setForeground(QColor(color))
        for position, length in ranges:
            cursor = QTextCursor(document)
            cursor.setPosition(position)
            cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
            cursor.mergeCharFormat(formatting)

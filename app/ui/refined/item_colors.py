"""Theme-aware presentation of legacy semantic colors; never rewrites data."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QPalette
from PySide6.QtWidgets import QApplication, QStyledItemDelegate, QStyle, QStyleOptionViewItem
from .theme import PALETTES
from app.ui.sphere_colors import sphere_surface


class RefinedItemDelegate(QStyledItemDelegate):
    def __init__(self, table, theme):
        super().__init__(table)
        self.table = table
        self.theme = theme
        self.sphere_column = next((c for c in range(table.columnCount())
            if table.horizontalHeaderItem(c) and table.horizontalHeaderItem(c).text().casefold() == 'sphere'), None)

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        palette = PALETTES.get(self.theme(), PALETTES["classic"])
        background = index.data(Qt.ItemDataRole.BackgroundRole)
        color = background.color().name().lower() if isinstance(background, QBrush) else ""
        category = {"#dae9f8": "magic", "#fbe2d5": "martial"}.get(color)
        if not color:
            category = self.table.property("refinedCategory")
        if category in ("magic", "martial"):
            sphere = index.siblingAtColumn(self.sphere_column).data() if self.sphere_column is not None else ''
            option.backgroundBrush = QBrush(QColor(sphere_surface(category, str(sphere or ''), self.theme(), getattr(palette, category))))
            option.features &= ~QStyleOptionViewItem.ViewItemFeature.Alternate
        foreground = index.data(Qt.ItemDataRole.ForegroundRole)
        text = foreground.color().name().lower() if isinstance(foreground, QBrush) else ""
        mapped = {
            "#252c35": palette.text,
            "#808080": palette.muted,
            "#a0a0a4": palette.muted,
            "#b00020": "#FFB4AA" if self.theme() == "dark" else "#A12E35",
            "#ff0000": "#FFB4AA" if self.theme() == "dark" else "#A12E35",
        }.get(text)
        if mapped:
            option.palette.setColor(QPalette.ColorRole.Text, QColor(mapped))
        option.palette.setColor(QPalette.ColorRole.Highlight, QColor(palette.selection))
        option.palette.setColor(QPalette.ColorRole.HighlightedText, QColor(palette.text))

    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        if styled.backgroundBrush.style() == Qt.BrushStyle.NoBrush:
            return super().paint(painter, option, index)
        # Stylesheet item backgrounds otherwise override both semantic brushes
        # and user colors. Draw these cells with Qt's application item style,
        # retaining the table's font, selection, check state, and elision.
        palette = PALETTES.get(self.theme(), PALETTES["classic"])
        selected = bool(styled.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.fillRect(styled.rect, QColor(palette.selection) if selected else styled.backgroundBrush)
        styled.widget = None
        styled.rect.adjust(5, 0, -5, -1)
        QApplication.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter)
        painter.setPen(QColor(palette.line))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        painter.restore()

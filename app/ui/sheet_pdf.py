"""Qt-native, paginated export of the current sheet presentation."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QEventLoop, QIODevice, QMarginsF, QRectF, QSaveFile, QSignalBlocker, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter, QPixmap
from PySide6.QtWidgets import (
    QAbstractButton, QAbstractSpinBox, QApplication, QHeaderView, QLabel,
    QLineEdit, QScrollArea, QTableWidget, QTabWidget, QWidget,
)
from app.ui.equipment_figure import EquipmentFigure


def _content_spans(canvas):
    """Keep labels, value fields, and table rows together at page boundaries."""
    spans = []
    for child in canvas.findChildren(QWidget):
        if not child.isVisibleTo(canvas):
            continue
        if isinstance(child, QLabel) and child.height() >= 120:
            bottom = (child.mapTo(canvas, child.rect().topLeft()).y() + child.height()) * 2
            spans.append((bottom, bottom))
        if ((child.objectName() == "refinedCard" and child.height() < 300)
                or isinstance(child, EquipmentFigure)):
            top = child.mapTo(canvas, child.rect().topLeft()).y()
            spans.append((top * 2, (top + child.height()) * 2))
        if (isinstance(child, (QLabel, QAbstractButton, QAbstractSpinBox, QLineEdit, QHeaderView))
                and child.height() < 120):
            top = child.mapTo(canvas, child.rect().topLeft()).y()
            extra = 80 if child.objectName() in ("refinedSectionTitle", "sectionTitle") else 2
            spans.append((top * 2, (top + child.height() + extra) * 2))
        if isinstance(child, QTableWidget):
            top = child.viewport().mapTo(canvas, child.viewport().rect().topLeft()).y()
            for row in range(child.rowCount()):
                y = child.rowViewportPosition(row)
                if not child.isRowHidden(row) and 0 <= y < child.viewport().height():
                    padding = max(0, (child.rowHeight(row) - child.fontMetrics().height()) // 2)
                    spans.append(((top + y + padding) * 2,
                                  (top + y + child.rowHeight(row) - padding) * 2))
    return spans


def _page_ranges(height, available, spans):
    top = 0
    while top < height:
        end = min(height, top + int(available))
        if end < height:
            relevant = [(start, stop) for start, stop in spans if stop - start < available * .9]
            # Side-by-side tables may have staggered row boundaries. Search a
            # bounded area, rather than cascading back through every other row.
            candidates = [end, *(start for start, _ in relevant
                                 if end - available * .15 <= start <= end and start > top),
                          *(start for start, stop in relevant if stop - start > available * .3
                            and top + available * .3 < start < end < stop)]
            end = min(candidates, key=lambda y: (
                sum((8 if stop - start > available * .3 else 1)
                    for start, stop in relevant if start < y < stop), -y))
        yield top, end - top
        top = end


def _snapshot_page(canvas):
    """Expand scrollable tables only for capture, then restore live geometry."""
    original_size = canvas.size()
    tables = [(table, table.minimumHeight(), table.maximumHeight(), table.size(),
               table.verticalScrollBar().value(), table.horizontalScrollBar().value())
              for table in canvas.findChildren(QTableWidget) if table.isVisibleTo(canvas)]
    try:
        for table, *_ in tables:
            height = (table.horizontalHeader().height() + table.frameWidth() * 2 +
                      sum(table.rowHeight(row) for row in range(table.rowCount())
                          if not table.isRowHidden(row)) + 4)
            table.setFixedHeight(height)
            table.verticalScrollBar().setValue(0)
            table.horizontalScrollBar().setValue(0)
        # Propagate changed table minimums through nested responsive rows before
        # measuring the canvas. Do not run calculation/persistence timers here.
        for _ in range(3):
            QApplication.sendPostedEvents(None, QEvent.Type.LayoutRequest)
        if canvas.layout():
            canvas.layout().activate()
            canvas.resize(canvas.width(), max(canvas.height(), canvas.layout().sizeHint().height()))
            canvas.layout().activate()
        snapshot = QPixmap(canvas.size() * 2)
        snapshot.setDevicePixelRatio(2)
        snapshot.fill(Qt.GlobalColor.transparent)
        canvas.render(snapshot)
        spans = _content_spans(canvas)
        # QScrollArea can keep a tall, now-empty viewport below the last field.
        bottom = min(snapshot.height(), max((stop for _, stop in spans), default=snapshot.height()) + 32)
        return snapshot.toImage().copy(0, 0, snapshot.width(), bottom), spans
    finally:
        for table, minimum, maximum, size, vertical, horizontal in tables:
            table.setMinimumHeight(minimum)
            table.setMaximumHeight(maximum)
            table.resize(size)
            table.verticalScrollBar().setValue(vertical)
            table.horizontalScrollBar().setValue(horizontal)
        canvas.resize(original_size)
        if canvas.layout():
            canvas.layout().activate()


def export_sheet_pdf(tabs: QTabWidget, filename: str | Path, title: str) -> int:
    """Render visible tabs, preserving the live UI and atomically saving the PDF."""
    pages = []
    current = tabs.currentIndex()
    scroll_positions = [(page, page.horizontalScrollBar().value(), page.verticalScrollBar().value())
                        for page in (tabs.widget(i) for i in range(tabs.count()))
                        if isinstance(page, QScrollArea)]
    # Materialize hidden tabs at their real viewport width without invoking
    # tab-change handlers that persist arrangements or change the details panel.
    with QSignalBlocker(tabs):
        try:
            for index in range(tabs.count()):
                if not tabs.isTabVisible(index):
                    continue
                tabs.setCurrentIndex(index)
                QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                page = tabs.widget(index)
                canvas = page.widget() if isinstance(page, QScrollArea) else page
                if canvas is None:
                    continue
                canvas.ensurePolished()
                if canvas.layout():
                    canvas.layout().activate()
                # Never render live widgets onto a printer: printer DPI and
                # QWidget.render's clipping can reflow/clip child widgets.
                snapshot, spans = _snapshot_page(canvas)
                pages.append((tabs.tabText(index), snapshot, spans))
        finally:
            tabs.setCurrentIndex(current)
            for page, horizontal, vertical in scroll_positions:
                page.horizontalScrollBar().setValue(horizontal)
                page.verticalScrollBar().setValue(vertical)
    if not pages:
        raise ValueError("There are no visible sheet pages to export.")

    output = QSaveFile(str(filename))
    if not output.open(QIODevice.OpenModeFlag.WriteOnly):
        raise OSError(output.errorString())
    writer = QPdfWriter(output)
    writer.setTitle(title)
    writer.setCreator("Character Sheet App")
    writer.setResolution(144)
    writer.setPageLayout(QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape,
        QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter,
    ))
    painter = QPainter()
    count = 0
    try:
        if not painter.begin(writer):
            raise OSError("Could not initialize PDF rendering.")
        header = 36
        for name, snapshot, spans in pages:
            scale = writer.width() / max(1, snapshot.width())
            original_scale = scale
            ranges = list(_page_ranges(snapshot.height(), (writer.height() - header) / scale, spans))
            # A small reduction avoids an almost-empty continuation page.
            while len(ranges) > 1 and ranges[-1][1] * scale < (writer.height() - header) * .2 and scale > original_scale * .86:
                scale *= .98
                ranges = list(_page_ranges(snapshot.height(), (writer.height() - header) / scale, spans))
            width = snapshot.width() * scale
            left = (writer.width() - width) / 2
            for top, height in ranges:
                if count and not writer.newPage():
                    raise OSError("Could not create a PDF page.")
                painter.fillRect(QRectF(0, 0, writer.width(), writer.height()), Qt.GlobalColor.white)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(QRectF(0, 0, writer.width(), header),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 f"{title} — {name}  |  {count + 1}")
                painter.drawImage(QRectF(left, header, width, height * scale), snapshot,
                                  QRectF(0, top, snapshot.width(), height))
                count += 1
        painter.end()
        # QPdfWriter finalizes the document before the atomic file is committed.
        del writer
        if not output.commit():
            raise OSError(output.errorString())
    except Exception:
        if painter.isActive():
            painter.end()
        output.cancelWriting()
        raise
    return count

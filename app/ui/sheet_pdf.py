"""Qt-native, paginated export of the current sheet presentation."""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QIODevice, QMarginsF, QPoint, QRectF, QSaveFile, Qt
from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtWidgets import QScrollArea, QTabWidget, QWidget


def export_sheet_pdf(tabs: QTabWidget, filename: str | Path, title: str) -> int:
    """Render visible tabs, preserving the live UI and atomically saving the PDF."""
    pages = []
    for index in range(tabs.count()):
        if not tabs.isTabVisible(index):
            continue
        page = tabs.widget(index)
        canvas = page.widget() if isinstance(page, QScrollArea) else page
        if canvas is not None:
            canvas.ensurePolished()
            if canvas.layout():
                canvas.layout().activate()
            pages.append((tabs.tabText(index), canvas))
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
        for name, canvas in pages:
            scale = writer.width() / max(1, canvas.width())
            slice_height = (writer.height() - header) / scale
            for part in range(max(1, math.ceil(canvas.height() / slice_height))):
                if count and not writer.newPage():
                    raise OSError("Could not create a PDF page.")
                painter.fillRect(QRectF(0, 0, writer.width(), writer.height()), Qt.GlobalColor.white)
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(QRectF(0, 0, writer.width(), header),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 f"{title} — {name}  |  {count + 1}")
                painter.save()
                painter.setClipRect(QRectF(0, header, writer.width(), writer.height() - header))
                painter.translate(0, header)
                painter.scale(scale, scale)
                painter.translate(0, -part * slice_height)
                canvas.render(painter, QPoint(), renderFlags=(
                    QWidget.RenderFlag.DrawWindowBackground | QWidget.RenderFlag.DrawChildren))
                painter.restore()
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

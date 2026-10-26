import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtPdf import QPdfDocument
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget

from app.ui.sheet_pdf import export_sheet_pdf, _page_ranges, _snapshot_page


def test_pdf_exports_visible_pages_and_preserves_view(tmp_path):
    app = QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/georgia.ttf")
    app.setFont(QFont("Georgia", 10))
    tabs = QTabWidget()
    tabs.resize(900, 600)
    for name, height in (("Overview", 1800), ("Equipment", 600), ("Hidden", 600)):
        scroll = QScrollArea()
        canvas = QWidget()
        canvas.resize(850, height)
        canvas.setStyleSheet("background: #efe6cc;")
        for y, text in ((20, f"{name} top"), (height - 60, f"{name} bottom")):
            label = QLabel(text, canvas)
            label.setGeometry(20, y, 400, 40)
            if text.endswith("bottom"):
                label.setStyleSheet("background: #ff0000;")
        scroll.setWidget(canvas)
        tabs.addTab(scroll, name)
    tabs.setTabVisible(2, False)
    tabs.show()
    app.processEvents()
    tabs.widget(0).verticalScrollBar().setValue(120)
    before = tabs.widget(0).verticalScrollBar().value()
    changes = QSignalSpy(tabs.currentChanged)
    path = tmp_path / "sheet.pdf"
    count = export_sheet_pdf(tabs, path, "Test Character")
    document = QPdfDocument()
    assert document.load(str(path)) == QPdfDocument.Error.None_
    assert document.pageCount() == count
    assert count > 2
    text = " ".join(document.getAllText(i).text() for i in range(count))
    assert "Overview" in text and "Equipment" in text and "Hidden" not in text
    # Content is snapshotted before printing, so printer metrics cannot reflow
    # live widgets. Verify bottom markers survive pagination visually.
    red_pages = 0
    for index in range(count):
        image = document.render(index, QSize(800, 560))
        red_pages += any(image.pixelColor(x, y).red() > 240
                         and image.pixelColor(x, y).green() < 20
                         for y in range(0, image.height(), 4)
                         for x in range(0, image.width(), 4))
    assert red_pages == 2
    assert not document.render(0, QSize(800, 560)).isNull()
    assert tabs.currentIndex() == 0
    assert changes.count() == 0
    assert tabs.widget(0).verticalScrollBar().value() == before
    tabs.close()


def test_empty_export_preserves_existing_file(tmp_path):
    app = QApplication.instance() or QApplication([])
    target = tmp_path / "existing.pdf"
    target.write_bytes(b"existing")
    import pytest
    with pytest.raises(ValueError, match="no visible"):
        export_sheet_pdf(QTabWidget(), target, "Empty")
    assert target.read_bytes() == b"existing"


def test_page_breaks_do_not_split_values_or_rows():
    ranges = list(_page_ranges(2500, 1000, [(950, 1050), (1900, 2000)]))
    assert ranges == [(0, 950), (950, 950), (1900, 600)]


def test_scrollable_table_is_captured_fully_and_restored():
    app = QApplication.instance() or QApplication([])
    canvas = QWidget()
    layout = QVBoxLayout(canvas)
    table = QTableWidget(30, 1)
    for row in range(30):
        table.setItem(row, 0, QTableWidgetItem(f"Row {row}"))
    table.setFixedHeight(100)
    layout.addWidget(table)
    canvas.resize(800, 150)
    canvas.show()
    app.processEvents()
    table.verticalScrollBar().setValue(5)
    before = (table.minimumHeight(), table.maximumHeight(), table.verticalScrollBar().value())
    image, spans = _snapshot_page(canvas)
    assert image.height() > 1000
    assert max(stop for _, stop in spans) > 1000
    assert (table.minimumHeight(), table.maximumHeight(), table.verticalScrollBar().value()) == before
    canvas.close()

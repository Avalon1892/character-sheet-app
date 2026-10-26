import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtPdf import QPdfDocument
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QTabWidget, QWidget

from app.ui.sheet_pdf import export_sheet_pdf


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
        scroll.setWidget(canvas)
        tabs.addTab(scroll, name)
    tabs.setTabVisible(2, False)
    tabs.show()
    app.processEvents()
    tabs.widget(0).verticalScrollBar().setValue(120)
    before = tabs.widget(0).verticalScrollBar().value()
    path = tmp_path / "sheet.pdf"
    count = export_sheet_pdf(tabs, path, "Test Character")
    document = QPdfDocument()
    assert document.load(str(path)) == QPdfDocument.Error.None_
    assert document.pageCount() == count
    assert count > 2
    text = " ".join(document.getAllText(i).text() for i in range(count))
    assert "Overview" in text and "Equipment" in text and "Hidden" not in text
    assert "Overview bottom" in text and "Equipment bottom" in text
    assert not document.render(0, QSize(800, 560)).isNull()
    assert tabs.currentIndex() == 0
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

"""Exercise reference routing in real dialogs with disposable character data."""
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings, QUrl, Qt
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui.main_window import MainWindow, CodexDialog
from app.ui.dialog_theme import dialog_stylesheet
from tools.create_validation_character import build_character
from tools.render_refined_sheet import settle

app = QApplication([])
for name in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + name)
app.setFont(QFont("Segoe UI", 10))
output = Path("artifacts/reference-details")
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, folder)
    repo = CharacterRepository(Path(folder) / "preview.db")
    try:
        cid = build_character(repo, "Skill reference preview")
        window = MainWindow(repo)
        window.resize(1500, 950)
        window.refresh_characters(cid)
        window.show()
        sheet = window.refined_sheet
        codex = CodexDialog(parent=window)
        for theme in ("classic", "light", "dark"):
            window._set_theme(theme)
            sheet.session.select_tab("skills")
            sheet.details_button.setChecked(True)
            settle(app)
            table = sheet.skill_table
            row = next(r for r in range(table.rowCount())
                       if table.item(r, 0).data(Qt.ItemDataRole.UserRole) == "acrobatics")
            table.cellClicked.emit(row, 0)
            settle(app)
            assert "Your check:" in sheet.feature_details.toPlainText()
            assert "narrow" in sheet.feature_details.toPlainText()
            assert "Skill Unlock" in sheet.feature_details.toPlainText()
            window.grab().save(str(output / (theme + "-skill-details.png")))
            codex.setStyleSheet(dialog_stylesheet(theme))
            codex._open_codex_link(QUrl("codex:skill:acrobatics"))
            assert "narrow" in codex.browser.toPlainText()
            codex.show()
            settle(app)
            codex.grab().save(str(output / (theme + "-skill-codex.png")))
            codex._open_codex_link(QUrl("codex:sequence-reference:finishers-arcane-apocalypse"))
            assert "9 link" in codex.browser.toPlainText()
            settle(app)
            codex.grab().save(str(output / (theme + "-sequence-codex.png")))
            codex.hide()
            print(theme, "skill Details and both Codex references OK", flush=True)
        codex.close()
        window.close()
        app.processEvents()
    finally:
        repo.close()

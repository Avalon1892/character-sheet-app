import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QUrl
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.ui.main_window import CodexDialog
from app.ui.dialog_theme import dialog_stylesheet
from tools.render_refined_sheet import settle

app = QApplication([])
for font in ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'georgiab.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
app.setFont(QFont('Segoe UI', 10))
output = Path('artifacts/gizmo-rules')
output.mkdir(parents=True, exist_ok=True)
dialog = CodexDialog()
dialog.resize(1450, 900)
for theme in ('classic', 'dark'):
    dialog.theme = theme
    dialog.setStyleSheet(dialog_stylesheet(theme))
    dialog.show()
    for page in ('mastering-gizmos', 'ai-and-mechanoids'):
        dialog._open_codex_link(QUrl('codex:gizmo-reference:' + page))
        settle(app)
        assert len(dialog.browser.toPlainText()) > 2000
        dialog.grab().save(str(output / (theme + '-' + page + '.png')))
    print(theme, 'gizmo reference displays OK', flush=True)
dialog.close()

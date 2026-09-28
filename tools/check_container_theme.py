"""Render container colors without touching any saved characters."""
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from app.database import CharacterRepository
from app.inventory_organization import InventoryOrganizationService
from app.ui.inventory_dialog import InventoryOrganizerDialog
from app.ui.dialog_theme import dialog_stylesheet

app = QApplication([])
for name in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + name)
app.setFont(QFont("Segoe UI", 10))
output = Path("artifacts/container-theme")
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    repo = CharacterRepository(Path(folder) / "preview.db")
    cid = repo.create_character("Preview", "Spheres")
    repo.add_equipment(cid, "Bag of Holding, Type I", "Gear", 1, 15,
                       False, 0, "untyped", None, "")
    dialog = InventoryOrganizerDialog(InventoryOrganizationService(repo, cid))
    for theme in ("classic", "dark"):
        dialog.setStyleSheet(dialog_stylesheet(theme))
        dialog.show()
        app.processEvents()
        dialog.grab().save(str(output / (theme + ".png")))
    dialog.close()
    repo.close()

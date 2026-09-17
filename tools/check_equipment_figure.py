"""Offscreen equipment-window review with temporary character data."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QFont, QFontDatabase
from app.database import CharacterRepository
from app.equipment_wearing import EquipmentWearService
from app.ui.equipment_figure import EquipmentFigureDialog
from app.ui.dialog_theme import dialog_stylesheet
app = QApplication([])
for face in ("segoeui.ttf", "segoeuib.ttf", "georgia.ttf", "georgiab.ttf"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + face)
app.setFont(QFont("Segoe UI", 10))
output = Path("artifacts/equipment-figure"); output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    repo = CharacterRepository(Path(folder) / "preview.db")
    try:
        cid = repo.create_character("Preview", "Spheres")
        service = EquipmentWearService(repo, cid)
        for name, slot in (("Boots of Speed", "Feet"), ("Cloak of Resistance", "Shoulders"),
                           ("Ring of Protection", "Ring (Left)"), ("Amulet of Mighty Fists", "Neck")):
            item = repo.add_equipment(cid, name, "Gear", 1, 1, False, 0, "untyped", None, "", slot=slot)
            service.equip(item, slot)
        owner = QWidget()
        dialog = EquipmentFigureDialog(service, owner)
        for theme in ("classic", "light", "dark"):
            owner.theme = theme
            dialog.setStyleSheet(dialog_stylesheet(theme))
            dialog.refresh(); dialog.show(); app.processEvents()
            dialog.grab().save(str(output / (theme + ".png")))
        dialog.close(); app.processEvents()
    finally:
        repo.close()

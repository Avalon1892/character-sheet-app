"""One scoped equipment drag format shared by tables, organizer and silhouette."""
from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QTableWidget, QAbstractItemView

INVENTORY_ITEM_MIME = "application/x-character-sheet-inventory-item"
SCOPE_MIME = "application/x-character-sheet-equipment-scope"
WORN_MIME = "application/x-character-sheet-equipped-source"

def item_mime(item_id, scope, worn=False):
    mime = QMimeData()
    mime.setData(INVENTORY_ITEM_MIME, str(int(item_id)).encode("ascii"))
    mime.setData(SCOPE_MIME, scope.encode("utf-8"))
    if worn:
        mime.setData(WORN_MIME, b"1")
    return mime

def dropped_item(mime, scope):
    if not mime.hasFormat(INVENTORY_ITEM_MIME) or bytes(mime.data(SCOPE_MIME)).decode("utf-8", errors="replace") != scope:
        return None
    try:
        return int(bytes(mime.data(INVENTORY_ITEM_MIME)).decode("ascii"))
    except ValueError:
        return None

class EquipmentDragTable(QTableWidget):
    equipment_dropped = Signal(int, str)

    def __init__(self, sheet, *, worn=False):
        super().__init__()
        self.sheet, self.worn = sheet, worn
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def scope(self):
        from app.equipment_wearing import EquipmentWearService
        return EquipmentWearService(self.sheet.repository, self.sheet.character_id).scope

    def startDrag(self, supported_actions):
        item = self.item(self.currentRow(), 0)
        if item is None or item.data(Qt.ItemDataRole.UserRole) is None:
            return
        drag = QDrag(self)
        drag.setMimeData(item_mime(item.data(Qt.ItemDataRole.UserRole), self.scope(), self.worn))
        drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event):
        if dropped_item(event.mimeData(), self.scope()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        item_id = dropped_item(event.mimeData(), self.scope())
        if self.worn and item_id is not None:
            row = self.rowAt(int(event.position().y()))
            try:
                if row < 0: raise ValueError()
                from app.equipment_wearing import EquipmentWearService
                EquipmentWearService(self.sheet.repository, self.sheet.character_id).validate(item_id, self.item(row, 0).text())
            except ValueError:
                event.ignore(); return
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        item_id = dropped_item(event.mimeData(), self.scope())
        row = self.rowAt(int(event.position().y()))
        if item_id is None or (self.worn and row < 0):
            event.ignore()
            return
        slot = self.item(row, 0).text() if self.worn else ""
        if slot:
            from app.equipment_wearing import EquipmentWearService
            try:
                EquipmentWearService(self.sheet.repository, self.sheet.character_id).validate(item_id, slot)
            except ValueError:
                event.ignore(); return
        self.equipment_dropped.emit(item_id, slot)
        event.acceptProposedAction()

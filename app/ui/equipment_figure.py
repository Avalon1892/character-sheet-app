"""Modeless equipment figure; all persistence stays in EquipmentWearService."""
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRectF, Signal, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QIcon, QDrag, QPolygonF
from PySide6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QGridLayout, QMenu)
from app.equipment_wearing import EquipmentWearService, WIELDED_SLOT
from app.item_enchantments import item_display_name
from app.ui.equipment_drag import item_mime, dropped_item
from app.ui.refined.theme import PALETTES

# Normalized locations are deliberately separate from equipment rules. Extra
# user-created slots remain available in the tray rather than being discarded.
SLOT_POSITIONS = {
    "Head": (200, 38), "Headband": (150, 60), "Eyes": (200, 82),
    "Neck": (200, 125), "Shoulders": (258, 146), "Chest": (200, 171),
    "Armor": (176, 216), "Body": (224, 216), "Belt": (200, 261),
    "Wrists": (105, 273), "Hands": (100, 318),
    "Ring (Left)": (126, 362), "Ring (Right)": (274, 362),
    "Shield": (310, 247), WIELDED_SLOT: (302, 318), "Feet": (151, 525),
}

ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "equipment"
# Source artwork is kept intact. These rectangles exclude its printed labels.
SLOT_ICON_RECTS = {
    "Armor": (39, 47, 260, 248), "Shield": (321, 47, 254, 248),
    "Belt": (597, 47, 252, 248), "Body": (874, 47, 252, 248),
    "Chest": (1151, 47, 258, 248), "Eyes": (39, 377, 260, 251),
    "Feet": (321, 377, 254, 251), "Hands": (597, 377, 252, 251),
    "Head": (874, 377, 252, 251), "Headband": (1151, 377, 258, 251),
    "Neck": (133, 707, 274, 253), "Ring": (433, 707, 275, 253),
    "Shoulders": (734, 707, 275, 253), "Wrists": (1034, 707, 278, 253),
}
_slot_icons = {}

def slot_icon(slot, color):
    key = "Ring" if slot.startswith("Ring") else slot
    if key in SLOT_ICON_RECTS:
        if key not in _slot_icons:
            atlas = QPixmap(str(ASSET_DIRECTORY / "slots.png"))
            # Coordinates refer to the 1448 × 1086 supplied atlas.
            x, y, width, height = SLOT_ICON_RECTS[key]
            sx, sy = atlas.width() / 1448, atlas.height() / 1086
            _slot_icons[key] = QIcon(atlas.copy(round(x*sx), round(y*sy), round(width*sx), round(height*sy)))
        return _slot_icons[key]
    pix = QPixmap(32, 32); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(color), 2)); p.setBrush(Qt.BrushStyle.NoBrush)
    if slot.startswith("Ring"):
        p.drawEllipse(8, 11, 16, 16); p.drawPolygon(QPolygonF([QPointF(12, 8), QPointF(16, 3), QPointF(20, 8), QPointF(16, 13)]))
    elif slot == "Eyes":
        p.drawEllipse(3, 11, 11, 10); p.drawEllipse(18, 11, 11, 10); p.drawLine(14, 16, 18, 16)
    elif slot == "Shield":
        p.drawPolygon(QPolygonF([QPointF(5, 5), QPointF(27, 5), QPointF(25, 21), QPointF(16, 29), QPointF(7, 21)]))
    elif slot == WIELDED_SLOT:
        p.drawLine(9, 26, 24, 5); p.drawLine(6, 19, 17, 26); p.drawLine(23, 5, 27, 3)
    elif slot == "Feet":
        p.drawPolygon(QPolygonF([QPointF(8, 4), QPointF(19, 4), QPointF(19, 20), QPointF(28, 23), QPointF(28, 28), QPointF(8, 28)]))
    elif slot in {"Head", "Headband"}:
        p.drawPolygon(QPolygonF([QPointF(4, 10), QPointF(10, 15), QPointF(16, 5), QPointF(22, 15), QPointF(28, 10), QPointF(25, 25), QPointF(7, 25)]))
        if slot == "Headband": p.drawLine(7, 21, 25, 21)
    elif slot == "Neck":
        p.drawArc(5, 2, 22, 23, 180 * 16, 180 * 16); p.drawEllipse(12, 22, 8, 8)
    elif slot in {"Belt", "Wrists"}:
        p.drawRoundedRect(3, 10, 26, 12, 3, 3)
        if slot == "Belt": p.drawRect(12, 9, 8, 14)
        else: p.drawEllipse(12, 12, 8, 8)
    elif slot == "Hands":
        p.drawRoundedRect(9, 10, 15, 19, 5, 5)
        for x in (10, 14, 18, 22): p.drawLine(x, 6, x, 17)
        p.drawLine(9, 20, 4, 15)
    elif slot == "Shoulders":
        p.drawPolygon(QPolygonF([QPointF(12, 4), QPointF(20, 4), QPointF(29, 28), QPointF(3, 28)]))
        p.drawLine(16, 8, 16, 24)
    elif slot == "Body":
        p.drawPolygon(QPolygonF([QPointF(10, 4), QPointF(22, 4), QPointF(20, 15), QPointF(27, 29), QPointF(5, 29), QPointF(12, 15)]))
        p.drawLine(16, 6, 16, 27)
    elif slot == "Armor":
        p.drawPolygon(QPolygonF([QPointF(7, 4), QPointF(12, 8), QPointF(20, 8), QPointF(25, 4), QPointF(25, 19), QPointF(21, 28), QPointF(11, 28), QPointF(7, 19)]))
        p.drawLine(10, 16, 22, 16); p.drawLine(11, 21, 21, 21)
    elif slot == "Chest":
        p.drawPolygon(QPolygonF([QPointF(10, 4), QPointF(22, 4), QPointF(29, 11), QPointF(24, 16), QPointF(23, 28), QPointF(9, 28), QPointF(8, 16), QPointF(3, 11)]))
    else:
        p.drawRoundedRect(5, 5, 22, 22, 4, 4)
        p.drawEllipse(11, 11, 10, 10)
    p.end()
    return QIcon(pix)

class SlotTarget(QPushButton):
    dropped = Signal(int, str)
    remove_requested = Signal(int)

    def __init__(self, slot, service, parent=None):
        super().__init__(parent)
        self.slot, self.service, self.items = slot, service, []
        self.press_position = None
        self.setAcceptDrops(True)
        self.setAccessibleName(slot)
        self.setIconSize(QSize(30, 30))
        self.setFixedSize(42, 42)

    def populate(self, items, palette, enchantments):
        self.items = items
        self.setToolTip(self.slot + ("\n" + "\n".join(item_display_name(item, enchantments) for item in items) if items else "\nEmpty"))
        self.setIcon(slot_icon(self.slot, palette.accent) if items else QIcon())
        self.setStyleSheet(f"QPushButton {{ background: transparent; border: 1px solid {palette.muted}; border-radius: 6px; }} QPushButton:hover {{ background: {palette.selection}; border: 2px solid {palette.accent}; }}")

    def dragEnterEvent(self, event):
        item_id = dropped_item(event.mimeData(), self.service.scope)
        try:
            if item_id is None: raise ValueError()
            if self.slot: self.service.validate(item_id, self.slot)
            event.acceptProposedAction()
        except ValueError:
            event.ignore()

    def dragMoveEvent(self, event): self.dragEnterEvent(event)

    def dropEvent(self, event):
        item_id = dropped_item(event.mimeData(), self.service.scope)
        if item_id is None:
            event.ignore(); return
        try:
            if self.slot: self.service.validate(item_id, self.slot)
        except ValueError:
            event.ignore(); return
        self.dropped.emit(item_id, self.slot)
        event.acceptProposedAction()

    def mousePressEvent(self, event):
        self.press_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self.items and self.press_position is not None and event.buttons() & Qt.MouseButton.LeftButton
                and (event.position().toPoint() - self.press_position).manhattanLength() >= QApplication.startDragDistance()):
            drag = QDrag(self)
            drag.setMimeData(item_mime(self.items[0].id, self.service.scope, True))
            drag.setPixmap(self.grab())
            self.press_position = None
            drag.exec(Qt.DropAction.MoveAction)
            return
        super().mouseMoveEvent(event)

    def contextMenuEvent(self, event):
        if not self.items: return
        menu = QMenu(self)
        for item in self.items:
            action = menu.addAction("Unequip " + item.name)
            action.triggered.connect(lambda checked=False, item_id=item.id: self.remove_requested.emit(item_id))
        menu.exec(event.globalPos())

class EquipmentFigure(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.palette_tokens = PALETTES["classic"]
        self.targets = {}
        self.silhouette = QPixmap(str(ASSET_DIRECTORY / "silhouette.png"))
        self.setMinimumSize(360, 560)

    def artwork_rect(self):
        scale = min(self.width() / 400, self.height() / 580)
        return QRectF((self.width()-400*scale)/2, (self.height()-580*scale)/2, 400*scale, 580*scale)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        frame = self.artwork_rect()
        if not self.silhouette.isNull():
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            size = self.silhouette.size().scaled(frame.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
            image_rect = QRectF(0, 0, size.width(), size.height())
            image_rect.moveCenter(frame.center())
            p.drawPixmap(image_rect, self.silhouette, QRectF(self.silhouette.rect()))
            p.end()
            return
        p.translate(frame.topLeft())
        p.scale(frame.width() / 400, frame.height() / 580)
        p.setPen(Qt.PenStyle.NoPen)
        color = QColor(self.palette_tokens.muted); color.setAlpha(65); p.setBrush(color)
        p.drawEllipse(QRectF(165, 40, 70, 90))
        path = QPainterPath(QPointF(181, 124))
        path.lineTo(219, 124); path.lineTo(226, 149)
        path.cubicTo(259, 151, 280, 163, 288, 197)
        path.lineTo(327, 343); path.cubicTo(337, 373, 307, 381, 299, 353)
        path.lineTo(254, 228); path.lineTo(246, 292)
        path.lineTo(239, 520); path.lineTo(253, 550); path.lineTo(211, 550)
        path.lineTo(201, 337); path.lineTo(199, 337)
        path.lineTo(189, 550); path.lineTo(147, 550); path.lineTo(161, 520)
        path.lineTo(154, 292); path.lineTo(146, 228)
        path.lineTo(101, 353); path.cubicTo(93, 381, 63, 373, 73, 343)
        path.lineTo(112, 197); path.cubicTo(120, 163, 141, 151, 174, 149)
        path.closeSubpath(); p.drawPath(path); p.end()

    def resizeEvent(self, event):
        self.position_targets()
        super().resizeEvent(event)

    def position_targets(self):
        frame = self.artwork_rect()
        size = min(44, max(26, round(frame.height() / 580 * 40)))
        for slot, target in self.targets.items():
            x, y = SLOT_POSITIONS[slot]
            target.setFixedSize(size, size)
            target.setIconSize(QSize(size - 8, size - 8))
            target.move(round(frame.x() + x * frame.width() / 400 - size / 2),
                        round(frame.y() + y * frame.height() / 580 - size / 2))

class EquipmentFigureContent:
    """Shared live figure body for an embedded panel or a separate dialog."""

    def _build_content(self, service):
        self.service = service
        layout = QVBoxLayout(self)
        self.title = QLabel("EQUIPMENT FIGURE"); self.title.setObjectName("heroTitle"); layout.addWidget(self.title)
        self.figure = EquipmentFigure(service); layout.addWidget(self.figure, 1)
        self.extras = QWidget(); self.extra_grid = QGridLayout(self.extras); layout.addWidget(self.extras)
        self.unequip = SlotTarget("", service)
        self.unequip.setFixedHeight(42)
        self.unequip.setMinimumWidth(300)
        self.unequip.setText("Drop here to unequip")
        self.unequip.dropped.connect(self.change_equipment)
        layout.addWidget(self.unequip, 0, Qt.AlignmentFlag.AlignHCenter)
        self.status = QLabel("Drag an occupied slot back to Inventory to unequip.")
        self.status.setWordWrap(True); layout.addWidget(self.status)
        self.refresh()

    def refresh(self):
        parent = self.parentWidget()
        while parent is not None and not hasattr(parent, "theme"): parent = parent.parentWidget()
        palette = PALETTES.get(getattr(parent, "theme", "classic"), PALETTES["classic"])
        self.figure.palette_tokens = palette
        slots = self.service.slots()
        occupants = self.service.occupants()
        enchantments = self.service.repository.list_item_enchantments(self.service.character_id)
        if getattr(self, "_built_slots", None) == slots:
            for slot, target in self.all_targets.items():
                target.populate(occupants.get(slot, []), palette, enchantments)
            self.unequip.populate([], palette, enchantments)
            self.figure.update()
            return
        self._built_slots = slots
        self.all_targets = {}
        for target in self.figure.targets.values(): target.deleteLater()
        self.figure.targets.clear()
        while self.extra_grid.count():
            item = self.extra_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        extra = 0
        for slot in slots:
            if not slot: continue
            target = SlotTarget(slot, self.service, self.figure if slot in SLOT_POSITIONS else self.extras)
            target.populate(occupants.get(slot, []), palette, enchantments)
            self.all_targets[slot] = target
            target.dropped.connect(self.change_equipment)
            target.remove_requested.connect(lambda item_id: self.change_equipment(item_id, ""))
            if slot in SLOT_POSITIONS:
                self.figure.targets[slot] = target
                x, y = SLOT_POSITIONS[slot]
                target.move(round(x * self.figure.width() / 400 - 21), round(y * self.figure.height() / 580 - 21))
            else:
                self.extra_grid.addWidget(target, extra // 4 * 2, extra % 4)
                label = QLabel(slot); label.setWordWrap(True)
                self.extra_grid.addWidget(label, extra // 4 * 2 + 1, extra % 4)
                extra += 1
            target.show()
        self.unequip.populate([], palette, enchantments)
        self.unequip.setToolTip("Unequip without deleting the item")
        self.figure.position_targets()
        self.figure.update()

    def change_equipment(self, item_id, slot):
        try:
            if slot: self.service.equip(item_id, slot)
            else: self.service.unequip(item_id)
        except ValueError as error:
            self.status.setText(str(error)); return
        self.status.setText("Equipment updated.")
        self.refresh()
        self.equipment_changed.emit()


class EquipmentFigurePanel(QWidget, EquipmentFigureContent):
    equipment_changed = Signal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self._build_content(service)
        self.title.hide()
        self.status.setText("")
        self.figure.setMinimumSize(320, 460)


class EquipmentFigureDialog(QDialog, EquipmentFigureContent):
    equipment_changed = Signal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Equipment Figure")
        self.resize(460, 790)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._build_content(service)

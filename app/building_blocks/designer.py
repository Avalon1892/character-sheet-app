from __future__ import annotations

import uuid
from dataclasses import replace

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.building_blocks.actions import ACTIONS
from app.building_blocks.bindings import BINDINGS
from app.building_blocks.registry import CELL_TYPE_REGISTRY
from app.building_blocks.schemas import BlockDefinition, CellDefinition
from app.database import CharacterRepository
from app.custom_trackers import CustomTrackerResolver
from app.formulas import FormulaError, parse_formula
from app.ui.components import FormulaLineEdit
from app.ui.theme import THEME_LABELS, style_sheet


class DesignCell(QFrame):
    EDGE = 7

    def __init__(self, definition: CellDefinition, canvas: "DesignCanvas") -> None:
        super().__init__(canvas)
        self.definition = definition
        self.canvas = canvas
        self.drag_origin = QPoint()
        self.start_geometry = self.geometry()
        self.operation = "move"
        self.selection_starts: dict[DesignCell, object] = {}
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMouseTracking(True)
        self.apply_definition()

    def apply_definition(self) -> None:
        text = self.definition.label or self.definition.cell_type.title()
        if self.definition.binding:
            text += f"\n↳ {self.definition.binding}"
        if self.definition.formula:
            text += f"\n= {self.definition.formula}"
        self.label.setText(text)
        self.label.setGeometry(3, 3, max(1, self.width() - 6), max(1, self.height() - 6))
        self.setGeometry(
            self.definition.x,
            self.definition.y,
            self.definition.width,
            self.definition.height,
        )
        self._selection_style()

    def _selection_style(self) -> None:
        selected = self in self.canvas.selected
        style = self.definition.style
        background = str(style.get("background") or "#d9eef9")
        foreground = str(style.get("foreground") or "#17313d")
        border_color = str(style.get("border_color") or "#557482")
        border_width = int(style.get("border_width") or 1)
        font_size = int(style.get("font_size") or 10)
        weight = "bold" if bool(style.get("bold")) else "normal"
        italic = "italic" if bool(style.get("italic")) else "normal"
        self.setStyleSheet(
            f"QFrame {{ background: {background}; border: "
            + ("3px dashed #1b78b0" if selected else f"{border_width}px solid {border_color}")
            + f"; }} QLabel {{ background: transparent; color: {foreground}; "
              f"font-size: {font_size}px; font-weight: {weight}; font-style: {italic}; }}"
        )
        alignment = str(style.get("alignment") or "center")
        self.label.setAlignment({
            "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "center": Qt.AlignmentFlag.AlignCenter,
        }.get(alignment, Qt.AlignmentFlag.AlignCenter))

    def resizeEvent(self, event) -> None:
        self.label.setGeometry(3, 3, max(1, self.width() - 6), max(1, self.height() - 6))
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self.canvas.select(self, bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
        self.drag_origin = event.globalPosition().toPoint()
        self.start_geometry = self.geometry()
        self.selection_starts = {
            cell: cell.geometry() for cell in self.canvas.selected
        }
        position = event.position().toPoint()
        right = position.x() >= self.width() - self.EDGE
        bottom = position.y() >= self.height() - self.EDGE
        self.operation = "resize" if right or bottom else "move"
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        delta = event.globalPosition().toPoint() - self.drag_origin
        if self.operation == "resize":
            descriptor = CELL_TYPE_REGISTRY.get(self.definition.cell_type)
            self.resize(
                max(descriptor.minimum_width, self.start_geometry.width() + delta.x()),
                max(descriptor.minimum_height, self.start_geometry.height() + delta.y()),
            )
        else:
            for cell, start in self.selection_starts.items():
                cell.move(
                    max(0, start.x() + delta.x()),
                    max(26, start.y() + delta.y()),
                )
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            for cell in self.canvas.selected:
                geometry = cell.geometry()
                cell.definition = replace(
                    cell.definition,
                    x=geometry.x(), y=geometry.y(), width=geometry.width(), height=geometry.height(),
                )
            self.canvas.changed()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DesignCanvas(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("blockDesignerCanvas")
        self.setMinimumSize(620, 460)
        self.cells: dict[str, DesignCell] = {}
        self.selected: list[DesignCell] = []
        self.selection_changed = lambda: None
        self.changed = lambda: None
        title = QLabel("CUSTOM BLOCK", self)
        title.setObjectName("runtimeBlockTitle")
        title.setGeometry(0, 0, 620, 28)
        self.title = title

    def set_cells(self, definitions: tuple[CellDefinition, ...]) -> None:
        for cell in tuple(self.cells.values()):
            cell.deleteLater()
        self.cells.clear()
        self.selected.clear()
        for definition in definitions:
            widget = DesignCell(definition, self)
            self.cells[definition.key] = widget
            widget.show()

    def add_cell(self, cell_type: str) -> DesignCell:
        descriptor = CELL_TYPE_REGISTRY.get(cell_type)
        offset = 16 * (len(self.cells) % 12)
        key = f"cell:{uuid.uuid4().hex}"
        definition = CellDefinition(
            key,
            cell_type,
            descriptor.name,
            24 + offset,
            48 + offset,
            max(140, descriptor.minimum_width),
            max(32, descriptor.minimum_height),
        )
        widget = DesignCell(definition, self)
        self.cells[key] = widget
        widget.show()
        self.select(widget)
        self.changed()
        return widget

    def select(self, cell: DesignCell, additive: bool = False) -> None:
        if not additive:
            self.selected = []
        if cell not in self.selected:
            self.selected.append(cell)
        group_id = cell.definition.group_id
        if group_id:
            for peer in self.cells.values():
                if peer.definition.group_id == group_id and peer not in self.selected:
                    self.selected.append(peer)
        for widget in self.cells.values():
            widget._selection_style()
        self.selection_changed()

    def clear_selection(self) -> None:
        self.selected.clear()
        for widget in self.cells.values():
            widget._selection_style()
        self.selection_changed()

    def definitions(self) -> tuple[CellDefinition, ...]:
        return tuple(widget.definition for widget in self.cells.values())

    def delete_selected(self) -> None:
        for cell in tuple(self.selected):
            self.cells.pop(cell.definition.key, None)
            cell.deleteLater()
        self.selected.clear()
        self.selection_changed()
        self.changed()

    def duplicate_selected(self) -> None:
        copies = []
        for cell in tuple(self.selected):
            definition = replace(
                cell.definition,
                key=f"cell:{uuid.uuid4().hex}",
                x=cell.x() + 18,
                y=cell.y() + 18,
            )
            widget = DesignCell(definition, self)
            self.cells[definition.key] = widget
            widget.show()
            copies.append(widget)
        self.selected = copies
        for widget in self.cells.values():
            widget._selection_style()
        self.selection_changed()
        self.changed()

    def group_selected(self) -> None:
        if len(self.selected) < 2:
            return
        group_id = f"group:{uuid.uuid4().hex}"
        for cell in self.selected:
            cell.definition = replace(cell.definition, group_id=group_id)
        self.changed()

    def ungroup_selected(self) -> None:
        for cell in self.selected:
            cell.definition = replace(cell.definition, group_id="")
        self.changed()


class BlockDesignerDialog(QDialog):
    def __init__(
        self,
        repository: CharacterRepository,
        character_id: int,
        definition: BlockDefinition | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.character_id = character_id
        self._formula_resolver = CustomTrackerResolver(repository, character_id)
        self.original = definition
        self.setWindowTitle("Custom Building Block Designer")
        self.resize(1380, 850)
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        heading = QLabel("BUILDING BLOCK DESIGNER")
        heading.setObjectName("heroTitle")
        header.addWidget(heading)
        header.addStretch()
        self.theme = QComboBox()
        for key, label in THEME_LABELS.items():
            self.theme.addItem(label, key)
        self.theme.currentIndexChanged.connect(self._preview_theme)
        header.addWidget(QLabel("Preview theme"))
        header.addWidget(self.theme)
        root.addLayout(header)

        splitter = QSplitter()
        tools = QWidget()
        tools.setMinimumWidth(220)
        tools.setMaximumWidth(270)
        tools_layout = QVBoxLayout(tools)
        tools_layout.addWidget(QLabel("ADD CELLS"))
        for descriptor in CELL_TYPE_REGISTRY.all():
            button = QPushButton(descriptor.name)
            button.clicked.connect(lambda _checked=False, key=descriptor.key: self.canvas.add_cell(key))
            tools_layout.addWidget(button)
        tools_layout.addSpacing(12)
        duplicate = QPushButton("Duplicate selected")
        duplicate.clicked.connect(self._duplicate)
        tools_layout.addWidget(duplicate)
        group = QPushButton("Group selected")
        group.clicked.connect(self.canvas_group)
        tools_layout.addWidget(group)
        ungroup = QPushButton("Ungroup selected")
        ungroup.clicked.connect(self.canvas_ungroup)
        tools_layout.addWidget(ungroup)
        remove = QPushButton("Remove selected cells")
        remove.setObjectName("dangerButton")
        remove.clicked.connect(self._delete)
        tools_layout.addWidget(remove)
        tools_layout.addStretch()
        splitter.addWidget(tools)

        scroll = QScrollArea()
        scroll.setWidgetResizable(False)
        scroll.setMinimumWidth(650)
        self.canvas = DesignCanvas()
        scroll.setWidget(self.canvas)
        splitter.addWidget(scroll)

        properties = QWidget()
        properties.setMinimumWidth(420)
        properties.setMaximumWidth(520)
        properties_layout = QVBoxLayout(properties)
        form = QFormLayout()
        self.name = QLineEdit(definition.name if definition else "New Block")
        self.category = QLineEdit(definition.category if definition else "Custom")
        self.description = QPlainTextEdit(definition.description if definition else "")
        self.block_width = QSpinBox(); self.block_width.setRange(240, 2400); self.block_width.setValue(definition.width if definition else 620)
        self.block_height = QSpinBox(); self.block_height.setRange(140, 1800); self.block_height.setValue(definition.height if definition else 460)
        form.addRow("Block name", self.name)
        form.addRow("Category", self.category)
        form.addRow("Description", self.description)
        form.addRow("Block width", self.block_width)
        form.addRow("Block height", self.block_height)
        properties_layout.addLayout(form)
        properties_layout.addWidget(QLabel("SELECTED CELL"))
        cell_form = QFormLayout()
        self.cell_label = QLineEdit()
        self.cell_binding = QComboBox(); self.cell_binding.addItem("No binding", "")
        for item in BINDINGS.all(repository, character_id):
            self.cell_binding.addItem(f"{item.category} · {item.name}", item.key)
        self.cell_formula = FormulaLineEdit(
            suggestion_provider=self._formula_resolver.context.suggestions,
            require_equals=False,
        )
        self.cell_action = QComboBox(); self.cell_action.addItem("No action", "")
        for item in ACTIONS.all():
            self.cell_action.addItem(item.name, item.key)
        self.cell_anchored = QCheckBox("Scale and move with parent")
        self.cell_options = QLineEdit(); self.cell_options.setPlaceholderText("Comma-separated dropdown options")
        cell_form.addRow("Label / text", self.cell_label)
        cell_form.addRow("Data binding", self.cell_binding)
        cell_form.addRow("Formula", self.cell_formula)
        cell_form.addRow("Button action", self.cell_action)
        cell_form.addRow("Dropdown options", self.cell_options)
        cell_form.addRow("Anchoring", self.cell_anchored)
        properties_layout.addLayout(cell_form)
        colors = QHBoxLayout()
        background = QPushButton("Background…"); background.clicked.connect(lambda: self._choose_color("background"))
        foreground = QPushButton("Text color…"); foreground.clicked.connect(lambda: self._choose_color("foreground"))
        border = QPushButton("Border…"); border.clicked.connect(lambda: self._choose_color("border_color"))
        colors.addWidget(background); colors.addWidget(foreground); colors.addWidget(border)
        properties_layout.addLayout(colors)
        typography = QFormLayout()
        self.cell_border_width = QSpinBox(); self.cell_border_width.setRange(0, 12); self.cell_border_width.setValue(1)
        self.cell_font_size = QSpinBox(); self.cell_font_size.setRange(6, 72); self.cell_font_size.setValue(10)
        self.cell_bold = QCheckBox("Bold")
        self.cell_italic = QCheckBox("Italic")
        self.cell_alignment = QComboBox()
        for label, value in (("Left", "left"), ("Center", "center"), ("Right", "right")):
            self.cell_alignment.addItem(label, value)
        typography.addRow("Border width", self.cell_border_width)
        typography.addRow("Font size", self.cell_font_size)
        typography.addRow("Text style", self.cell_bold)
        typography.addRow("", self.cell_italic)
        typography.addRow("Alignment", self.cell_alignment)
        properties_layout.addLayout(typography)
        apply_cell = QPushButton("Apply cell properties")
        apply_cell.setObjectName("primaryButton")
        apply_cell.clicked.connect(self._apply_cell_properties)
        properties_layout.addWidget(apply_cell)
        properties_layout.addStretch()
        splitter.addWidget(properties)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([235, 680, 465])
        root.addWidget(splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.canvas.selection_changed = self._selection_changed
        self.block_width.valueChanged.connect(self._resize_canvas)
        self.block_height.valueChanged.connect(self._resize_canvas)
        self.canvas.set_cells(definition.cells if definition else ())
        self._resize_canvas()
        self._selection_changed()

    def _resize_canvas(self) -> None:
        self.canvas.setFixedSize(self.block_width.value(), self.block_height.value())
        self.canvas.title.setGeometry(0, 0, self.block_width.value(), 28)

    def _preview_theme(self) -> None:
        self.setStyleSheet(style_sheet(str(self.theme.currentData() or "classic")))

    def _selection_changed(self) -> None:
        selected = self.canvas.selected
        enabled = bool(selected)
        for widget in (
            self.cell_label, self.cell_binding, self.cell_formula, self.cell_action,
            self.cell_anchored, self.cell_options, self.cell_border_width,
            self.cell_font_size, self.cell_bold, self.cell_italic,
            self.cell_alignment,
        ):
            widget.setEnabled(enabled)
        if not selected:
            return
        cell = selected[0].definition
        self.cell_label.setText(cell.label)
        self.cell_binding.setCurrentIndex(max(0, self.cell_binding.findData(cell.binding)))
        self.cell_formula.setText(cell.formula)
        self.cell_action.setCurrentIndex(max(0, self.cell_action.findData(cell.action)))
        self.cell_anchored.setChecked(cell.anchored)
        self.cell_options.setText(", ".join(str(value) for value in cell.config.get("options", ())))
        self.cell_border_width.setValue(int(cell.style.get("border_width") or 1))
        self.cell_font_size.setValue(int(cell.style.get("font_size") or 10))
        self.cell_bold.setChecked(bool(cell.style.get("bold")))
        self.cell_italic.setChecked(bool(cell.style.get("italic")))
        self.cell_alignment.setCurrentIndex(max(0, self.cell_alignment.findData(str(cell.style.get("alignment") or "center"))))

    def _apply_cell_properties(self) -> None:
        formula = self.cell_formula.text().strip()
        if formula:
            try:
                parse_formula(formula)
            except FormulaError as error:
                QMessageBox.warning(self, "Invalid formula", str(error))
                return
        options = [value.strip() for value in self.cell_options.text().split(",") if value.strip()]
        for widget in self.canvas.selected:
            descriptor = CELL_TYPE_REGISTRY.get(widget.definition.cell_type)
            config = dict(widget.definition.config)
            if options:
                config["options"] = options
            elif "options" in config:
                config.pop("options")
            if descriptor.validate_config is not None:
                try:
                    descriptor.validate_config(config)
                except ValueError as error:
                    QMessageBox.warning(self, "Invalid cell configuration", str(error))
                    return
            style = dict(widget.definition.style)
            style.update({
                "border_width": self.cell_border_width.value(),
                "font_size": self.cell_font_size.value(),
                "bold": self.cell_bold.isChecked(),
                "italic": self.cell_italic.isChecked(),
                "alignment": str(self.cell_alignment.currentData() or "center"),
            })
            widget.definition = replace(
                widget.definition,
                label=self.cell_label.text(),
                binding=str(self.cell_binding.currentData() or ""),
                formula=formula,
                action=str(self.cell_action.currentData() or ""),
                anchored=self.cell_anchored.isChecked(),
                config=config,
                style=style,
            )
            widget.apply_definition()

    def _choose_color(self, key: str) -> None:
        color = QColorDialog.getColor(parent=self)
        if not color.isValid():
            return
        for widget in self.canvas.selected:
            style = dict(widget.definition.style)
            style[key] = color.name()
            widget.definition = replace(widget.definition, style=style)
            widget.apply_definition()

    def _duplicate(self) -> None:
        self.canvas.duplicate_selected()

    def _delete(self) -> None:
        self.canvas.delete_selected()

    def canvas_group(self) -> None:
        self.canvas.group_selected()

    def canvas_ungroup(self) -> None:
        self.canvas.ungroup_selected()

    def _accept_if_valid(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Missing name", "Enter a block name.")
            return
        self.accept()

    def definition(self, key: str) -> BlockDefinition:
        return BlockDefinition(
            key=key,
            name=self.name.text().strip(),
            category=self.category.text().strip() or "Custom",
            description=self.description.toPlainText().strip(),
            builtin=False,
            width=self.block_width.value(),
            height=self.block_height.value(),
            cells=self.canvas.definitions(),
        )

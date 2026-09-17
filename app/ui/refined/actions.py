"""Compact section commands, delegating to the original controls and signals."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QToolButton, QHBoxLayout, QMenu


def compact_actions(section):
    root = section.layout()
    if root is None:
        return
    command_rows = []
    for index in range(root.count()):
        layout = root.itemAt(index).layout()
        if not isinstance(layout, QHBoxLayout):
            continue
        widgets = [layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget()]
        if widgets and all(isinstance(w, (QPushButton, QToolButton)) for w in widgets):
            command_rows.append((layout, widgets))
    if not command_rows:
        return
    title = next((w for w in section.findChildren(QLabel) if w.objectName() == "refinedSectionTitle"), None)
    if title is None:
        return
    # Find or create the title row without disturbing summary labels.
    header = None
    for index in range(root.count()):
        item = root.itemAt(index)
        if item.widget() is title:
            root.takeAt(index)
            header = QHBoxLayout()
            header.addWidget(title, 1)
            root.insertLayout(index, header)
            break
        if item.layout() and item.layout().indexOf(title) >= 0:
            header = item.layout()
            break
    if header is None:
        return
    holder = QWidget(section)
    holder.hide()
    holder.setObjectName("refinedHiddenCommands")
    menu = QMenu(section)
    proxies = []
    primary_count = 0
    for layout, buttons in command_rows:
        root.removeItem(layout)
        for button in buttons:
            layout.removeWidget(button)
            text = button.text().strip()
            prominent = (bool(button.property('prominentAction')) or "book" in text.casefold() or text.casefold() == "open inventory"
                         or text.casefold() in ("choose / change", "choose / change talents", "use / end adaptation")
                         or (text.startswith("+") and primary_count == 0))
            if (prominent and primary_count < 2) or text.casefold() == "equipment figure":
                button.setText(text.removeprefix("+ "))
                header.addWidget(button)
                primary_count += 1
            else:
                button.setParent(holder)
                if button.menu():
                    submenu = button.menu()
                    submenu.setTitle(text)
                    menu.addMenu(submenu)
                else:
                    action = menu.addAction(text)
                    action.triggered.connect(lambda _checked=False, target=button: target.click())
                    proxies.append((action, button))
        layout.deleteLater()
    def synchronize():
        for action, button in proxies:
            action.setText(button.text())
            action.setEnabled(button.isEnabled())
            action.setCheckable(button.isCheckable())
            action.setChecked(button.isChecked())
    menu.aboutToShow.connect(synchronize)
    more = QToolButton(section)
    more.setText("Actions")
    more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    more.setMenu(menu)
    more.setToolTip("Edit, remove, and additional actions for this section")
    header.addWidget(more)
    section._refined_command_holder = holder
    section._refined_actions_menu = menu

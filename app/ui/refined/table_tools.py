"""Small, reusable table-search tools; no rules or persistence ownership."""
from __future__ import annotations

from PySide6.QtCore import Qt, QEvent, QTimer, Slot
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QComboBox


class TableFilterChoice(QComboBox):
    """A named set of filters over values already rendered by a table adapter."""
    def __init__(self,adapter,key,options,*,noun="entries",parent=None):
        super().__init__(parent)
        self.adapter=adapter
        self.key=key
        self.noun=noun
        self.options=tuple(options)
        self.addItems([label for label,_predicate in self.options])
        self.setAccessibleName(f"Filter {noun}")
        self.setMinimumWidth(145)
        self.setMaximumWidth(190)
        self.currentIndexChanged.connect(self._changed)

    @Slot(int)
    def _changed(self,index):
        self.adapter.set_row_filter(self.key,self.options[index][1])

    def is_active(self):
        return self.currentIndex()!=0

    def reset(self):
        self.setCurrentIndex(0)


class PageSearchBar(QWidget):
    """Debounced search with live results, explicit reset, and keyboard access.

    Ownership is resolved at use time so the same toolbar supports blocks moved
    to different pages. Filters belong to their table, never to character rules.
    """
    def __init__(self,controllers,*,placeholder="Search this page…",parent=None):
        super().__init__(parent)
        self.controllers=controllers
        self.filters=[]
        self._connected=set()
        self.setObjectName("refinedSearchBar")
        layout=QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(10)
        self.field=QLineEdit()
        self.field.setObjectName("refinedPageSearch")
        self.field.setPlaceholderText(placeholder)
        self.field.setAccessibleName(placeholder.rstrip("…"))
        self.field.setClearButtonEnabled(True)
        self.field.setMinimumWidth(100)
        self.field.setToolTip("Search this page · Ctrl+F to focus · Escape to clear")
        layout.addWidget(self.field,1)
        self.feedback=QLabel("Ctrl+F")
        self.feedback.setObjectName("refinedSearchFeedback")
        self.feedback.setMinimumWidth(80)
        self.feedback.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.feedback)
        self.clear_button=QPushButton("Reset filters")
        self.clear_button.setToolTip("Clear the search and restore all entries")
        self.clear_button.setAccessibleName("Reset page search and filters")
        self.clear_button.clicked.connect(self.clear)
        self.clear_button.hide()
        layout.addWidget(self.clear_button)
        self.timer=QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.apply)
        self.field.textChanged.connect(self._query_changed)
        self.field.returnPressed.connect(self.apply)
        self.field.installEventFilter(self)

    def current_controllers(self):
        return list(self.controllers() if callable(self.controllers) else self.controllers)

    def _bind(self):
        for controller in self.current_controllers():
            if controller not in self._connected:
                controller.fitted.connect(self.update_feedback)
                self._connected.add(controller)

    def showEvent(self,event):
        super().showEvent(event)
        self._bind()
        self.update_feedback()

    def add_filter(self,control):
        self.filters.append(control)
        self.layout().insertWidget(self.layout().indexOf(self.feedback),control)
        control.currentIndexChanged.connect(self.update_feedback)
        control.adapter.fitted.connect(self.update_feedback)

    @Slot(str)
    def _query_changed(self,_text):
        self.timer.start()
        self.feedback.setText("Searching…")
        self.clear_button.setVisible(bool(self.field.text()) or any(f.is_active() for f in self.filters))

    @Slot()
    def apply(self):
        self.timer.stop()
        self._bind()
        for controller in self.current_controllers():
            controller.filter(self.field.text())
        self.update_feedback()

    @Slot()
    def clear(self):
        self.field.clear()
        for control in self.filters:
            control.reset()
        self.apply()

    def reset(self):
        self.clear()

    @Slot()
    @Slot(int)
    @Slot(int,int)
    def update_feedback(self,*_):
        owned=self.current_controllers()
        for control in self.filters:
            control.setVisible(control.adapter in owned)
        active=[f for f in self.filters if f.adapter in owned and f.is_active()]
        if self.timer.isActive():
            self.feedback.setText("Searching…")
            return
        if self.field.text().strip():
            controllers=[c for c in self.current_controllers()
                         if c.table.isVisibleTo(self.parentWidget())]
            count=sum(c.matching_count for c in controllers)
            self.feedback.setText(f"{count} {'match' if count==1 else 'matches'}")
        elif active:
            self.feedback.setText(" · ".join(f"{f.adapter.matching_count} {f.noun}" for f in active))
        else:
            self.feedback.setText("Ctrl+F")
        self.clear_button.setVisible(bool(self.field.text()) or bool(active))

    def eventFilter(self,watched,event):
        if watched is self.field and event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Escape:
            self.clear()
            return True
        return super().eventFilter(watched,event)


def skill_filter_choice(adapter):
    def has_ranks(table,row):
        item=table.item(row,4)
        try:return float(item.text())>0 if item else False
        except ValueError:return False

    def class_skill(table,row):
        item=table.item(row,1)
        return item is not None and item.text()=="■"

    return TableFilterChoice(adapter,"skill-kind",(
        ("All skills",None),("With ranks",has_ranks),("Class skills",class_skill)),noun="skills")

"""Refined presentation adapters for the existing bonded-companion panels."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QFormLayout, QSizePolicy
from .components import ResponsiveRow, TablePresentation


def decorate_companions(sheet):
    for key in ("familiar", "corpse_puppet", "phantom"):
        panel=getattr(sheet,key+"_panel")
        root=panel.layout()
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        for label in panel.findChildren(QLabel):
            if label.objectName() in ("sectionTitle","sheetSectionTitle"):
                label.setObjectName("refinedSectionTitle")
                label.setText(label.text().capitalize())
        for index in range(root.count()):
            columns=root.itemAt(index).layout()
            if not isinstance(columns,QHBoxLayout):continue
            widgets=[columns.itemAt(i).widget() for i in range(columns.count()) if columns.itemAt(i).widget()]
            if len(widgets)!=2:continue
            for widget in widgets:
                columns.removeWidget(widget)
                widget.setMinimumWidth(0)
                widget.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Maximum)
                layout=widget.layout()
                if isinstance(layout,QFormLayout):
                    layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
                    layout.setVerticalSpacing(10)
            root.removeItem(columns);columns.deleteLater()
            root.insertWidget(index,ResponsiveRow(*widgets,breakpoint=1100))
            break
        for table in (panel.progression,panel.creature_details):
            table.setProperty("refinedTable",True)
            adapter=TablePresentation(table,sheet,name_column=0,max_rows=50,sortable=False,balanced=True)
            sheet.table_presentations.append(adapter)

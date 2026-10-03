"""Engineering workbench: presentation only; mutations go through the service."""
from html import escape
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QLabel,
    QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,
    QSpinBox,QCheckBox,QTextBrowser,QSplitter,QWidget,QMessageBox,QInputDialog)
from app.services.engineering import EngineeringService
from app.engineering_rules import occupied_limit
from app.content import martial_entry
from app.ui.dialog_theme import dialog_stylesheet


class EngineeringDialog(QDialog):
    def __init__(self,sheet):
        super().__init__(sheet)
        self.sheet=sheet
        self.setWindowTitle("Engineering — Tech & Tinker")
        self.resize(1400,850)
        self.setStyleSheet(dialog_stylesheet(getattr(sheet,"theme","classic")))
        root=QVBoxLayout(self)
        bar=QHBoxLayout();root.addLayout(bar)
        self.system=QComboBox()
        base=EngineeringService(sheet.repository,sheet.character_id)
        for sphere in ("Tech","Tinker"):
            if base.available(sphere):self.system.addItem(sphere)
        bar.addWidget(self.system)
        self.kit=QCheckBox("Engineering kit / sufficient tools")
        bar.addWidget(self.kit)
        bar.addWidget(QLabel("Associated skill"))
        self.skill=QComboBox()
        self.skill.addItem("Craft (mechanical) — shared Craft rank provider","craft")
        for key in ("knowledge_engineering","profession","perform"):
            self.skill.addItem(key.replace("_"," ").title()+" (manual alternative)",key)
        bar.addWidget(self.skill)
        bar.addWidget(QLabel("Practitioner modifier (at creation)"))
        self.modifier=QSpinBox();self.modifier.setRange(-100,100);bar.addWidget(self.modifier)
        self.summary=QLabel();root.addWidget(self.summary)
        notice=QLabel("Baseline lifecycle and resource tracking. Device-specific effects and construction exceptions still require manual rules review.")
        notice.setWordWrap(True);root.addWidget(notice)
        controls=QHBoxLayout();root.addLayout(controls)
        self.known=QComboBox();self.known.setMinimumContentsLength(25);controls.addWidget(self.known,1)
        self.minor=QCheckBox("Minor (confirm device rule)");controls.addWidget(self.minor)
        controls.addWidget(QLabel("Advanced increases"))
        self.advanced=QSpinBox();self.advanced.setRange(0,99);controls.addWidget(self.advanced)
        self.create=QPushButton("Craft device");controls.addWidget(self.create)
        split=QSplitter();root.addWidget(split,1)
        left=QWidget();layout=QVBoxLayout(left);split.addWidget(left)
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(("Device","Level","State","HP (base)","Hardness (base)","Save (base)","DC (base)","Energy"))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in range(1,8):
            self.table.horizontalHeader().setSectionResizeMode(column,QHeaderView.ResizeMode.ResizeToContents)
        self.table.setWordWrap(True)
        self.table.verticalHeader().hide();layout.addWidget(self.table)
        actions=QHBoxLayout();layout.addLayout(actions)
        self.actions=[]
        for label,state in (("Activate","active"),("Deactivate","inactive"),("Deplete","depleted"),("Abandon","abandoned")):
            button=QPushButton(label);button.clicked.connect(lambda checked=False,s=state:self.change_state(s))
            actions.addWidget(button);self.actions.append(button)
        self.maintenance=QPushButton("Maintain depleted devices");actions.addWidget(self.maintenance)
        self.details=QTextBrowser();self.details.setOpenExternalLinks(True);split.addWidget(self.details)
        split.setSizes([850,500])
        resources=QHBoxLayout();root.addLayout(resources)
        self.charges=QLabel();resources.addWidget(self.charges)
        self.spend=QSpinBox();self.spend.setRange(1,99999);resources.addWidget(self.spend)
        self.use=QPushButton("Spend charges");resources.addWidget(self.use)
        self.recharge=QPushButton("Recharge");resources.addWidget(self.recharge)
        self.attach=QPushButton("Attach battery");resources.addWidget(self.attach)
        self.battery_use=QPushButton("Use attached batteries");resources.addWidget(self.battery_use)
        self.personal=QCheckBox("Personal battery use");resources.addWidget(self.personal)
        self.device_charge_controls=[]
        for label,operation in (("Load selected",lambda:self.service().transfer_charges(self.selected(),self.spend.value())),
                                ("Return selected",lambda:self.service().transfer_charges(self.selected(),-self.spend.value())),
                                ("Use stored charges",lambda:self.service().transfer_charges(self.selected(),self.spend.value(),spend=True))):
            button=QPushButton(label);button.clicked.connect(lambda checked=False,op=operation:self.perform(op))
            resources.addWidget(button);self.device_charge_controls.append(button)
        resources.addStretch()
        self.status=QLabel();self.status.setWordWrap(True);root.addWidget(self.status)
        self.system.currentIndexChanged.connect(self.refresh)
        self.skill.currentIndexChanged.connect(self.refresh)
        self.kit.toggled.connect(self.refresh)
        self.known.currentIndexChanged.connect(self.preview_known)
        self.table.itemSelectionChanged.connect(self.preview_device)
        self.create.clicked.connect(self.craft)
        self.maintenance.clicked.connect(lambda:self.perform(lambda:self.service().maintain(self.system.currentText())))
        self.use.clicked.connect(lambda:self.perform(lambda:self.service().change_charges(-self.spend.value())))
        self.recharge.clicked.connect(lambda:self.perform(lambda:self.service().recharge()))
        self.attach.clicked.connect(self.attach_battery)
        self.battery_use.clicked.connect(lambda:self.perform(lambda:self.service().use_batteries(self.selected(),self.spend.value(),personal=self.personal.isChecked())))
        self.refresh()

    def service(self):
        return EngineeringService(self.sheet.repository,self.sheet.character_id,self.skill.currentData())

    def refresh(self,*_):
        service=self.service();sphere=self.system.currentText()
        if not sphere:return
        limits=service.limits(sphere)
        devices=service.devices(sphere)
        minutes=15 if self.kit.isChecked() else 30
        self.summary.setText(f"Maintained devices: {occupied_limit(devices,limits)} / {limits.device_limit} · Crafting: {limits.batch_size} per {minutes} minutes"+
                             (f" · Minor devices per limit unit: {limits.minor_group_size}" if sphere=="Tinker" else ""))
        previous=self.known.currentData()
        self.known.blockSignals(True);self.known.clear()
        for entry in service.known_devices(sphere):self.known.addItem(entry["name"],entry["key"])
        if self.known.findData(previous)>=0:self.known.setCurrentIndex(self.known.findData(previous))
        self.known.blockSignals(False)
        self.create.setEnabled(bool(self.known.count()))
        self.minor.setEnabled(sphere=="Tinker");self.advanced.setEnabled(sphere=="Tinker")
        self.table.setRowCount(len(devices))
        for row,device in enumerate(devices):
            stats=service.statistics(device)
            attached=[d for d in devices if d["host_id"]==device["id"] and d["state"]!="abandoned"]
            energy=(device["charges"] if sphere=="Tech" else
                    f"#{device['host_id']}" if device["host_id"] else
                    f"{sum(d['state']=='active' for d in attached)}/{len(attached)} batteries" if attached else "—")
            values=(device["name"],device["level"],device["state"],stats["hp"],stats["hardness"],stats["save"],stats["dc"],energy)
            for column,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setData(Qt.ItemDataRole.UserRole,device["id"])
                self.table.setItem(row,column,item)
        self.table.resizeRowsToContents()
        for button in self.actions:button.setEnabled(False)
        self.maintenance.setEnabled(sphere=="Tinker")
        pool=service.pool()
        self.charges.setText(f"Tech charges: {int(pool.current_value) if pool else 0} / {limits.charge_maximum}" if sphere=="Tech" else "Tinker: deplete individual batteries; rest does not replace maintenance.")
        self.spend.setVisible(True)
        for control in (self.use,self.recharge,*self.device_charge_controls):control.setVisible(sphere=="Tech")
        for control in (self.attach,self.battery_use,self.personal):control.setVisible(sphere=="Tinker")
        self.attach.setEnabled(False);self.battery_use.setEnabled(False)
        for button in self.device_charge_controls:button.setEnabled(False)
        self.recharge.setText(f"Recharge (+{limits.recharge_amount}, {minutes} min)")
        self.preview_known()

    def selected(self):
        row=self.table.currentRow()
        return self.table.item(row,0).data(Qt.ItemDataRole.UserRole) if row>=0 and self.table.item(row,0) else None

    def preview_known(self,*_):
        entry=next((e for e in self.service().known_devices(self.system.currentText()) if e["key"]==self.known.currentData()),None)
        self.show_details(entry)

    def show_details(self,entry):
        self.details.setHtml("" if entry is None else "<h2>"+escape(entry["name"])+"</h2><p>"+
                             escape(entry.get("description","")).replace("\n","<br>")+"</p><p><b>Device-specific effects are reference-only in this batch.</b></p>")

    def preview_device(self):
        device=next((d for d in self.service().devices(self.system.currentText()) if d["id"]==self.selected()),None)
        for button in self.actions:button.setEnabled(device is not None and device["state"]!="abandoned")
        for button in self.device_charge_controls:button.setEnabled(device is not None and device["state"] not in {"abandoned","depleted"})
        host=bool(device and device["sphere"]=="Tinker" and device["catalog_key"]!="tinker:battery" and device["state"] not in {"abandoned","depleted"})
        self.attach.setEnabled(host);self.battery_use.setEnabled(host)
        if device:self.show_details(martial_entry(device["catalog_key"]) or {"name":device["name"],"description":"Tinker battery. Deplete to spend; maintain to restore."})

    def perform(self,operation):
        try:
            operation()
        except (ValueError,KeyError) as error:
            self.status.setText(str(error));return
        self.status.setText("Saved.")
        self.sheet.refresh_all()
        self.refresh()

    def craft(self):
        sphere=self.system.currentText()
        self.perform(lambda:self.service().create(sphere,self.known.currentData(),self.modifier.value(),
                     minor=self.minor.isChecked() if sphere=="Tinker" else False,
                     advanced=self.advanced.value() if sphere=="Tinker" else 0))

    def change_state(self,state):
        if state=="abandoned" and QMessageBox.question(self,"Abandon device",
            "The selected device stops functioning permanently and no longer counts against your limit. Abandon it?"
            )!=QMessageBox.StandardButton.Yes:return
        if self.selected() is not None:self.perform(lambda:self.service().change_state(self.selected(),state))

    def attach_battery(self):
        batteries=[d for d in self.service().devices("Tinker") if d["catalog_key"]=="tinker:battery" and d["state"]!="abandoned"]
        labels=[f"#{d['id']} {d['name']} · level {d['level']} · {d['state']}" for d in batteries]
        if not labels:
            self.status.setText("Craft a Tinker battery first.");return
        label,accepted=QInputDialog.getItem(self,"Attach battery","Battery (swift action by default)",labels,0,False)
        if accepted:self.perform(lambda:self.service().attach_battery(batteries[labels.index(label)]["id"],self.selected()))

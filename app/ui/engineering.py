"""Engineering workbench: presentation only; mutations go through the service."""
from html import escape
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QLabel,
    QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,
    QSpinBox,QCheckBox,QTextBrowser,QSplitter,QWidget,QMessageBox,QInputDialog)
from app.services.engineering import EngineeringService
from app.engineering_rules import occupied_limit,is_battery,TECH_BATTERY_KEY,tech_battery_capacity,device_condition,PHYSICAL_AUGMENTOR_KEY
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
        bar.addWidget(QLabel("Practitioner modifier (creation / repair)"))
        self.modifier=QSpinBox();self.modifier.setRange(-100,100);bar.addWidget(self.modifier)
        self.summary=QLabel();root.addWidget(self.summary)
        notice=QLabel("Baseline lifecycle and resource tracking. Device-specific effects and construction exceptions still require manual rules review.")
        notice.setWordWrap(True);root.addWidget(notice)
        controls=QHBoxLayout();root.addLayout(controls)
        self.known=QComboBox();self.known.setMinimumContentsLength(25);controls.addWidget(self.known,1)
        self.configuration=QComboBox()
        for key in ("strength","dexterity","constitution"):self.configuration.addItem(key.title(),key)
        controls.addWidget(self.configuration)
        self.minor=QCheckBox("Minor (confirm device rule)");controls.addWidget(self.minor)
        controls.addWidget(QLabel("Advanced increases"))
        self.advanced=QSpinBox();self.advanced.setRange(0,99);controls.addWidget(self.advanced)
        self.create=QPushButton("Craft device");controls.addWidget(self.create)
        split=QSplitter();root.addWidget(split,1)
        left=QWidget();layout=QVBoxLayout(left);split.addWidget(left)
        self.table=QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(("Device","Level","State","HP","Hardness (base)","Save (base)","DC (base)","Energy"))
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
        self.maintenance=QPushButton("Maintain / fully repair gizmos");actions.addWidget(self.maintenance)
        self.details=QTextBrowser();self.details.setOpenExternalLinks(True);split.addWidget(self.details)
        split.setSizes([850,500])
        resources=QHBoxLayout();root.addLayout(resources)
        self.charges=QLabel();resources.addWidget(self.charges)
        self.spend=QSpinBox();self.spend.setRange(1,99999);resources.addWidget(self.spend)
        self.use=QPushButton("Spend charges");resources.addWidget(self.use)
        self.recharge=QPushButton("Recharge");resources.addWidget(self.recharge)
        resources.addStretch()
        health=QHBoxLayout();root.addLayout(health)
        self.damage_amount=QSpinBox();self.damage_amount.setRange(1,99999)
        health.addWidget(QLabel("Incoming device damage"));health.addWidget(self.damage_amount)
        self.hardness=QCheckBox("Apply hardness");self.hardness.setChecked(True);health.addWidget(self.hardness)
        self.damage_button=QPushButton("Damage selected");health.addWidget(self.damage_button)
        self.repair_button=QPushButton("Repair selected (1 minute)");health.addWidget(self.repair_button)
        self.applied=QCheckBox("Worn / used by this character");health.addWidget(self.applied)
        self.applied.clicked.connect(lambda checked:self.perform(lambda:self.service().apply_to_character(self.selected(),checked)))
        health.addStretch()
        self.damage_button.clicked.connect(lambda:self.perform(lambda:self.service().damage_device(self.selected(),self.damage_amount.value(),apply_hardness=self.hardness.isChecked())))
        self.repair_button.clicked.connect(lambda:self.perform(lambda:self.service().repair_tinker_device(self.selected(),self.modifier.value(),has_tools=self.kit.isChecked())))
        resources=QHBoxLayout();root.addLayout(resources)
        self.attach=QPushButton("Attach battery");resources.addWidget(self.attach)
        self.detach=QPushButton("Detach selected battery");resources.addWidget(self.detach)
        self.battery_recharge=QPushButton("Recharge battery (+1 min)");resources.addWidget(self.battery_recharge)
        self.battery_use=QPushButton("Use attached batteries");resources.addWidget(self.battery_use)
        self.personal=QCheckBox("Personal battery use");resources.addWidget(self.personal)
        self.device_charge_controls=[]
        for label,operation in (("Load selected",self.load_charges),
                                ("Return selected",lambda:self.service().transfer_charges(self.selected(),-self.spend.value())),
                                ("Use device charges",lambda:self.service().transfer_charges(self.selected(),self.spend.value(),spend=True))):
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
        self.detach.clicked.connect(lambda:self.perform(lambda:self.service().attach_battery(self.selected(),None)))
        self.battery_recharge.clicked.connect(lambda:self.perform(lambda:self.service().recharge_tech_battery(self.selected())))
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
            condition=device_condition(device)
            attached=[d for d in devices if d["host_id"]==device["id"] and d["state"]!="abandoned"]
            energy=(f"{device['charges']} + {sum(d['charges'] for d in attached if d['state'] not in {'depleted','abandoned'} and not device_condition(d)['destroyed'])} battery" if sphere=="Tech" and attached else
                    f"{device['charges']}/{tech_battery_capacity(device['modifier'])}" if sphere=="Tech" and is_battery(device) else
                    device["charges"] if sphere=="Tech" else
                    f"#{device['host_id']}" if device["host_id"] else
                    f"{sum(d['state']=='active' for d in attached)}/{len(attached)} batteries" if attached else "—")
            status="abandoned" if device["state"]=="abandoned" else "Destroyed" if condition["destroyed"] else f"Broken · {device['state']}" if condition["broken"] else device["state"]
            level=f"{device['level']} → {condition['effective_level']}" if condition["effective_level"]!=device["level"] else device["level"]
            name=device["name"]+(f" · {device['configuration'].title()}" if device["configuration"] else "")+(" · Worn" if device["applied_to_character"] else "")
            values=(name,level,status,f"{condition['current_hp']}/{condition['maximum_hp']}",stats["hardness"],stats["save"],stats["dc"],energy)
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
        for control in (self.battery_use,self.personal):control.setVisible(sphere=="Tinker")
        self.battery_recharge.setVisible(sphere=="Tech")
        self.detach.setEnabled(False);self.battery_recharge.setEnabled(False)
        self.damage_button.setEnabled(False);self.repair_button.setEnabled(False)
        self.applied.setEnabled(False);self.applied.setChecked(False)
        self.repair_button.setVisible(sphere=="Tinker")
        self.attach.setEnabled(False);self.battery_use.setEnabled(False)
        for button in self.device_charge_controls:button.setEnabled(False)
        self.recharge.setText(f"Recharge (+{limits.recharge_amount}, {minutes} min)")
        self.preview_known()

    def selected(self):
        row=self.table.currentRow()
        return self.table.item(row,0).data(Qt.ItemDataRole.UserRole) if row>=0 and self.table.item(row,0) else None

    def preview_known(self,*_):
        self.configuration.setVisible(self.known.currentData()==PHYSICAL_AUGMENTOR_KEY)
        entry=next((e for e in self.service().known_devices(self.system.currentText()) if e["key"]==self.known.currentData()),None)
        self.show_details(entry)

    def show_details(self,entry):
        self.details.setHtml("" if entry is None else "<h2>"+escape(entry["name"])+"</h2><p>"+
                             escape(entry.get("description","")).replace("\n","<br>")+"</p><p><b>"+
                             ("Selected-ability skill bonuses are automatic when active and worn. Ability checks and battery-use rerolls are currently resolved manually."
                              if entry.get("key")==PHYSICAL_AUGMENTOR_KEY else "Device-specific effects are reference-only in this batch.")+"</b></p>")

    def preview_device(self):
        device=next((d for d in self.service().devices(self.system.currentText()) if d["id"]==self.selected()),None)
        self.damage_button.setEnabled(bool(device and device["state"]!="abandoned"))
        self.repair_button.setEnabled(bool(device and device["state"]!="abandoned" and device["damage"] and self.kit.isChecked()))
        self.applied.setEnabled(bool(device and device["catalog_key"]==PHYSICAL_AUGMENTOR_KEY and device["state"]!="abandoned"))
        self.applied.setChecked(bool(device and device["applied_to_character"]))
        for button in self.actions:button.setEnabled(device is not None and device["state"]!="abandoned")
        if device and device_condition(device)["destroyed"]:
            self.actions[0].setEnabled(False)
        for button in self.device_charge_controls:button.setEnabled(device is not None and device["state"] not in {"abandoned","depleted"})
        self.device_charge_controls[1].setEnabled(bool(device and not is_battery(device) and device["state"] not in {"abandoned","depleted"}))
        self.device_charge_controls[2].setToolTip("Spend attached Tech battery charges first, then charges stored in the device.")
        host=bool(device and not is_battery(device) and device["state"] not in {"abandoned","depleted"})
        self.attach.setEnabled(host);self.battery_use.setEnabled(host)
        self.detach.setEnabled(bool(device and is_battery(device) and device["host_id"] and device["state"]!="abandoned"))
        self.battery_recharge.setEnabled(bool(device and device["catalog_key"]==TECH_BATTERY_KEY and device["state"]!="abandoned"))
        if device:self.show_details(martial_entry(device["catalog_key"]) or next((e for e in self.service().known_devices(device["sphere"]) if e["key"]==device["catalog_key"]),None) or {"name":device["name"],"description":"Saved engineering device."})

    def perform(self,operation):
        try:
            if operation() is False:
                return
        except (ValueError,KeyError) as error:
            self.status.setText(str(error));return
        self.status.setText("Saved.")
        self.sheet.refresh_all()
        self.refresh()

    def craft(self):
        sphere=self.system.currentText()
        self.perform(lambda:self.service().create(sphere,self.known.currentData(),self.modifier.value(),
                     minor=self.minor.isChecked() if sphere=="Tinker" else False,
                     advanced=self.advanced.value() if sphere=="Tinker" else 0,
                     configuration=self.configuration.currentData() if self.known.currentData()==PHYSICAL_AUGMENTOR_KEY else ""))

    def load_charges(self):
        device=next((d for d in self.service().devices("Tech") if d["id"]==self.selected()),None)
        if device and is_battery(device):
            room=max(0,tech_battery_capacity(device["modifier"],from_pool=True)-device["charges"])
            wasted=max(0,self.spend.value()-room)
            if wasted and QMessageBox.question(self,"Excess battery charges",
                f"This transfer will waste {wasted} charges. Continue?")!=QMessageBox.StandardButton.Yes:
                return False
        self.service().transfer_charges(self.selected(),self.spend.value())

    def change_state(self,state):
        if state=="abandoned" and QMessageBox.question(self,"Abandon device",
            "The selected device stops functioning permanently and no longer counts against your limit. Any Tech battery charges are lost. Abandon it?"
            )!=QMessageBox.StandardButton.Yes:return
        if self.selected() is not None:self.perform(lambda:self.service().change_state(self.selected(),state))

    def attach_battery(self):
        batteries=[d for d in self.service().devices(self.system.currentText()) if is_battery(d) and d["state"]!="abandoned"]
        labels=[f"#{d['id']} {d['name']} · level {d['level']} · {d['state']}" for d in batteries]
        if not labels:
            self.status.setText("Craft a battery first.");return
        label,accepted=QInputDialog.getItem(self,"Attach battery","Battery (swift action by default)",labels,0,False)
        if accepted:self.perform(lambda:self.service().attach_battery(batteries[labels.index(label)]["id"],self.selected()))

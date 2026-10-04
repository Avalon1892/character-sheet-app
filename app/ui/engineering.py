"""Engineering workbench: presentation only; mutations go through the service."""
from html import escape
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QLabel,
    QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,
    QSpinBox,QCheckBox,QTextBrowser,QSplitter,QWidget,QMessageBox,QInputDialog)
from app.services.engineering import EngineeringService
from app.engineering_rules import TACTILE_FIELD_KEY,RESISTANCE_ROUTINE_KEY,DERMAL_PLATING_KEY,tech_augment_suppressed
from app.engineering_rules import occupied_limit,is_battery,TECH_BATTERY_KEY,tech_battery_capacity,device_condition,PHYSICAL_AUGMENTOR_KEY,AUGMENTOR_ABILITIES,JET_BOOSTERS_KEY,JET_MODES
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
        practitioner=QHBoxLayout();root.addLayout(practitioner)
        practitioner.addWidget(QLabel("Practitioner modifier (creation / repair)"))
        self.practitioner_ability=QComboBox()
        self.practitioner_ability.addItem("Manual override","")
        for ability in ("intelligence","wisdom","charisma","strength","dexterity","constitution"):
            self.practitioner_ability.addItem(ability.title(),ability)
        self.practitioner_ability.setToolTip("Select the ability granted by your class or archetype. Without a practitioner class, the default is Wisdom. Class choice resolution is not yet automatic.")
        practitioner.addWidget(self.practitioner_ability)
        self.modifier=QSpinBox();self.modifier.setRange(-100,100);practitioner.addWidget(self.modifier)
        practitioner.addStretch()
        self.polymorphed=QCheckBox("Polymorphed — suppress worn Tech augments")
        self.polymorphed.setToolTip("Tracks the current transformation for augment effects. It does not remove installed devices, refund charges or stop paid timers. Devices crafted as bio augments retain their effects; graft handling is still pending.")
        practitioner.addWidget(self.polymorphed)
        self.polymorphed.clicked.connect(lambda checked:self.perform(lambda:self.service().set_polymorphed(checked)))
        self.summary=QLabel();root.addWidget(self.summary)
        notice=QLabel("Baseline lifecycle and resource tracking. Device-specific effects and construction exceptions still require manual rules review.")
        notice.setWordWrap(True);root.addWidget(notice)
        controls=QHBoxLayout();root.addLayout(controls)
        self.known=QComboBox();self.known.setMinimumContentsLength(25);controls.addWidget(self.known,1)
        self.configuration=QComboBox()
        for key in ("strength","dexterity","constitution"):self.configuration.addItem(key.title(),key)
        controls.addWidget(self.configuration)
        self.minor=QCheckBox("Minor (confirm device rule)");controls.addWidget(self.minor)
        self.bio_augment=QCheckBox("Bio augment (made for this character)");controls.addWidget(self.bio_augment)
        self.bio_augment.setToolTip("Creation-time variant requiring qualifying Tech training. Preserves the augment through polymorph; contextual disguise/detection and remote-control checks remain manual.")
        controls.addWidget(QLabel("Advanced increases"))
        self.advanced=QSpinBox();self.advanced.setRange(0,99);controls.addWidget(self.advanced)
        self.create=QPushButton("Craft device");controls.addWidget(self.create)
        split=QSplitter();root.addWidget(split,1)
        left=QWidget();layout=QVBoxLayout(left);split.addWidget(left)
        self.table=QTableWidget(0,9)
        self.table.setHorizontalHeaderLabels(("Device","Level","State","HP","Hardness (base)","Save (base)","DC (base)","Energy","Paid time"))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for column in range(1,9):
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
        timed=QHBoxLayout();root.addLayout(timed)
        self.jet_slot=QComboBox()
        for slot in sheet.repository.list_worn_slots(sheet.character_id):
            if slot and slot!="Slotless":self.jet_slot.addItem(slot)
        timed.addWidget(self.jet_slot)
        self.jet_buttons=[]
        for mode,label in (("normal","Boost (1 charge / round)"),("slow_burn","Slow burn (1 charge / 4h)"),("overdrive","Overdrive (2 charges / round)")):
            button=QPushButton(label);button.clicked.connect(lambda checked=False,m=mode:self.perform(lambda:self.service().start_jet_boosters(self.selected(),m,self.jet_slot.currentText())))
            timed.addWidget(button);self.jet_buttons.append(button)
        self.stop=QPushButton("Stop function");timed.addWidget(self.stop)
        self.stop.clicked.connect(lambda:self.perform(lambda:self.service().stop_function(self.selected())))
        self.unequip_jet=QPushButton("Unequip boosters");timed.addWidget(self.unequip_jet)
        self.unequip_jet.clicked.connect(lambda:self.perform(lambda:self.service().stop_function(self.selected(),unequip=True)))
        timed.addStretch()
        clock=QHBoxLayout();root.addLayout(clock)
        self.elapsed=QSpinBox();self.elapsed.setRange(1,999999);clock.addWidget(self.elapsed)
        self.advance=QPushButton("Advance game time (rounds)");clock.addWidget(self.advance)
        self.advance.clicked.connect(lambda:self.perform(lambda:self.service().advance_time(self.elapsed.value())))
        clock.addStretch()
        field_controls=QHBoxLayout();root.addLayout(field_controls)
        self.tactile_boost=QPushButton("Enhance Tactile Field — 1 battery")
        self.dermal_activate=QPushButton("Power Dermal Plating — 1 charge")
        field_controls.addWidget(self.dermal_activate)
        self.dermal_activate.clicked.connect(lambda:self.perform(lambda:self.service().start_dermal_plating(self.selected())))
        self.tactile_reroll=QPushButton("Use reroll / end enhancement")
        self.augmentor_reroll=QPushButton("Roll benefiting check twice — 1 battery")
        self.augmentor_reroll.setToolTip("Before a check benefiting from this augmentor, spend one attached battery. Roll the check twice and take the higher result; resolve the dice manually.")
        field_controls.addWidget(self.augmentor_reroll)
        self.augmentor_reroll.clicked.connect(lambda:self.perform(lambda:self.service().use_augmentor_reroll(self.selected())))
        self.tactile_reroll.setToolTip("Resolve the immediate-action reroll manually; clicking ends the enhanced bonus and remaining duration.")
        field_controls.addWidget(self.tactile_boost);field_controls.addWidget(self.tactile_reroll);field_controls.addStretch()
        self.tactile_boost.clicked.connect(lambda:self.perform(lambda:self.service().use_batteries(self.selected(),1,tactile_boost=True)))
        self.tactile_reroll.clicked.connect(lambda:self.perform(self.use_tactile_reroll))
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
        self.install_routine=QPushButton("Install routine");resources.addWidget(self.install_routine)
        self.remove_routine=QPushButton("Remove routine");resources.addWidget(self.remove_routine)
        self.install_routine.clicked.connect(self.install_resistance_routine)
        self.remove_routine.clicked.connect(lambda:self.perform(lambda:self.service().install_resistance_routine(self.selected(),None)))
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
        self.practitioner_ability.currentIndexChanged.connect(self.update_practitioner_modifier)
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

    def update_practitioner_modifier(self,*_):
        ability=self.practitioner_ability.currentData()
        self.modifier.setEnabled(not bool(ability))
        if ability:self.modifier.setValue(self.service().practitioner_modifier(ability))

    def refresh(self,*_):
        self.polymorphed.setChecked(self.sheet.repository.engineering_polymorphed(self.sheet.character_id))
        self.update_practitioner_modifier()
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
            attached=[d for d in devices if is_battery(d) and d["host_id"]==device["id"] and d["state"]!="abandoned"]
            energy=(f"{device['charges']} + {sum(d['charges'] for d in attached if d['state'] not in {'depleted','abandoned'} and not device_condition(d)['destroyed'])} battery" if sphere=="Tech" and attached else
                    f"{device['charges']}/{tech_battery_capacity(device['modifier'])}" if sphere=="Tech" and is_battery(device) else
                    device["charges"] if sphere=="Tech" else
                    f"#{device['host_id']}" if device["host_id"] else
                    f"{sum(d['state']=='active' for d in attached)}/{len(attached)} batteries" if attached else "—")
            status="abandoned" if device["state"]=="abandoned" else "Destroyed" if condition["destroyed"] else f"Broken · {device['state']}" if condition["broken"] else device["state"]
            if tech_augment_suppressed(device,self.polymorphed.isChecked()):status+=" · Polymorph-suppressed"
            level=f"{device['level']} → {condition['effective_level']}" if condition["effective_level"]!=device["level"] else device["level"]
            name=device["name"]+(f" · {device['configuration'].title()}" if device["configuration"] else "")+(f" · {device['worn_slot']}" if device["worn_slot"] else " · Worn" if device["applied_to_character"] else "")
            if device["augment_slot"]:name+=f" · Augment: {device['augment_slot']}"
            if device["bio_augment"]:name+=" · Bio"
            values=(name,level,status,f"{condition['current_hp']}/{condition['maximum_hp']}",stats["hardness"],stats["save"],stats["dc"],energy,f"{device['effect_rounds']} rounds" if device["effect_rounds"] else "—")
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
        for button in (*self.jet_buttons,self.stop,self.unequip_jet):button.setEnabled(False)
        has_jets=any(e["key"]==JET_BOOSTERS_KEY for e in service.known_devices(sphere))
        for control in (*self.jet_buttons,self.stop,self.unequip_jet,self.jet_slot):control.setVisible(has_jets)
        timed=any(d["effect_rounds"]>0 for d in self.sheet.repository.list_engineering_devices(self.sheet.character_id))
        self.advance.setEnabled(timed);self.elapsed.setEnabled(timed)
        self.repair_button.setVisible(sphere=="Tinker")
        self.attach.setEnabled(False);self.battery_use.setEnabled(False)
        for button in self.device_charge_controls:button.setEnabled(False)
        self.recharge.setText(f"Recharge (+{limits.recharge_amount}, {minutes} min)")
        self.preview_known()

    def selected(self):
        row=self.table.currentRow()
        return self.table.item(row,0).data(Qt.ItemDataRole.UserRole) if row>=0 and self.table.item(row,0) else None

    def preview_known(self,*_):
        key=self.known.currentData()
        bio_allowed=self.system.currentText()=="Tech" and self.service().can_create_bio_augment(key)
        self.bio_augment.setVisible(self.system.currentText()=="Tech")
        self.bio_augment.setEnabled(bio_allowed)
        if not bio_allowed:self.bio_augment.setChecked(False)
        self.minor.setEnabled(self.system.currentText()=="Tinker" and key!=RESISTANCE_ROUTINE_KEY)
        if key==RESISTANCE_ROUTINE_KEY:self.minor.setChecked(True)
        previous=self.configuration.currentData()
        self.configuration.clear()
        for option in (("flight","aquatic") if key==JET_BOOSTERS_KEY else AUGMENTOR_ABILITIES.get(key,())):
            self.configuration.addItem(option.title(),option)
        if self.configuration.findData(previous)>=0:self.configuration.setCurrentIndex(self.configuration.findData(previous))
        self.configuration.setVisible(key in AUGMENTOR_ABILITIES or key==JET_BOOSTERS_KEY)
        entry=next((e for e in self.service().known_devices(self.system.currentText()) if e["key"]==self.known.currentData()),None)
        self.show_details(entry)

    def show_details(self,entry):
        self.details.setHtml("" if entry is None else "<h2>"+escape(entry["name"])+"</h2><p>"+
                             escape(entry.get("description","")).replace("\n","<br>")+"</p><p><b>"+
                             ("Selected-ability skill bonuses are automatic when active and worn. Ability checks and battery-use rerolls are currently resolved manually."
                              if entry.get("key") in AUGMENTOR_ABILITIES else
                              "CMD, Acrobatics and Escape Artist bonuses, one-battery enhancement and duration are automatic. Resolve the immediate-action reroll manually, then use the reroll/end button to end the enhancement."
                              if entry.get("key")==TACTILE_FIELD_KEY else
                              "Install and activate this routine to improve its host gizmo's saving throws. The live save column includes the highest active insight bonus; character saves are unchanged."
                              if entry.get("key")==RESISTANCE_ROUTINE_KEY else
                              "Install in the dedicated Body augment slot (separate from magic-item slots), then pay one charge for a timed period. Energy Efficient Augments extends the base one-minute duration when qualified. Natural armor enhancement, expiry and ordinary polymorph suppression are automatic; crafted bio augments retain their effects. Donning/removal follows leather armor; hasty donning and graft installation are not yet automated."
                              if entry.get("key")==DERMAL_PLATING_KEY else
                              "Flight/swim speed, maneuverability, charge costs and paid durations are automatic. Flight slow burn is limited to 3 feet above the surface; height and hover/exhaust effects require manual resolution."
                              if entry.get("key")==JET_BOOSTERS_KEY else "Device-specific effects are reference-only in this batch.")+"</b></p>")

    def preview_device(self):
        device=next((d for d in self.service().devices(self.system.currentText()) if d["id"]==self.selected()),None)
        tactile=bool(device and device["catalog_key"]==TACTILE_FIELD_KEY)
        dermal=bool(device and device["catalog_key"]==DERMAL_PLATING_KEY)
        self.dermal_activate.setVisible(dermal)
        self.dermal_activate.setEnabled(bool(dermal and device["applied_to_character"] and device["state"] not in {"abandoned","depleted"} and device["effect_rounds"]==0 and not device_condition(device)["destroyed"]))
        routine=bool(device and device["catalog_key"]==RESISTANCE_ROUTINE_KEY)
        self.install_routine.setVisible(routine);self.remove_routine.setVisible(routine)
        self.install_routine.setEnabled(bool(routine and device["state"]!="abandoned"))
        self.remove_routine.setEnabled(bool(routine and device["host_id"] is not None and device["state"]!="abandoned"))
        augmentor=bool(device and device["catalog_key"] in AUGMENTOR_ABILITIES)
        self.augmentor_reroll.setVisible(augmentor)
        self.augmentor_reroll.setEnabled(bool(augmentor and device["state"]=="active" and device["applied_to_character"] and not device_condition(device)["destroyed"]))
        self.tactile_boost.setVisible(tactile);self.tactile_reroll.setVisible(tactile)
        self.tactile_boost.setEnabled(bool(tactile and device["state"]=="active" and device["applied_to_character"] and device["effect_rounds"]==0))
        at_will=self.service().tactile_reroll_at_will() if tactile else False
        self.tactile_reroll.setText("Use reroll — At will" if at_will and not device["effect_rounds"] else "Use reroll / end enhancement")
        self.tactile_reroll.setToolTip("Resolve the immediate-action reroll manually. Advanced Field Projectors allows it at will; using an active battery enhancement ends that enhancement. The defensive bonus increase still costs a battery.")
        self.tactile_reroll.setEnabled(bool(tactile and device["state"]=="active" and device["applied_to_character"] and not device_condition(device)["destroyed"] and (device["effect_rounds"]>0 or at_will)))
        self.damage_button.setEnabled(bool(device and device["state"]!="abandoned"))
        self.repair_button.setEnabled(bool(device and device["state"]!="abandoned" and device["damage"] and self.kit.isChecked()))
        self.applied.setEnabled(bool(device and device["catalog_key"] in {*AUGMENTOR_ABILITIES,TACTILE_FIELD_KEY,DERMAL_PLATING_KEY} and device["state"]!="abandoned"))
        self.applied.setChecked(bool(device and device["applied_to_character"]))
        jet=bool(device and device["catalog_key"]==JET_BOOSTERS_KEY and device["state"]!="abandoned" and not device_condition(device)["destroyed"])
        for button in self.jet_buttons:button.setEnabled(jet and device["effect_rounds"]==0)
        self.stop.setEnabled(jet and device["effect_rounds"]>0)
        self.unequip_jet.setEnabled(jet and bool(device["worn_slot"]))
        if jet and device["worn_slot"]:self.jet_slot.setCurrentText(device["worn_slot"])
        for button in self.actions:button.setEnabled(device is not None and device["state"]!="abandoned")
        if device and device_condition(device)["destroyed"]:
            self.actions[0].setEnabled(False)
        for button in self.device_charge_controls:button.setEnabled(device is not None and device["state"] not in {"abandoned","depleted"})
        self.device_charge_controls[1].setEnabled(bool(device and not is_battery(device) and device["state"] not in {"abandoned","depleted"}))
        self.device_charge_controls[2].setToolTip("Spend attached Tech battery charges first, then charges stored in the device.")
        host=bool(device and not is_battery(device) and device["catalog_key"]!=RESISTANCE_ROUTINE_KEY and device["state"] not in {"abandoned","depleted"})
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

    def use_tactile_reroll(self):
        result=self.service().use_tactile_reroll(self.selected())
        if result is False:self.status.setText("At-will reroll: resolve the immediate-action roll manually. No battery spent.")
        return result

    def craft(self):
        sphere=self.system.currentText()
        self.perform(lambda:self.service().create(sphere,self.known.currentData(),self.modifier.value(),
                     minor=self.minor.isChecked() if sphere=="Tinker" else False,
                     advanced=self.advanced.value() if sphere=="Tinker" else 0,
                     bio_augment=self.bio_augment.isChecked() if sphere=="Tech" else False,
                     configuration=self.configuration.currentData() if self.known.currentData() in AUGMENTOR_ABILITIES or self.known.currentData()==JET_BOOSTERS_KEY else ""))

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

    def install_resistance_routine(self):
        hosts=[d for d in self.service().devices("Tinker") if d["catalog_key"]!=RESISTANCE_ROUTINE_KEY and d["state"] not in {"abandoned","depleted"} and not device_condition(d)["destroyed"]]
        if not hosts:
            self.status.setText("Craft a functioning host gizmo first.");return
        labels=[f"#{d['id']} · {d['name']}" for d in hosts]
        label,accepted=QInputDialog.getItem(self,"Install Resistance Routine","Host gizmo",labels,0,False)
        if accepted:self.perform(lambda:self.service().install_resistance_routine(self.selected(),hosts[labels.index(label)]["id"]))

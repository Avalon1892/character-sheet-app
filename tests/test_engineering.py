import tempfile
import unittest
from pathlib import Path
from app.database import CharacterRepository
from app.content import martial_entries
from app.engineering_rules import engineering_limits,device_statistics,occupied_limit
from app.services.engineering import EngineeringService
from app.transfer import export_character,import_character
from app.recovery import FullRestEngine
from app.sphere_rules import base_sphere_choice_options


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.repo=CharacterRepository(Path(self.temp.name)/"engineering.db")
        self.cid=self.repo.create_character("Engineer","Spheres")
        self.repo.add_class_level(self.cid,"Conscript",6,"Full","Good","Poor","Poor",hit_die=10,hp_gained=40)
        self.add("Tech","Tech Sphere","tech:base","Base Sphere")
        self.add("Tinker","Tinker Sphere","tinker:base","Base Sphere")
        self.service=EngineeringService(self.repo,self.cid)

    def tearDown(self):
        self.repo.close();self.temp.cleanup()

    def add(self,sphere,name,key,category="Talent"):
        self.repo.add_martial_talent(self.cid,name,sphere,"Talent",catalog_key=key,catalog_category=category)

    def gadget(self):
        entry=next(e for e in martial_entries("Tech") if e["name"].startswith("Camera ("))
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        return self.service.create("Tech",entry["key"],3)

    def test_distinct_rules_and_repeatable_limits(self):
        self.assertEqual((9,4,6),(engineering_limits("Tinker",6,1,extra=1).device_limit,
                                  engineering_limits("Tinker",8,1,extra=1).batch_size,
                                  engineering_limits("Tinker",6,1,extra=1).minor_group_size))
        self.assertEqual(20,device_statistics("Tech",6,3)["hp"])
        self.assertEqual(18,device_statistics("Tinker",6,3)["hp"])
        self.assertEqual(13,device_statistics("Tinker",6,-3)["dc"])
        self.add("Tech","Extra Gadgets","custom:extra")
        self.assertEqual(5,self.service.limits("Tech").device_limit)

    def test_charge_recharge_transfer_spend_and_rest(self):
        device=self.gadget()
        self.assertEqual(4,self.service.recharge())
        self.service.transfer_charges(device,3)
        with self.assertRaises(ValueError):self.service.change_state(device,"depleted")
        self.assertEqual(4,self.service.charge_total())
        self.assertEqual(1,self.service.pool().current_value)
        self.service.transfer_charges(device,2,spend=True)
        self.assertEqual(2,self.service.charge_total())
        with self.assertRaises(ValueError):self.service.transfer_charges(device,2,spend=True)
        self.assertEqual(2,self.service.charge_total())
        FullRestEngine(self.repo,self.cid).perform()
        self.assertEqual(2,self.service.charge_total())
        with self.assertRaises(ValueError):self.service.change_charges(-2)
        self.service.transfer_charges(device,-1)
        self.assertEqual(2,self.service.pool().current_value)

    def test_battery_lifecycle_and_creation_snapshot(self):
        battery=self.service.create("Tinker","tinker:battery",3)
        self.service.change_state(battery,"depleted")
        self.assertEqual(1,occupied_limit(self.service.devices("Tinker"),self.service.limits("Tinker")))
        with self.assertRaises(ValueError):self.service.change_state(battery,"active")
        self.service.maintain("Tinker")
        self.assertEqual("active",self.service.devices("Tinker")[0]["state"])
        with self.assertRaises(ValueError):self.service.change_state(battery,"inactive")
        self.service.change_state(battery,"abandoned")
        self.assertEqual(0,occupied_limit(self.service.devices("Tinker"),self.service.limits("Tinker")))
        with self.assertRaises(ValueError):self.service.change_state(battery,"active")

    def test_tech_battery_storage_attachment_and_atomic_spending(self):
        from app.engineering_rules import TECH_BATTERY_KEY
        entry=next(e for e in martial_entries("Tech") if e["key"]==TECH_BATTERY_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        host=self.gadget()
        battery=self.service.create("Tech",TECH_BATTERY_KEY,3)
        second=self.service.create("Tech",TECH_BATTERY_KEY,3)
        self.assertEqual(0,self.service.charge_total())
        self.service.recharge()
        self.service.transfer_charges(host,2)
        self.service.attach_battery(battery,host)
        with self.assertRaises(ValueError):self.service.attach_battery(second,host)
        with self.assertRaises(ValueError):self.service.attach_battery(second,battery)
        before=self.service.devices("Tech")
        with self.assertRaises(ValueError):self.service.transfer_charges(host,6,spend=True)
        self.assertEqual(before,self.service.devices("Tech"))
        self.service.transfer_charges(host,4,spend=True)
        devices={d["id"]:d for d in self.service.devices("Tech")}
        self.assertEqual(0,devices[battery]["charges"])
        self.assertEqual(1,devices[host]["charges"])
        FullRestEngine(self.repo,self.cid).perform()
        self.assertEqual(0,next(d for d in self.service.devices("Tech") if d["id"]==battery)["charges"])
        self.service.recharge_tech_battery(battery)
        self.assertEqual(3,next(d for d in self.service.devices("Tech") if d["id"]==battery)["charges"])
        self.assertEqual(2,self.service.transfer_charges(battery,2))
        self.assertEqual(0,self.service.pool().current_value)
        self.assertEqual(1,self.service.charge_total())

    def test_minor_advanced_limits_and_overflow(self):
        limits=engineering_limits("Tinker",6,1)
        devices=[dict(sphere="Tinker",state="depleted",minor=True,advanced=0) for _ in range(6)]
        self.assertEqual(2,occupied_limit(devices,limits))
        devices[0]["advanced"]=2
        self.assertEqual(3,occupied_limit(devices,limits))
        for _ in range(6):self.service.create("Tinker","tinker:battery",0)
        with self.assertRaises(ValueError):self.service.create("Tinker","tinker:battery",0)
        self.assertEqual(6,len(self.service.devices("Tinker")))

    def test_tech_battery_minimum_recharge_detach_and_abandon(self):
        from app.engineering_rules import TECH_BATTERY_KEY
        entry=next(e for e in martial_entries("Tech") if e["key"]==TECH_BATTERY_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        host=self.gadget()
        battery=self.service.create("Tech",TECH_BATTERY_KEY,-2)
        self.service.attach_battery(battery,host)
        self.service.attach_battery(battery,None)
        self.assertIsNone(next(d for d in self.service.devices("Tech") if d["id"]==battery)["host_id"])
        self.service.transfer_charges(battery,1,spend=True)
        self.service.recharge_tech_battery(battery)
        self.assertEqual(1,next(d for d in self.service.devices("Tech") if d["id"]==battery)["charges"])
        with self.assertRaises(ValueError):self.service.maintain("Tech")
        self.service.attach_battery(battery,host)
        path=Path(self.temp.name)/"tech-battery.json"
        export_character(self.repo,self.cid,path)
        imported=EngineeringService(self.repo,import_character(self.repo,path)).devices("Tech")
        imported_battery=next(d for d in imported if d["catalog_key"]==TECH_BATTERY_KEY)
        self.assertEqual(next(d["id"] for d in imported if d["catalog_key"]!=TECH_BATTERY_KEY),imported_battery["host_id"])
        self.service.change_state(battery,"abandoned")
        record=next(d for d in self.service.devices("Tech") if d["id"]==battery)
        self.assertEqual((0,None),(record["charges"],record["host_id"]))
        with self.assertRaises(ValueError):self.service.recharge_tech_battery(battery)

    def test_tech_battery_owner_and_pool_charging_bounds(self):
        from app.engineering_rules import TECH_BATTERY_KEY
        entry=next(e for e in martial_entries("Tech") if e["key"]==TECH_BATTERY_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        battery=self.service.create("Tech",TECH_BATTERY_KEY,0)
        host=self.gadget()
        other=self.repo.create_character("Other engineer","Spheres")
        with self.assertRaises(ValueError):EngineeringService(self.repo,other).attach_battery(battery,host)
        with self.assertRaises(ValueError):self.service.attach_battery(battery,self.service.create("Tinker","tinker:battery",2))
        self.service.recharge()
        before=self.service.devices("Tech")
        with self.assertRaises(ValueError):self.service.transfer_charges(battery,5)
        self.assertEqual(before,self.service.devices("Tech"))
        self.assertEqual(2,self.service.transfer_charges(battery,2))
        self.assertEqual(1,next(d for d in self.service.devices("Tech") if d["id"]==battery)["charges"])
        with self.assertRaises(ValueError):self.service.transfer_charges(battery,-1)
        with self.assertRaises(ValueError):self.repo.transfer_engineering_charges(self.cid,battery,self.service.pool().id,1)

    def test_transfer_preserves_devices_and_charge_pool(self):
        self.gadget();self.service.recharge()
        path=Path(self.temp.name)/"character.json"
        export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        other=EngineeringService(self.repo,imported)
        self.assertEqual(4,other.charge_total())
        self.assertEqual(self.service.devices("Tech")[0]["catalog_key"],other.devices("Tech")[0]["catalog_key"])
        with self.assertRaises(KeyError):self.repo.save_engineering_device(imported,self.service.devices("Tech")[0],self.service.devices("Tech")[0]["id"])

    def test_starting_tech_gadget_excludes_routines(self):
        self.assertFalse(any("routine" in name.casefold() for name in base_sphere_choice_options("Tech","martial")))

    def test_attached_batteries_personal_use_and_host_remapping(self):
        entry=next(e for e in martial_entries("Tinker") if e["name"].startswith("Grappling Hook ("))
        self.add("Tinker",entry["name"],entry["key"],entry["category"])
        host=self.service.create("Tinker",entry["key"],3)
        battery=self.service.create("Tinker","tinker:battery",3)
        self.service.attach_battery(battery,host)
        with self.assertRaises(ValueError):self.service.use_batteries(host,1)
        self.service.change_state(host,"active")
        self.service.use_batteries(host,1,personal=True)
        with self.assertRaises(ValueError):self.service.use_batteries(host,1)
        self.service.maintain("Tinker")
        path=Path(self.temp.name)/"attached.json"
        export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        devices=EngineeringService(self.repo,imported).devices("Tinker")
        new_battery=next(d for d in devices if d["catalog_key"]=="tinker:battery")
        new_host=next(d for d in devices if d["catalog_key"]!= "tinker:battery")
        self.assertEqual(new_host["id"],new_battery["host_id"])
        self.assertNotEqual(host,new_host["id"])
        with self.assertRaises(ValueError):self.service.attach_battery(battery,battery)

    def test_opening_service_is_read_only(self):
        before=self.repo.sqlite_connection.total_changes
        self.service.limits("Tech");self.service.devices("Tinker");self.service.known_devices("Tech")
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)

    def test_tinker_battery_must_reach_host_level(self):
        entry=next(e for e in martial_entries("Tinker") if e["name"].startswith("Grappling Hook ("))
        self.add("Tinker",entry["name"],entry["key"],entry["category"])
        host=self.service.create("Tinker",entry["key"],3)
        battery=self.service.create("Tinker","tinker:battery",3)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==battery)
        self.repo.save_engineering_device(self.cid,{**record,"level":record["level"]-1},battery)
        self.service.attach_battery(battery,host)
        self.service.change_state(host,"active")
        with self.assertRaises(ValueError):self.service.use_batteries(host,1)
        self.assertEqual("active",next(d for d in self.service.devices("Tinker") if d["id"]==battery)["state"])

    def test_workbench_controls_in_both_themes(self):
        from PySide6.QtWidgets import QApplication,QWidget
        from PySide6.QtCore import QEvent
        from app.ui.engineering import EngineeringDialog
        app=QApplication.instance() or QApplication([])
        for theme in ("classic","dark"):
            with self.subTest(theme=theme):
                sheet=QWidget();sheet.repository=self.repo;sheet.character_id=self.cid
                sheet.theme=theme;sheet.refresh_all=lambda:None
                before=self.repo.sqlite_connection.total_changes
                dialog=EngineeringDialog(sheet)
                self.assertEqual(before,self.repo.sqlite_connection.total_changes)
                dialog.system.setCurrentText("Tinker")
                self.assertEqual("tinker:battery",dialog.known.currentData())
                dialog.craft()
                self.assertIn("Saved",dialog.status.text())
                self.assertGreater(dialog.table.rowCount(),0)
                dialog.table.selectRow(0)
                self.assertTrue(dialog.actions[0].isEnabled())
                dialog.system.setCurrentText("Tech")
                self.assertFalse(dialog.attach.isHidden())
                self.assertFalse(dialog.battery_recharge.isHidden())
                dialog.close();dialog.deleteLater();sheet.deleteLater()
                app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

    def test_cancelled_battery_overfill_does_not_write_or_refresh(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication,QWidget,QMessageBox
        from PySide6.QtCore import QEvent
        from app.ui.engineering import EngineeringDialog
        from app.engineering_rules import TECH_BATTERY_KEY
        entry=next(e for e in martial_entries("Tech") if e["key"]==TECH_BATTERY_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        self.service.create("Tech",TECH_BATTERY_KEY,2)
        self.service.recharge()
        app=QApplication.instance() or QApplication([])
        sheet=QWidget();sheet.repository=self.repo;sheet.character_id=self.cid;sheet.theme="classic"
        refreshed=[];sheet.refresh_all=lambda:refreshed.append(True)
        dialog=EngineeringDialog(sheet);dialog.table.selectRow(0)
        before=self.repo.sqlite_connection.total_changes
        with patch.object(QMessageBox,"question",return_value=QMessageBox.StandardButton.No):
            dialog.perform(dialog.load_charges)
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)
        self.assertEqual([],refreshed)
        dialog.close();dialog.deleteLater();sheet.deleteLater()
        app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

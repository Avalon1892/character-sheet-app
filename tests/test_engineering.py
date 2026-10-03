import tempfile
import unittest
from pathlib import Path
from app.database import CharacterRepository
from app.content import martial_entries
from app.engineering_rules import engineering_limits,device_statistics,occupied_limit,device_condition
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

    def test_practitioner_ability_uses_live_calculated_modifier(self):
        from app.services.character_calculations import CharacterCalculationService
        for ability in ("strength","dexterity","constitution","intelligence","wisdom","charisma"):
            self.assertEqual(CharacterCalculationService(self.repo,self.cid).ability_result(ability).ability_modifier,self.service.practitioner_modifier(ability))
        with self.assertRaises(ValueError):self.service.practitioner_modifier("invalid")

    def test_device_formula_references_track_state_without_name_collisions(self):
        from app.services.character_calculations import CharacterCalculationService
        first=self.gadget()
        device=next(d for d in self.service.devices("Tech") if d["id"]==first)
        second=self.service.create("Tech",device["catalog_key"],3)
        def context():return CharacterCalculationService(self.repo,self.cid).formula_context()
        prefix=f"devices.device_{first}"
        self.assertEqual(0,context().evaluate(prefix+".charges"))
        self.service.recharge();self.service.transfer_charges(first,2)
        self.assertEqual(2,context().evaluate(prefix+".charges"))
        self.assertEqual(0,context().evaluate(f"devices.device_{second}.charges"))
        self.service.change_state(first,"active")
        self.assertTrue(context().evaluate(prefix+".active"))
        self.service.damage_device(first,999,apply_hardness=False)
        self.assertEqual(0,context().evaluate(prefix+".hp.current"))
        self.assertTrue(context().evaluate(prefix+".destroyed"))
        self.assertFalse(context().evaluate(prefix+".active"))
        self.assertIn(prefix+".hp.maximum",context()._canonical_references())
        self.repo.add_custom_tracker(self.cid,"device_health","Device Health","calculated",formula=prefix+".hp.maximum")
        path=Path(self.temp.name)/"device-formulas.json"
        export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        imported_device=next(d for d in self.repo.list_engineering_devices(imported) if d["damage"]>0)
        tracker=next(t for t in self.repo.list_custom_trackers(imported) if t.key=="device_health")
        self.assertNotEqual(first,imported_device["id"])
        self.assertEqual(f"devices.device_{imported_device['id']}.hp.maximum",tracker.formula)
        self.assertEqual(context().evaluate(prefix+".hp.maximum"),CharacterCalculationService(self.repo,imported).formula_context().evaluate(tracker.formula))

    def test_tactile_field_requires_modification_and_does_not_stack_copies(self):
        from app.engineering_rules import TACTILE_FIELD_KEY
        from app.services.character_calculations import CharacterCalculationService
        entry=next(e for e in martial_entries("Tinker") if e["key"]=="tinker:gizmo-talent:personal-field-projector-gizmo-modification")
        self.add("Tinker",entry["name"],entry["key"],entry["category"])
        with self.assertRaises(ValueError):self.service.create("Tinker",TACTILE_FIELD_KEY,3)
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Modification")
        before=CharacterCalculationService(self.repo,self.cid)
        cmd=before.combat_results()["cmd"].total
        acrobatics=before.skill_result("acrobatics").total
        for _ in range(2):
            device=self.service.create("Tinker",TACTILE_FIELD_KEY,3)
            self.service.change_state(device,"active");self.service.apply_to_character(device,True)
        after=CharacterCalculationService(self.repo,self.cid)
        self.assertEqual(cmd+2,after.combat_results()["cmd"].total)
        self.assertEqual(acrobatics+2,after.skill_result("acrobatics").total)
        for device in self.service.devices("Tinker"):
            self.service.damage_device(device["id"],999,apply_hardness=False)
        self.assertEqual(cmd,CharacterCalculationService(self.repo,self.cid).combat_results()["cmd"].total)

    def test_tinker_effect_expiry_preserves_passive_device_activation(self):
        from app.engineering_rules import TACTILE_FIELD_KEY
        device=self.repo.save_engineering_device(self.cid,dict(sphere="Tinker",catalog_key=TACTILE_FIELD_KEY,name="Tactile Field",level=4,modifier=3,state="active",applied_to_character=True,effect_rounds=10))
        self.service.advance_time(9)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==device)
        self.assertEqual(("active",1),(record["state"],record["effect_rounds"]))
        self.service.advance_time(1)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==device)
        self.assertEqual(("active",0),(record["state"],record["effect_rounds"]))
        self.assertTrue(record["applied_to_character"])

    def test_supporting_battery_identity_transfer_and_detach_end_effect(self):
        from app.engineering_rules import TACTILE_FIELD_KEY
        host=self.repo.save_engineering_device(self.cid,dict(sphere="Tinker",catalog_key=TACTILE_FIELD_KEY,name="Field",level=4,modifier=3,state="active"))
        battery=self.service.create("Tinker","tinker:battery",3)
        self.service.attach_battery(battery,host)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==host)
        self.repo.save_engineering_device(self.cid,{**record,"effect_rounds":40,"effect_battery_id":battery},host)
        path=Path(self.temp.name)/"supporting-battery.json";export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        devices=self.repo.list_engineering_devices(imported)
        field=next(d for d in devices if d["catalog_key"]==TACTILE_FIELD_KEY)
        imported_battery=next(d for d in devices if d["catalog_key"]=="tinker:battery")
        self.assertEqual(imported_battery["id"],field["effect_battery_id"])
        self.service.attach_battery(battery,None)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==host)
        self.assertEqual((0,None,"active"),(record["effect_rounds"],record["effect_battery_id"],record["state"]))
        with self.assertRaises(ValueError):self.repo.save_engineering_device(self.cid,{**record,"effect_battery_id":imported_battery["id"]},host)
        self.service.attach_battery(battery,host)
        self.repo.save_engineering_device(self.cid,{**record,"effect_rounds":40,"effect_battery_id":battery},host)
        self.service.change_state(battery,"abandoned")
        record=next(d for d in self.service.devices("Tinker") if d["id"]==host)
        self.assertEqual((0,None),(record["effect_rounds"],record["effect_battery_id"]))

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

    def test_damage_hardness_broken_and_destroyed_gizmos(self):
        battery=self.service.create("Tinker","tinker:battery",3)
        record=self.service.devices("Tinker")[0]
        maximum=self.service.statistics(record)["hp"]
        self.service.damage_device(battery,2)
        self.assertEqual(0,self.service.devices("Tinker")[0]["damage"])
        self.service.damage_device(battery,maximum//2,apply_hardness=False)
        self.assertFalse(device_condition(self.service.devices("Tinker")[0])["broken"])
        self.service.damage_device(battery,1,apply_hardness=False)
        condition=device_condition(self.service.devices("Tinker")[0])
        self.assertTrue(condition["broken"])
        self.assertEqual(record["level"]-2,condition["effective_level"])
        self.service.damage_device(battery,99999,apply_hardness=False)
        self.assertEqual(0,device_condition(self.service.devices("Tinker")[0])["current_hp"])
        with self.assertRaises(ValueError):self.service.change_state(battery,"active")
        with self.assertRaises(ValueError):self.service.repair_tinker_device(battery,3)
        self.service.repair_tinker_device(battery,0,has_tools=True)
        self.assertEqual(maximum-record["level"],self.service.devices("Tinker")[0]["damage"])
        self.service.maintain("Tinker")
        self.assertEqual((0,"active"),(self.service.devices("Tinker")[0]["damage"],self.service.devices("Tinker")[0]["state"]))

    def test_physical_augmentor_configuration_and_live_skill_effects(self):
        from app.engineering_rules import PHYSICAL_AUGMENTOR_KEY
        from app.services.character_calculations import CharacterCalculationService
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Augmentation")
        with self.assertRaises(ValueError):self.service.create("Tinker",PHYSICAL_AUGMENTOR_KEY,3)
        device=self.service.create("Tinker",PHYSICAL_AUGMENTOR_KEY,3,configuration="dexterity")
        baseline=CharacterCalculationService(self.repo,self.cid).skill_result("acrobatics").total
        ability_score=CharacterCalculationService(self.repo,self.cid).ability_result("dexterity").total
        with self.assertRaises(ValueError):self.service.apply_to_character(device,True)
        self.service.change_state(device,"active");self.service.apply_to_character(device,True)
        self.assertEqual(baseline+3,CharacterCalculationService(self.repo,self.cid).skill_result("acrobatics").total)
        self.assertEqual(ability_score,CharacterCalculationService(self.repo,self.cid).ability_result("dexterity").total)
        self.service.damage_device(device,10,apply_hardness=False)
        self.assertEqual(baseline+2,CharacterCalculationService(self.repo,self.cid).skill_result("acrobatics").total)
        self.service.apply_to_character(device,False)
        self.assertEqual(baseline,CharacterCalculationService(self.repo,self.cid).skill_result("acrobatics").total)

    def test_mental_augmentor_requires_cognitive_set_and_applies_mental_skills(self):
        from app.engineering_rules import MENTAL_AUGMENTOR_KEY
        from app.services.character_calculations import CharacterCalculationService
        with self.assertRaises(ValueError):self.service.create("Tinker",MENTAL_AUGMENTOR_KEY,3,configuration="wisdom")
        entry=next(e for e in martial_entries("Tinker") if e["key"]=="tinker:gizmo-talent:cognitive-set-gizmo-utility")
        self.add("Tinker",entry["name"],entry["key"],entry["category"])
        with self.assertRaises(ValueError):self.service.create("Tinker",MENTAL_AUGMENTOR_KEY,3,configuration="wisdom")
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Augmentation")
        with self.assertRaises(ValueError):self.service.create("Tinker",MENTAL_AUGMENTOR_KEY,3,configuration="dexterity")
        device=self.service.create("Tinker",MENTAL_AUGMENTOR_KEY,3,configuration="wisdom")
        before=CharacterCalculationService(self.repo,self.cid).skill_result("perception").total
        score=CharacterCalculationService(self.repo,self.cid).ability_result("wisdom").total
        self.service.change_state(device,"active");self.service.apply_to_character(device,True)
        self.assertEqual(before+3,CharacterCalculationService(self.repo,self.cid).skill_result("perception").total)
        self.assertEqual(score,CharacterCalculationService(self.repo,self.cid).ability_result("wisdom").total)
        self.service.change_state(device,"inactive")
        self.assertEqual(before,CharacterCalculationService(self.repo,self.cid).skill_result("perception").total)

    def test_load_bearer_changes_capacity_not_strength_and_handles_damage(self):
        from app.engineering_rules import LOAD_BEARER_KEY
        from app.services.character_calculations import CharacterCalculationService
        from app.rules import calculate_encumbrance
        entry=next(e for e in martial_entries("Tinker") if e["key"]=="tinker:gizmo-talent:pressure-jack-gizmo")
        self.add("Tinker",entry["name"],entry["key"],entry["category"])
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Augmentation")
        with self.assertRaises(ValueError):self.service.create("Tinker",LOAD_BEARER_KEY,3,configuration="dexterity")
        normal=self.service.create("Tinker",LOAD_BEARER_KEY,3,configuration="strength")
        advanced=self.service.create("Tinker",LOAD_BEARER_KEY,3,configuration="strength",advanced=1)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==advanced)
        self.repo.save_engineering_device(self.cid,{**record,"level":4},advanced)
        calculation=CharacterCalculationService(self.repo,self.cid)
        strength=calculation.ability_result("strength").total
        size=calculation.state.details.size
        baseline=calculation.encumbrance()
        for device in (normal,advanced):
            self.service.change_state(device,"active");self.service.apply_to_character(device,True)
        result=CharacterCalculationService(self.repo,self.cid)
        self.assertEqual(strength,result.ability_result("strength").total)
        self.assertEqual(calculate_encumbrance(strength+6,size,0,0),result.encumbrance())
        from app.services.sheet_presentation import build_character_sheet_snapshot
        self.assertEqual(result.encumbrance().capacity,build_character_sheet_snapshot(self.repo,self.cid).carrying_capacity)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==advanced)
        self.service.damage_device(advanced,device_condition(record)["maximum_hp"]//2+1,apply_hardness=False)
        self.assertEqual(calculate_encumbrance(strength+4,size,0,0),CharacterCalculationService(self.repo,self.cid).encumbrance())
        self.service.change_state(normal,"inactive");self.service.change_state(advanced,"inactive")
        self.assertEqual(baseline,CharacterCalculationService(self.repo,self.cid).encumbrance())

    def test_expanded_tinkering_packages_unlock_functions_and_validate_choices(self):
        from app.engineering_rules import tinker_packages,validate_tinker_package_choice,PHYSICAL_AUGMENTOR_KEY
        from app.talent_automation import martial_automation
        from app.ui.dialogs import FeatChoiceDialog
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([])
        automation=martial_automation("Expanded Tinkering")
        self.assertEqual("tinker_packages_two",automation["choice_type"])
        dialog=FeatChoiceDialog("tinker_packages_two","Packages",[],[],excluded_choices=("Computation",))
        self.assertEqual(4,dialog.selection.count())
        self.assertEqual(-1,dialog.selection.findText("Computation"))
        dialog.close();dialog.deleteLater()
        records=self.repo.list_martial_talents(self.cid)
        for choice in ("Augmentation / Augmentation","Augmentation","Unknown / Modification"):
            with self.assertRaises(ValueError):validate_tinker_package_choice(choice,records)
        validate_tinker_package_choice("Augmentation / Modification",records)
        self.add("Tinker","Expanded Tinkering","tinker:talent:expanded-tinkering")
        expanded=next(t for t in self.repo.list_martial_talents(self.cid) if t.name=="Expanded Tinkering")
        self.repo.update_martial_talent(self.cid,expanded.id,expanded.name,"Tinker","Talent",catalog_key=expanded.catalog_key,catalog_category="Talent",choice="Augmentation / Modification")
        records=self.repo.list_martial_talents(self.cid)
        self.assertEqual(frozenset({"Augmentation","Modification"}),tinker_packages(records))
        with self.assertRaises(ValueError):validate_tinker_package_choice("Augmentation / Computation",records)
        self.assertIn(PHYSICAL_AUGMENTOR_KEY,{e["key"] for e in self.service.known_devices("Tinker")})

    def test_flexible_tinker_choices_validate_order_and_owned_packages(self):
        from app.flexible_talent_rules import validate_flexible_talent_entries
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Augmentation")
        def record(choice):
            return dict(talent_kind="martial",catalog_key="tinker:talent:expanded-tinkering",choice=choice,choice_key=choice.casefold())
        def validate(records):
            return validate_flexible_talent_entries(self.repo,self.cid,records,source_key="test",capacity=3,feature_name="Test",allow_base_spheres=True)
        for choice in ("Augmentation / Computation","Computation / Computation","Invalid / Modification"):
            with self.assertRaises(ValueError):validate([record(choice)])
        self.assertEqual(2,len(validate([record("Computation / Modification"),record("Transmission / Transportation")])))
        with self.assertRaises(ValueError):validate([record("Computation / Modification"),record("Computation / Transmission")])
        self.assertEqual([],self.repo.list_flexible_talent_selections(self.cid,"test"))

    def test_augmentor_choices_and_wearer_state_survive_transfer(self):
        from app.engineering_rules import PHYSICAL_AUGMENTOR_KEY
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Augmentation")
        device=self.service.create("Tinker",PHYSICAL_AUGMENTOR_KEY,3,configuration="strength")
        self.service.change_state(device,"active");self.service.apply_to_character(device,True)
        path=Path(self.temp.name)/"augmentor.json"
        export_character(self.repo,self.cid,path)
        other=EngineeringService(self.repo,import_character(self.repo,path))
        record=next(d for d in other.devices("Tinker") if d["catalog_key"]==PHYSICAL_AUGMENTOR_KEY)
        self.assertEqual(("strength",1),(record["configuration"],record["applied_to_character"]))
        with self.assertRaises(ValueError):other.apply_to_character(device,False)

    def test_jet_boosters_paid_movement_and_expiration(self):
        from app.engineering_rules import JET_BOOSTERS_KEY,TECH_BATTERY_KEY
        from app.services.character_calculations import CharacterCalculationService
        for key in (JET_BOOSTERS_KEY,TECH_BATTERY_KEY):
            entry=next(e for e in martial_entries("Tech") if e["key"]==key)
            self.add("Tech",entry["name"],entry["key"],entry["category"])
        jet=self.service.create("Tech",JET_BOOSTERS_KEY,3,configuration="flight")
        battery=self.service.create("Tech",TECH_BATTERY_KEY,3)
        self.service.attach_battery(battery,jet)
        self.service.start_jet_boosters(jet,"overdrive","Feet")
        movement=CharacterCalculationService(self.repo,self.cid).movement_results()
        self.assertEqual((90,"Clumsy"),(movement["fly_speed"],movement["fly_maneuverability"]))
        self.assertEqual(1,next(d for d in self.service.devices("Tech") if d["id"]==battery)["charges"])
        self.service.advance_time(1)
        self.assertEqual(0,CharacterCalculationService(self.repo,self.cid).movement_results()["fly_speed"])
        before=self.service.devices("Tech")
        with self.assertRaises(ValueError):self.service.start_jet_boosters(jet,"overdrive","Feet")
        self.assertEqual(before,self.service.devices("Tech"))
        self.service.start_jet_boosters(jet,"slow_burn","Feet")
        self.service.advance_time(2399)
        self.assertEqual(30,CharacterCalculationService(self.repo,self.cid).movement_results()["fly_speed"])
        self.repo.add_martial_talent(self.cid,"Athletics Sphere","Athletics","Base Sphere",catalog_key="athletics:base",catalog_category="Base Sphere",choice="Fly")
        self.add("Athletics","Swift Movement","athletics:talent:swift-movement")
        self.assertEqual(45,CharacterCalculationService(self.repo,self.cid).movement_results()["fly_speed"])
        FullRestEngine(self.repo,self.cid).perform()
        self.assertEqual(0,CharacterCalculationService(self.repo,self.cid).movement_results()["fly_speed"])

    def test_jet_slot_ownership_and_aquatic_configuration(self):
        from app.engineering_rules import JET_BOOSTERS_KEY
        from app.services.character_calculations import CharacterCalculationService
        entry=next(e for e in martial_entries("Tech") if e["key"]==JET_BOOSTERS_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        jet=self.service.create("Tech",JET_BOOSTERS_KEY,3,configuration="aquatic")
        second=self.service.create("Tech",JET_BOOSTERS_KEY,3,configuration="flight")
        self.service.recharge();self.service.transfer_charges(jet,1);self.service.transfer_charges(second,1)
        with self.assertRaises(ValueError):self.service.start_jet_boosters(jet,"normal","Slotless")
        self.service.start_jet_boosters(jet,"normal","Shoulders")
        self.assertEqual(60,CharacterCalculationService(self.repo,self.cid).movement_results()["swim_speed"])
        before=self.service.devices("Tech")
        with self.assertRaises(ValueError):self.service.start_jet_boosters(second,"normal","Shoulders")
        self.assertEqual(before,self.service.devices("Tech"))
        self.service.stop_function(jet,unequip=True)
        self.service.start_jet_boosters(second,"normal","Shoulders")
        self.repo.add_equipment(self.cid,"Cloak","Gear",1,1,True,0,"untyped",None,"",slot="Shoulders",state="worn")
        record=next(d for d in self.service.devices("Tech") if d["id"]==second)
        self.assertEqual(("",0),(record["worn_slot"],record["effect_rounds"]))
        self.assertEqual(0,CharacterCalculationService(self.repo,self.cid).movement_results()["fly_speed"])

    def test_jet_slow_burn_load_and_saved_timer(self):
        from app.engineering_rules import JET_BOOSTERS_KEY
        from app.services.character_calculations import CharacterCalculationService
        entry=next(e for e in martial_entries("Tech") if e["key"]==JET_BOOSTERS_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        jet=self.service.create("Tech",JET_BOOSTERS_KEY,3,configuration="flight")
        self.service.recharge();self.service.transfer_charges(jet,2)
        self.service.start_jet_boosters(jet,"slow_burn","Feet")
        self.service.advance_time(10)
        path=Path(self.temp.name)/"timed-jet.json"
        export_character(self.repo,self.cid,path)
        other=EngineeringService(self.repo,import_character(self.repo,path))
        imported=next(d for d in other.devices("Tech") if d["catalog_key"]==JET_BOOSTERS_KEY)
        self.assertEqual((2390,"Feet"),(imported["effect_rounds"],imported["worn_slot"]))
        self.repo.add_equipment(self.cid,"Heavy cargo","Gear",1,200,True,0,"untyped",None,"",state="carried")
        self.assertEqual(0,CharacterCalculationService(self.repo,self.cid).movement_results()["fly_speed"])
        self.service.stop_function(jet)
        before=self.service.devices("Tech")
        with self.assertRaises(ValueError):self.service.start_jet_boosters(jet,"slow_burn","Feet")
        self.assertEqual(before,self.service.devices("Tech"))

    def test_damage_survives_rest_transfer_and_does_not_repair_abandoned(self):
        device=self.gadget()
        self.service.damage_device(device,3,apply_hardness=False)
        FullRestEngine(self.repo,self.cid).perform()
        self.assertEqual(3,self.service.devices("Tech")[0]["damage"])
        path=Path(self.temp.name)/"damaged.json"
        export_character(self.repo,self.cid,path)
        other=EngineeringService(self.repo,import_character(self.repo,path))
        self.assertEqual(3,other.devices("Tech")[0]["damage"])
        battery=self.service.create("Tinker","tinker:battery",3)
        self.service.damage_device(battery,2,apply_hardness=False)
        self.service.change_state(battery,"abandoned")
        self.service.maintain("Tinker")
        self.assertEqual(2,self.service.devices("Tinker")[0]["damage"])
        with self.assertRaises(ValueError):self.service.repair_tinker_device(battery,3,has_tools=True)

    def test_destroyed_tech_battery_cannot_supply_charges(self):
        from app.engineering_rules import TECH_BATTERY_KEY
        entry=next(e for e in martial_entries("Tech") if e["key"]==TECH_BATTERY_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        host=self.gadget();battery=self.service.create("Tech",TECH_BATTERY_KEY,3)
        self.service.attach_battery(battery,host)
        self.service.damage_device(battery,99999,apply_hardness=False)
        with self.assertRaises(ValueError):self.service.transfer_charges(host,1,spend=True)
        with self.assertRaises(ValueError):self.service.recharge_tech_battery(battery)
        self.assertEqual(3,next(d for d in self.service.devices("Tech") if d["id"]==battery)["charges"])

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
                dialog.practitioner_ability.setCurrentIndex(dialog.practitioner_ability.findData("wisdom"))
                self.assertFalse(dialog.modifier.isEnabled())
                self.assertEqual(self.service.practitioner_modifier("wisdom"),dialog.modifier.value())
                dialog.practitioner_ability.setCurrentIndex(0)
                self.assertTrue(dialog.modifier.isEnabled())
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

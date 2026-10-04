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

    def test_energy_efficient_augment_duration_and_paid_expiry(self):
        from app.engineering_rules import DERMAL_PLATING_KEY,tech_minute_augment_rounds
        for ranks,expected in ((4,10),(5,50),(9,50),(10,100),(14,100),(15,300),(20,300)):
            self.assertEqual(expected,tech_minute_augment_rounds(ranks,energy_efficient=True,augment_talents=2))
            self.assertEqual(10,tech_minute_augment_rounds(ranks,augment_talents=2))
            self.assertEqual(10,tech_minute_augment_rounds(ranks,energy_efficient=True,augment_talents=1))
        self.add("Tech","Dermal Plating",DERMAL_PLATING_KEY)
        ordinary=self.service.create("Tech",DERMAL_PLATING_KEY,3)
        self.add("Tech","Energy Efficient Augments","tech:legendary-talent:energy-efficient-augments","Legendary Talent")
        self.add("Tech","Clamp Boots","tech:gadget-talent:clamp-boots-augment-drone-gadget")
        host=self.service.create("Tech",DERMAL_PLATING_KEY,3)
        self.assertFalse(next(d for d in self.service.devices("Tech") if d["id"]==ordinary)["energy_efficient"])
        self.assertTrue(next(d for d in self.service.devices("Tech") if d["id"]==host)["energy_efficient"])
        training=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tech:legendary-talent:energy-efficient-augments")
        self.repo.set_martial_talent_enabled(self.cid,training.id,False)
        self.service.apply_to_character(host,True)
        self.service.recharge();self.service.transfer_charges(host,1)
        self.service.start_dermal_plating(host)
        record=lambda:next(d for d in self.service.devices("Tech") if d["id"]==host)
        self.assertEqual(50,record()["effect_rounds"])
        self.assertEqual(0,record()["charges"])
        self.service.advance_time(49)
        self.assertEqual("active",record()["state"])
        self.service.advance_time(1)
        self.assertEqual("inactive",record()["state"])
        with self.assertRaises(ValueError):
            self.repo.spend_tech_device_charges(self.cid,host,1,function_mode="dermal",dermal_rounds=999)
        path=Path(self.temp.name)/"efficient.json"
        export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        self.assertEqual(1,sum(d["energy_efficient"] for d in self.repo.list_engineering_devices(imported)))

    def test_graft_implantation_shared_capacity_and_absent_scores(self):
        from app.engineering_rules import graft_implantation_status
        status=graft_implantation_status(12,8,graft_values=(2,2),cybertech_value=4)
        self.assertEqual((8,8,0,False,0),tuple(status[key] for key in ("capacity","total","remaining","overloaded","save_penalty")))
        self.assertEqual(-4,graft_implantation_status(12,8,graft_values=(2,2,2),cybertech_value=4)["save_penalty"])
        self.assertEqual(12,graft_implantation_status(None,12,graft_values=(2,))["capacity"])
        self.assertEqual(12,graft_implantation_status(12,None,graft_values=(2,))["capacity"])
        self.assertFalse(graft_implantation_status(None,None,graft_values=(2,))["has_controlling_score"])
        self.assertEqual(0,graft_implantation_status(12,8,cybertech_value=20)["save_penalty"])
        for kwargs in ({"graft_values":(-1,)},{"cybertech_value":1.5},{"graft_values":(True,)}):
            with self.assertRaises(ValueError):graft_implantation_status(12,8,**kwargs)
        with self.assertRaises(ValueError):graft_implantation_status("12",8)

    def test_graft_construction_plan_cost_time_prerequisites_and_no_writes(self):
        from app.engineering_rules import DERMAL_PLATING_KEY,tech_graft_quote
        quote=tech_graft_quote("appliance",3)
        self.assertEqual((1200,2400,13,20,3,1),tuple(quote[k] for k in ("cost_gp","base_price_gp","craft_dc","hours","days","charge_capacity")))
        self.assertEqual(600,tech_graft_quote("contraption",3)["cost_gp"])
        self.assertEqual(8,tech_graft_quote("contraption",1)["hours"])
        with self.assertRaises(ValueError):tech_graft_quote("appliance",1,2)
        self.assertEqual(800,tech_graft_quote("appliance",1,2,versatile_crafter=True)["cost_gp"])
        for args in (("gizmo",3),("appliance",0),("contraption",True)):
            with self.assertRaises(ValueError):tech_graft_quote(*args)
        self.add("Tech","Dermal Plating",DERMAL_PLATING_KEY)
        before=self.repo.list_engineering_devices(self.cid)
        with self.assertRaises(ValueError):self.service.graft_plan(DERMAL_PLATING_KEY,"appliance",3)
        with self.assertRaises(ValueError):self.service.graft_plan(DERMAL_PLATING_KEY,"appliance",3,gm_permission=True)
        self.repo.add_feat(self.cid,"Craft Appliances And Contraptions")
        self.repo.add_feat(self.cid,"Craft Augment Graft")
        self.assertEqual(quote,self.service.graft_plan(DERMAL_PLATING_KEY,"appliance",3,gm_permission=True))
        with self.assertRaises(ValueError):self.service.graft_plan(DERMAL_PLATING_KEY,"appliance",7,gm_permission=True)
        with self.assertRaises(ValueError):self.service.graft_plan("tech:gadget-talent:camera-drone-gadget","appliance",3,gm_permission=True)
        self.assertEqual(before,self.repo.list_engineering_devices(self.cid))

    def test_completed_graft_recording_validation_charges_and_transfer(self):
        from app.engineering_rules import DERMAL_PLATING_KEY
        self.add("Tech","Dermal Plating",DERMAL_PLATING_KEY)
        self.repo.add_feat(self.cid,"Craft Appliances And Contraptions")
        self.repo.add_feat(self.cid,"Craft Augment Graft")
        options=dict(check_result=13,materials_paid=True,time_completed=True,gm_permission=True)
        for invalid in ({"materials_paid":False},{"time_completed":False},{"check_result":12},{"check_result":True},{"gm_permission":False}):
            with self.assertRaises(ValueError):
                self.service.record_completed_graft(DERMAL_PLATING_KEY,"appliance",3,2,**{**options,**invalid})
        self.assertEqual([],self.repo.list_engineering_devices(self.cid))
        graft=self.service.record_completed_graft(DERMAL_PLATING_KEY,"appliance",3,2,**options)
        record=lambda:next(d for d in self.service.devices("Tech") if d["id"]==graft)
        self.assertEqual(("graft_appliance",1,"inactive"),(record()["construction_kind"],record()["charges"],record()["state"]))
        self.assertEqual(0,occupied_limit(self.service.devices("Tech"),self.service.limits("Tech")))
        with self.assertRaises(ValueError):self.service.apply_to_character(graft,True)
        self.service.recharge()
        for amount in (-1,1):
            with self.assertRaises(ValueError):self.service.transfer_charges(graft,amount)
        self.repo.spend_tech_device_charges(self.cid,graft,1)
        with self.assertRaises(ValueError):self.service.recharge_graft(graft)
        self.assertEqual(0,record()["charges"])
        self.service.recharge_graft(graft,recharge_completed=True)
        self.assertEqual(1,record()["charges"])
        path=Path(self.temp.name)/"graft.json"
        export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        restored=self.repo.list_engineering_devices(imported)
        self.assertEqual(("graft_appliance",1),(restored[0]["construction_kind"],restored[0]["charges"]))

    def test_clamp_boots_paid_movement_clamping_polymorph_and_transfer(self):
        from app.engineering_rules import CLAMP_BOOTS_KEY
        from app.services.character_calculations import CharacterCalculationService
        self.add("Tech","Clamp Boots",CLAMP_BOOTS_KEY)
        boots=self.service.create("Tech",CLAMP_BOOTS_KEY,3)
        with self.assertRaises(ValueError):self.service.set_boots_clamped(boots,True)
        self.service.apply_to_character(boots,True)
        other=self.service.create("Tech",CLAMP_BOOTS_KEY,3)
        with self.assertRaises(ValueError):self.service.apply_to_character(other,True)
        self.service.recharge();self.service.transfer_charges(boots,1)
        self.service.start_timed_augment(boots,CLAMP_BOOTS_KEY)
        movement=lambda:CharacterCalculationService(self.repo,self.cid).movement_results()
        self.assertGreater(movement()["climb_speed"],0)
        self.assertEqual(movement()["land_speed"],movement()["climb_speed"])
        self.service.set_boots_clamped(boots,True)
        self.assertEqual(0,movement()["land_speed"])
        self.assertEqual(3,self.service.clamp_boots_resistance(boots))
        self.service.set_polymorphed(True)
        self.assertGreater(movement()["land_speed"],0)
        self.assertEqual(0,self.service.clamp_boots_resistance(boots))
        self.service.set_polymorphed(False)
        path=Path(self.temp.name)/"boots.json";export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        self.assertEqual(0,CharacterCalculationService(self.repo,imported).movement_results()["land_speed"])
        self.service.set_boots_clamped(boots,False)
        self.assertGreater(movement()["land_speed"],0)
        self.service.advance_time(10)
        self.assertEqual(0,movement()["climb_speed"])
        self.service.apply_to_character(boots,False)
        self.service.apply_to_character(other,True)

    def test_augmentor_reroll_requires_wearer_and_spends_one_battery(self):
        from app.engineering_rules import PHYSICAL_AUGMENTOR_KEY
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Augmentation")
        host=self.service.create("Tinker",PHYSICAL_AUGMENTOR_KEY,3,configuration="strength")
        battery=self.service.create("Tinker","tinker:battery",3)
        self.service.attach_battery(battery,host)
        self.service.change_state(host,"active")
        with self.assertRaises(ValueError):self.service.use_augmentor_reroll(host)
        self.assertEqual("active",next(d for d in self.service.devices("Tinker") if d["id"]==battery)["state"])
        self.service.apply_to_character(host,True)
        self.service.use_augmentor_reroll(host)
        self.assertEqual("depleted",next(d for d in self.service.devices("Tinker") if d["id"]==battery)["state"])
        with self.assertRaises(ValueError):self.service.use_augmentor_reroll(host)
        self.assertEqual("active",next(d for d in self.service.devices("Tinker") if d["id"]==host)["state"])

    def test_resistance_routine_installation_saves_stacking_and_transfer(self):
        from app.engineering_rules import RESISTANCE_ROUTINE_KEY
        entry=next(e for e in martial_entries("Tinker") if e["key"]=="tinker:gizmo-talent:defensive-set-gizmo")
        self.add("Tinker",entry["name"],entry["key"],entry["category"])
        with self.assertRaises(ValueError):self.service.create("Tinker",RESISTANCE_ROUTINE_KEY,3)
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Computation")
        host=self.service.create("Tinker","tinker:battery",3)
        record=lambda key:next(d for d in self.service.devices("Tinker") if d["id"]==key)
        before=self.service.statistics(record(host))["save"]
        routines=[]
        for _ in range(2):
            routine=self.service.create("Tinker",RESISTANCE_ROUTINE_KEY,3)
            # A retained level-4 routine crosses a bonus breakpoint when broken.
            self.repo.save_engineering_device(self.cid,{**record(routine),"level":4},routine)
            self.assertTrue(record(routine)["minor"])
            self.service.install_resistance_routine(routine,host)
            self.assertEqual(before if not routines else before+2,self.service.statistics(record(host))["save"])
            self.service.change_state(routine,"active");routines.append(routine)
        self.assertEqual(before+2,self.service.statistics(record(host))["save"])
        for routine in routines:self.service.damage_device(routine,7,apply_hardness=False)
        self.assertEqual(before+1,self.service.statistics(record(host))["save"])
        path=Path(self.temp.name)/"routine.json";export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        service=EngineeringService(self.repo,imported)
        imported_host=next(d for d in service.devices("Tinker") if d["catalog_key"]=="tinker:battery")
        self.assertEqual(before+1,service.statistics(imported_host)["save"])
        self.assertTrue(all(d["host_id"]==imported_host["id"] for d in service.devices("Tinker") if d["catalog_key"]==RESISTANCE_ROUTINE_KEY))
        for routine in routines:self.service.install_resistance_routine(routine,None)
        self.assertEqual(before,self.service.statistics(record(host))["save"])
        with self.assertRaises(ValueError):self.service.install_resistance_routine(routines[0],routines[0])
        foreign=self.repo.create_character("Other","Spheres")
        with self.assertRaises(ValueError):self.repo.save_engineering_device(foreign,{**record(routines[0]),"host_id":host})

    def test_routine_activation_follows_host_lifecycle(self):
        from app.engineering_rules import RESISTANCE_ROUTINE_KEY
        entry=next(e for e in martial_entries("Tinker") if e["key"]=="tinker:gizmo-talent:defensive-set-gizmo")
        self.add("Tinker",entry["name"],entry["key"],entry["category"])
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Computation")
        host=self.service.create("Tinker",entry["key"],3)
        battery=self.service.create("Tinker","tinker:battery",3)
        routine=self.service.create("Tinker",RESISTANCE_ROUTINE_KEY,3)
        record=lambda key:next(d for d in self.service.devices("Tinker") if d["id"]==key)
        with self.assertRaises(ValueError):self.service.change_state(routine,"active")
        self.service.install_resistance_routine(routine,host)
        before=self.repo.sqlite_connection.total_changes
        with self.assertRaises(ValueError):self.service.change_state(routine,"active")
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)
        self.service.change_state(host,"active");self.service.change_state(routine,"active")
        self.service.change_state(host,"inactive")
        self.assertEqual("inactive",record(routine)["state"])
        self.service.change_state(host,"active")
        self.assertEqual("inactive",record(routine)["state"])
        self.service.install_resistance_routine(routine,battery);self.service.change_state(routine,"active")
        self.service.attach_battery(battery,host);self.service.use_batteries(host,1)
        self.assertEqual("inactive",record(routine)["state"])
        self.service.maintain("Tinker");self.service.change_state(routine,"active")
        self.service.damage_device(battery,999,apply_hardness=False)
        self.assertEqual("inactive",record(routine)["state"])
        self.service.maintain("Tinker");self.service.change_state(routine,"active")
        self.service.install_resistance_routine(routine,None)
        self.assertEqual("inactive",record(routine)["state"])

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

    def test_tactile_battery_enhancement_payment_expiry_and_reroll(self):
        from app.engineering_rules import TACTILE_FIELD_KEY,tactile_field_bonus
        host=self.repo.save_engineering_device(self.cid,dict(sphere="Tinker",catalog_key=TACTILE_FIELD_KEY,name="Field",level=4,modifier=3,state="active",applied_to_character=True))
        battery=self.service.create("Tinker","tinker:battery",3);self.service.attach_battery(battery,host)
        self.service.use_batteries(host,1,tactile_boost=True)
        records={d["id"]:d for d in self.service.devices("Tinker")}
        self.assertEqual("depleted",records[battery]["state"])
        self.assertEqual((40,3),(records[host]["effect_rounds"],tactile_field_bonus(records[host])))
        with self.assertRaises(ValueError):self.service.use_batteries(host,1,tactile_boost=True)
        self.service.end_tactile_enhancement(host)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==host)
        self.assertEqual((0,2,"active"),(record["effect_rounds"],tactile_field_bonus(record),record["state"]))
        self.service.maintain("Tinker");self.service.use_batteries(host,1,tactile_boost=True)
        self.service.advance_time(40)
        record=next(d for d in self.service.devices("Tinker") if d["id"]==host)
        self.assertEqual((0,2,"active"),(record["effect_rounds"],tactile_field_bonus(record),record["state"]))

    def test_advanced_tactile_reroll_is_free_but_enhancement_is_not(self):
        from app.engineering_rules import TACTILE_FIELD_KEY
        host=self.repo.save_engineering_device(self.cid,dict(sphere="Tinker",catalog_key=TACTILE_FIELD_KEY,name="Field",level=6,modifier=3,state="active",applied_to_character=True))
        with self.assertRaises(ValueError):self.service.use_tactile_reroll(host)
        base=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tinker:base")
        self.repo.update_martial_talent(self.cid,base.id,base.name,"Tinker","Base Sphere",catalog_key=base.catalog_key,catalog_category="Base Sphere",choice="Modification")
        key="tinker:legendary-talent:advanced-field-projectors-gizmo-modification"
        self.add("Tinker","Advanced Field Projectors",key,"Legendary Talent")
        self.assertTrue(self.service.tactile_reroll_at_will())
        before=self.repo.sqlite_connection.total_changes
        self.assertIs(False,self.service.use_tactile_reroll(host))
        self.assertEqual(before,self.repo.sqlite_connection.total_changes)
        with self.assertRaises(ValueError):self.service.use_batteries(host,1,tactile_boost=True)
        battery=self.service.create("Tinker","tinker:battery",3);self.service.attach_battery(battery,host)
        self.service.use_batteries(host,1,tactile_boost=True)
        self.assertEqual("depleted",next(d for d in self.service.devices("Tinker") if d["id"]==battery)["state"])
        self.service.use_tactile_reroll(host)
        self.assertEqual(0,next(d for d in self.service.devices("Tinker") if d["id"]==host)["effect_rounds"])
        self.service.apply_to_character(host,False)
        with self.assertRaises(ValueError):self.service.use_tactile_reroll(host)

    def test_dermal_plating_dedicated_slot_payment_ac_and_expiration(self):
        from app.engineering_rules import DERMAL_PLATING_KEY
        from app.services.character_calculations import CharacterCalculationService
        entry=next(e for e in martial_entries("Tech") if e["key"]==DERMAL_PLATING_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        host=self.service.create("Tech",DERMAL_PLATING_KEY,3)
        other=self.service.create("Tech",DERMAL_PLATING_KEY,3)
        ac=lambda:CharacterCalculationService(self.repo,self.cid).combat_results()["ac"].total
        baseline=ac()
        with self.assertRaises(ValueError):self.service.start_dermal_plating(host)
        self.service.apply_to_character(host,True)
        with self.assertRaises(ValueError):self.service.apply_to_character(other,True)
        self.repo.add_equipment(self.cid,"Robe","Gear",1,0,True,0,"untyped",None,"",slot="Body")
        record=lambda key:next(d for d in self.service.devices("Tech") if d["id"]==key)
        self.assertEqual("Body",record(host)["augment_slot"])
        self.assertEqual(baseline,ac())
        with self.assertRaises(ValueError):self.service.start_dermal_plating(host)
        self.service.recharge();self.service.transfer_charges(host,1)
        self.service.start_dermal_plating(host)
        self.assertEqual((0,10),(record(host)["charges"],record(host)["effect_rounds"]))
        self.assertEqual(baseline+3,ac())
        paid=dict(record(host))
        self.service.set_polymorphed(True)
        self.assertEqual(baseline,ac())
        self.assertEqual(paid,record(host))
        self.assertTrue(CharacterCalculationService(self.repo,self.cid).formula_context().evaluate(f"devices.device_{host}.suppressed"))
        self.service.set_polymorphed(False)
        self.assertEqual(baseline+3,ac())
        self.service.advance_time(10)
        self.assertEqual("inactive",record(host)["state"])
        self.assertEqual(baseline,ac())
        self.repo.add_modifier(self.cid,"ac","Existing natural armor enhancement","natural armor enhancement",5)
        self.service.transfer_charges(host,1);self.service.start_dermal_plating(host)
        self.assertEqual(baseline+5,ac())
        self.service.set_polymorphed(True)
        path=Path(self.temp.name)/"dermal.json";export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        self.assertTrue(self.repo.engineering_polymorphed(imported))
        self.assertEqual("Body",next(d for d in self.repo.list_engineering_devices(imported) if d["applied_to_character"])["augment_slot"])
        self.service.apply_to_character(host,False);self.service.apply_to_character(other,True)
        self.assertEqual("",record(host)["augment_slot"])

    def test_polymorph_state_is_owned_and_does_not_apply_tech_rule_to_tinker(self):
        from app.engineering_rules import tech_augment_suppressed
        self.assertFalse(self.repo.engineering_polymorphed(self.cid))
        with self.assertRaises(ValueError):self.service.set_polymorphed("yes")
        with self.assertRaises(KeyError):self.repo.set_engineering_polymorphed(999999,True)
        self.service.set_polymorphed(True)
        other=self.repo.create_character("Other","Spheres")
        self.assertFalse(self.repo.engineering_polymorphed(other))
        self.assertFalse(tech_augment_suppressed(dict(sphere="Tinker",augment_slot="Body",applied_to_character=True),True))

    def test_bio_augment_is_creation_specific_and_survives_polymorph_and_transfer(self):
        from app.models import SkillState
        from app.engineering_rules import DERMAL_PLATING_KEY
        from app.services.character_calculations import CharacterCalculationService
        entry=next(e for e in martial_entries("Tech") if e["key"]==DERMAL_PLATING_KEY)
        self.add("Tech",entry["name"],entry["key"],entry["category"])
        plain=self.service.create("Tech",DERMAL_PLATING_KEY,3)
        with self.assertRaises(ValueError):self.service.create("Tech",DERMAL_PLATING_KEY,3,bio_augment=True)
        self.repo.add_class_level(self.cid,"Conscript",4,"Full","Good","Poor","Poor",hit_die=10,hp_gained=20)
        self.repo.update_skill_state(self.cid,SkillState("disguise",ranks=10))
        self.add("Tech","Hidden Gadget","tech:legendary-talent:hidden-gadget","Legendary Talent")
        self.add("Tech","Bio Augment","tech:legendary-talent:bio-augment","Legendary Talent")
        self.assertFalse(self.service.can_create_bio_augment(DERMAL_PLATING_KEY))
        for name in ("Auto Injector (","Clamp Boots ("):
            extra=next(e for e in martial_entries("Tech") if e["name"].startswith(name))
            self.add("Tech",extra["name"],extra["key"],extra["category"])
        self.assertTrue(self.service.can_create_bio_augment(DERMAL_PLATING_KEY))
        bio=self.service.create("Tech",DERMAL_PLATING_KEY,3,bio_augment=True)
        training=next(t for t in self.repo.list_martial_talents(self.cid) if t.catalog_key=="tech:legendary-talent:bio-augment")
        self.repo.set_martial_talent_enabled(self.cid,training.id,False)
        self.assertFalse(self.service.can_create_bio_augment(DERMAL_PLATING_KEY))
        self.add("Tech","Untraceable Gadget","tech:legendary-talent:untraceable-gadget","Legendary Talent")
        self.assertTrue(self.service.can_create_bio_augment(DERMAL_PLATING_KEY))
        self.assertFalse(next(d for d in self.service.devices("Tech") if d["id"]==plain)["bio_augment"])
        self.service.apply_to_character(bio,True)
        self.service.recharge();self.service.transfer_charges(bio,1);self.service.start_dermal_plating(bio)
        ac=lambda:CharacterCalculationService(self.repo,self.cid).combat_results()["ac"].total
        before=ac();self.service.set_polymorphed(True)
        self.assertEqual(before,ac())
        self.assertFalse(CharacterCalculationService(self.repo,self.cid).formula_context().evaluate(f"devices.device_{bio}.suppressed"))
        path=Path(self.temp.name)/"bio.json";export_character(self.repo,self.cid,path)
        imported=import_character(self.repo,path)
        imported_bio=next(d for d in self.repo.list_engineering_devices(imported) if d["bio_augment"])
        self.assertTrue(imported_bio["applied_to_character"])
        self.assertTrue(self.repo.engineering_polymorphed(imported))
        self.assertEqual(before,CharacterCalculationService(self.repo,imported).combat_results()["ac"].total)
        with self.assertRaises(ValueError):self.service.create("Tinker","tinker:battery",3,bio_augment=True)

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

    def test_graft_planner_themes_and_cancel_have_no_writes(self):
        from PySide6.QtWidgets import QApplication,QWidget
        from PySide6.QtCore import QEvent
        from app.ui.engineering import EngineeringDialog,GraftPlanningDialog
        from app.engineering_rules import DERMAL_PLATING_KEY
        self.add("Tech","Dermal Plating",DERMAL_PLATING_KEY)
        self.repo.add_feat(self.cid,"Craft Appliances And Contraptions")
        self.repo.add_feat(self.cid,"Craft Augment Graft")
        app=QApplication.instance() or QApplication([])
        for theme in ("classic","dark"):
            with self.subTest(theme=theme):
                sheet=QWidget();sheet.repository=self.repo;sheet.character_id=self.cid;sheet.theme=theme
                before=self.repo.sqlite_connection.total_changes
                parent=EngineeringDialog(sheet)
                planner=GraftPlanningDialog(self.service,DERMAL_PLATING_KEY,parent)
                self.assertIn("GM permission",planner.result.text())
                planner.permission.setChecked(True)
                self.assertIn("1,200 gp",planner.result.text())
                self.assertIn("20 working hours",planner.result.text())
                planner.kind.setCurrentIndex(1)
                self.assertIn("600 gp",planner.result.text())
                planner.reject()
                self.assertEqual(before,self.repo.sqlite_connection.total_changes)
                planner.deleteLater();parent.deleteLater();sheet.deleteLater()
                app.sendPostedEvents(None,QEvent.Type.DeferredDelete)

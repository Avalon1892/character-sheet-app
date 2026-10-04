"""Character-owned device lifecycle, separate from sheet presentation."""
from app.content import martial_entry
from app.engineering_rules import (engineering_limits, occupied_limit, device_statistics,
                                   is_battery, TECH_BATTERY_KEY, tech_battery_capacity,device_condition,
                                   PHYSICAL_AUGMENTOR_KEY,MENTAL_AUGMENTOR_KEY,LOAD_BEARER_KEY,AUGMENTOR_ABILITIES,JET_BOOSTERS_KEY,JET_MODES,tinker_packages)
from app.engineering_rules import physical_augmentor_bonus, tech_minute_augment_rounds,TECH_AUGMENT_SLOTS,TECH_TIMED_AUGMENT_MODES,CLAMP_BOOTS_KEY,clamp_boots_active
from app.services.character_calculations import CharacterCalculationService
from app.exploitant_rules import effective_martial_talents
from app.engineering_rules import TACTILE_FIELD_KEY,RESISTANCE_ROUTINE_KEY,resistance_routine_bonus,DERMAL_PLATING_KEY


def device_talent(entry):
    name = entry.get("name", "").casefold()
    return any(tag in name for tag in ("(gadget", ", gadget", "(gizmo", ", gizmo"))


class EngineeringService:
    def __init__(self, repository, character_id, skill_key="craft"):
        self.repository, self.character_id, self.skill_key = repository, character_id, skill_key

    def records(self, sphere):
        return tuple(t for t in effective_martial_talents(self.repository,self.character_id)
                     if t.enabled and t.sphere == sphere)

    def practitioner_modifier(self,ability):
        if ability not in {"strength","dexterity","constitution","intelligence","wisdom","charisma"}:
            raise ValueError("Choose a valid practitioner ability.")
        return CharacterCalculationService(self.repository,self.character_id).ability_result(ability).ability_modifier

    def set_implant_profile(self,**profile):
        self.repository.set_engineering_implant_profile(self.character_id,**profile)

    def known_devices(self, sphere):
        entries = {}
        for talent in self.records(sphere):
            entry = martial_entry(talent.catalog_key)
            if entry and device_talent(entry):
                entries[entry["key"]] = entry
        if sphere == "Tinker" and self.available(sphere):
            entries["tinker:battery"] = {"key":"tinker:battery", "name":"Battery (gizmo)",
                                        "description":"Depleting this battery powers a battery-use ability. A depleted battery still counts against your gizmo limit."}
            augmentation="Augmentation" in tinker_packages(self.records(sphere))
            if "Computation" in tinker_packages(self.records(sphere)) and any(t.catalog_key=="tinker:gizmo-talent:defensive-set-gizmo" for t in self.records(sphere)):
                entries[RESISTANCE_ROUTINE_KEY]={"key":RESISTANCE_ROUTINE_KEY,"name":"Resistance Routine (gizmo, minor, routine)",
                    "description":"Install in a gizmo to grant that gizmo a +1 insight bonus to all saves, +1 per 4 effective routine levels. Activate the routine after installation. This protects the host device, not the character. Multiple copies do not stack.",
                    "source_url":"https://spheresofpower.wikidot.com/tinker"}
            if augmentation:
                entries[PHYSICAL_AUGMENTOR_KEY]={"key":PHYSICAL_AUGMENTOR_KEY,"name":"Physical Augmentor (gizmo)",
                    "description":"Choose Strength, Dexterity or Constitution. Grants a competence bonus to checks based on that ability: 2 + 1 per 4 effective gizmo levels. Deplete an attached battery before a benefiting check to roll twice and take the higher result.",
                    "source_url":"https://spheresofpower.wikidot.com/tinker"}
            if augmentation and any(t.catalog_key=="tinker:gizmo-talent:cognitive-set-gizmo-utility" for t in self.records(sphere)):
                entries[MENTAL_AUGMENTOR_KEY]={"key":MENTAL_AUGMENTOR_KEY,"name":"Mental Augmentor (gizmo)",
                    "description":"Choose Intelligence, Wisdom or Charisma. Functions as a physical augmentor: competence bonus to matching ability and skill checks, 2 + 1 per 4 effective gizmo levels. Its battery use rolls a benefiting check twice and takes the higher result.",
                    "source_url":"https://spheresofpower.wikidot.com/tinker"}
            if augmentation and any(t.catalog_key=="tinker:gizmo-talent:pressure-jack-gizmo" for t in self.records(sphere)):
                entries[LOAD_BEARER_KEY]={"key":LOAD_BEARER_KEY,"name":"Load Bearer (gizmo)",
                    "description":"A Strength physical augmentor which also adds its bonus to Strength for carrying capacity. An advanced Load Bearer doubles that carrying-capacity bonus and treats the user as one size larger for Strength checks to break objects. Ability-check rolls and battery rerolls are resolved manually.",
                    "source_url":"https://spheresofpower.wikidot.com/tinker"}
            if "Modification" in tinker_packages(self.records(sphere)) and any(t.catalog_key=="tinker:gizmo-talent:personal-field-projector-gizmo-modification" for t in self.records(sphere)):
                entries[TACTILE_FIELD_KEY]={"key":TACTILE_FIELD_KEY,"name":"Tactile Field (gizmo)",
                    "description":"While active and attached, grants a circumstance bonus to CMD, Acrobatics and Escape Artist: 2 + 1 per 10 effective gizmo levels. Multiple Tactile Fields do not stack. Deplete one attached battery to add 1 per 4 effective gizmo levels for one minute per effective gizmo level. Once during that period, use an immediate action to reroll a failed Acrobatics/Escape Artist check or force a successful opposing combat maneuver to be rerolled with the same modifier; then end the enhancement. Resolve the roll manually and click the reroll/end control.",
                    "source_url":"https://spheresofpower.wikidot.com/tinker"}
        return tuple(sorted(entries.values(), key=lambda e:e["name"].casefold()))

    def available(self, sphere):
        return any(t.catalog_category.casefold() == "base sphere" or t.catalog_key.endswith(":base")
                   for t in self.records(sphere))

    def limits(self, sphere):
        ranks = CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get(self.skill_key,0)
        records = [t for t in self.records(sphere) if "drawback" not in t.catalog_category.casefold()
                   and "drawback" not in t.talent_type.casefold()
                   and "feat" not in t.catalog_category.casefold()]
        extra_name = "Extra Gadgets" if sphere == "Tech" else "Efficient Maintenance"
        extra = sum(t.name == extra_name for t in records)
        gadgets = sum(device_talent(martial_entry(t.catalog_key) or {}) for t in records)
        return engineering_limits(sphere,ranks,len(records),gadget_count=gadgets,extra=extra)

    def devices(self, sphere):
        return tuple(d for d in self.repository.list_engineering_devices(self.character_id) if d["sphere"]==sphere)

    def can_create_bio_augment(self,key):
        entry=next((e for e in self.known_devices("Tech") if e["key"]==key),None)
        if not entry or "augment" not in entry["name"].partition("(")[2].casefold():
            return False
        ranks=CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks()
        records=self.records("Tech");keys={t.catalog_key for t in records}
        if ranks.get("craft",0)<10 or ranks.get("disguise",0)<10 or "tech:legendary-talent:hidden-gadget" not in keys:
            return False
        if "tech:legendary-talent:untraceable-gadget" in keys:
            return True
        augments=sum("augment" in (martial_entry(t.catalog_key) or {}).get("name","").partition("(")[2].casefold() for t in records)
        return "tech:legendary-talent:bio-augment" in keys and augments>=3

    def graft_plan(self,key,kind,ranks,complexity=1,*,gm_permission=False):
        from app.services.crafting import CraftingService
        from app.skill_rank_rules import effective_skill_ranks
        from app.engineering_rules import tech_graft_quote
        if not gm_permission:
            raise ValueError("Expanded technical-item crafting requires GM permission.")
        permanent=self.repository.list_martial_talents(self.character_id)
        if not any(t.enabled and t.catalog_key=="tech:base" for t in permanent):
            raise ValueError("Permanent Tech sphere training is required for this owned-talent planner.")
        entry=martial_entry(key)
        if not entry or "augment" not in entry["name"].partition("(")[2].casefold() or not any(t.enabled and t.catalog_key==key for t in permanent):
            raise ValueError("Select a permanently learned augment talent.")
        calculations=CharacterCalculationService(self.repository,self.character_id)
        maximum=effective_skill_ranks(permanent,calculations.state.skills,calculations.state.character_level).get("craft",0)
        if maximum<3 or type(ranks) is not int or ranks>maximum:
            raise ValueError("Crafting requires 3 permanent Craft ranks; item ranks cannot exceed permanent ranks.")
        feats=CraftingService(self.repository,self.character_id).feats
        required={"craft appliances and contraptions","craft augment graft"}
        if not required<=feats:
            raise ValueError("Requires Craft Appliances And Contraptions and Craft Augment Graft.")
        return tech_graft_quote(kind,ranks,complexity,versatile_crafter="versatile crafter" in feats)

    def custom_graft_allowance(self):
        from app.class_choice_rules import resolve_class_choice_slots
        return sum(option.name=="Custom Graft" for slot in resolve_class_choice_slots(self.repository,self.character_id)
            if slot.key=="machinehead-prowesses" for option in slot.selected_options)

    def custom_graft_remaining(self):
        occupied=sum(d["construction_kind"]=="graft_custom" and d["state"]!="abandoned" for d in self.devices("Tech"))
        return max(0,self.custom_graft_allowance()-occupied)

    def create_custom_graft(self,key,modifier,*,construction_completed=False,bio_augment=False):
        if construction_completed is not True:raise ValueError("Confirm the custom graft construction period was completed.")
        if not self.custom_graft_remaining():raise ValueError("Select an unused Machinehead Custom Graft prowess first.")
        if not self.available("Tech") or key not in TECH_AUGMENT_SLOTS or not any(e["key"]==key for e in self.known_devices("Tech")):
            raise ValueError("Select a supported augment talent this character possesses.")
        if type(bio_augment) is not bool or (bio_augment and not self.can_create_bio_augment(key)):
            raise ValueError("Bio graft construction requires qualifying training.")
        ranks=CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get("craft",0)
        if ranks<1:raise ValueError("Custom grafts require Craft ranks to function.")
        efficient=tech_minute_augment_rounds(ranks,energy_efficient=any(t.catalog_key=="tech:legendary-talent:energy-efficient-augments" for t in self.records("Tech")),
            augment_talents=sum("augment" in (martial_entry(t.catalog_key) or {}).get("name","").partition("(")[2].casefold() for t in self.records("Tech")))>10
        entry=martial_entry(key)
        return self.repository.save_engineering_device(self.character_id,dict(sphere="Tech",catalog_key=key,name=entry["name"],level=ranks,modifier=modifier,
            state="inactive",charges=0,construction_kind="graft_custom",bio_augment=bio_augment,energy_efficient=efficient))

    def record_completed_graft(self,key,kind,ranks,modifier,*,check_result,materials_paid=False,time_completed=False,gm_permission=False,bio_augment=False):
        if type(bio_augment) is not bool or (bio_augment and not self.can_create_bio_augment(key)):
            raise ValueError("Bio graft construction requires qualifying Bio Augment or Untraceable Gadget training.")
        quote=self.graft_plan(key,kind,ranks,gm_permission=gm_permission)
        if materials_paid is not True or time_completed is not True:
            raise ValueError("Confirm materials were paid and construction time completed outside this recording action.")
        if type(check_result) is not int or check_result<quote["craft_dc"]:
            raise ValueError("A successful final construction check is required.")
        if key not in TECH_AUGMENT_SLOTS:
            raise ValueError("This graft's device effect and slot are not yet supported.")
        entry=martial_entry(key)
        permanent=self.repository.list_martial_talents(self.character_id)
        efficient=tech_minute_augment_rounds(ranks,
            energy_efficient=any(t.enabled and t.catalog_key=="tech:legendary-talent:energy-efficient-augments" for t in permanent),
            augment_talents=sum(t.enabled and "augment" in (martial_entry(t.catalog_key) or {}).get("name","").partition("(")[2].casefold() for t in permanent))>10
        return self.repository.save_engineering_device(self.character_id,dict(sphere="Tech",catalog_key=key,name=entry["name"],
            level=ranks,modifier=modifier,state="inactive",charges=quote["charge_capacity"],
            construction_kind="graft_"+kind,energy_efficient=efficient,bio_augment=bio_augment))

    def recharge_graft(self,device_id,*,recharge_completed=False):
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if recharge_completed is not True or not device or device["construction_kind"] not in {"graft_appliance","graft_contraption"} or device["state"]=="abandoned" or device_condition(device)["destroyed"]:
            raise ValueError("Select a functioning graft and confirm its 15-minute recharge was completed.")
        self.repository.save_engineering_device(self.character_id,{**device,"charges":max(1,device["level"]//2)},device_id)

    def install_graft(self,device_id,*,subject_willing_or_helpless=False,installation_completed=False,cybertech_value=None,allow_overload=False):
        if type(allow_overload) is not bool:raise ValueError("Over-limit installation requires an explicit true/false confirmation.")
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if subject_willing_or_helpless is not True or installation_completed is not True:
            raise ValueError("Confirm the subject remained willing or helpless throughout the completed two-hour installation.")
        if not device or not device["construction_kind"] or device["graft_slot"] or device["state"]=="abandoned" or device_condition(device)["destroyed"]:
            raise ValueError("Select a functioning, uninstalled graft owned by this character.")
        if device["construction_kind"]=="graft_custom":
            maintained=sorted(d["id"] for d in self.devices("Tech") if d["construction_kind"]=="graft_custom" and d["state"]!="abandoned")[:self.custom_graft_allowance()]
            if device_id not in maintained:raise ValueError("This custom graft requires its selected Machinehead prowess for self-implantation.")
        calculations=CharacterCalculationService(self.repository,self.character_id)
        profile=self.repository.engineering_implant_profile(self.character_id)
        if cybertech_value is None:cybertech_value=profile["cybertech_value"]
        status=calculations.graft_status(additional_values=(2,),cybertech_value=cybertech_value)
        if status["overloaded"] and not allow_overload:
            raise ValueError("This graft exceeds the current shared cybertech/graft limit. Explicitly confirm nonfunctioning, over-limit implantation first.")
        if not status["has_controlling_score"] and not allow_overload:raise ValueError("A creature without Constitution and Intelligence cannot benefit from grafts.")
        self.repository.install_engineering_graft(self.character_id,device_id,cybertech_value=cybertech_value)

    def remove_graft(self,device_id,*,removal_completed=False,save_succeeded=None):
        if removal_completed is not True:
            raise ValueError("Confirm surgical removal was completed first.")
        self.repository.remove_engineering_graft(self.character_id,device_id,save_succeeded=save_succeeded)

    def create(self, sphere, key, modifier, *, minor=False, advanced=0,configuration="",bio_augment=False):
        if not self.available(sphere):
            raise ValueError("This character does not currently have that base sphere.")
        entry = next((e for e in self.known_devices(sphere) if e["key"]==key),None)
        if entry is None:
            raise ValueError("Learn the device's talent first.")
        if bio_augment and (sphere!="Tech" or not self.can_create_bio_augment(key)):
            raise ValueError("Bio construction requires an augment, 10 Craft/Disguise ranks, Hidden Gadget, and qualifying Bio Augment or Untraceable Gadget training.")
        if sphere == "Tech" and (minor or advanced):
            raise ValueError("Minor and advanced gizmo rules belong to Tinker, not Tech.")
        if key in AUGMENTOR_ABILITIES and configuration not in AUGMENTOR_ABILITIES[key]:
            raise ValueError("Choose an appropriate ability for the augmentor.")
        if key==JET_BOOSTERS_KEY and configuration not in {"flight","aquatic"}:
            raise ValueError("Choose flight or aquatic boosters at creation.")
        if key==RESISTANCE_ROUTINE_KEY:
            minor=True
        ranks = CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get(self.skill_key,0)
        if sphere=="Tinker" and ranks<1:
            raise ValueError("A gizmo requires at least one rank in its associated skill.")
        tech_records=self.records("Tech") if sphere=="Tech" else ()
        efficient=sphere=="Tech" and "augment" in entry["name"].partition("(")[2].casefold() and tech_minute_augment_rounds(ranks,
            energy_efficient=any(t.catalog_key=="tech:legendary-talent:energy-efficient-augments" for t in tech_records),
            augment_talents=sum("augment" in (martial_entry(t.catalog_key) or {}).get("name","").partition("(")[2].casefold() for t in tech_records))>10
        record = dict(sphere=sphere,catalog_key=key,name=entry["name"],level=ranks,modifier=modifier,
                      state="active" if key in {"tinker:battery",TECH_BATTERY_KEY} else "inactive",
                      charges=tech_battery_capacity(modifier) if key==TECH_BATTERY_KEY else 0,
                      minor=minor,advanced=advanced,configuration=configuration,bio_augment=bio_augment,energy_efficient=efficient)
        if occupied_limit((*self.devices(sphere),record),self.limits(sphere)) > self.limits(sphere).device_limit:
            raise ValueError("Device limit exceeded. Abandon an existing device first.")
        return self.repository.save_engineering_device(self.character_id,record)

    def apply_to_character(self,device_id,enabled):
        device=next((d for d in self.repository.list_engineering_devices(self.character_id) if d["id"]==device_id),None)
        if device and device["catalog_key"] in TECH_AUGMENT_SLOTS:
            if device["state"]=="abandoned" or (enabled and not self.available("Tech")):
                raise ValueError("Select an available Tech augment.")
            changes={"applied_to_character":bool(enabled),"augment_slot":TECH_AUGMENT_SLOTS[device["catalog_key"]] if enabled else ""}
            if not enabled:changes.update(state="inactive",effect_rounds=0)
            self.repository.save_engineering_device(self.character_id,{**device,**changes},device_id)
            return
        if not device or device["catalog_key"] not in {*AUGMENTOR_ABILITIES,TACTILE_FIELD_KEY}:
            raise ValueError("This device does not yet support automatic wearer effects.")
        if enabled and (device["state"]!="active" or device_condition(device)["destroyed"] or not self.available(device["sphere"])):
            raise ValueError("Activate a functioning device before applying it to this character.")
        self.repository.save_engineering_device(self.character_id,{**device,"applied_to_character":bool(enabled)},device_id)

    def start_jet_boosters(self,device_id,mode,slot):
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if not self.available("Tech") or not device or device["catalog_key"]!=JET_BOOSTERS_KEY or mode not in JET_MODES:
            raise ValueError("Select your Jet-boosters and an operating mode.")
        if device["effect_rounds"]>0:
            raise ValueError("Stop the current function before changing modes.")
        if mode=="slow_burn" and CharacterCalculationService(self.repository,self.character_id).encumbrance().load!="Light":
            raise ValueError("Slow burn requires a light load.")
        self.repository.spend_tech_device_charges(self.character_id,device_id,JET_MODES[mode][0],function_mode=mode,worn_slot=slot)

    def start_dermal_plating(self,device_id):
        self.start_timed_augment(device_id,DERMAL_PLATING_KEY)

    def start_timed_augment(self,device_id,key=None):
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if key is None and device:key=device["catalog_key"]
        if key not in TECH_TIMED_AUGMENT_MODES or not device or device["catalog_key"]!=key:
            raise ValueError("Select your supported timed augment.")
        if device["construction_kind"] in {"","graft_custom"} and not self.available("Tech"):
            raise ValueError("The Tech sphere is required for temporary gadgets.")
        if device["graft_slot"] and device_id in CharacterCalculationService(self.repository,self.character_id).graft_status()["blocked_ids"]:
            raise ValueError("This implanted graft lacks its supporting prowess or exceeds the current implantation limit.")
        ranks=device["level"] if device["construction_kind"] in {"graft_appliance","graft_contraption"} else CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get("craft",0)
        duration=tech_minute_augment_rounds(ranks,
            energy_efficient=bool(device["energy_efficient"]),augment_talents=2)
        if device["construction_kind"]:duration*=2
        self.repository.spend_tech_device_charges(self.character_id,device_id,1,function_mode=TECH_TIMED_AUGMENT_MODES[key],dermal_rounds=duration)

    def set_boots_clamped(self,device_id,clamped):
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if device and device["graft_slot"] and device_id in CharacterCalculationService(self.repository,self.character_id).graft_status()["blocked_ids"]:
            raise ValueError("The implanted Clamp Boots exceed the current implantation limit.")
        if not device or not clamp_boots_active(device,polymorphed=self.repository.engineering_polymorphed(self.character_id),retain_innate=self.repository.engineering_retains_innate(self.character_id)):
            raise ValueError("Wear powered, functioning Clamp Boots first.")
        self.repository.save_engineering_device(self.character_id,{**device,"function_mode":"clamped" if clamped else "climb"},device_id)

    def clamp_boots_resistance(self,device_id):
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if device and device["graft_slot"] and device_id in CharacterCalculationService(self.repository,self.character_id).graft_status()["blocked_ids"]:return 0
        if not device or device["function_mode"]!="clamped" or not clamp_boots_active(device,polymorphed=self.repository.engineering_polymorphed(self.character_id),retain_innate=self.repository.engineering_retains_innate(self.character_id)):
            return 0
        ranks=device["level"] if device["construction_kind"] in {"graft_appliance","graft_contraption"} else CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get("craft",0)
        return max(1,ranks//2)

    def stop_function(self,device_id,*,unequip=False):
        device=next((d for d in self.repository.list_engineering_devices(self.character_id) if d["id"]==device_id),None)
        if not device or device["catalog_key"]!=JET_BOOSTERS_KEY or device["state"]=="abandoned":
            raise ValueError("Select a supported timed device function.")
        self.repository.save_engineering_device(self.character_id,{**device,"state":"inactive","effect_rounds":0,
            "worn_slot":"" if unequip else device["worn_slot"],"applied_to_character":False if unequip else device["applied_to_character"]},device_id)

    def advance_time(self,rounds):
        self.repository.advance_engineering_time(self.character_id,rounds)

    def set_polymorphed(self,enabled,*,retain_innate=False):
        self.repository.set_engineering_polymorphed(self.character_id,enabled,retain_innate=retain_innate)

    def change_state(self, device_id, state):
        record = next((d for d in self.repository.list_engineering_devices(self.character_id) if d["id"]==device_id),None)
        if record is None:
            raise ValueError("Unknown device for this character.")
        if state not in {"active","inactive","depleted","abandoned"}:
            raise ValueError("Unknown device state.")
        if state=="active" and device_condition(record)["destroyed"]:
            raise ValueError("Repair this destroyed device before activating it.")
        if not self.available(record["sphere"]) and state != "abandoned":
            raise ValueError("The base sphere is no longer available.")
        if record["state"] in {"depleted","abandoned"} and state in {"active","inactive"}:
            raise ValueError("Maintain depleted devices; abandoned devices cannot be restored.")
        if record["catalog_key"]=="tinker:battery" and state=="inactive":
            raise ValueError("Tinker batteries cannot be deactivated.")
        if record["catalog_key"]==TECH_BATTERY_KEY and state=="abandoned":
            record={**record,"charges":0,"host_id":None}
        if record["catalog_key"] in {JET_BOOSTERS_KEY,TACTILE_FIELD_KEY,*TECH_AUGMENT_SLOTS} and state!="active":
            record={**record,"effect_rounds":0,"effect_battery_id":None}
            if state=="abandoned":record={**record,"worn_slot":"","augment_slot":"","applied_to_character":False}
        if state in {"abandoned","depleted"} and record["charges"]:
            raise ValueError("Return or spend stored charges before abandoning or depleting this device.")
        self.repository.save_engineering_device(self.character_id,{**record,"state":state},device_id)

    def maintain(self, sphere):
        if not self.available(sphere):
            raise ValueError("The base sphere is no longer available.")
        if sphere!="Tinker":
            raise ValueError("Tech batteries must be recharged, not maintained as Tinker gizmos.")
        for device in self.devices(sphere):
            if device["state"]!="abandoned" and (device["state"]=="depleted" or device["damage"]):
                state = "active" if is_battery(device) else "inactive" if device["state"]=="depleted" else device["state"]
                self.repository.save_engineering_device(self.character_id,{**device,"state":state,"damage":0},device["id"])

    def damage_device(self,device_id,amount,*,apply_hardness=True):
        device=next((d for d in self.repository.list_engineering_devices(self.character_id) if d["id"]==device_id),None)
        if not device or device["state"]=="abandoned" or int(amount)<=0:
            raise ValueError("Select a maintained device and a positive damage amount.")
        stats=self.statistics(device)
        amount=max(0,int(amount)-(stats["hardness"] if apply_hardness else 0))
        damage=min(stats["hp"],device["damage"]+amount)
        state="inactive" if damage>=stats["hp"] and device["state"]=="active" else device["state"]
        self.repository.save_engineering_device(self.character_id,{**device,"damage":damage,"state":state},device_id)

    def repair_tinker_device(self,device_id,modifier,*,has_tools=False):
        device=next((d for d in self.devices("Tinker") if d["id"]==device_id),None)
        if not self.available("Tinker") or not has_tools or not device or device["state"]=="abandoned":
            raise ValueError("Repair requires your Tinker gizmo and sufficient tools.")
        if not -100<=int(modifier)<=100:
            raise ValueError("Practitioner modifier is outside supported bounds.")
        ranks=CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get(self.skill_key,0)
        damage=max(0,device["damage"]-max(0,ranks+int(modifier)))
        state="active" if is_battery(device) and device["state"]=="inactive" and damage<self.statistics(device)["hp"] else device["state"]
        self.repository.save_engineering_device(self.character_id,{**device,"damage":damage,"state":state},device_id)

    def attach_battery(self,battery_id,host_id):
        devices={d["id"]:d for d in self.repository.list_engineering_devices(self.character_id)}
        battery=devices.get(battery_id)
        if not battery or not is_battery(battery) or not self.available(battery["sphere"]) or battery["state"]=="abandoned":
            raise ValueError("Select an available battery.")
        host=devices.get(host_id)
        if host_id is not None and (not host or host["state"] in {"depleted","abandoned"} or device_condition(host)["destroyed"]):
            raise ValueError("Select a functioning gizmo as the battery host.")
        self.repository.save_engineering_device(self.character_id,{**battery,"host_id":host_id},battery_id)

    def use_batteries(self,host_id,amount,*,personal=False,tactile_boost=False):
        if not self.available("Tinker"):
            raise ValueError("The Tinker sphere is required.")
        host=next((d for d in self.devices("Tinker") if d["id"]==host_id),None)
        if not host or host["state"]!="active" or device_condition(host)["destroyed"]:
            raise ValueError("Activate the host gizmo first.")
        level=CharacterCalculationService(self.repository,self.character_id).state.character_level
        batteries=[d for d in self.devices("Tinker") if d["host_id"]==host_id
                   and d["state"]=="active" and d["level"]>=host["level"]
                   and not device_condition(d)["destroyed"]
                   and (not personal or d["level"]>=level)]
        if amount<=0 or len(batteries)<amount:
            raise ValueError("Not enough usable attached batteries: battery level must reach the host level, and personal uses also require character level.")
        self.repository.deplete_engineering_batteries(self.character_id,host_id,[b["id"] for b in batteries[:amount]],tactile_boost=tactile_boost)

    def use_augmentor_reroll(self,device_id):
        device=next((d for d in self.devices("Tinker") if d["id"]==device_id),None)
        if not device or not physical_augmentor_bonus(device):
            raise ValueError("Wear an active augmentor before using its benefiting-check reroll.")
        self.use_batteries(device_id,1)

    def end_tactile_enhancement(self,device_id):
        device=next((d for d in self.devices("Tinker") if d["id"]==device_id),None)
        if not device or device["catalog_key"]!=TACTILE_FIELD_KEY or device["function_mode"]!="tactile_boost" or device["effect_rounds"]<=0:
            raise ValueError("Select a Tactile Field with an active enhancement.")
        self.repository.save_engineering_device(self.character_id,{**device,"effect_rounds":0,"effect_battery_id":None},device_id)

    def tactile_reroll_at_will(self):
        return (self.available("Tinker")
                and "Modification" in tinker_packages(self.records("Tinker"))
                and CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get(self.skill_key,0)>=5
                and any(t.catalog_key=="tinker:legendary-talent:advanced-field-projectors-gizmo-modification" for t in self.records("Tinker")))

    def use_tactile_reroll(self,device_id):
        device=next((d for d in self.devices("Tinker") if d["id"]==device_id),None)
        if (not device or device["catalog_key"]!=TACTILE_FIELD_KEY or device["state"]!="active"
                or not device["applied_to_character"] or device_condition(device)["destroyed"] or not self.available("Tinker")):
            raise ValueError("Wear an active, functioning Tactile Field first.")
        if device["effect_rounds"]>0 and device["function_mode"]=="tactile_boost":
            self.end_tactile_enhancement(device_id)
        elif not self.tactile_reroll_at_will():
            raise ValueError("Enhance the field with a battery first, or qualify for Advanced Field Projectors' at-will reroll.")
        else:
            return False  # No resource mutation or sheet refresh for an at-will roll.

    def pool(self):
        return next((t for t in self.repository.list_custom_trackers(self.character_id) if t.key=="engineering_tech_charges"),None)

    def charge_total(self):
        return int(self.pool().current_value if self.pool() else 0) + sum(d["charges"] for d in self.devices("Tech") if not is_battery(d) and d["construction_kind"] in {"","graft_custom"})

    def change_charges(self, amount):
        if not self.available("Tech"):
            raise ValueError("The Tech sphere is required.")
        pool = self.pool()
        current = int(pool.current_value) if pool else 0
        if current + amount < 0 or (amount > 0 and self.charge_total() + amount > self.limits("Tech").charge_maximum):
            raise ValueError("Not enough charges or charge maximum exceeded.")
        if pool is None:
            self.repository.add_custom_tracker(self.character_id,"engineering_tech_charges","Tech Charges","pool",
                manual_maximum=self.limits("Tech").charge_maximum,current_value=current+amount,
                recovery_event="none",recovery_operation="none")
        else:
            self.repository.update_custom_tracker(self.character_id,pool.id,pool.key,pool.name,pool.tracker_type,
                formula=pool.formula,manual_maximum=self.limits("Tech").charge_maximum,
                current_value=current+amount,temporary_value=pool.temporary_value,unit=pool.unit,
                description=pool.description,recovery_event="none",recovery_operation="none")

    def transfer_charges(self, device_id, amount, *, spend=False):
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if not device or device["state"] in {"abandoned","depleted"} or device_condition(device)["destroyed"]:
            raise ValueError("Select a functioning Tech device.")
        pool=self.pool()
        current=int(pool.current_value) if pool else 0
        if not spend and (device["charges"]+amount<0 or current-amount<0):
            raise ValueError("Not enough charges for this transfer.")
        if not self.available("Tech"):
            raise ValueError("The Tech sphere is required.")
        if not spend and pool is None:
            raise ValueError("Recharge the pool before loading devices.")
        if spend:
            self.repository.spend_tech_device_charges(self.character_id,device_id,amount)
        elif is_battery(device):
            if amount<0:
                raise ValueError("Battery charges cannot be returned to the pool.")
            received=min(amount,max(0,tech_battery_capacity(device["modifier"],from_pool=True)-device["charges"]))
            self.repository.transfer_engineering_charges(self.character_id,device_id,pool.id,amount,received_amount=received)
            return amount-received
        else:
            self.repository.transfer_engineering_charges(self.character_id,device_id,pool.id,amount)

    def recharge_tech_battery(self,device_id):
        device=next((d for d in self.devices("Tech") if d["id"]==device_id),None)
        if not self.available("Tech") or not device or device["catalog_key"]!=TECH_BATTERY_KEY or device["state"]=="abandoned" or device_condition(device)["destroyed"]:
            raise ValueError("Select a non-abandoned Tech battery.")
        self.repository.save_engineering_device(self.character_id,
            {**device,"charges":tech_battery_capacity(device["modifier"]),"state":"active"},device_id)

    def recharge(self):
        amount=max(0,min(self.limits("Tech").recharge_amount,self.limits("Tech").charge_maximum-self.charge_total()))
        if amount:
            self.change_charges(amount)
        return amount

    def install_resistance_routine(self,device_id,host_id):
        devices={d["id"]:d for d in self.devices("Tinker")}
        routine=devices.get(device_id)
        host=devices.get(host_id)
        if not self.available("Tinker") or not routine or routine["catalog_key"]!=RESISTANCE_ROUTINE_KEY or routine["state"]=="abandoned":
            raise ValueError("Select an available Resistance Routine.")
        if host_id is not None and (not host or host["catalog_key"]==RESISTANCE_ROUTINE_KEY or host["state"] in {"abandoned","depleted"} or device_condition(host)["destroyed"]):
            raise ValueError("Select a functioning host gizmo; nested routines are not yet supported.")
        state=routine["state"] if host and host["state"]=="active" else "inactive" if routine["state"]=="active" else routine["state"]
        self.repository.save_engineering_device(self.character_id,{**routine,"host_id":host_id,"state":state},device_id)

    def statistics(self,device):
        stats=device_statistics(device["sphere"],device["level"],device["modifier"])
        if device["state"]!="abandoned" and not device_condition(device)["destroyed"]:
            stats["save"]+=max((resistance_routine_bonus(d,device) for d in self.devices(device["sphere"]) if d["host_id"]==device["id"]),default=0)
        return stats

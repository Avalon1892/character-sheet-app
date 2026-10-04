"""Character-owned device lifecycle, separate from sheet presentation."""
from app.content import martial_entry
from app.engineering_rules import (engineering_limits, occupied_limit, device_statistics,
                                   is_battery, TECH_BATTERY_KEY, tech_battery_capacity,device_condition,
                                   PHYSICAL_AUGMENTOR_KEY,MENTAL_AUGMENTOR_KEY,LOAD_BEARER_KEY,AUGMENTOR_ABILITIES,JET_BOOSTERS_KEY,JET_MODES,tinker_packages)
from app.engineering_rules import physical_augmentor_bonus
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

    def create(self, sphere, key, modifier, *, minor=False, advanced=0,configuration=""):
        if not self.available(sphere):
            raise ValueError("This character does not currently have that base sphere.")
        entry = next((e for e in self.known_devices(sphere) if e["key"]==key),None)
        if entry is None:
            raise ValueError("Learn the device's talent first.")
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
        record = dict(sphere=sphere,catalog_key=key,name=entry["name"],level=ranks,modifier=modifier,
                      state="active" if key in {"tinker:battery",TECH_BATTERY_KEY} else "inactive",
                      charges=tech_battery_capacity(modifier) if key==TECH_BATTERY_KEY else 0,
                      minor=minor,advanced=advanced,configuration=configuration)
        if occupied_limit((*self.devices(sphere),record),self.limits(sphere)) > self.limits(sphere).device_limit:
            raise ValueError("Device limit exceeded. Abandon an existing device first.")
        return self.repository.save_engineering_device(self.character_id,record)

    def apply_to_character(self,device_id,enabled):
        device=next((d for d in self.repository.list_engineering_devices(self.character_id) if d["id"]==device_id),None)
        if device and device["catalog_key"]==DERMAL_PLATING_KEY:
            if device["state"]=="abandoned" or (enabled and not self.available("Tech")):
                raise ValueError("Select an available Dermal Plating augment.")
            changes={"applied_to_character":bool(enabled),"augment_slot":"Body" if enabled else ""}
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
        if not self.available("Tech"):
            raise ValueError("The Tech sphere is required.")
        self.repository.spend_tech_device_charges(self.character_id,device_id,1,function_mode="dermal")

    def stop_function(self,device_id,*,unequip=False):
        device=next((d for d in self.repository.list_engineering_devices(self.character_id) if d["id"]==device_id),None)
        if not device or device["catalog_key"]!=JET_BOOSTERS_KEY or device["state"]=="abandoned":
            raise ValueError("Select a supported timed device function.")
        self.repository.save_engineering_device(self.character_id,{**device,"state":"inactive","effect_rounds":0,
            "worn_slot":"" if unequip else device["worn_slot"],"applied_to_character":False if unequip else device["applied_to_character"]},device_id)

    def advance_time(self,rounds):
        self.repository.advance_engineering_time(self.character_id,rounds)

    def set_polymorphed(self,enabled):
        self.repository.set_engineering_polymorphed(self.character_id,enabled)

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
        if record["catalog_key"] in {JET_BOOSTERS_KEY,TACTILE_FIELD_KEY,DERMAL_PLATING_KEY} and state!="active":
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
        return int(self.pool().current_value if self.pool() else 0) + sum(d["charges"] for d in self.devices("Tech") if not is_battery(d))

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

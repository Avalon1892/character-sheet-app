"""Character-owned device lifecycle, separate from sheet presentation."""
from app.content import martial_entry
from app.engineering_rules import engineering_limits, occupied_limit, device_statistics
from app.services.character_calculations import CharacterCalculationService
from app.exploitant_rules import effective_martial_talents


def device_talent(entry):
    name = entry.get("name", "").casefold()
    return any(tag in name for tag in ("(gadget", ", gadget", "(gizmo", ", gizmo"))


class EngineeringService:
    def __init__(self, repository, character_id, skill_key="craft"):
        self.repository, self.character_id, self.skill_key = repository, character_id, skill_key

    def records(self, sphere):
        return tuple(t for t in effective_martial_talents(self.repository,self.character_id)
                     if t.enabled and t.sphere == sphere)

    def known_devices(self, sphere):
        entries = {}
        for talent in self.records(sphere):
            entry = martial_entry(talent.catalog_key)
            if entry and device_talent(entry):
                entries[entry["key"]] = entry
        if sphere == "Tinker" and self.available(sphere):
            entries["tinker:battery"] = {"key":"tinker:battery", "name":"Battery (gizmo)",
                                        "description":"Depleting this battery powers a battery-use ability. A depleted battery still counts against your gizmo limit."}
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

    def create(self, sphere, key, modifier, *, minor=False, advanced=0):
        if not self.available(sphere):
            raise ValueError("This character does not currently have that base sphere.")
        entry = next((e for e in self.known_devices(sphere) if e["key"]==key),None)
        if entry is None:
            raise ValueError("Learn the device's talent first.")
        if sphere == "Tech" and entry["name"].startswith("Battery ("):
            raise ValueError("Tech batteries have special charge-storage rules; their construction is not automated yet.")
        if sphere == "Tech" and (minor or advanced):
            raise ValueError("Minor and advanced gizmo rules belong to Tinker, not Tech.")
        ranks = CharacterCalculationService(self.repository,self.character_id).effective_skill_ranks().get(self.skill_key,0)
        record = dict(sphere=sphere,catalog_key=key,name=entry["name"],level=ranks,modifier=modifier,
                      state="active" if key=="tinker:battery" else "inactive",charges=0,minor=minor,advanced=advanced)
        if occupied_limit((*self.devices(sphere),record),self.limits(sphere)) > self.limits(sphere).device_limit:
            raise ValueError("Device limit exceeded. Abandon an existing device first.")
        return self.repository.save_engineering_device(self.character_id,record)

    def change_state(self, device_id, state):
        record = next((d for d in self.repository.list_engineering_devices(self.character_id) if d["id"]==device_id),None)
        if record is None:
            raise ValueError("Unknown device for this character.")
        if state not in {"active","inactive","depleted","abandoned"}:
            raise ValueError("Unknown device state.")
        if not self.available(record["sphere"]) and state != "abandoned":
            raise ValueError("The base sphere is no longer available.")
        if record["state"] in {"depleted","abandoned"} and state in {"active","inactive"}:
            raise ValueError("Maintain depleted devices; abandoned devices cannot be restored.")
        if record["catalog_key"]=="tinker:battery" and state=="inactive":
            raise ValueError("Tinker batteries cannot be deactivated.")
        if state in {"abandoned","depleted"} and record["charges"]:
            raise ValueError("Return or spend stored charges before abandoning or depleting this device.")
        self.repository.save_engineering_device(self.character_id,{**record,"state":state},device_id)

    def maintain(self, sphere):
        if not self.available(sphere):
            raise ValueError("The base sphere is no longer available.")
        for device in self.devices(sphere):
            if device["state"]=="depleted":
                state = "active" if device["catalog_key"]=="tinker:battery" else "inactive"
                self.repository.save_engineering_device(self.character_id,{**device,"state":state},device["id"])

    def attach_battery(self,battery_id,host_id):
        devices={d["id"]:d for d in self.devices("Tinker")}
        battery=devices.get(battery_id)
        if not self.available("Tinker") or not battery or battery["catalog_key"]!="tinker:battery" or battery["state"]=="abandoned":
            raise ValueError("Select a maintained Tinker battery.")
        host=devices.get(host_id)
        if host_id is not None and (not host or host["state"] in {"depleted","abandoned"}):
            raise ValueError("Select a functioning gizmo as the battery host.")
        self.repository.save_engineering_device(self.character_id,{**battery,"host_id":host_id},battery_id)

    def use_batteries(self,host_id,amount,*,personal=False):
        if not self.available("Tinker"):
            raise ValueError("The Tinker sphere is required.")
        host=next((d for d in self.devices("Tinker") if d["id"]==host_id),None)
        if not host or host["state"]!="active":
            raise ValueError("Activate the host gizmo first.")
        level=CharacterCalculationService(self.repository,self.character_id).state.character_level
        batteries=[d for d in self.devices("Tinker") if d["host_id"]==host_id
                   and d["state"]=="active" and (not personal or d["level"]>=level)]
        if amount<=0 or len(batteries)<amount:
            raise ValueError("Not enough usable attached batteries (personal uses require battery level at least character level).")
        self.repository.deplete_engineering_batteries(self.character_id,host_id,[b["id"] for b in batteries[:amount]])

    def pool(self):
        return next((t for t in self.repository.list_custom_trackers(self.character_id) if t.key=="engineering_tech_charges"),None)

    def charge_total(self):
        return int(self.pool().current_value if self.pool() else 0) + sum(d["charges"] for d in self.devices("Tech"))

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
        if not device or device["state"] in {"abandoned","depleted"}:
            raise ValueError("Select a functioning Tech device.")
        pool=self.pool()
        current=int(pool.current_value) if pool else 0
        if spend:
            if amount<=0 or device["charges"]<amount:
                raise ValueError("Not enough charges stored in this device.")
        elif device["charges"]+amount<0 or current-amount<0:
            raise ValueError("Not enough charges for this transfer.")
        if not self.available("Tech"):
            raise ValueError("The Tech sphere is required.")
        if not spend and pool is None:
            raise ValueError("Recharge the pool before loading devices.")
        if spend:
            self.repository.save_engineering_device(self.character_id,
                {**device,"charges":device["charges"]-amount},device_id)
        else:
            self.repository.transfer_engineering_charges(self.character_id,device_id,pool.id,amount)

    def recharge(self):
        amount=max(0,min(self.limits("Tech").recharge_amount,self.limits("Tech").charge_maximum-self.charge_total()))
        if amount:
            self.change_charges(amount)
        return amount

    @staticmethod
    def statistics(device):
        return device_statistics(device["sphere"],device["level"],device["modifier"])

"""Core Tech/Tinker device rules; catalog prose is never executed."""
from dataclasses import dataclass
from math import ceil

TINKER_PACKAGES = ("Augmentation","Computation","Modification","Transmission","Transportation")


def tinker_packages(talents):
    result=set()
    for talent in talents:
        if not talent.enabled or talent.sphere!="Tinker":
            continue
        if talent.catalog_category.casefold()=="base sphere" or talent.catalog_key=="tinker:base" or talent.catalog_key=="tinker:talent:expanded-tinkering":
            result.update(value.strip() for value in talent.choice.split("/") if value.strip() in TINKER_PACKAGES)
    return frozenset(result)


def validate_tinker_package_choice(choice,talents):
    choices=tuple(value.strip() for value in choice.split("/"))
    if len(choices)!=2 or len(set(choices))!=2 or any(value not in TINKER_PACKAGES for value in choices):
        raise ValueError("Choose two different Tinker packages.")
    if set(choices)&tinker_packages(talents):
        raise ValueError("Choose Tinker packages not already possessed.")

TECH_BATTERY_KEY = "tech:gadget-talent:battery-gadget"
TINKER_BATTERY_KEY = "tinker:battery"
PHYSICAL_AUGMENTOR_KEY = "tinker:device:physical-augmentor"
MENTAL_AUGMENTOR_KEY = "tinker:device:mental-augmentor"
LOAD_BEARER_KEY = "tinker:device:load-bearer"
TACTILE_FIELD_KEY = "tinker:device:tactile-field"
RESISTANCE_ROUTINE_KEY = "tinker:device:resistance-routine"
DERMAL_PLATING_KEY = "tech:gadget-talent:dermal-plating-augment-drone-gadget"
CLAMP_BOOTS_KEY = "tech:gadget-talent:clamp-boots-augment-drone-gadget"
EXO_MUSCLES_KEY = "tech:gadget-talent:exo-skeletal-muscles-augment-drone-gadget"
SYNAPTIC_MAXIMIZER_KEY = "tech:gadget-talent:synaptic-reaction-maximizer-augment-drone-gadget"
TECH_ABILITY_AUGMENTS = {EXO_MUSCLES_KEY:"strength",SYNAPTIC_MAXIMIZER_KEY:"dexterity"}
TECH_AUGMENT_SLOTS = {DERMAL_PLATING_KEY:"Body",CLAMP_BOOTS_KEY:"Legs",EXO_MUSCLES_KEY:"Body",SYNAPTIC_MAXIMIZER_KEY:"Brain"}
TECH_TIMED_AUGMENT_MODES = {DERMAL_PLATING_KEY:"dermal",CLAMP_BOOTS_KEY:"climb",**TECH_ABILITY_AUGMENTS}


def tech_minute_augment_rounds(ranks, *, energy_efficient=False, augment_talents=0):
    """Duration for augment functions whose base cost is one charge per minute."""
    if not energy_efficient or ranks < 5 or augment_talents < 2:
        return 10
    return 300 if ranks >= 15 else 100 if ranks >= 10 else 50


def graft_implantation_status(constitution, intelligence, *, graft_values=(), cybertech_value=0):
    """Assess the shared implant limit; None represents a genuinely absent score.

    Scores must include applicable implantation-limit adjustments before calling.
    An overloaded implant remains installed; this assessment never removes records.
    """
    values=tuple(graft_values)
    if any(type(value) is not int or value < 0 for value in (*values,cybertech_value)):
        raise ValueError("Implantation values must be nonnegative integers.")
    scores=tuple(score for score in (constitution,intelligence) if score is not None)
    if any(type(score) is not int or score < 0 for score in scores):
        raise ValueError("Implantation scores must be nonnegative integers or absent.")
    capacity=min(scores) if scores else 0
    total=sum(values)+cybertech_value
    overloaded=bool(values) and total>capacity
    return {"capacity":capacity,"total":total,"remaining":max(0,capacity-total),
            "has_controlling_score":bool(scores),"overloaded":overloaded,
            "save_penalty":-4 if overloaded else 0}


def tech_graft_quote(kind,ranks,complexity=1,*,versatile_crafter=False):
    """Expanded Tech construction, distinct from free temporary gadgets."""
    if kind not in {"appliance","contraption"}:
        raise ValueError("Choose appliance or contraption construction.")
    if any(type(value) is not int or not 1<=value<=999 for value in (ranks,complexity)):
        raise ValueError("Craft ranks and complexity must be positive integers within supported bounds.")
    if complexity>ranks and not versatile_crafter:
        raise ValueError("Item Craft ranks must cover complexity unless Versatile Crafter applies.")
    cost=(400 if kind=="appliance" else 200)*ranks*complexity
    hours=max(8,4*ceil(2*cost/1000*2))
    days=ceil(hours/8)
    return {"cost_gp":cost,"base_price_gp":2*cost,"craft_dc":10+ranks,
            "days":days,"hours":hours,"charge_capacity":max(1,ranks//2),
            "implantation_value":2,"installation_hours":2,
            "charged_duration_multiplier":2,"activation_check_required_for_other_users":kind=="contraption"}


def tech_augment_installed(device,slot):
    return bool(device.get("graft_slot")==slot or (device.get("applied_to_character") and device.get("augment_slot")==slot))


def tech_augment_suppressed(device,polymorphed,*,retain_innate=False):
    return bool(polymorphed and device["sphere"]=="Tech"
                and (device.get("graft_slot") or (device.get("augment_slot") and device.get("applied_to_character")))
                and not device.get("bio_augment") and not (device.get("graft_slot") and retain_innate))


def clamp_boots_active(device, *, polymorphed=False,retain_innate=False):
    return bool(device["sphere"]=="Tech" and device["catalog_key"]==CLAMP_BOOTS_KEY
        and device["state"]=="active" and tech_augment_installed(device,"Legs") and device.get("effect_rounds",0)>0
        and device.get("function_mode") in {"climb","clamped"}
        and not device_condition(device)["destroyed"] and not tech_augment_suppressed(device,polymorphed,retain_innate=retain_innate))


def dermal_plating_bonus(device,ranks,*,polymorphed=False,retain_innate=False):
    if (device["sphere"]!="Tech" or device["catalog_key"]!=DERMAL_PLATING_KEY
            or device["state"]!="active" or not tech_augment_installed(device,"Body") or device.get("effect_rounds",0)<=0
            or device_condition(device)["destroyed"] or tech_augment_suppressed(device,polymorphed,retain_innate=retain_innate)):
        return 0
    return 2+max(0,int(device["level"] if device.get("construction_kind") in {"graft_appliance","graft_contraption"} else ranks))//5


def tech_ability_augment_bonus(device,ranks,*,polymorphed=False,retain_innate=False):
    ability=TECH_ABILITY_AUGMENTS.get(device["catalog_key"])
    if (not ability or device["sphere"]!="Tech" or device["state"]!="active"
            or not tech_augment_installed(device,TECH_AUGMENT_SLOTS[device["catalog_key"]])
            or device.get("effect_rounds",0)<=0 or device.get("function_mode")!=ability
            or device_condition(device)["destroyed"] or tech_augment_suppressed(device,polymorphed,retain_innate=retain_innate)):
        return None
    ranks=device["level"] if device.get("construction_kind") in {"graft_appliance","graft_contraption"} else ranks
    return ability,2+2*(max(0,int(ranks))//7)


def resistance_routine_bonus(device,host):
    if (device["sphere"]!="Tinker" or device["catalog_key"]!=RESISTANCE_ROUTINE_KEY
            or device["state"]!="active" or device.get("host_id") is None
            or host["id"]!=device["host_id"] or host["state"]!="active"
            or device_condition(host)["destroyed"]
            or device_condition(device)["destroyed"]):
        return 0
    return 1+device_condition(device)["effective_level"]//4


AUGMENTOR_ABILITIES = {
    PHYSICAL_AUGMENTOR_KEY: ("strength","dexterity","constitution"),
    MENTAL_AUGMENTOR_KEY: ("intelligence","wisdom","charisma"),
    LOAD_BEARER_KEY: ("strength",),
}
JET_BOOSTERS_KEY = "tech:gadget-talent:jet-boosters-drone-gadget"
# cost, paid duration in rounds, speed, flight maneuverability
JET_MODES = {"normal":(1,1,60,"Poor"),"slow_burn":(1,2400,30,"Perfect"),
             "overdrive":(2,1,90,"Clumsy")}


def jet_movement(device, *, light_load=True):
    if (device["catalog_key"]!=JET_BOOSTERS_KEY or device["state"]!="active"
            or not device.get("applied_to_character") or device.get("effect_rounds",0)<=0
            or device_condition(device)["destroyed"]):
        return None
    mode=device.get("function_mode","")
    if mode not in JET_MODES or device["configuration"] not in {"flight","aquatic"}:
        return None
    if mode=="slow_burn" and not light_load:
        return None
    _,_,speed,maneuverability=JET_MODES[mode]
    return ("swim_speed" if device["configuration"]=="aquatic" else "fly_speed",speed,maneuverability)


def is_battery(device):
    return (device["sphere"],device["catalog_key"]) in {
        ("Tech",TECH_BATTERY_KEY),("Tinker",TINKER_BATTERY_KEY)}


def tech_battery_capacity(modifier, *, from_pool=False):
    # Creation/full recharge explicitly has minimum 1; pool charging uses the
    # separate creator-modifier cap in the Charging Batteries paragraph.
    return max(0 if from_pool else 1, int(modifier))


@dataclass(frozen=True)
class EngineeringLimits:
    device_limit: int
    batch_size: int
    minor_group_size: int = 1
    charge_maximum: int = 0
    recharge_amount: int = 0


def engineering_limits(sphere, ranks, talent_count, *, gadget_count=0, extra=0):
    ranks, talent_count = max(0, int(ranks)), max(0, int(talent_count))
    if sphere == "Tech":
        return EngineeringLimits(max(1, ranks // 2) + gadget_count + 2 * extra,
                                 1, charge_maximum=max(4, ranks + talent_count) + extra,
                                 recharge_amount=1 + ranks // 2)
    if sphere == "Tinker":
        return EngineeringLimits(ranks + talent_count + 2 * extra,
                                 1 + ranks // 4 + extra, 2 + ranks // 2 + extra)
    raise ValueError("Unknown engineering sphere.")


def device_statistics(sphere, level, modifier):
    level = max(0, int(level))
    if sphere == "Tech":
        return {"hp": 5 + 5 * (level // 2), "hardness": level,
                "save": level // 2 + modifier, "dc": 10 + level // 2 + modifier}
    if sphere == "Tinker":
        return {"hp": 3 * level, "hardness": 5 + level // 2,
                "save": level // 2 + modifier, "dc": 10 + level // 2 + max(0, modifier)}
    raise ValueError("Unknown engineering sphere.")


def device_condition(device):
    stats=device_statistics(device["sphere"],device["level"],device["modifier"])
    damage=max(0,int(device.get("damage",0)))
    current=max(0,stats["hp"]-damage)
    broken=current>0 and damage*2>stats["hp"]
    effective=max(1,device["level"]-2) if broken and device["sphere"]=="Tinker" else device["level"]
    return {"current_hp":current,"maximum_hp":stats["hp"],"broken":broken,
            "destroyed":current==0,"effective_level":effective}


def physical_augmentor_bonus(device):
    if (device["catalog_key"] not in AUGMENTOR_ABILITIES or device["sphere"]!="Tinker"
            or device.get("configuration") not in AUGMENTOR_ABILITIES[device["catalog_key"]]
            or device["state"]!="active" or not device.get("applied_to_character")
            or device_condition(device)["destroyed"]):
        return 0
    return 2+device_condition(device)["effective_level"]//4


def tactile_field_bonus(device):
    if (device["catalog_key"]!=TACTILE_FIELD_KEY or device["sphere"]!="Tinker"
            or device["state"]!="active" or not device.get("applied_to_character")
            or device_condition(device)["destroyed"]):
        return 0
    level=device_condition(device)["effective_level"]
    return 2+level//10+(level//4 if device.get("function_mode")=="tactile_boost" and device.get("effect_rounds",0)>0 and device.get("effect_battery_id") is not None else 0)


def occupied_limit(devices, limits):
    normal, minor = 0, 0
    for device in devices:
        if device["state"] == "abandoned" or device.get("construction_kind") in {"graft_appliance","graft_contraption","graft_custom"}:
            continue
        if device["sphere"] == "Tinker" and device["minor"] and not device["advanced"]:
            minor += 1
        else:
            normal += (max(1, device["advanced"]) if device["minor"] else 1 + device["advanced"])
    return normal + ceil(minor / limits.minor_group_size)

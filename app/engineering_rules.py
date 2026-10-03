"""Core Tech/Tinker device rules; catalog prose is never executed."""
from dataclasses import dataclass
from math import ceil

TECH_BATTERY_KEY = "tech:gadget-talent:battery-gadget"
TINKER_BATTERY_KEY = "tinker:battery"
PHYSICAL_AUGMENTOR_KEY = "tinker:device:physical-augmentor"
MENTAL_AUGMENTOR_KEY = "tinker:device:mental-augmentor"
AUGMENTOR_ABILITIES = {
    PHYSICAL_AUGMENTOR_KEY: ("strength","dexterity","constitution"),
    MENTAL_AUGMENTOR_KEY: ("intelligence","wisdom","charisma"),
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


def occupied_limit(devices, limits):
    normal, minor = 0, 0
    for device in devices:
        if device["state"] == "abandoned":
            continue
        if device["sphere"] == "Tinker" and device["minor"] and not device["advanced"]:
            minor += 1
        else:
            normal += (max(1, device["advanced"]) if device["minor"] else 1 + device["advanced"])
    return normal + ceil(minor / limits.minor_group_size)

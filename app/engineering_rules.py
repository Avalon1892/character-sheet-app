"""Core Tech/Tinker device rules; catalog prose is never executed."""
from dataclasses import dataclass
from math import ceil

TECH_BATTERY_KEY = "tech:gadget-talent:battery-gadget"
TINKER_BATTERY_KEY = "tinker:battery"


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

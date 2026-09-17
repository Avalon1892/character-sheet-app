from __future__ import annotations

from dataclasses import dataclass


PRODIGY_SOURCE_URL = "https://spheresofpower.wikidot.com/prodigy"


@dataclass(frozen=True, slots=True)
class ProdigyOption:
    name: str
    option_type: str
    sphere: str = ""
    minimum_links: int = 0
    action: str = ""
    description: str = ""
    requires_package: str = ""
    requires_talent: str = ""

    def database_tuple(self) -> tuple[str, str, str, int, str, str]:
        return (
            self.name,
            self.option_type,
            self.sphere,
            self.minimum_links,
            self.action,
            self.description,
        )


@dataclass(frozen=True, slots=True)
class ProdigyImbue:
    key: str
    sphere: str
    name: str
    description: str
    metric: str = ""
    requires_package: str = ""


UNIVERSAL_PRODIGY_OPTIONS = (
    ProdigyOption("Attack", "Opener", action="Standard action or longer", description="Deal damage to one or more hostile creatures with an attack action, a standard- or full-round charge, a sphere ability whose casting time is at least a standard action, or another ability whose activation time is at least a standard action."),
    ProdigyOption("Critical Hit", "Opener", action="On confirmation", description="Confirm a critical hit against a hostile creature."),
    ProdigyOption("Defeat", "Opener", action="On defeat", description="Reduce a hostile creature whose CR is at least half your character level to 0 or fewer hit points."),
    ProdigyOption("Heal", "Opener", action="Standard action or longer", description="With an ability requiring at least a standard action, restore hit points to an ally or remove ability damage, ability drain, or the blinded, dazed, frightened, nauseated, shaken, sickened, or stunned condition."),
    ProdigyOption("Maneuver", "Opener", action="On success", description="Succeed on a combat maneuver check against a hostile creature."),
    ProdigyOption("Magic Save", "Opener", action="Standard action or longer", description="A hostile creature fails a save against a sphere effect whose casting time is at least a standard action. This opener applies only to the first hostile creature that fails a save against that casting."),
    ProdigyOption("Reflection", "Opener", action="On success", description="Successfully use the reflect spell class feature."),
    ProdigyOption("Abandon Focus", "Link", action="Free action", description="Expend martial focus."),
    ProdigyOption("Adopt Form", "Link", action="Part of activating a stance", description="Expend martial focus while activating a stance talent."),
    ProdigyOption("Close the Gap", "Link", action="Move action", description="Move up to your speed and end with a hostile creature threatened."),
    ProdigyOption("Counting Coup", "Link", action="Swift action", description="Make a successful weapon touch attack that deals no damage."),
    ProdigyOption("Disengage", "Link", action="Move action", description="Move up to half your speed without provoking for leaving your starting square; you may sheathe one weapon and draw another."),
    ProdigyOption("Preparation", "Link", action="Attack of opportunity", description="When an attack of opportunity is triggered, expend it without making the attack to complete this link."),
    ProdigyOption("Save", "Link", action="On success", description="Succeed on a saving throw against a non-harmless effect from a hostile creature."),
    ProdigyOption("Swift Heal", "Link", action="Immediate action or longer", description="With an ability requiring at least an immediate action, restore hit points to an ally or remove ability damage, ability drain, or the blinded, dazed, frightened, nauseated, shaken, sickened, or stunned condition."),
    ProdigyOption("Steel Mind", "Link", action="On concentration check", description="Succeed on a concentration check to maintain a sphere effect after taking damage."),
    ProdigyOption("Adroit Momentum", "Finisher", action="Part of a skill check", description="Gain a competence bonus equal to the sequence links on the check."),
    ProdigyOption("Arcane Apocalypse", "Finisher", minimum_links=5, action="Move action", description="At 5 links, cast one sphere effect as a move action. At 7 links, cast one as a swift action. At 9 links, cast up to three sphere effects: one each as a standard, move, and swift action. Each effect must normally take no longer than a standard action."),
    ProdigyOption("Certain Strike", "Finisher", minimum_links=3, action="Swift action", description="Resolve your next attack before your next turn as a touch attack."),
    ProdigyOption("Doombringer", "Finisher", minimum_links=3, action="Swift action", description="At 3 links, make one attack as a swift action. At 5 links, make an attack action as a move action; at 7 links, make it as a swift action. At 9 links, make up to three attack actions: one each as a standard, move, and swift action. Each attack action must normally take no longer than a standard action."),
    ProdigyOption("Executioner", "Finisher", minimum_links=5, action="Move action", description="At 5 links, spend a move action to make your next attack before the end of this turn automatically threaten a critical hit. At 7 or more links, use a swift action instead. A miss wastes the effect, and it cannot combine with an effect that automatically confirms critical threats."),
    ProdigyOption("Focus", "Finisher", minimum_links=3, action="Free action", description="Regain martial focus."),
    ProdigyOption("Ironhide", "Finisher", action="Immediate action", description="Gain temporary hit points equal to character level for one round per link."),
    ProdigyOption("Penetrating Magic", "Finisher", action="Part of casting", description="Add the sequence length to MSB checks made to overcome spell resistance."),
    ProdigyOption("Prodigy's Reflexes", "Finisher", minimum_links=3, action="Immediate action", description="At 3 links, when targeted by an attack or required to make a Reflex save, spend an immediate action and use an Acrobatics check result in place of AC or the save—even if the result is worse. At 5 or more links, use this as a free action, even outside your turn."),
    ProdigyOption("Resilience", "Finisher", minimum_links=5, action="Immediate action", description="After failing a saving throw with a sequence of at least 5 links, spend an immediate action to reroll it. Gain a +1 competence bonus on the reroll for every link beyond 5."),
)


SPHERE_PRODIGY_OPTIONS = (
    ProdigyOption("All Coming Together", "Opener", "Any Skill Sphere", action="Reveal a plan", description="Reveal a plan."),
    ProdigyOption("Revised Strategy", "Opener", "Any Skill Sphere", action="Move action or longer", description="Change your approach; a swift-action approach may instead be begun as a move action."),
    ProdigyOption("Upper Hand", "Opener", "Any Skill Sphere", action="Part of an action", description="Outwit a target, no more than once per round."),
    ProdigyOption("Carpet Bombing", "Finisher", "Alchemy", action="Standard action", description="Throw one formula or poison dose per link; a creature can be affected only once."),
    ProdigyOption("Opening Toss", "Opener", "Alchemy", action="Standard action", description="Deal damage, cause a failed save, or grant a benefit with a formula, or cause a failed save with thrown poison."),
    ProdigyOption("Poisoner", "Link", "Alchemy", action="Apply poison", description="Apply a dose of poison to a weapon."),
    ProdigyOption("Build it Up", "Opener", "Artifice", action="Cobbled creation", description="Create a trinket using cobbled creation."),
    ProdigyOption("Hard Target", "Link", "Athletics", action="During movement", description="Avoid a movement-provoked attack of opportunity or successfully tumble through a threatened square."),
    ProdigyOption("Flurry", "Finisher", "Barrage", action="Standard action", description="Make one ranged attack per link at full BAB; no target receives more than half the attacks."),
    ProdigyOption("Liquid Preparation", "Opener", "Barroom", action="Standard action or longer", description="Draw if needed and drink alcohol, an elixir, extract, formula, or potion."),
    ProdigyOption("Quaff", "Link", "Barroom", action="Move action or longer", description="Draw if needed and drink alcohol, an elixir, extract, formula, or potion."),
    ProdigyOption("Stumbling Flow", "Link", "Barroom", action="Free action", description="While drunk, fall prone."),
    ProdigyOption("Defend Mount", "Link", "Beastmastery", action="Defensive rider", description="Negate an attack from a hostile creature using defensive rider."),
    ProdigyOption("Leading the Pack", "Opener", "Beastmastery", action="Move action or longer", description="Handle or push an animal ally."),
    ProdigyOption("Pack Attack", "Finisher", "Beastmastery", action="Standard action", description="Grant attack actions to animal allies in close range equal to half the sequence length."),
    ProdigyOption("Whirlwind", "Finisher", "Berserker", action="Standard action", description="Make one melee or thrown attack per link at full BAB; no target receives more than half the attacks."),
    ProdigyOption("Fighting Words", "Opener", "Bluster", action="Use a quip", description="Successfully affect a creature with a quip."),
    ProdigyOption("Let It Loose", "Link", "Body Control", action="Abandon approach", description="Abandon a meditate approach that has lasted at least one round."),
    ProdigyOption("Ready for Action", "Opener", "Boxing", action="Ready counter punch", description="Ready a counter punch; its damage does not grant another link."),
    ProdigyOption("Clear the Field", "Finisher", "Brute", action="Standard or full-round action", description="Bull rush or reposition one creature per link; the full-round version includes half-speed movement."),
    ProdigyOption("Shoving Combo", "Link", "Brute", action="Use shove", description="Deal damage with the shove ability."),
    ProdigyOption("Shoving Open", "Opener", "Brute", action="Standard action", description="Deal damage with the shove ability."),
    ProdigyOption("In This Together", "Opener", "Communication", action="Form rapport", description="Form a rapport with a creature."),
    ProdigyOption("Follow-through", "Link", "Dual Wielding", action="Swift action", description="After damaging with an off-hand attack, make an off-hand attack against another creature; damage completes the link."),
    ProdigyOption("Surface Cut", "Opener", "Duelist", action="Move action", description="Make a weapon touch attack that deals only Duelist sphere bleed damage."),
    ProdigyOption("Feinting Set-up", "Link", "Fencing", action="Move action or longer", description="Succeed on a feint."),
    ProdigyOption("Braggadocio", "Link", "Gladiator", action="Perform boast", description="Perform a boast."),
    ProdigyOption("Roar", "Opener", "Gladiator", action="Standard action or longer", description="Use strike fear."),
    ProdigyOption("Scare", "Link", "Gladiator", action="Demoralize", description="Succeed on a demoralization check."),
    ProdigyOption("Taunt", "Opener", "Gladiator", action="Standard action", description="Perform a boast without its usual trigger."),
    ProdigyOption("Deliberate Challenge", "Opener", "Guardian", action="Move or standard action", description="Use challenge."),
    ProdigyOption("Endurance", "Link", "Guardian", action="Fill delayed damage pool", description="Fill the delayed damage pool to maximum capacity."),
    ProdigyOption("Lockdown", "Opener", "Guardian", action="Use patrol", description="Use patrol."),
    ProdigyOption("Bottoms Up", "Opener", "Herbalism", action="Consume item", description="Consume an herb or concoction."),
    ProdigyOption("Gremlin", "Opener", "Infiltration", action="Fast sabotage", description="Successfully use fast sabotage."),
    ProdigyOption("Appraise Threat", "Opener", "Investigation", action="Standard action or longer", description="Use analyze."),
    ProdigyOption("Impale", "Link", "Lancer", action="Impale", description="Successfully impale a creature."),
    ProdigyOption("Directing the Charge", "Opener", "Leadership", action="Joint action", description="Your cohort damages or maneuvers a hostile creature as part of a joint action."),
    ProdigyOption("Press the Attack", "Finisher", "Leadership", action="Move action", description="Grant a cohort in close range an attack action with a morale bonus equal to the sequence length."),
    ProdigyOption("Pathfinder", "Opener", "Navigation", action="Standard action or longer", description="Use pathing."),
    ProdigyOption("Focus", "Link", "Open Hand", action="Move action", description="Pause to focus, or use Focusing Breath if possessed."),
    ProdigyOption("Hit the Floor", "Finisher", "Open Hand", action="Standard or full-round action", description="Make one trip per link; the full-round version includes half-speed movement."),
    ProdigyOption("Overture", "Opener", "Performance", action="Move action or longer", description="Start an act, dance, instrumental, or lyric."),
    ProdigyOption("Payoff", "Link", "Performance", action="Expend or complete performance", description="Expend a lyric affecting you, complete a scene, or complete a finale not begun this turn."),
    ProdigyOption("Rising Excitement", "Link", "Performance", action="Move action or longer", description="Maintain a dance or instrumental."),
    ProdigyOption("Mark", "Link", "Scoundrel", action="Marked target", description="Successfully use marked target against a hostile creature."),
    ProdigyOption("Kleptomaniac", "Finisher", "Scoundrel", action="Standard or full-round action", description="Make one steal maneuver per link; the full-round version includes half-speed movement."),
    ProdigyOption("Battlefield Assessment", "Opener", "Scout", action="Standard action", description="Scout up to your casting ability modifier in creatures, gaining a bonus for unused targets."),
    ProdigyOption("Perceptive", "Link", "Scout", action="Swift action or longer", description="Successfully scout a hostile creature."),
    ProdigyOption("Vanish", "Link", "Scout", action="Hide in combat", description="Successfully hide during combat; sniping's hide check is separate from its attack."),
    ProdigyOption("Defender", "Link", "Shield", action="Active defense", description="A creature misses a target benefiting from your active defense."),
    ProdigyOption("Deliberate Load", "Link", "Sniper", action="Swift or move action", description="Reload a weapon."),
    ProdigyOption("Intentional Mishap", "Opener", "Spellhacking", action="Coax mishap", description="Coax a mishap from a magic item."),
    ProdigyOption("Spell Tweaker", "Opener", "Spellhacking", action="Hack magic", description="Successfully use hack magic."),
    ProdigyOption("Pose Hypothesis", "Opener", "Study", action="Swift, move, or standard action", description="Begin a theory."),
    ProdigyOption("Supported Conclusion", "Link", "Study", action="Spend notions", description="Spend at least three notions in one round."),
    ProdigyOption("Masked Tactics", "Opener", "Subterfuge", action="Standard or full-round action", description="Use fast disguise."),
    ProdigyOption("Dig In", "Opener", "Survivalism", action="Standard or full-round action", description="Use dredge."),
    ProdigyOption("Gadget Activation", "Opener", "Tech", action="Standard action or longer", description="Activate a gadget."),
    ProdigyOption("Mass Self-Destruct", "Finisher", "Tech", action="Standard action", description="Self-destruct one crafted device per link within medium range; each creature is affected only once."),
    ProdigyOption("Recharge Tech", "Link", "Tech", action="Swift action", description="Attach a battery gadget to a crafted device; requires Battery.", requires_talent="Battery"),
    ProdigyOption("Gizmo Activation", "Opener", "Tinker", action="Standard action or longer", description="Activate a gizmo or a gizmo ability, optionally slowing a faster ability to a standard action."),
    ProdigyOption("Recharge Gizmo", "Link", "Tinker", action="Swift, move, or standard action", description="Attach a battery to a crafted gizmo."),
    ProdigyOption("Turbocharge", "Finisher", "Tinker", action="Part of gizmo use", description="Raise a non-project gizmo's effective level by 1 plus half the sequence length."),
    ProdigyOption("Unlimited Power", "Finisher", "Tinker", 1, "Full-round action; faster with links", "Create and immediately attach a temporary battery to one of your gizmos. It does not count against your gizmo limit and lasts for at most sequence links + casting ability modifier rounds. Use it as a full-round action at 1 link, standard at 3 links, move at 5 links, swift at 7 links, or free at 9 links."),
    ProdigyOption("Trapped", "Opener", "Trap", action="Trap triggers", description="A hostile creature fails a save against or takes damage from your trap."),
    ProdigyOption("Battlefield Coordination", "Opener", "Warleader", action="Standard action or longer", description="Use a shout or activate a tactic."),
    ProdigyOption("Continue Guidance", "Link", "Warleader", action="Move or swift action", description="Maintain a tactic."),
    ProdigyOption("Big Move", "Link", "Wrestling", action="Slam", description="Succeed on a combat maneuver or deal damage as part of a slam."),
    ProdigyOption("Parting Shove", "Link", "Wrestling", action="Swift action", description="After failing to grapple, make a harmless unarmed strike that batters the target on a hit."),
    ProdigyOption("Tentacle Swarm", "Finisher", "Alteration", 0, "Standard action", "Attempt one trip maneuver per link against creatures in close range, with no creature targeted twice."),
    ProdigyOption("Bear Rush", "Finisher", "Bear", 0, "Standard action", "Rush through a line whose length scales with links; affected creatures can be knocked prone and take scaling physical damage."),
    ProdigyOption("Extract Minions", "Finisher", "Blood", 0, "Standard action", "Extract a number of blood constructs equal to the sequence links; they remain for a number of rounds equal to the links."),
    ProdigyOption("Conjure Army", "Finisher", "Conjuration", 0, "Standard action", "Create temporary copies of a companion, one per link, each making one attack before disappearing."),
    ProdigyOption("Anvil Drop", "Finisher", "Creation", 0, "Standard action", "Create one object per link above targets in creation range; the objects vanish on your next turn.", "Create"),
    ProdigyOption("Petrify", "Finisher", "Creation", 0, "Full-round action", "After damaging a target with an attack action, spend a spell point to attempt to turn it to stone for half the sequence links in rounds.", "Alter"),
    ProdigyOption("Sunset", "Finisher", "Dark", 0, "Standard action", "Create mobile darkness centered on yourself out to long range for one round per link; you remain able to see through it."),
    ProdigyOption("Walking Dead", "Finisher", "Death", 0, "Move or full-round action", "Temporarily reanimate one nearby target, or a number of targets equal to the links with the longer action."),
    ProdigyOption("Explosive Finish", "Finisher", "Destruction", 0, "Standard action", "Release a destructive burst centered on yourself with a radius of 5 feet per link; its damage and blast type follow your destructive blast."),
    ProdigyOption("Precognizant Save", "Finisher", "Divination", 0, "Immediate action", "Gain an insight bonus equal to the sequence links on one saving throw."),
    ProdigyOption("Animate Ally", "Finisher", "Enhancement", 0, "Move action", "Animate one object for one round per link."),
    ProdigyOption("Seelie Beauty", "Finisher", "Fallen Fey", 0, "Standard action", "A number of nearby targets equal to the links must save or be blinded for half the links in rounds."),
    ProdigyOption("Unseelie Terror", "Finisher", "Fallen Fey", 0, "Standard action", "A number of nearby targets equal to the links must save or be frightened for one round per link."),
    ProdigyOption("Curse", "Finisher", "Fate", 0, "Swift action", "Give one creature in close range a penalty on d20 rolls equal to the links until your next turn."),
    ProdigyOption("Vanish", "Finisher", "Illusion", 0, "Swift action", "Become effectively invisible for one round per link, subject to the class feature's suppression rules."),
    ProdigyOption("Healing Burst", "Finisher", "Life", 0, "Move action", "Allies in close range recover hit points equal to casting ability modifier multiplied by sequence links.", "Cure / Invigorate"),
    ProdigyOption("Nova", "Finisher", "Light", 0, "Move action", "Release a flash whose radius grows with links; failed Reflex saves cause blindness for half the links in rounds."),
    ProdigyOption("Whence They Came", "Finisher", "Mana", 3, "Special attack action", "On a failed Fortitude save, remove dissonance points to deal 1d8 damage per point; at seven links it also damages spell points."),
    ProdigyOption("Enslave", "Finisher", "Mind", 0, "Standard action", "Attempt a powerful command charm against one creature in close range for half the sequence links in rounds."),
    ProdigyOption("Nature Surge", "Finisher", "Nature", 0, "Part of geomancing", "Cast a geomancing ability with an insight caster-level bonus equal to links and reduce its spell-point cost by one, minimum zero."),
    ProdigyOption("Adamantine Skin", "Finisher", "Protection", 0, "Immediate action", "Reduce incoming damage by casting ability modifier multiplied by sequence links."),
    ProdigyOption("System Overload", "Finisher", "Technomancy", 0, "Standard action", "Generate one temporary sprite per link in hosts within long range."),
    ProdigyOption("Fling", "Finisher", "Telekinesis", 0, "Immediate action", "After a damaging attack action or maneuver, lift the target and make one bludgeon attack with it; larger targets require more links."),
    ProdigyOption("Timeless Duel", "Finisher", "Time", 3, "Swift action", "On a failed Will save, you and one nearby hostile creature act apart from everyone else for one round per three links."),
    ProdigyOption("Motivate Cohort", "Finisher", "War", 0, "Move action", "A number of allies equal to half the sequence links may immediately make one attack."),
    ProdigyOption("Private Battlefield", "Finisher", "Warp", 3, "Swift action", "On a failed Will save, draw one nearby hostile creature into a private battlefield with you for one round per three links.", "Bend Space"),
    ProdigyOption("Sudden Shuffle", "Finisher", "Warp", 0, "Move action", "Reposition a number of willing targets equal to the links by swapping their spaces within teleport range.", "Teleport"),
    ProdigyOption("Call Bolts", "Finisher", "Weather", 0, "Standard action", "Call one weather bolt per link within your controlled weather; each deals scaling electricity damage with a Reflex save to negate."),
    ProdigyOption("Pressure Front", "Finisher", "Weather", 0, "Standard action", "Create a wind line whose dimensions scale with links and bull rush creatures using caster level plus casting ability modifier."),
)

SKILL_SPHERES = {
    "Artifice", "Bluster", "Body Control", "Communication", "Faction", "Herbalism",
    "Infiltration", "Investigation", "Navigation", "Performance", "Spellhacking",
    "Study", "Subterfuge", "Survivalism", "Vocation",
}


SPHERE_IMBUES = (
    ProdigyImbue("alteration_minor_shapeshift", "Alteration", "Minor Shapeshift", "Gain one trait that could be applied through Blank Transformation while the sequence lasts."),
    ProdigyImbue("bear_bearing", "Bear", "Bearing", "Gain one bearacteristic you qualify to use; pay any additional spell-point requirement normally."),
    ProdigyImbue("blood_bleeding_cuts", "Blood", "Bleeding Cuts", "Attack actions cause bleed damage equal to half your Prodigy level; this bleed does not stack with itself.", "bleed"),
    ProdigyImbue("conjuration_double_team", "Conjuration", "Double Team", "Your companion's aid-another and flanking bonuses increase by half the sequence links, minimum +1.", "companion_bonus"),
    ProdigyImbue("creation_breaker", "Creation", "Breaker", "Your attacks can ignore hardness equal to your Prodigy level.", requires_package="Alter"),
    ProdigyImbue("creation_debris_field", "Creation", "Debris Field", "Create difficult terrain in a radius of 5 feet per link; activating it requires the create package.", requires_package="Create"),
    ProdigyImbue("creation_sudden_arsenal", "Creation", "Sudden Arsenal", "Create a weapon, armor, shield, or ammunition that lasts until the imbue ends.", requires_package="Create"),
    ProdigyImbue("dark_shadow", "Dark", "Shadow", "Carry an area of darkness centered on yourself without impairing your own sight."),
    ProdigyImbue("death_vampiric_blade", "Death", "Vampiric Blade", "Attack actions deal extra negative energy damage equal to half class level and grant limited stacking temporary hit points.", "negative_damage"),
    ProdigyImbue("destruction_destructive_edge", "Destruction", "Destructive Edge", "Attack actions deal extra damage equal to class level using an available destructive blast damage type.", "extra_damage"),
    ProdigyImbue("divination_clear_sighted", "Divination", "Clear Sighted", "Gain an insight bonus to Armor Class and Reflex saves that improves every six class levels.", "defense_bonus"),
    ProdigyImbue("enhancement_enhanced_combatant", "Enhancement", "Enhanced Combatant", "Apply one enhancement talent you possess to yourself or one held weapon, armor, or shield."),
    ProdigyImbue("fallen_fey_fey_manner", "Fallen Fey", "Fey Manner", "Gain one fey blessing talent you possess for the duration of the sequence."),
    ProdigyImbue("fate_lucky", "Fate", "Lucky", "Benefit from one consecration talent you possess; only one such consecration can be maintained by the imbue."),
    ProdigyImbue("illusion_blurred", "Illusion", "Blurred", "Gain a 20% miss chance while the sequence remains active.", "miss_chance"),
    ProdigyImbue("life_regenerate", "Life", "Regenerate", "Gain fast healing equal to the number of links in the sequence.", "fast_healing", "Cure / Invigorate"),
    ProdigyImbue("light_sunrise", "Light", "Sunrise", "Glow with bright light and optionally add a light talent you possess."),
    ProdigyImbue("mana_amped_up", "Mana", "Amped Up", "Choose an amp that costs no spell points; eligible sphere effects count as amplified."),
    ProdigyImbue("mana_inject_dissonance", "Mana", "Inject Dissonance", "Damaging attack actions place dissonance on their targets, penalizing caster level, MSB, and MSD."),
    ProdigyImbue("mind_mind_breaker", "Mind", "Mind Breaker", "Targets of your attack actions and maneuvers take a scaling penalty against your charms and compulsions until your next turn.", "save_penalty"),
    ProdigyImbue("nature_aura_of_flame", "Nature", "Aura of Flame", "Hostile creatures near you risk catching fire; the damage and radius grow with links.", "fire_damage", "Fire"),
    ProdigyImbue("nature_fog_of_war", "Nature", "Fog of War", "Create concealment-producing mist in a radius of 5 feet per link while retaining your own sight.", "radius", "Water"),
    ProdigyImbue("nature_greenstep", "Nature", "Greenstep", "Ignore plant-based difficult terrain and see through plant life within 30 feet.", requires_package="Plant"),
    ProdigyImbue("nature_steel_skin", "Nature", "Steel Skin", "Reduce armor-check penalties from metal equipment and gain a link-based defense against sunder.", "sunder_defense", "Metal"),
    ProdigyImbue("nature_tunnel", "Nature", "Tunnel", "Gain a burrow speed of 20 feet, increasing by 5 feet per five class levels.", "burrow_speed", "Earth"),
    ProdigyImbue("nature_wind_barrier", "Nature", "Wind Barrier", "Gain an Armor Class bonus against ranged attacks equal to sequence links.", "ranged_ac", "Air"),
    ProdigyImbue("protection_defended", "Protection", "Defended", "Gain one aegis you possess, using class level in place of caster level where required.", requires_package="Aegis"),
    ProdigyImbue("technomancy_program_slice", "Technomancy", "Program Slice", "A successful attack can generate a sprite in the target or its equipment until the sequence ends."),
    ProdigyImbue("telekinesis_air_step", "Telekinesis", "Air Step", "Become immune to falling damage; qualifying self-telekinesis can grant flight as links are added."),
    ProdigyImbue("time_time_slip", "Time", "Time Slip", "Gain a scaling dodge bonus to Armor Class and competence bonus to Reflex saves.", "defense_bonus"),
    ProdigyImbue("war_inspiring", "War", "Inspiring", "Allies within close range gain the benefits of Inspired Sequence."),
    ProdigyImbue("warp_step_between", "Warp", "Step Between", "Once per turn as a move action, teleport 5 feet plus 5 feet per link.", "teleport_distance", "Teleport"),
    ProdigyImbue("warp_warping_presence", "Warp", "Warping Presence", "Hostile creatures entering the nearby area must save or treat it as difficult terrain.", "radius", "Bend Space"),
    ProdigyImbue("weather_ignore_tempest", "Weather", "Ignore Tempest", "Treat weather severity as one category lower, improving by another category per seven class levels.", "weather_reduction"),
)


def sphere_options(
    sphere_names: set[str], package_access: dict[str, set[str]] | None = None,
    talent_names: set[str] | None = None,
) -> tuple[ProdigyOption, ...]:
    owned = {name.casefold() for name in sphere_names}
    talents = {name.casefold() for name in (talent_names or set())}
    package_access = package_access or {}
    return tuple(
        option
        for option in SPHERE_PRODIGY_OPTIONS
        if (option.sphere.casefold() in owned or (option.sphere == "Any Skill Sphere" and any(name.casefold() in owned for name in SKILL_SPHERES)))
        and (
            not option.requires_package
            or option.requires_package in package_access.get(option.sphere, {option.requires_package})
        )
        and (
            not option.requires_talent
            or any(
                name == option.requires_talent.casefold()
                or name.startswith(option.requires_talent.casefold() + " (")
                for name in talents
            )
        )
    )


def sphere_imbues(
    sphere_names: set[str], package_access: dict[str, set[str]] | None = None
) -> tuple[ProdigyImbue, ...]:
    owned = {name.casefold() for name in sphere_names}
    package_access = package_access or {}
    return tuple(
        imbue
        for imbue in SPHERE_IMBUES
        if imbue.sphere.casefold() in owned
        and (
            not imbue.requires_package
            or imbue.requires_package in package_access.get(imbue.sphere, {imbue.requires_package})
        )
    )


def imbue_numeric_value(imbue: ProdigyImbue, links: int, class_level: int) -> int:
    """Return the primary numeric benefit of an imbue for sheet formulas.

    Metrics use different units (feet, percentage points, bonuses, damage, and
    so on), so callers should retain the metric name when presenting the value.
    Imbues without one deterministic numeric value intentionally return zero.
    """

    half_level = max(0, class_level // 2)
    values = {
        "bleed": half_level,
        "companion_bonus": max(1, links // 2),
        "negative_damage": half_level,
        "extra_damage": class_level,
        "defense_bonus": 1 + class_level // 6,
        "miss_chance": 20,
        "fast_healing": links,
        "save_penalty": 1 + class_level // 7,
        "fire_damage": links,
        "radius": 5 * links,
        "sunder_defense": links,
        "burrow_speed": 20 + 5 * (class_level // 5),
        "ranged_ac": links,
        "teleport_distance": 5 + 5 * links,
        "weather_reduction": 1 + class_level // 7,
    }
    return int(values.get(imbue.metric, 0))


def imbue_value(imbue: ProdigyImbue, links: int, class_level: int) -> str:
    half_level = max(0, class_level // 2)
    values = {
        "bleed": f"Bleed {half_level}",
        "companion_bonus": f"Companion bonus +{max(1, links // 2)}",
        "negative_damage": f"+{half_level} negative energy damage",
        "extra_damage": f"+{class_level} damage",
        "defense_bonus": f"AC / Reflex +{1 + class_level // 6}",
        "miss_chance": "20% miss chance",
        "fast_healing": f"Fast Healing {links}",
        "save_penalty": f"Save penalty −{1 + class_level // 7}",
        "fire_damage": f"Fire damage {links}",
        "radius": f"Radius {5 * links} ft",
        "sunder_defense": f"Sunder defense +{links}",
        "burrow_speed": f"Burrow {20 + 5 * (class_level // 5)} ft",
        "ranged_ac": f"Ranged AC +{links}",
        "teleport_distance": f"Teleport {5 + 5 * links} ft",
        "weather_reduction": f"Weather severity −{1 + class_level // 7} categories",
    }
    return values.get(imbue.metric, "Active while the sequence lasts")


def prodigy_codex_html() -> str:
    from app.reference_rules import sequence_reference, reference_html
    def full_description(item):
        entry = sequence_reference(item.name, item.sphere)
        return reference_html(entry, show_heading=False) if entry else item.description
    universal = "".join(
        f"<li><b>{item.option_type} — {item.name}</b> — "
        f"{item.action or 'Special'}: {full_description(item)}</li>"
        for item in UNIVERSAL_PRODIGY_OPTIONS
    )
    spheres = []
    for sphere in sorted({item.sphere for item in SPHERE_IMBUES} | {item.sphere for item in SPHERE_PRODIGY_OPTIONS}):
        imbues = [item for item in SPHERE_IMBUES if item.sphere == sphere]
        sequence_options = [
            item for item in SPHERE_PRODIGY_OPTIONS if item.sphere == sphere
        ]
        body = "".join(f"<li><b>Imbue — {item.name}:</b> {full_description(item)}</li>" for item in imbues)
        body += "".join(
            f"<li><b>{item.option_type} — {item.name}</b> "
            f"({item.action}{f', minimum {item.minimum_links} links' if item.minimum_links else ''}): "
            f"{full_description(item)}</li>"
            for item in sequence_options
        )
        spheres.append(f"<h3>{sphere}</h3><ul>{body}</ul>")
    progression_data = (
        (1, "+0", "+0", "+2", "+2", "Casting; blended training; sequence (4); inspired sequence", "1 + 2 magic", "0 (1)"),
        (2, "+1", "+0", "+3", "+3", "Adaptation; imbue sequence", "2", "1"),
        (3, "+2", "+1", "+3", "+3", "Sequence (5); steady skill; skill attunement", "3", "2"),
        (4, "+3", "+1", "+4", "+4", "Unbroken Sequence", "4", "3"),
        (5, "+3", "+1", "+4", "+4", "Improved Adaptation", "5", "3"),
        (6, "+4", "+2", "+5", "+5", "Sequence (6)", "6", "4"),
        (7, "+5", "+2", "+5", "+5", "Reflect Spell", "7", "5"),
        (8, "+6/+1", "+2", "+6", "+6", "Greater Adaptation", "8", "6"),
        (9, "+6/+1", "+3", "+6", "+6", "Sequence (7)", "9", "6"),
        (10, "+7/+2", "+3", "+7", "+7", "Share Adaptation", "10", "7"),
        (11, "+8/+3", "+3", "+7", "+7", "Variable Skill", "11", "8"),
        (12, "+9/+4", "+4", "+8", "+8", "Sequence (8)", "12", "9"),
        (13, "+9/+4", "+4", "+8", "+8", "Master Adaptation", "13", "9"),
        (14, "+10/+5", "+4", "+9", "+9", "Flawless Sequence", "14", "10"),
        (15, "+11/+6/+1", "+5", "+9", "+9", "Sequence (9)", "15", "11"),
        (16, "+12/+7/+2", "+5", "+10", "+10", "Greater Reflect Spell", "16", "12"),
        (17, "+12/+7/+2", "+5", "+10", "+10", "Grandmaster Adaptation", "17", "12"),
        (18, "+13/+8/+3", "+6", "+11", "+11", "Sequence (10)", "18", "13"),
        (19, "+14/+9/+4", "+6", "+11", "+11", "Skill Juggler", "19", "14"),
        (20, "+15/+10/+5", "+6", "+12", "+12", "Perfected Prodigy", "20", "15"),
    )
    progression_rows = "".join(
        "<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>"
        for row in progression_data
    )
    integrated_spheres = (
        "Any Skill Sphere, Alchemy, Artifice, Athletics, Barrage, Barroom, Beastmastery, "
        "Berserker, Bluster, Body Control, Boxing, Brute, Communication, Dual Wielding, "
        "Duelist, Fencing, Gladiator, Guardian, Herbalism, Infiltration, Investigation, "
        "Lancer, Leadership, Navigation, Open Hand, Performance, Scoundrel, Scout, Shield, "
        "Sniper, Spellhacking, Study, Subterfuge, Survivalism, Tech, Tinker, Trap, "
        "Warleader and Wrestling"
    )
    return f"""
    <h1>Prodigy</h1>
    <p><i>Class overview with complete imported Sequence action descriptions.</i></p>
    <p><a href="codex:reference-index:prodigy">Browse every Sequence action and imbue by sphere</a></p>
    <h2>Class chassis</h2>
    <p>The Prodigy is a flexible mid-caster able to fill many party roles. It permits any alignment, uses a d8 Hit Die, starts with 3d6 × 10 gp, uses the intuitive starting-age category, and gains 4 + Intelligence skill ranks per level.</p>
    <p><b>Class skills:</b> Acrobatics, Bluff, Climb, Craft, Diplomacy, Intimidate, every Knowledge skill, Perception, Perform, Profession, Sense Motive, Spellcraft, Use Magic Device, plus three additional skills selected at character creation.</p>
    <p><b>Proficiencies:</b> simple weapons, light armor and bucklers. If Prodigy is the character's first class level, it may also grant a martial tradition.</p>
    <h2>Progression</h2>
    <table border="1" cellspacing="0" cellpadding="4"><tr><th>Level</th><th>BAB</th><th>Fort</th><th>Ref</th><th>Will</th><th>Features</th><th>Blended talents</th><th>CL</th></tr>{progression_rows}</table>
    <h2>Casting, talents and spell pool</h2>
    <p>Prodigy levels grant mid-caster progression. Casting grants the usual two starting magic talents, and Blended Training supplies further combat or magic talents. The base spell pool is Prodigy level plus the casting ability modifier, with later traditions, drawbacks, boons and other classes able to contribute through the app's modular spell-point calculation.</p>
    <h2>Sequence</h2>
    <p>An opener begins a sequence at one link. A link, or an opener used while the sequence is already active, adds one link. A single action can add no more than one link even if it satisfies several triggers; bonus attacks belonging to the same action are part of that action, while attacks of opportunity are separate. The sequence normally loses one link when the Prodigy begins a turn without having added one since the beginning of the prior turn. At zero it ends. Dazed, dead, helpless, paralyzed, stunned or unconscious normally ends it immediately until later class features protect it. Only one sequence can be active.</p>
    <p>A finisher requires the listed minimum and ends the sequence after resolving; actions within it do not begin a replacement sequence. The maximum starts at four and rises every third Prodigy level to ten at 18th level.</p>
    <p>Inspired Sequence grants an insight bonus to attacks, damage and caster level equal to half the current links, minimum +1 while active. Imbue Sequence attaches one eligible magic sphere to the active sequence and supplies that sphere's imbuement and finishers.</p>
    <h2>Universal openers, links and finishers</h2><ul>{universal}</ul>
    <h2>Integrated techniques</h2>
    <p>Possessing certain combat or skill spheres supplies extra openers, links and finishers. The source page defines groups for: {integrated_spheres}. These techniques include plan and approach openers from skill spheres; formula, poison, trinket, movement, barrage, drink, shove, feint, boast, patrol, reload, gadget, trap and tactic triggers; and sphere-specific finishers such as multi-formula throws, full-BAB ranged flurries, mass bull rushes, device self-destruction and temporary batteries.</p>
    <p>The character sheet currently imports magic-sphere Imbues and Finishers automatically. Combat- and skill-sphere integrated techniques are recorded here so their later automation can use the same Codex hierarchy.</p>
    <h2>Sphere-granted sequence options</h2>{''.join(spheres)}
    <h2>Adaptation and later class features</h2>
    <p>Adaptation begins at level 2 as a standard action that grants one qualifying combat or magic talent for one minute. It requires the base sphere and advanced-talent prerequisites, has 3 + half class level daily uses, and a new use replaces the prior one. Improved, Greater, Master and Grandmaster Adaptation successively increase the number of simultaneous talents and improve the action required. Talents chosen together may satisfy later choices' prerequisites. Share Adaptation spends two uses to grant one qualifying talent to a nearby ally for one minute.</p>
    <p>Reflect Spell expends martial focus as an immediate action and contests the incoming effect with MSB against MSD. Success returns the effect to the original caster, while either result initially leaves the Prodigy staggered next turn. Greater Reflect Spell removes the stagger and restores focus on success.</p>
    <p>Steady Skill lets the Prodigy prepare one class skill after daily rest, take 10 under pressure, and spend focus a limited number of times to treat the roll as 15. Variable Skill allows changing it by spending a spell point; Skill Juggler reduces the change to one minute and improves the focus option to 20. At level 20, sequences begin with half the casting ability modifier in links and Adaptation can grant any number of talents as a swift action, paying one daily use per talent.</p>
    <h2>Skill attunements</h2>
    <p>From level 3, Steady Skill may be replaced by an attunement from a possessed skill sphere. The page includes Artifice, Bluster, Body Control, Communication, Faction, Herbalism, Infiltration, Investigation, Navigation, Performance, Spellhacking, Study, Subterfuge, Survivalism and Vocation. Their benefits accelerate crafting, research, information gathering, forgery, herb gathering, device work, travel, performance income and other sphere-specific skill routines; each receives a stronger level-19 benefit.</p>
    <h2>Archetypes and related options</h2>
    <ul><li><b>Battle-Born:</b> emphasizes martial prowess.</li><li><b>Chromamancer:</b> channels color-based powers.</li><li><b>Exploitant:</b> trades breadth for highly flexible insight and moldable talent use.</li><li><b>Extemporizer:</b> develops new battle techniques.</li><li><b>Gutter Rat:</b> emphasizes adaptable rogue-like skills.</li><li><b>Mimic:</b> copies nearby capabilities.</li><li><b>Sync:</b> follows a personal combat rhythm.</li><li><b>Void Dancer:</b> binds an outsider and gains void-themed sequence features.</li><li><b>DRS Prodigy features:</b> a linked collection of alternate third-party class features.</li></ul>
    <h2>Class equipment</h2>
    <ul><li><b>Gloves of Imbuement:</b> grant the sequence options of one chosen magic sphere without granting the sphere itself.</li><li><b>Manual of Techniques:</b> temporarily supplies the integrated techniques and base effect of one combat sphere after study.</li><li><b>Mirror of the Sun Goddess:</b> modifies Reflect Spell several times per day so a successful reflection can be redirected to another legal target.</li></ul>
    <h2>Special sphere systems</h2><p>The source also supplies Wild Magic and Card Casting interactions. Wild Magic can build a chaos aura and spend a finisher to suppress surge chance; Card Casting can draw cards as links are gained and spend a six-link finisher to play a qualifying card quickly.</p>
    <h2>Using this entry</h2>
    <p>The class overview is condensed; Sequence action descriptions are imported from the linked rules. Consult the <a href="{PRODIGY_SOURCE_URL}">full Prodigy rules page</a> for the complete class and archetypes.</p>
    """

# Tech & Tinker implementation status

Updated: 2026-10-03. This is an implementation ledger, not a claim of complete automation.

## Implemented in this batch

- Conditional Engineering Workbench on the Crafting page for characters with an active Tech or Tinker base sphere.
- Character-owned, persistent device roster with stable catalog provenance.
- Additive SQLite storage; existing saved characters remain compatible.
- Device creation from currently learned gadget/gizmo talents; Tinker base sphere also unlocks batteries.
- Basic device limits, repeatable Extra Gadgets and Efficient Maintenance bonuses.
- Minor gizmo grouping and additive advanced increases. Selecting those flags is manual: the workbench does not yet validate whether an individual device qualifies.
- Creation-time level and practitioner-modifier snapshots; baseline HP, hardness, saves and DC displayed. Specific device exceptions are not applied.
- Activate, deactivate, deplete and confirmed irreversible abandonment.
- Tinker batteries cannot be deactivated, depletion still uses a limit slot, maintenance restores depleted devices, abandoned devices cannot be restored.
- Tinker batteries can attach to owned non-battery gizmos, multiple batteries can be depleted atomically, and personal battery uses enforce minimum battery level. Battery costs are selected manually; individual talent costs and reload-time reductions are not automated. Import/export remaps battery host identities.
- Tech pool begins empty, recharges by the associated-rank rule, spends without going negative, transfers charges atomically between pool and devices.
- Charges allocated to regular gadgets remain counted against the total pool maximum.
- Tech batteries are created charged, remain outside the pool maximum, attach one per same-system device, and are drained first through atomic device spending. Explicit recharge and detach controls are available; excess pool charging requires confirmation. Abandonment discards battery charges.
- Rest preserves Tech charges and does not silently maintain Tinker batteries.
- Device and resource import/export with ownership checks.
- Persistent device damage, current/max HP, optional hardness subtraction, and automatic deactivation at zero HP. Destroyed devices and batteries cannot activate or supply charges.
- Tinker broken-condition threshold and effective-level penalty, one-minute tool-assisted repairs, and maintenance-based full repair of non-abandoned gizmos. Rest does not perform repairs.
- Augmentation-package Physical Augmentor crafting with a selected Strength/Dexterity/Constitution configuration and explicit wearer state. Active, worn augmentors contribute typed competence bonuses to matching skill checks through shared calculations, including skill ability overrides and broken effective levels. Ability scores are not increased.
- Jet-boosters: creation-time flight/aquatic choice, normal/slow-burn/overdrive modes, atomic battery-first payment, paid durations, live movement/maneuverability, light-load restrictions and equipment-slot conflicts. Explicit game-round advancement expires timed functions; eight-hour rest advances those timers without recharge or maintenance.
- First Tech gadget choices exclude routine talents.
- Timer expiration distinguishes paid Jet-boosters operation (device deactivates) from Tinker temporary enhancements (passive device activation is retained). Supporting-battery identity is stored with ownership/attachment checks and remapped on import. Detaching, abandoning or destroying the supporting battery ends its linked timed effect without disabling the host's passive activation. Function-specific enhancement activation remains pending.
- Personal Field Projector with the Modification package unlocks a separate Tactile Field recipe. Active/attached CMD, Acrobatics and Escape Artist circumstance bonuses are automatic, use effective gizmo level and do not stack multiple copies. One attached battery atomically activates its enhanced bonus for one minute per effective gizmo level. Expiry retains the passive field; the reroll/end control ends enhancement early. Dice/opponent reroll resolution remains manual.
- Pressure Jack unlocks a Strength Load Bearer recipe. Active/worn skill bonuses and carrying-capacity Strength are automatic, including doubled capacity bonus for advanced devices and reduced bonuses when broken. Actual Strength is unchanged; object-breaking size benefits and roll actions remain manual.
- Cognitive Set unlocks a separate Mental Augmentor recipe with Intelligence/Wisdom/Charisma configuration and active/worn competence skill bonuses. Brain Jack/storage, ability-check rolls and battery rerolls remain pending.

## Partial support / manual inputs

- Defensive Set plus Computation unlocks a separate Resistance Routine recipe, automatically classified as minor. Installation/removal uses owned Tinker host identities and existing transfer remapping. Active functioning routines add the highest applicable insight save bonus to their host's displayed saves (including broken-level changes), never to character saves. AI sharing and nested routine composition remain pending.

- Physical/Mental Augmentor and Load Bearer now have a dedicated one-battery benefiting-check action. It validates active, worn, functioning, correctly configured devices and uses the existing atomic battery depletion path. Actual dice are resolved manually (roll twice and take the higher result); no persistent reroll buff is created. Focused validation: 33 engineering tests and 2 theme subtests passed.

- Associated skill defaults to the existing shared Craft rank provider. Alternative associated skills can be selected in the workbench, but tradition-specific skill-rank grants and skill specialties are not completely automated.
- Practitioner modifier may be manually entered or linked to a chosen ability's live calculated modifier. The workbench recalculates linked values on refresh; creation still stores the required snapshot. Automatic selection of the governing ability from every class/archetype/tradition remains pending; no unrelated class resource ability is assumed to be a practitioner ability.
- Crafting/maintenance duration and batch allowance are calculated and displayed. Timed device functions use explicit game-round advancement; a general campaign clock and crafting session ledger remain pending. Ordinary Tinker gizmos last indefinitely under the current rules; optional GM neglect is not imposed automatically.
- Base package grants can include multiple gizmo types within one talent. Physical Augmentor is now a separate craftable function; other package functions still need function-level recipes.
- Current talent validation still relies on the existing character selection system.
- Workbench maxima are live calculated. The reusable Tech tracker maximum is refreshed when changing pool charges, not on every character edit.
- Losing a base sphere prevents new crafting/resource use, but the saved roster is retained for review rather than deleted.
- Device baseline statistics are frozen at creation. This is intentional for Tinker; Tech device-specific scaling and later upgrades need further verification.

## Still missing

1. Function-level recipes and configurations for remaining gadget/gizmo talents and base packages. Physical Augmentor skill effects are implemented; its ability-check roll integration and battery reroll are still manual.
2. Automatic equipment/attack/AC/save/movement/skill modifiers from installed and activated devices.
3. Tech batteries attached to external technological inventory items. Current hosts are character-owned workbench devices. Nonpositive-modifier pool charging follows the separate printed creator-modifier cap; interpretation needs rules verification because creation explicitly has a minimum of one.
4. Augment/graft slots, installation checks, incompatibilities and polymorph suppression.
5. Drone and mechanoid stat blocks, upgrades, piloting, innate devices and rote functions.
6. AI stat blocks, commands, routines, hosts and installation.
7. Accessories, combined devices, accommodation/secondary-function composition.
8. Tech-specific repair methods, sundering attack resolution, damage-type adjustments, scavenging and detailed upkeep. Current HP and basic Tinker repair/maintenance are implemented; AI/mechanoid exceptions, Redundant Systems and It Just Works remain pending.
9. Timed activation/duration profiles for remaining functions and temporary charges. Jet-boosters' paid periods and expiration are implemented.
10. Project construction costs/times and technical-item creation feat integration.
11. Tinker tradition restrictions/boons, optional variants and skill substitutions.
12. Class/archetype-specific personal gizmos and personal battery-use requirements.
13. Prodigy engineering interactions: effective-level boosts, temporary batteries and their expiry.
14. Direct Martial Book actions for individual saved devices. Shared formula references now expose per-device level/effective level, current/max HP, own charges, remaining paid rounds and state flags; autocomplete includes them and character import remaps device identities in references.
15. Complete rules-safe validation of minor/advanced/exempt devices and alternate construction sources.
16. Automatic handling of all sphere drawbacks and interactions with other spheres.
17. Current website completeness verification. The table below describes bundled entries only.
18. Packaged-runtime verification for this batch. The full isolated suite has run; three pre-existing failures remain separate from engineering work.

## Validation

Current accumulated engineering validation at `1ae99de`: complete isolated suite finished across all 142 modules, 2,003 cases, 2,000 passing, 3 failing, 0 errors and 0 skipped. Failures match the previously reproduced baseline issues: archetype count (1,830 expected versus 1,887 bundled), custom-tracker parent placement, and tradition placement (with secondary database cleanup lock). No new failures were introduced by damage/repair, Physical/Mental Augmentor, Jet-boosters or Load Bearer. Reports: `artifacts/engineering-validation-current/summary.json` and `complete.xml`. This does not prove missing device mechanics or packaged-runtime behavior.

Package-validation follow-up: Physical/Mental Augmentor and Load Bearer recipes now require Augmentation. Expanded Tinkering uses the shared two-package picker, excludes owned packages, validates distinct/unowned choices on permanent add/edit, and saves them for engineering access. Shared flexible-talent validation also checks choices against permanent and earlier staged selections; the temporary picker excludes those packages and cancellation performs no writes. Remaining function-specific package restrictions still need coverage. Focused engineering, catalog redesign and Athletics run: 39 tests and 2 theme subtests passed.

74 focused tests and two theme subtests passed across engineering, database, sphere choices, crafting, skill ranks, recovery, Codex and import/export. The full isolated suite was not run; no assertion is made about its current baseline. Actual workbench renders were inspected in parchment and dark themes.

Tech battery follow-up: full isolated run completed with 1,991 cases, 1,988 passing and 3 failing. All three failures reproduce against the untouched `87b4e8e` baseline: stale archetype count, custom-tracker parent placement, and tradition placement. Latest focused engineering run: 14 tests and 2 theme subtests passed, including the subsequent Tinker battery host-level guard and cancelled-overfill checks. Normal/portable deployment and packaged verification are not yet performed for this follow-up.

Damage/repair follow-up: 51 focused engineering, database, transfer and recovery tests plus 2 theme subtests passed. The parchment workbench render was inspected with a broken gizmo showing current/max HP and effective level. The full isolated suite has not been repeated after this follow-up. Damage-type adjustments are manual before applying hardness; device-specific defensive exceptions and attack/sunder resolution remain pending.

Physical Augmentor follow-up: 58 focused engineering, shared rules, skill-rank, transfer and recovery tests plus 2 theme subtests passed. Configuration and wearer state are additive/defaulted database fields. Device slot validation, duration/expiry, external wearers and alternate construction grants remain pending.

Jet-boosters follow-up: 76 broad focused tests plus 2 theme subtests passed; after additional slot/load/transfer and Athletics Fly-package coverage, all 22 engineering tests and 2 theme subtests passed. A further 19 performance/layout/movement tests and 2 theme subtests passed. The parchment timed-jet dialog was rendered and inspected. The full suite has not yet been repeated. Long Distance Fuel Pack, external/unwilling users, exhaust/hover geometry and equipment-figure display remain pending.

## Verified rule sources

### Installation rules verified for the next implementation

- Tech augments use dedicated slots separate from magic-item and cybertech slots. A slot normally holds one augment; nonstandard anatomy can add limb/sensory slots, but never additional body or brain slots.
- Tech augment donning/removal follows leather armor. Hasty donning adds 2 armor check penalty. Visible augments impose a Disguise penalty of 10 + 2 per donned augment.
- Ordinary Tech augments do not function during polymorph, including augments donned after transformation. Grafts instead follow innate-trait retention. Bio Augment and Untraceable Gadget contain explicit exceptions which must be modeled rather than applying blanket suppression.
- Tinker augmentation installation must use its own rules: worn augmentation donning/removal takes one minute; same-function benefits do not stack, but differently configured augmentations can coexist. Prosthetics have separate fitting/implantation rules. Do not reuse Tech's dedicated-slot or polymorph rules without a Tinker rule supporting that behavior.
- These are verified requirements, not implemented installation behavior. Next work must connect installation state to shared calculations and existing condition/equipment state, with regression coverage for both systems and exceptions.

- [Tech](https://spheresofpower.wikidot.com/tech)
- [Tinker](https://spheresofpower.wikidot.com/tinker)
- [Using Tinker Sphere](https://spheresofpower.wikidot.com/using-tinker-sphere)
- [Mastering Gizmos](https://spheresofpower.wikidot.com/mastering-gizmos)

## Bundled entry ledger

Every entry remains available through existing catalogs/Codex. “Roster” means lifecycle tracking only, not automatic effects.

| Sphere | Entry | Category | Functional status |
| --- | --- | --- | --- |
| Tech | Tech Sphere | Base Sphere | Basic workbench access and calculations |
| Tech | Alternate Element Pack (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Chameleon Suit (gadget, accessory) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Control Harness (accessory, drone, gadget, signal) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Dash Engine (accessory, augment, drone, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Disarmer (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Homing Pack (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Hookshot (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Integrated Armory (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Internal Tool (accessory, augment, drone, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Laser Pack (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Misfire Manager (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Mobile Armor (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Pressure Mechanism (accessory, augment, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Range Amplifier (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Sniper Scope (accessory, augment, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Speed Lever (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Superior Joints (gadget, accessory) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Weapon Upgrade (accessory, gadget) | Accessory Talent | Roster; device-specific effects not automated |
| Tech | Alternative-Craft | Drawback | Reference / existing selection only |
| Tech | Environmental Fuel Source | Drawback | Reference / existing selection only |
| Tech | Expensive Fuel Source | Drawback | Reference / existing selection only |
| Tech | Expensive Gadgets | Drawback | Reference / existing selection only |
| Tech | Explosive Gadgets | Drawback | Reference / existing selection only |
| Tech | Extended Charge | Drawback | Reference / existing selection only |
| Tech | Generated Power | Drawback | Reference / existing selection only |
| Tech | Imbued Gadgets | Drawback | Reference / existing selection only |
| Tech | Incomplete Knowledge | Drawback | Reference / existing selection only |
| Tech | Mana Engineering | Drawback | Reference / existing selection only |
| Tech | Obvious Activation | Drawback | Reference / existing selection only |
| Tech | Specific Drone | Drawback | Reference / existing selection only |
| Tech | Uninsulated | Drawback | Reference / existing selection only |
| Tech | Unsecured | Drawback | Reference / existing selection only |
| Tech | Wired Gadgets | Drawback | Reference / existing selection only |
| Tech | Accessory Suit (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Alt Weapon Mode (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Alternate Element Pack (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Ammo Spitter (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Anatomical Structure (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Antivirus Application (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Artificial Intelligence (drone, gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Auto Injector (augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Automator (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Battery (gadget) | Gadget Talent | Construction, exempt storage, attachment, atomic battery-first spending and explicit recharge; external inventory hosts pending |
| Tech | Camera (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Chameleon Suit (gadget, accessory) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Chemalyzer (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Clamp Boots (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Collapsible Vehicle (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Commset (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Compact Shield (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Control Harness (accessory, drone, gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Dash Engine (accessory, augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Dermal Plating (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Diga Drill (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Disarmer (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Drone (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Emergency Gear (drone, gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Evac Pack (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Exo-Skeletal Muscles (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Extendo Appendage (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | External Health Modulator (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Firefighter Equipment (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Gravity Clip (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Homing Pack (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Hookshot (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Integrated Armory (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Internal Tool (accessory, augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Jet-boosters (drone, gadget) | Gadget Talent | Flight/aquatic configuration, paid operating modes, movement, slot checks and timers; fuel pack/external users/hover geometry pending |
| Tech | Laser Pack (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Load Bearer (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Mechanical Ranged Weaponry (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Mechanical Tool (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Misfire Manager (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Mobile Armor (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Modular Slot (augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Overdrive (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Particle Weapon (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Pneumatic Box (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Pressure Mechanism (accessory, augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Range Amplifier (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Remote Control (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Seeker Missile Cannon (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Self Destructive Device (moddable) | Gadget Talent | Reference / existing selection only |
| Tech | Sensory Set (augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Signal Attenuator (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Signal Cable (gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Sniper Scope (accessory, augment, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Speed Lever (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Superior Joints (gadget, accessory) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Synaptic Reaction Maximizer (augment, drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Targeting Application (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Taser (gadget, moddable) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Tracker Chip (gadget, signal) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Turret (drone, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Tutor (drone, gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Virus (gadget, routine) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Weapon Upgrade (accessory, gadget) | Gadget Talent | Roster; device-specific effects not automated |
| Tech | Alchemical Drone | Legendary Talent | Reference / existing selection only |
| Tech | Arcanoscientific Tool (drone, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Artificial Intelligence, Greater (drone, gadget, routine) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Artificial Intelligence, Improved (drone, gadget, routine) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Automatic, Semi-Automatic, and Slow Firing | Legendary Talent | Reference / existing selection only |
| Tech | Bio Augment | Legendary Talent | Reference / existing selection only |
| Tech | Clockwork Drone | Legendary Talent | Reference / existing selection only |
| Tech | Combat Limbs (augment, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Compactor (accessory, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Computer (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Drawback Alleviator (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Energy Efficient Augments | Legendary Talent | Reference / existing selection only |
| Tech | Extreme Distance Communication (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Generator (drone, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Hammerspace Augment | Legendary Talent | Reference / existing selection only |
| Tech | Hidden Gadget | Legendary Talent | Reference / existing selection only |
| Tech | It Just Works [Jester's HB] | Legendary Talent | Reference / existing selection only |
| Tech | Long Distance Fuel Pack (drone, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Protonic Energypack (accessory, gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Return to Sender | Legendary Talent | Reference / existing selection only |
| Tech | Robot Drone | Legendary Talent | Reference / existing selection only |
| Tech | Signal Penetration | Legendary Talent | Reference / existing selection only |
| Tech | Steampowered Drone | Legendary Talent | Reference / existing selection only |
| Tech | Strength Of A Million And Seventy | Legendary Talent | Reference / existing selection only |
| Tech | Superior Mechanical Melee Weaponry (gadget, moddable) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Superior Mechanical Ranged Weaponry | Legendary Talent | Reference / existing selection only |
| Tech | Transporter (gadget) | Legendary Talent | Roster; device-specific effects not automated |
| Tech | Untraceable Gadget | Legendary Talent | Reference / existing selection only |
| Tech | Vigorous Gadgets | Legendary Talent | Reference / existing selection only |
| Tech | Wireless Charge | Legendary Talent | Reference / existing selection only |
| Tech | Collapsible Drone | Talent | Reference / existing selection only |
| Tech | Combined Augment | Talent | Reference / existing selection only |
| Tech | Efficient Drones | Talent | Reference / existing selection only |
| Tech | Extra Gadgets | Talent | Basic limit bonus automated |
| Tech | Improved User Interface | Talent | Reference / existing selection only |
| Tech | Mass Drone Deployment | Talent | Reference / existing selection only |
| Tech | Momentum Transfer (stance) [Youxia HB] | Talent | Reference / existing selection only |
| Tech | Repairable Drone | Talent | Reference / existing selection only |
| Tech | Standardized Drones | Talent | Reference / existing selection only |
| Tech | Tech Savvy | Talent | Reference / existing selection only |
| Tinker | Tinker Sphere | Base Sphere | Basic workbench access and calculations |
| Tinker | Powerless [SUE] | Drawback | Reference / existing selection only |
| Tinker | Specialized Inventorship [SUE] | Drawback | Reference / existing selection only |
| Tinker | Specific Mechanoids [SUE] | Drawback | Reference / existing selection only |
| Tinker | Tinker Tradition [SUE] | Drawback | Reference / existing selection only |
| Tinker | Armor Modifications (gizmo, modification) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Arsenal Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Aviation Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Cognitive Set (gizmo) [utility] | Gizmo Talent | Mental Augmentor configuration and mental skill bonuses automated; remaining functions pending |
| Tinker | Defensive Set (gizmo) | Gizmo Talent | Resistance Routine recipe, installation and host save bonus automated; other functions and AI sharing pending |
| Tinker | Disruption Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Emergency Gear (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Energy Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Excavation Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Exploration Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Grappling Hook (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Infiltration Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Medical Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Movement Set (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Personal Field Projector (gizmo, modification) | Gizmo Talent | Tactile Field passive/enhanced bonuses, battery cost, timer and reroll termination automated; actual reroll and other fields pending |
| Tinker | Pressure Jack (gizmo) | Gizmo Talent | Load Bearer recipe, skill bonuses and carrying capacity automated; other functions pending |
| Tinker | Primal Augmentations (augmentation, gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Prosthetics Mastery (augmentation, gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Ranged Set (gizmo, modification) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Repair Kits (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Sensory Set (gizmo) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Table: Elemental Infuser | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Lifter Type | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Portable Wall | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Power Plants | Gizmo Talent | Reference / existing selection only |
| Tinker | Table: Translator Fluency | Gizmo Talent | Reference / existing selection only |
| Tinker | Technological Weapons (gizmo) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Transmission Mastery (gizmo, transmission) [utility] | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Transportation Mastery (gizmo, transportation) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Weapon Modifications (gizmo, modification) | Gizmo Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Arsenal (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Augmentation (gizmo, augmentation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Computation (gizmo, computation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Energy Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Excavation (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Field Projectors (gizmo, modification) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Movement (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Prosthetics (gizmo, augmentation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Ranged Set (gizmo, modification) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Transmission (gizmo, transmission) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Advanced Transportation (gizmo, transportation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Automation Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Dynamic Repurposing [LG] | Legendary Talent | Reference / existing selection only |
| Tinker | Energy-Attuned Gizmos | Legendary Talent | Reference / existing selection only |
| Tinker | Extra Automatons (computation, transportation) | Legendary Talent | Reference / existing selection only |
| Tinker | Full Integration (gizmo, transportation) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Hammerspace (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Magic Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Master Of Technology | Legendary Talent | Reference / existing selection only |
| Tinker | Multimedia Mastery (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Radiation Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Restoration Mastery (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Security Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Spooky Set (gizmo) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Table: Advanced Lifter Type | Legendary Talent | Reference / existing selection only |
| Tinker | Table: Distant Teleport | Legendary Talent | Reference / existing selection only |
| Tinker | Table: Turrets | Legendary Talent | Reference / existing selection only |
| Tinker | Teleportation Set (gizmo, transmission) | Legendary Talent | Roster; device-specific effects not automated |
| Tinker | Disguised Gizmo [utility] | Talent | Reference / existing selection only |
| Tinker | Efficient Maintenance | Talent | Basic limit bonus automated |
| Tinker | Expanded Tinkering | Talent | Reference / existing selection only |
| Tinker | Machine Horde (transportation) | Talent | Reference / existing selection only |
| Tinker | Mass Interface | Talent | Reference / existing selection only |
| Tinker | Multifunctional Gizmos | Talent | Reference / existing selection only |
| Tinker | Redundant Systems | Talent | Reference / existing selection only |
| Tinker | Security Measures [utility] | Talent | Reference / existing selection only |
| Tinker | Tinker Savvy [utility] | Talent | Reference / existing selection only |

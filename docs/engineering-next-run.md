# Engineering handoff

## Scope and status

The full Tech/Tinker effects and augment/graft goal is **not complete**. Continue it without treating catalog descriptions or roster entries as functional implementations. Do not deploy or rebuild the portable package unless separately requested.

Read `AGENTS.md`, the current worktree, and `docs/engineering-status.md` first. The per-device table in that ledger is the detailed inventory of implemented and missing functions. Earlier chronological entries can describe work that later entries completed; use current code and the latest entries to resolve that.

## Recent implemented work

- Pressure Jack contextual lifting, extension, crushing and cooperative-jack values.
- Spring Boots pressure lifecycle, battery enhancement, jump context and advanced jump duration spending.
- Pressure Sensor crafting prerequisites, hazard-only bonus, explicit normal/quick activation, upkeep, separately paid tremorsense, automatic paid renewal and fuel exhaustion.
- Optional saved close/medium/long/extra-long detector construction; talent/rank gates; broken-level scaling. Tinker extra-long range is 1,000 + 100 feet per gizmo level.
- Advanced wearable Pressure Sensor construction: requires Augmentation and Advanced Transmission, forces close range, needs no upkeep while worn, retains separately paid tremorsense. Removing it ends its benefit.
- Optional Effortless Detection construction: confirmed full-round activation; battery quick activation grants a separate 100-rounds-per-effective-level operation timer. This does not grant tremorsense. Both time-advance paths and transfer preserve separate clocks.
- Tech Load Bearer carrying-capacity projection; supported augment/graft installation and removal; separate implant slots, overload handling, bio/retained-innate polymorph exceptions; Machinehead Custom Graft lifecycle. These are partial systems, not all devices or installation rules.

## Next implementation priorities

1. Finish detector integration: ordinary detector flat-footed must affect shared defenses rather than remain a manual reminder. Preserve class/feat exceptions and existing user conditions. Add contextual hazard-check actions without granting a global Perception bonus.
2. Implement the remaining detector types and saved accommodations: parameters, conductive signals, reliable detection, data uplink, security detectors, wearable variants and signal interactions. Do not silently add optional construction improvements to old devices.
3. Complete Pressure Weapon equipment attachments and effects, Innate Jack and mechanoid integration; remaining Spring Boots legendary options.
4. Complete remaining Tech and Tinker function-level recipes and effects using the ledger's roster-only/partial rows. Reuse shared modifiers, movement, attacks, resource transactions and timers; keep Tech and Tinker rules distinct.
5. Complete installation rules: nonstandard anatomy, external recipients, device-specific incompatibilities, combined devices/accessories, supplemental/natural prosthetics, all graft-compatible effects, remaining Machinehead features, and polymorph interactions. Do not equate ordinary equipment slots with dedicated augment or graft slots.
6. Complete drones/mechanoids, AI, routines, projects, piloting, innate gizmos, tradition restrictions/boons, class-specific devices, Prodigy engineering interactions, external technological-item battery hosts and creation-feat integration.
7. Complete automatic device actions in the Martial Book and verify current official-source catalog coverage. A general campaign clock/crafting ledger remains pending; current game-round advancement is explicit.

## Rules and compatibility checks

- Verify each function against its official Spheres source; report uncertain rules as “Needs rules verification.”
- Effortless Detection currently deactivates a non-wearable detector when its paid operation period ends. Verify any intended transition to ordinary maintained operation before changing that behavior; do not assume an unpaid extension.
- Detector operation and tremorsense are separate costs/timers. Wearable upkeep exemption does not grant free powered tremorsense.
- Remaining cross-timer edge case: a single large time advance that crosses both the paid operation expiry and several tremorsense renewals needs chronological resource-accounting verification. The current operation-expiry pass precedes renewal and may skip batteries that would have been spent before shutdown. Add a regression and resolve this before claiming complete detector time simulation.
- Report an interval only once: wearer-turn end or elapsed rounds, not both.
- Construction choices persist even if current talents change; creation gates do not retroactively rewrite records.
- Preserve saves, manual overrides, supporting-battery remapping and formula identity remapping. Additive fields default safely for old characters.

## Validation and delivery

Run focused tests and the relevant engineering/database/transfer/recovery checks after changes. Run a new full isolated suite for a substantial follow-up and distinguish known baseline failures.

The last full isolated run (`artifacts/engineering-validation-spring-boots/summary.json`) recorded 2,063 passed and three pre-existing failures: class-mechanics archetype count, custom tracker canvas parenting, and obsolete tradition-layout placement assertion (with a secondary Windows SQLite cleanup error). Do not silently fix unrelated failures or claim the full suite is green.

Before ending: update the per-device ledger and this handoff as appropriate, review the diff, commit validated changes and push `main`, verify remote HEAD and clean worktree. No deployment is part of this handoff.

# Craft Marvelous Items handoff

Status: foundational pricing only; the complete feature is not implemented.

## Implemented

- Pure `app/marvelous_item_rules.py` base-effect pricing and save DC.
- Daily activation tiers, unlimited activation at five-use pricing, and fifty-total-use construction.
- Input validation and focused regression coverage. No database, UI or catalog changes.
- Verified against https://spheresofpower.wikidot.com/magical-items.

## Required next

1. Verify and implement talent-based complexity (including spell points, duration and advanced effects), prerequisite checks, creation DC/time/cost, traditions and optional construction multipliers. The current function takes resolved complexity; never substitute raw talent count.
2. Reuse `app/crafting_catalog.py`, `app/services/crafting.py`, existing equipment persistence and reference-data import tooling. Do not duplicate the item database or assume ordinary PF1 crafting applies unchanged.
3. Import all current Marvelous Items from the official Marvelous Items and Marvelous Items 2 pages with stable identifiers/provenance; distinguish Original/Ultimate and third-party options. Slotted charms/apparatus are not automatically Marvelous Items.
4. Build a custom composer with live price, explicit effect selections, prerequisites and activation options. Allow manual Name, Slot and Description overrides without changing mechanical effect identity.
5. Integrate supported effects with shared modifiers/resources/recovery, clearly mark unsupported effects for manual handling, and cover persistence/import/export and cancellation.
6. Run relevant crafting/equipment tests and the isolated suite; distinguish existing failures. Review, commit and push successful work. Do not deploy unless requested.

Existing Tech/Tinker work remains incomplete; see `engineering-next-run.md` and `engineering-status.md`. Do not claim all engineering effects are automated.

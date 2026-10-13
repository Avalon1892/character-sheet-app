# Craft Marvelous Items handoff

Status: base pricing and explicit complexity/crafting estimates; the complete feature is not implemented.

## Implemented

- Pure `app/marvelous_item_rules.py` base-effect pricing and save DC.
- Daily activation tiers, unlimited activation at five-use pricing, and fifty-total-use construction.
- Input validation and focused regression coverage. No database, UI or catalog changes.
- Exact fractional complexity, alternative-effect pricing, range/duration steps, activation adjustments and explicit unique changes. The item caster level must meet its complexity.
- Separate Spheres crafting estimates: half-price materials, DC 10 + caster level + 5 per bypassable missing talent, minimum work duration, distraction and adventuring rates. This does not reuse the PF1 DC 5 + caster level.
- Focused verification: 34 tests passed across `test_marvelous_item_rules.py` and existing `test_crafting.py`.
- Explicit prerequisite checks are exposed through `CraftingService.marvelous_requirements`: creation feat equivalence, permanent sphere caster levels, cooperative access, ordinary versus advanced talents, protected features and prohibited abilities. Versatile Crafter bypasses missing base spheres and caster-level deficits with separate DC costs. Validated results feed the quote without double-counting; blocked plans cannot produce a validated quote.
- Character access beyond saved feats must still be supplied explicitly by the future composer/provider; live casting statistics are not a safe permanent-crafting-level source.
- Verified against https://spheresofpower.wikidot.com/magical-items.
- Added a reproducible build-time importer for both Marvelous Items pages. 122 construction entries/recipes use shared inventory identities, preserve reviewed automation and retain unrelated records. Catalog manifest hashes/sizes are updated. Existing legacy records remain for saved-character compatibility.
- Crafting browser now exposes these recipes with Spheres DC 10 + CL; it does not offer unvalidated prerequisite waivers or PF accelerated-crafting assumptions. Published scaling/variable prices require explicit input rather than mixing a low-tier price with high-tier construction cost.
- Import is not effect automation. Creature-targeted, mythic, scaling and special item behaviors remain unimplemented unless existing equipment automation already supports the item.

## Required next

1. Implement sphere-specific base-power and talent contributions (including extra spell points and advanced effects), automatic permanent-access collection, traditions and remaining optional multipliers. The current functions accept explicit verified contributions/access; they do not yet map catalog talents automatically. Never substitute raw talent count. Advanced talents, creation feats and protected class requirements cannot be waived; base sphere/CL bypass requires Versatile Crafter.
2. Reuse `app/crafting_catalog.py`, `app/services/crafting.py`, existing equipment persistence and reference-data import tooling. Do not duplicate the item database or assume ordinary PF1 crafting applies unchanged.
3. Verify catalog coverage beyond the 122 construction entries imported from the two official pages (including entries without normal construction requirements and class-page items). Verify edition tags and grouped item variants, then implement structured sphere/talent prerequisite metadata; current text is preserved but not runtime-parsed. Slotted charms/apparatus are not automatically Marvelous Items.
4. Build a custom composer with live price, explicit effect selections, prerequisites and activation options. Allow manual Name, Slot and Description overrides without changing mechanical effect identity.
5. Integrate supported effects with shared modifiers/resources/recovery, clearly mark unsupported effects for manual handling, and cover persistence/import/export and cancellation.
6. Run relevant crafting/equipment tests and the isolated suite; distinguish existing failures. Review, commit and push successful work. Do not deploy unless requested.

Existing Tech/Tinker work remains incomplete; see `engineering-next-run.md` and `engineering-status.md`. Do not claim all engineering effects are automated.

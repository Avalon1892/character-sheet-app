# Craft Marvelous Items handoff

Status: pricing, prerequisite checks, catalog import and initial custom composer; the complete feature is not implemented.

## Implemented

- Pure `app/marvelous_item_rules.py` base-effect pricing and save DC.
- Daily activation tiers, unlimited activation at five-use pricing, and fifty-total-use construction.
- Input validation and focused regression coverage; saved-character compatibility uses existing equipment fields.
- Exact fractional complexity, alternative-effect pricing, range/duration steps, activation adjustments and explicit unique changes. The item caster level must meet its complexity.
- Separate Spheres crafting estimates: half-price materials, DC 10 + caster level + 5 per bypassable missing talent, minimum work duration, distraction and adventuring rates. This does not reuse the PF1 DC 5 + caster level.
- Focused verification: 34 tests passed across `test_marvelous_item_rules.py` and existing `test_crafting.py`.
- Explicit prerequisite checks are exposed through `CraftingService.marvelous_requirements`: creation feat equivalence, permanent sphere caster levels, cooperative access, ordinary versus advanced talents, protected features and prohibited abilities. Versatile Crafter bypasses missing base spheres and caster-level deficits with separate DC costs. Validated results feed the quote without double-counting; blocked plans cannot produce a validated quote.
- Character access beyond saved feats must still be supplied explicitly by the future composer/provider; live casting statistics are not a safe permanent-crafting-level source.
- Verified against https://spheresofpower.wikidot.com/magical-items.
- Added a reproducible build-time importer for both Marvelous Items pages. 122 construction entries/recipes use shared inventory identities, preserve reviewed automation and retain unrelated records. Catalog manifest hashes/sizes are updated. Existing legacy records remain for saved-character compatibility.
- Crafting browser now exposes these recipes with Spheres DC 10 + CL; it does not offer unvalidated prerequisite waivers or PF accelerated-crafting assumptions. Published scaling/variable prices require explicit input rather than mixing a low-tier price with high-tier construction cost.
- Import is not effect automation. Creature-targeted, mythic, scaling and special item behaviors remain unimplemented unless existing equipment automation already supports the item.
- Custom composer on the Crafting page for characters with Craft Marvelous Item / Craft Wondrous Item. Live quotes, talent contribution controls, action/use choices and manual Name/Slot/Description. Stores blueprint in additive `automation_json` metadata via CraftingService; no custom schema or duplicate item database. Effect automation is explicitly marked rules-only. No gold is deducted and no project is marked completed.
- Latest focused run: 46 passed (`test_marvelous_crafting_ui`, `test_marvelous_item_rules`, `test_marvelous_item_import`, `test_crafting`).
- Structured base powers: 34 choices with published range/duration defaults, bounded adjustment ladders, and explicit calculated base-effect projections. Supports temporary HP, blast dice, teleport distance, darkness radius, transformation trait count and construct/undead HD limits. These projections are not application of effects to characters/targets. Manual descriptions remain independent. Metadata now also preserves the calculated base effect.
- Custom item activation resources now persist in the existing equipment metadata: daily, unlimited and 50-total-use modes; ownership/quantity validation and atomic zero-floor spending. Full Rest resets daily uses only. No separate trackers can become orphaned when deleting an item.
- `Use Marvelous Items` dialog displays remaining uses, calculated base effect and activation controls. Unmodified Life temporary-HP powers can apply to self atomically with spending; they do not stack or reduce a larger existing temporary-HP pool. Modified/unsupported effects require explicit manual-effect confirmation. Stacked devices must be split into separate inventory records.
- Duration expiration is still manual and explicitly stated. Published catalog items do not yet receive custom-blueprint activation tracking automatically. Keep this distinction visible; neither named-item coverage nor complete effect automation is proven.

## Required next

1. Implement sphere-specific base-power and talent contributions (including extra spell points and advanced effects), automatic permanent-access collection, traditions and remaining optional multipliers. The current functions accept explicit verified contributions/access; they do not yet map catalog talents automatically. Never substitute raw talent count. Advanced talents, creation feats and protected class requirements cannot be waived; base sphere/CL bypass requires Versatile Crafter.
2. Reuse `app/crafting_catalog.py`, `app/services/crafting.py`, existing equipment persistence and reference-data import tooling. Do not duplicate the item database or assume ordinary PF1 crafting applies unchanged.
3. Verify catalog coverage beyond the 122 construction entries imported from the two official pages (including entries without normal construction requirements and class-page items). Verify edition tags and grouped item variants, then implement structured sphere/talent prerequisite metadata; current text is preserved but not runtime-parsed. Slotted charms/apparatus are not automatically Marvelous Items.
4. Complete the initial composer: automatic talent/SP contributions and exceptions, alternative-effect groups, creation eligibility, saved-blueprint re-editing, costly components and project completion. General contribution defaults currently require explicit review, not inferred rules. Base-power previews do not yet incorporate every talent's changed effect. Visual inspection in both supported themes remains required.
5. Integrate supported effects with shared modifiers/resources/recovery, clearly mark unsupported effects for manual handling, and cover persistence/import/export and cancellation.
6. Run relevant crafting/equipment tests and the isolated suite; distinguish existing failures. Review, commit and push successful work. Do not deploy unless requested.

Existing Tech/Tinker work remains incomplete; see `engineering-next-run.md` and `engineering-status.md`. Do not claim all engineering effects are automated.

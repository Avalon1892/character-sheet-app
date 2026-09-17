# Item creation documentation

The existing feat catalog contained short index summaries for Pathfinder crafting
feats. `tools/import_item_creation_rules.py` compares it against the Archives of
Nethys Item Creation index and imports full feat rules, including technological
crafting feats and Master Craftsman. It also updates Spheres crafting conversions
from the magical-items page and supplies the missing Forge Construct entry.

`data/pf1e/item_creation_rules.json` stores the imported full descriptions and
formatted rules. `app/item_creation_rules.py` merges feat supplements by stable
catalog key, retaining existing identities and avoiding duplicate selections.
Automation is still supplied by the existing feat automation layer, not by parsing
these descriptions. Existing saved characters are not rewritten.

Supporting core crafting rules, campaign guidance, optional dynamic creation,
construct building/modifications, fleshwarping, and Spheres item creation are
registered as the `crafting` reference family. The index links to existing feat
entries and the Craft skill reference instead of copying them into another catalog.
Previously imported crafting traditions remain under Traditions.

The import preserves tables, source credits, and source links. License notices are
in `data/pf1e/reference_rules_LICENSE.txt`. No crafting automation or Review
requirements are introduced by this documentation update.

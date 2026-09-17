from __future__ import annotations

import json
import re
from functools import cached_property, lru_cache
from pathlib import Path

from app.catalog_versions import active_catalog_root

from app.feat_automation import feat_automation
from app.talent_automation import magic_automation, martial_automation
from app.trait_automation import trait_automation
from app.item_effects import automation_dict, automation_for_entry
from app.item_enchantments import COMPOSABLE_ITEM_ENTRIES, enchantment_spec
from app.codex_descriptions import (
    normalize_spheres_archetype_codex_entry,
    normalize_spheres_class_codex_entry,
)
from app.class_packages import enrich_archetype_from_package, enrich_class_from_package
from app.class_packages.loader import supplemental_archetype_entries


DATA_ROOT = active_catalog_root()


@lru_cache(maxsize=64)
def _load_json(path_text: str) -> dict:
    """Load one immutable bundled document once across catalog gateways."""

    with Path(path_text).open(encoding="utf-8") as file:
        return json.load(file)


# The casting-traditions page continues with drawback feats, general boons,
# and class-specific drawbacks after the Weather section.  Older imports kept
# attributing those later headings to Weather.  These reviewed section ranges
# protect both current saved catalogs and future catalog refreshes.
SPHERE_DRAWBACK_TOC_RANGES: dict[str, tuple[int, int]] = {
    "Alteration": (68, 74), "Blood": (76, 80), "Conjuration": (82, 90),
    "Creation": (92, 98), "Dark": (100, 110), "Death": (112, 119),
    "Destruction": (121, 126), "Divination": (128, 132),
    "Enhancement": (134, 139), "Fallen Fey": (141, 141),
    "Fate": (143, 149), "Illusion": (151, 157), "Life": (159, 167),
    "Light": (169, 176), "Mana": (178, 181), "Mind": (183, 192),
    "Nature": (194, 195), "Protection": (197, 206),
    "Telekinesis": (213, 218), "Time": (220, 223), "War": (225, 234),
    "Warp": (236, 245), "Weather": (247, 251),
}


def reviewed_sphere_drawback(entry: dict, sphere_name: str) -> bool:
    if str(entry.get("category", "")) != "Drawback":
        return True
    source = str(entry.get("source_url", ""))
    match = re.search(r"casting-traditions#toc(\d+)", source)
    limits = SPHERE_DRAWBACK_TOC_RANGES.get(sphere_name)
    if match is None or limits is None:
        return True
    return limits[0] <= int(match.group(1)) <= limits[1]


class RulesCatalog:
    """Read-only gateway for bundled rules data and its automation metadata."""

    def __init__(self, data_root: Path = DATA_ROOT) -> None:
        self.data_root = Path(data_root)

    def _json(self, name: str) -> dict:
        return _load_json(str((self.data_root / name).resolve()))

    @cached_property
    def core(self) -> dict[str, tuple[dict, ...]]:
        result = {
            category: tuple(self._json(f"{category}.json")["entries"])
            for category in ("races", "classes", "armor", "weapons")
        }
        imported = tuple(
            {
                "key": str(entry["key"]).removeprefix("pathfinder-class:"),
                "name": entry["name"], "hit_die": entry["hit_die"], "bab": entry["bab"],
                "fort": entry["fort"], "reflex": entry["reflex"], "will": entry["will"],
                "skill_points": entry["skill_points"], "class_skills": entry.get("class_skill_keys", ()),
                "source": entry.get("source", "Pathfinder RPG"), "source_url": entry.get("source_url", ""),
                "category": entry.get("category", "Pathfinder"),
                "casting": entry.get("casting", {}),
            }
            for entry in self.pathfinder_class_entries()
        )
        spheres = tuple(
            {
                "key": str(entry["key"]),
                "name": entry["name"], "hit_die": entry["hit_die"], "bab": entry["bab"],
                "fort": entry["fort"], "reflex": entry["reflex"], "will": entry["will"],
                "skill_points": entry["skill_points"], "class_skills": entry.get("class_skill_keys", ()),
                "source": entry.get("source", "Spheres of Power Wiki"), "source_url": entry.get("source_url", ""),
                "category": entry.get("category", "Spheres"), "source_group": "Spheres",
                "casting": entry.get("casting", {}), "capabilities": entry.get("capabilities", ()),
            }
            for entry in self.spheres_class_entries()
        )
        result["classes"] = tuple(
            sorted(imported + spheres, key=lambda entry: (str(entry.get("source_group", "Pathfinder")), str(entry["name"]).casefold()))
        )
        return result

    def entries(self, category: str) -> tuple[dict, ...]:
        return self.core[category]

    def entry_by_key(self, category: str, key: str) -> dict | None:
        return next((item for item in self.entries(category) if item["key"] == key), None)

    def entry_by_name(self, category: str, name: str) -> dict | None:
        return next((item for item in self.entries(category) if item["name"] == name), None)

    def race_entries(self, category: str | None = None) -> tuple[dict, ...]:
        result = self.entries("races")
        if category is not None:
            result = tuple(
                entry for entry in result
                if str(entry.get("category") or "Other").casefold() == category.casefold()
            )
        return tuple(sorted(result, key=lambda entry: str(entry["name"]).casefold()))

    def race_entry(self, key: str) -> dict | None:
        return self.entry_by_key("races", key)

    def race_categories(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            str(entry.get("category") or "Other") for entry in self.race_entries()
        ))

    @cached_property
    def martial_document(self) -> dict:
        return self._json("martial_spheres.json")

    def martial_spheres(self) -> tuple[dict, ...]:
        return tuple(self.martial_document["spheres"])

    def martial_sphere(self, name: str) -> dict | None:
        return next(
            (
                sphere
                for sphere in self.martial_spheres()
                if sphere["name"].casefold() == name.casefold()
            ),
            None,
        )

    def martial_entries(self, sphere_name: str | None = None) -> tuple[dict, ...]:
        result: list[dict] = []
        for sphere in self.martial_spheres():
            if sphere_name is not None and sphere["name"] != sphere_name:
                continue
            result.append(
                {
                    "key": f"{sphere['slug']}:base",
                    "name": f"{sphere['name']} Sphere",
                    "category": "Base Sphere",
                    "sphere": sphere["name"],
                    "description": sphere["description"],
                    "prerequisites": "",
                    "source_tags": [],
                    "source_url": sphere["source_url"],
                    "automation": {},
                }
            )
            for source_entry in sphere["talents"]:
                entry = dict(source_entry)
                entry["automation"] = martial_automation(str(entry["name"]))
                result.append(entry)
        return tuple(result)

    def martial_entry(self, key: str) -> dict | None:
        return next((item for item in self.martial_entries() if item["key"] == key), None)

    @cached_property
    def magic_document(self) -> dict:
        return self._json("magic_spheres.json")

    def magic_spheres(self) -> tuple[dict, ...]:
        return tuple(self.magic_document["spheres"])

    def magic_sphere(self, name: str) -> dict | None:
        return next(
            (
                sphere
                for sphere in self.magic_spheres()
                if sphere["name"].casefold() == name.casefold()
            ),
            None,
        )

    def magic_entries(self, sphere_name: str | None = None) -> tuple[dict, ...]:
        result: list[dict] = []
        for sphere in self.magic_spheres():
            if sphere_name is not None and sphere["name"] != sphere_name:
                continue
            result.append(
                {
                    "key": f"{sphere['slug']}:base",
                    "name": f"{sphere['name']} Sphere",
                    "category": "Base Sphere",
                    "sphere": sphere["name"],
                    "description": sphere["description"],
                    "prerequisites": "",
                    "source_tags": [],
                    "source_url": sphere["source_url"],
                    "automation": {},
                }
            )
            for source_entry in sphere["talents"]:
                if not reviewed_sphere_drawback(source_entry, str(sphere["name"])):
                    continue
                entry = dict(source_entry)
                entry["automation"] = magic_automation(str(entry["name"]))
                result.append(entry)
        if sphere_name in (None, "Universal"):
            for source_entry in self.magic_document.get("universal_drawbacks", []):
                entry = dict(source_entry)
                entry["automation"] = magic_automation(str(entry["name"]))
                result.append(entry)
        return tuple(result)

    def magic_entry(self, key: str) -> dict | None:
        return next((item for item in self.magic_entries() if item["key"] == key), None)

    @cached_property
    def tradition_document(self) -> dict:
        """Normalized casting and martial tradition packages from the Spheres wiki."""
        return self._json("traditions.json")

    def tradition_entries(self, kind: str | None = None) -> tuple[dict, ...]:
        from app.optional_traditions import catalog
        result = tuple(self.tradition_document.get("casting_traditions", ())) + tuple(
            self.tradition_document.get("martial_traditions", ())
        ) + tuple(catalog()['entries'])
        if kind is not None:
            result = tuple(
                entry for entry in result
                if str(entry.get("kind", "")).casefold() == kind.casefold()
            )
        return tuple(sorted(result, key=lambda entry: str(entry["name"]).casefold()))

    def tradition_entry(self, key: str) -> dict | None:
        return next((entry for entry in self.tradition_entries() if entry["key"] == key), None)

    @cached_property
    def all_tradition_rule_entries(self) -> tuple[dict, ...]:
        """Project drawbacks and boons into their own Codex-ready catalog.

        Older Spheres imports placed casting-tradition options under the last
        parsed magic sphere. Their stable source anchors preserve the real
        category and sphere, so this adapter corrects presentation without
        mutating the talent catalog used by existing characters.
        """

        result = [dict(entry) for entry in self.tradition_document.get(
            "casting_general_drawbacks", ()
        )]
        casting_sphere_ranges = (
            (66, 66, "Universal"), (68, 74, "Alteration"), (76, 80, "Blood"),
            (82, 90, "Conjuration"), (92, 98, "Creation"), (100, 110, "Dark"),
            (112, 119, "Death"), (121, 126, "Destruction"), (128, 132, "Divination"),
            (134, 139, "Enhancement"), (141, 141, "Fallen Fey"), (143, 149, "Fate"),
            (151, 157, "Illusion"), (159, 167, "Life"), (169, 176, "Light"),
            (178, 181, "Mana"), (183, 192, "Mind"), (194, 195, "Nature"),
            (197, 206, "Protection"), (208, 211, "Technomancy"),
            (213, 218, "Telekinesis"), (220, 223, "Time"), (225, 234, "War"),
            (236, 245, "Warp"), (247, 251, "Weather"),
        )

        def source_toc(entry: dict, page: str) -> int | None:
            match = re.search(rf"{re.escape(page)}#toc(\d+)", str(entry.get("source_url", "")))
            return int(match.group(1)) if match else None

        # Read the raw imported rows here deliberately.  The live magic talent
        # catalog filters headings which were historically misattributed to
        # Weather, while this Codex adapter re-homes those same dual-sphere
        # drawbacks and boons under their correct categories.
        raw_magic_rules = (
            dict(source)
            for sphere_document in self.magic_document.get("spheres", ())
            for source in sphere_document.get("talents", ())
        )
        for source in raw_magic_rules:
            toc = source_toc(source, "casting-traditions")
            if toc is None:
                continue
            category = ""
            sphere = ""
            if 66 <= toc <= 251:
                category = "Sphere-Specific Drawback"
                sphere = next(
                    (name for start, end, name in casting_sphere_ranges if start <= toc <= end),
                    "Universal",
                )
            elif 253 <= toc <= 281:
                category = "Dual Sphere Drawback"
                sphere = "Dual Sphere"
            elif 283 <= toc <= 301:
                category = "Boon"
            if not category:
                continue
            entry = dict(source)
            entry.update({
                "key": f"casting-rule:{toc}:{entry['key']}",
                "kind": "Casting", "category": category, "sphere": sphere,
            })
            result.append(entry)

        for source in self.martial_entries():
            if str(source.get("category")) != "Drawback":
                continue
            entry = dict(source)
            entry.update({
                "key": f"martial-rule:{entry['key']}",
                "kind": "Martial", "category": "Sphere-Specific Drawback",
            })
            result.append(entry)
        from app.optional_traditions import catalog
        result.extend(catalog()['rules'])
        unique = {str(entry["key"]): entry for entry in result}
        return tuple(sorted(
            unique.values(),
            key=lambda entry: (
                str(entry.get("kind", "")).casefold(),
                str(entry.get("category", "")).casefold(),
                str(entry.get("sphere", "")).casefold(),
                str(entry.get("name", "")).casefold(),
            ),
        ))

    def tradition_rule_entries(
        self, kind: str | None = None, category: str | None = None,
        sphere: str | None = None,
    ) -> tuple[dict, ...]:
        return tuple(
            entry for entry in self.all_tradition_rule_entries
            if (kind is None or str(entry.get("kind", "")).casefold() == kind.casefold())
            and (category is None or str(entry.get("category", "")).casefold() == category.casefold())
            and (sphere is None or str(entry.get("sphere", "")).casefold() == sphere.casefold())
        )

    def tradition_rule_entry(self, key: str) -> dict | None:
        return next(
            (entry for entry in self.all_tradition_rule_entries if entry["key"] == key),
            None,
        )

    @cached_property
    def feat_document(self) -> dict:
        return self._json("feats.json")

    @cached_property
    def all_feat_entries(self) -> tuple[dict, ...]:
        from app.item_creation_rules import enriched_feats
        result: list[dict] = []
        for source_entry in enriched_feats(self.feat_document["entries"], self.data_root):
            entry = dict(source_entry)
            entry["categories"] = tuple(entry.get("categories", ("General",)))
            entry["source_tags"] = tuple(entry.get("source_tags", ()))
            entry["automation"] = feat_automation(str(entry["name"]))
            result.append(entry)
        return tuple(
            sorted(result, key=lambda item: (str(item["name"]).casefold(), str(item["source_group"])))
        )

    def feat_entries(self, source_group: str | None = None) -> tuple[dict, ...]:
        if source_group is None:
            return self.all_feat_entries
        return tuple(
            entry
            for entry in self.all_feat_entries
            if entry["source_group"].casefold() == source_group.casefold()
        )

    def feat_entry(self, key: str) -> dict | None:
        return next((item for item in self.all_feat_entries if item["key"] == key), None)

    def feat_categories(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(category)
                    for entry in self.all_feat_entries
                    for category in entry["categories"]
                },
                key=str.casefold,
            )
        )

    @cached_property
    def trait_document(self) -> dict:
        return self._json("traits.json")

    @cached_property
    def all_trait_entries(self) -> tuple[dict, ...]:
        result: list[dict] = []
        for source_entry in self.trait_document["entries"]:
            entry = dict(source_entry)
            entry["categories"] = tuple(entry.get("categories", ("General",)))
            entry["source_tags"] = tuple(entry.get("source_tags", ()))
            entry["automation"] = trait_automation(
                str(entry["name"]), str(entry.get("description", ""))
            )
            result.append(entry)
        return tuple(
            sorted(result, key=lambda item: (str(item["name"]).casefold(), str(item["source_group"])))
        )

    def trait_entries(self, source_group: str | None = None) -> tuple[dict, ...]:
        if source_group is None:
            return self.all_trait_entries
        return tuple(
            entry
            for entry in self.all_trait_entries
            if str(entry["source_group"]).casefold() == source_group.casefold()
        )

    def trait_entry(self, key: str) -> dict | None:
        return next((item for item in self.all_trait_entries if item["key"] == key), None)

    def trait_categories(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(category)
                    for entry in self.all_trait_entries
                    for category in entry["categories"]
                },
                key=str.casefold,
            )
        )

    def trait_sources(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {str(entry["source_group"]) for entry in self.all_trait_entries},
                key=str.casefold,
            )
        )

    @cached_property
    def item_document(self) -> dict:
        return self._json("items.json")

    @cached_property
    def all_item_entries(self) -> tuple[dict, ...]:
        result = []
        for source_entry in (
            *COMPOSABLE_ITEM_ENTRIES,
            *self.item_document.get("entries", ()),
        ):
            entry = dict(source_entry)
            entry["item_automation"] = automation_dict(automation_for_entry(entry))
            result.append(entry)
        return tuple(result)

    def item_entries(
        self,
        source_group: str | None = None,
        family: str | None = None,
        category: str | None = None,
    ) -> tuple[dict, ...]:
        return tuple(
            entry for entry in self.all_item_entries
            if (source_group is None or str(entry["source_group"]).casefold() == source_group.casefold())
            and (family is None or str(entry["family"]).casefold() == family.casefold())
            and (category is None or str(entry["category"]).casefold() == category.casefold())
        )

    def item_entry(self, key: str) -> dict | None:
        return next((entry for entry in self.all_item_entries if entry["key"] == key), None)

    def item_sources(self) -> tuple[str, ...]:
        return tuple(sorted({str(entry["source_group"]) for entry in self.all_item_entries}, key=str.casefold))

    def item_families(self, source_group: str | None = None) -> tuple[str, ...]:
        return tuple(sorted({str(entry["family"]) for entry in self.item_entries(source_group)}, key=str.casefold))

    def item_categories(self, source_group: str | None = None, family: str | None = None) -> tuple[str, ...]:
        return tuple(sorted({str(entry["category"]) for entry in self.item_entries(source_group, family)}, key=str.casefold))

    @cached_property
    def enchantment_document(self) -> dict:
        return self._json("enchantments.json")

    @cached_property
    def all_enchantment_entries(self) -> tuple[dict, ...]:
        result = []
        for source_entry in self.enchantment_document.get("entries", ()):
            entry = dict(source_entry)
            spec = enchantment_spec(str(entry["key"]))
            if spec is not None and spec.effects:
                entry["automation_status"] = "automatic"
            result.append(entry)
        return tuple(result)

    def enchantment_entries(
        self, family: str | None = None, category: str | None = None
    ) -> tuple[dict, ...]:
        return tuple(
            entry for entry in self.all_enchantment_entries
            if (family is None or str(entry["family"]).casefold() == family.casefold())
            and (category is None or str(entry["category"]).casefold() == category.casefold())
        )

    def enchantment_entry(self, key: str) -> dict | None:
        return next(
            (entry for entry in self.all_enchantment_entries if entry["key"] == key),
            None,
        )

    def enchantment_families(self) -> tuple[str, ...]:
        return tuple(sorted({str(entry["family"]) for entry in self.all_enchantment_entries}, key=str.casefold))

    def enchantment_categories(self, family: str | None = None) -> tuple[str, ...]:
        preferred = ("Melee", "Ranged", "Armor", "Shield", "Universal")
        present = {str(entry["category"]) for entry in self.enchantment_entries(family)}
        return tuple(value for value in preferred if value in present)

    @cached_property
    def pathfinder_class_document(self) -> dict:
        return self._json("pathfinder_classes.json")

    def pathfinder_class_entries(self, category: str | None = None) -> tuple[dict, ...]:
        entries = tuple(self.pathfinder_class_document.get("entries", ()))
        if category is None:
            return entries
        return tuple(entry for entry in entries if str(entry["category"]).casefold() == category.casefold())

    def pathfinder_class_entry(self, key: str) -> dict | None:
        return next((entry for entry in self.pathfinder_class_entries() if entry["key"] == key), None)

    def pathfinder_class_categories(self) -> tuple[str, ...]:
        preferred = ("Core Classes", "Base Classes", "Alternate Classes", "Hybrid Classes", "Occult Classes", "Unchained Classes", "Later Classes", "Other Playable Classes")
        present = {str(entry["category"]) for entry in self.pathfinder_class_entries()}
        return tuple(value for value in preferred if value in present)

    @cached_property
    def spheres_class_document(self) -> dict:
        return self._json("spheres_classes.json")

    @cached_property
    def all_spheres_class_entries(self) -> tuple[dict, ...]:
        """Spheres class records projected through the shared Codex cleanup boundary."""

        return tuple(
            enrich_class_from_package(normalize_spheres_class_codex_entry(entry))
            for entry in self.spheres_class_document.get("entries", ())
        )

    def spheres_class_entries(self, category: str | None = None) -> tuple[dict, ...]:
        entries = self.all_spheres_class_entries
        if category is None:
            return entries
        return tuple(
            entry for entry in entries
            if str(entry.get("category", "")).casefold() == category.casefold()
        )

    def spheres_class_entry(self, key: str) -> dict | None:
        return next((entry for entry in self.spheres_class_entries() if entry["key"] == key), None)

    def spheres_class_categories(self) -> tuple[str, ...]:
        preferred = ("Spherecasters", "Practitioners", "Operatives", "Champions", "Prestige Classes")
        present = {str(entry["category"]) for entry in self.spheres_class_entries()}
        return tuple(value for value in preferred if value in present)

    def class_entries(
        self, source_group: str | None = None, category: str | None = None
    ) -> tuple[dict, ...]:
        entries: tuple[dict, ...] = self.pathfinder_class_entries() + self.spheres_class_entries()
        if source_group:
            entries = tuple(
                entry for entry in entries
                if ("Spheres" if str(entry["key"]).startswith("spheres-class:") or entry["key"] == "prodigy" else "Pathfinder").casefold()
                == source_group.casefold()
            )
        if category:
            entries = tuple(
                entry for entry in entries
                if str(entry.get("category", "")).casefold() == category.casefold()
            )
        return tuple(sorted(entries, key=lambda entry: str(entry["name"]).casefold()))

    def class_entry(self, key: str) -> dict | None:
        normalized = key if key.startswith("pathfinder-class:") else f"pathfinder-class:{key}"
        return next(
            (
                entry for entry in self.class_entries()
                if entry["key"] in {key, normalized}
            ),
            None,
        )

    @cached_property
    def class_choice_document(self) -> dict:
        return self._json("class_choices.json")

    def class_choice_entries(
        self,
        family: str | None = None,
        class_name: str | None = None,
    ) -> tuple[dict, ...]:
        entries = tuple(self.class_choice_document.get("entries", ()))
        if family is not None:
            entries = tuple(
                entry for entry in entries
                if str(entry.get("family", "")).casefold() == family.casefold()
            )
        if class_name is not None:
            compatible = tuple(
                entry for entry in entries
                if not entry.get("classes")
                or class_name.casefold() in {
                    str(value).casefold() for value in entry.get("classes", ())
                }
            )
            # Features granted outside their original class still need a usable
            # catalog. Fall back to the full family only when no association fits.
            entries = compatible or entries
        return tuple(sorted(entries, key=lambda entry: str(entry.get("name", "")).casefold()))

    def class_choice_entry(self, key: str) -> dict | None:
        return next(
            (
                entry for entry in self.class_choice_entries()
                if str(entry.get("key")) == key
            ),
            None,
        )

    @cached_property
    def class_power_document(self) -> dict:
        return self._json("class_powers.json")

    def class_power_families(self) -> tuple[dict, ...]:
        declared = {
            str(entry.get("key") or ""): dict(entry)
            for entry in self.class_power_document.get("families", ())
            if str(entry.get("key") or "")
        }
        for entry in self.class_power_document.get("entries", ()):
            key = str(entry.get("family") or "General")
            declared.setdefault(
                key,
                {"key": key, "label": key.replace("_", " ").title(), "source_url": ""},
            )
        return tuple(
            sorted(declared.values(), key=lambda entry: str(entry.get("label") or "").casefold())
        )

    def class_power_family_label(self, family: str) -> str:
        return next(
            (
                str(entry.get("label") or family.replace("_", " ").title())
                for entry in self.class_power_families()
                if str(entry.get("key") or "").casefold() == family.casefold()
            ),
            family.replace("_", " ").title(),
        )

    def class_power_entries(
        self,
        family: str | None = None,
        class_name: str | None = None,
        category: str | None = None,
    ) -> tuple[dict, ...]:
        entries = tuple(self.class_power_document.get("entries", ()))
        if family is not None:
            entries = tuple(
                entry for entry in entries
                if str(entry.get("family", "")).casefold() == family.casefold()
            )
        if class_name is not None:
            entries = tuple(
                entry for entry in entries
                if not entry.get("classes")
                or class_name.casefold() in {
                    str(value).casefold() for value in entry.get("classes", ())
                }
            )
        if category is not None:
            entries = tuple(
                entry for entry in entries
                if str(entry.get("category", "")).casefold() == category.casefold()
            )
        return tuple(sorted(entries, key=lambda entry: str(entry.get("name", "")).casefold()))

    def class_power_entry(self, key: str) -> dict | None:
        return next(
            (entry for entry in self.class_power_entries() if str(entry.get("key")) == key),
            None,
        )

    @cached_property
    def archetype_document(self) -> dict:
        return self._json("archetypes.json")

    @cached_property
    def spheres_class_archetype_document(self) -> dict:
        return self._json("spheres_class_archetypes.json")

    @cached_property
    def all_archetype_entries(self) -> tuple[dict, ...]:
        """Deduplicated archetypes with Spheres wiki prose normalized once."""

        combined = tuple(self.archetype_document.get("entries", ())) + tuple(
            self.spheres_class_archetype_document.get("entries", ())
        ) + supplemental_archetype_entries()
        # The Pathfinder/Spheres archetype index contains a few deliberately
        # hand-reviewed compatibility declarations (notably Prodigy).  The
        # class-page importer discovers the same entries while importing every
        # Spheres base class.  Keep the reviewed index record when keys overlap.
        unique: dict[str, dict] = {}
        for source_entry in combined:
            key = str(source_entry["key"])
            if key in unique:
                # Preserve hand-reviewed compatibility/prose while allowing the
                # complete class-page importer to enrich that same archetype
                # with declarative mechanics and reusable choice groups.
                for field in ("class_modifications", "choices", "features"):
                    if source_entry.get(field):
                        unique[key][field] = source_entry[field]
                continue
            entry = (
                normalize_spheres_archetype_codex_entry(source_entry)
                if str(source_entry.get("source_group", "")).casefold() == "spheres"
                else source_entry
            )
            unique[key] = enrich_archetype_from_package(entry)
        # A duplicate may have enriched the retained index record after its
        # first package overlay. Reapply the overlay once to keep the package
        # authoritative for runtime mechanics while catalogs own prose.
        unique = {
            key: enrich_archetype_from_package(entry)
            for key, entry in unique.items()
        }
        return tuple(unique.values())

    def archetype_entries(
        self,
        class_key: str | None = None,
        source_group: str | None = None,
    ) -> tuple[dict, ...]:
        entries = self.all_archetype_entries
        if class_key is not None:
            accepted_keys = {class_key}
            if not class_key.startswith("pathfinder-class:") and class_key != "prodigy":
                accepted_keys.add(f"pathfinder-class:{class_key}")
            entries = tuple(entry for entry in entries if entry["class_key"] in accepted_keys)
        if source_group is not None:
            entries = tuple(
                entry for entry in entries
                if str(entry["source_group"]).casefold() == source_group.casefold()
            )
        return entries

    def archetype_entry(self, key: str) -> dict | None:
        return next((entry for entry in self.archetype_entries() if entry["key"] == key), None)

    def archetype_sources(self, class_key: str | None = None) -> tuple[str, ...]:
        return tuple(
            sorted(
                {str(entry["source_group"]) for entry in self.archetype_entries(class_key)},
                key=str.casefold,
            )
        )

    @cached_property
    def spell_document(self) -> dict:
        return self._json("spells.json")

    @cached_property
    def all_spell_entries(self) -> tuple[dict, ...]:
        return tuple(self.spell_document.get("entries", ()))

    def spell_entries(
        self,
        source_group: str | None = None,
        publisher: str | None = None,
        class_name: str | None = None,
    ) -> tuple[dict, ...]:
        return tuple(
            entry for entry in self.all_spell_entries
            if (source_group is None or str(entry.get("source_group", "")).casefold() == source_group.casefold())
            and (publisher is None or str(entry.get("publisher", "")).casefold() == publisher.casefold())
            and (
                class_name is None
                or class_name.casefold() in {
                    str(value).casefold() for value in (entry.get("class_levels") or {}).keys()
                }
            )
        )

    def spell_entry(self, key: str) -> dict | None:
        return next((entry for entry in self.all_spell_entries if entry["key"] == key), None)

    def spell_sources(self) -> tuple[str, ...]:
        return tuple(
            sorted({str(entry["source_group"]) for entry in self.all_spell_entries}, key=str.casefold)
        )

    def spell_publishers(self, source_group: str | None = None) -> tuple[str, ...]:
        return tuple(
            sorted(
                {str(entry.get("publisher") or "Unknown") for entry in self.spell_entries(source_group)},
                key=str.casefold,
            )
        )


DEFAULT_CATALOG = RulesCatalog()

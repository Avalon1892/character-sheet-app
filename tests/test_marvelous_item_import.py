from tools.import_marvelous_items import parse_page, merge_records


def test_import_construction_and_skip_non_items():
    html = '''<div id="page-content"><h3>Not An Item</h3><p>General advice.</p>
    <h3 id="toc1">Example [TS]</h3><p>Aura weak Life; CL 3rd</p>
    <p>Slot neck; Price 2,400 gp; Weight 2 lbs.</p><p>Heal a target.</p>
    <h4>Construction Requirements</h4><p>Craft Marvelous Item, Life sphere; Cost 1,200 gp</p>
    <h3 id="toc2">Another</h3><p>No construction rules.</p></div>'''
    entries, recipes = parse_page(html, "marvelous-items")
    assert len(entries) == len(recipes) == 1
    assert entries[0]["key"] == "spheres:marvelous-items:example"
    assert entries[0]["slot"] == "neck"
    assert entries[0]["weight_lb"] == 2
    assert recipes[0]["caster_level"] == 3
    assert recipes[0]["creation_cost_gp"] == 1200
    assert recipes[0]["system"] == "spheres"


def test_merge_preserves_automation_order_and_unrelated_records():
    old = [{"key": "a", "name": "A", "automation": {"ac_bonus": 2}},
           {"key": "b", "name": "B"}]
    updated = merge_records(old, [{"key": "a", "name": "Improved", "automation": {}},
                                  {"key": "c", "name": "C"}])
    assert [x["key"] for x in updated] == ["a", "b", "c"]
    assert updated[0]["automation"] == {"ac_bonus": 2}
    assert updated[1]["name"] == "B"


def test_imported_pages_share_inventory_and_crafting_identities():
    from app.catalogs import DEFAULT_CATALOG
    from app.crafting_catalog import crafting_document
    from app.catalog_versions import inspect_catalog, BUNDLED_CATALOG_ROOT
    recipes = [r for r in crafting_document()["recipes"] if r.get("system") == "spheres"
               and r.get("category") == "Marvelous Items"]
    assert len(recipes) == 122
    assert {r["source_url"].rsplit("/", 1)[-1] for r in recipes} == {"marvelous-items", "marvelous-items-2"}
    for recipe in recipes:
        entry = DEFAULT_CATALOG.item_entry(recipe["item_key"])
        assert entry is not None
        assert entry["name"] == recipe["name"]
        assert "Construction Requirements" in entry["description"]
    assert inspect_catalog(BUNDLED_CATALOG_ROOT, "Bundled").valid

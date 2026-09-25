"""Read-only Bestiary filtering and presentation, shared by browser and Codex."""
from dataclasses import dataclass
from html import escape
from urllib.parse import quote

from app.catalog_search import CatalogSearchIndex


@dataclass(frozen=True)
class BestiaryFilters:
    minimum_cr: float | None = None
    maximum_cr: float | None = None
    kind: str = ""
    creature_type: str = ""
    subtype: str = ""
    environment: str = ""
    size: str = ""
    alignment: str = ""
    roles: tuple[str, ...] = ()
    movement: str = ""
    abilities: str = ""
    defenses: str = ""
    source: str = ""
    include_legacy: bool = True

    def matches(self, entry: dict) -> bool:
        cr = entry.get("cr_value")
        if self.minimum_cr is not None and (cr is None or cr < self.minimum_cr):
            return False
        if self.maximum_cr is not None and (cr is None or cr > self.maximum_cr):
            return False
        for field, value in (("type", self.creature_type), ("size", self.size), ("alignment", self.alignment)):
            if value and entry.get(field) != value:
                return False
        for field, value in (("kinds", self.kind), ("subtypes", self.subtype), ("movement", self.movement)):
            if value and value not in entry.get(field, ()):
                return False
        if not set(self.roles).issubset(entry.get("roles", ())):
            return False
        for field, value in (("environment", self.environment), ("special_abilities", self.abilities),
                             ("defenses", self.defenses), ("source", self.source)):
            if value.strip().casefold() not in str(entry.get(field, "")).casefold():
                return False
        return self.include_legacy or not entry.get("legacy_35", False)


class BestiaryIndex:
    def __init__(self, entries):
        self.entries = tuple(entries)
        self.search_index = CatalogSearchIndex(self.entries)

    def values(self, field: str) -> list[str]:
        values = set()
        for entry in self.entries:
            value = entry.get(field, "")
            values.update(value if isinstance(value, (list, tuple)) else [value])
        return sorted(filter(None, values), key=str.casefold)

    def search(self, query="", mode="name", filters=None, sort="name", limit=300):
        filters = filters or BestiaryFilters()
        def order(entry):
            name = entry["name"].casefold()
            cr = entry.get("cr_value")
            if sort == "cr_desc":
                return (cr is None, -(cr or 0), name)
            if sort == "cr":
                return (cr is None, cr or 0, name)
            return (name, entry["key"])
        return self.search_index.search(query, mode, predicate=filters.matches, sort_key=order, limit=limit)


def creature_html(entry: dict | None) -> str:
    if not entry:
        return "<p>Select a creature to read its statistics and abilities.</p>"
    tags = " · ".join((*entry.get("kinds", ()), *entry.get("roles", ())))
    warning = "<p><b>Legacy 3.5 entry:</b> check conversion before play.</p>" if entry.get("legacy_35") else ""
    ability_groups = "".join(f"<p><b>{escape(group)}:</b> {escape('; '.join(values))}</p>"
                             for group, values in entry.get("ability_tags", {}).items())
    ability_groups = "<h3>Ability tags</h3>" + ability_groups if ability_groups else ""
    return (f"<p>{escape(tags)}</p>{warning}" + entry.get("statblock_html", "") +
            ability_groups +
            f'<hr><p><a href="{escape(entry["source_url"], quote=True)}">Original source and publication credits</a></p>')


def bestiary_index_html(catalog, kind="") -> str:
    entries = [e for e in catalog.bestiary_entries() if not kind or kind in e.get("kinds", ())]
    data = catalog.bestiary
    rows = []
    for entry in entries:
        rows.append(f'<tr><td><a href="codex:bestiary:{quote(entry["key"], safe="")}">{escape(entry["name"])}</a></td>'
                    f'<td>{escape(entry["cr"])}</td><td>{escape(entry["type"])}</td>'
                    f'<td>{escape(entry["environment"])}</td></tr>')
    return (f"<h1>Bestiary{(' · ' + escape(kind)) if kind else ''}</h1>"
            f"<p>{len(entries):,} entries. Use the Bestiary menu for combined filters and encounters.</p>"
            f"<p>Archives of Nethys PF1 indexes: {data.get('imported_pages', 0):,} / "
            f"{data.get('indexed_unique_pages', 0):,} source pages imported. "
            "Published entries only; this is not every third-party or unpublished NPC.</p>"
            '<table cellpadding="5"><tr><th>Name</th><th>CR</th><th>Type</th><th>Environment</th></tr>' +
            "".join(rows) + "</table>")

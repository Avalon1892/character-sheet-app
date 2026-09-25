"""Read-only Bestiary filtering and presentation, shared by browser and Codex."""
from dataclasses import dataclass
from html import escape
from urllib.parse import quote

from app.catalog_search import CatalogSearchIndex


def filter_options(value: str | tuple[str, ...]) -> tuple[str, ...]:
    """Semicolons separate alternatives without breaking names containing commas."""
    return tuple(part.strip() for part in (value.split(";") if isinstance(value, str) else value) if part.strip())


@dataclass(frozen=True)
class BestiaryFilters:
    minimum_cr: float | None = None
    maximum_cr: float | None = None
    kind: str | tuple[str, ...] = ""
    creature_type: str | tuple[str, ...] = ""
    subtype: str | tuple[str, ...] = ""
    environment: str | tuple[str, ...] = ""
    size: str | tuple[str, ...] = ""
    alignment: str | tuple[str, ...] = ""
    challenge_ratings: str | tuple[str, ...] = ""
    roles: tuple[str, ...] = ()
    excluded_roles: tuple[str, ...] = ()
    movement: str | tuple[str, ...] = ""
    abilities: str | tuple[str, ...] = ""
    defenses: str | tuple[str, ...] = ""
    source: str | tuple[str, ...] = ""
    include_legacy: bool = True

    def __post_init__(self):
        for field in ("kind", "creature_type", "subtype", "environment", "size", "alignment",
                      "challenge_ratings", "movement", "abilities", "defenses", "source"):
            object.__setattr__(self, field, filter_options(getattr(self, field)))

    def matches(self, entry: dict) -> bool:
        cr = entry.get("cr_value")
        if self.minimum_cr is not None and (cr is None or cr < self.minimum_cr):
            return False
        if self.maximum_cr is not None and (cr is None or cr > self.maximum_cr):
            return False
        for field, value in (("type", self.creature_type), ("size", self.size), ("alignment", self.alignment), ("cr", self.challenge_ratings)):
            if value and entry.get(field) not in value:
                return False
        for field, value in (("kinds", self.kind), ("subtypes", self.subtype), ("movement", self.movement)):
            if value and not set(value).intersection(entry.get(field, ())):
                return False
        if not set(self.roles).issubset(entry.get("roles", ())):
            return False
        if set(self.excluded_roles).intersection(entry.get("roles", ())):
            return False
        for field, value in (("environment", self.environment), ("special_abilities", self.abilities),
                             ("defenses", self.defenses), ("source", self.source)):
            if value and not any(option.casefold() in str(entry.get(field, "")).casefold() for option in value):
                return False
        return self.include_legacy or not entry.get("legacy_35", False)


class BestiaryIndex:
    def __init__(self, entries):
        self.entries = tuple(entries)
        self.search_index = CatalogSearchIndex(self.entries)
        self.documents = {document.record["key"]: document for document in self.search_index.documents}

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
        alternatives = filter_options(query)
        if len(alternatives) <= 1:
            return self.search_index.search(alternatives[0] if alternatives else "", mode, predicate=filters.matches, sort_key=order, limit=limit)
        needles = tuple(value.casefold() for value in alternatives)
        def matches(entry):
            if not filters.matches(entry):
                return False
            document = self.documents[entry["key"]]
            texts = (document.description,) if mode == "description" else (document.name, document.description) if mode == "both" else (document.name,)
            return any(needle in text for needle in needles for text in texts)
        return self.search_index.search("", predicate=matches, sort_key=order, limit=limit)


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

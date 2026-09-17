from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


SEARCH_MODES = ("name", "description", "both")


@dataclass(frozen=True, slots=True)
class CatalogSearchDocument:
    record: dict
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class CatalogSearchResult:
    records: tuple[dict, ...]
    total: int
    limited: bool


class CatalogSearchIndex:
    """Small in-memory index shared by catalog browsers.

    Searchable strings are normalized once when a dialog opens. Filtering never
    rebuilds long description strings and rendering can be bounded independently.
    """

    def __init__(
        self,
        records: Iterable[dict],
        *,
        name_field: str = "name",
        description_fields: tuple[str, ...] = ("description",),
    ) -> None:
        self.documents = tuple(
            CatalogSearchDocument(
                record,
                str(record.get(name_field, "")).casefold(),
                " ".join(str(record.get(field, "")) for field in description_fields).casefold(),
            )
            for record in records
        )

    def search(
        self,
        query: str,
        mode: str = "name",
        *,
        predicate: Callable[[dict], bool] | None = None,
        sort_key: Callable[[dict], object] | None = None,
        limit: int = 250,
    ) -> CatalogSearchResult:
        if mode not in SEARCH_MODES:
            mode = "name"
        needle = query.strip().casefold()
        matches: list[dict] = []
        total = 0
        for document in self.documents:
            if predicate is not None and not predicate(document.record):
                continue
            if needle:
                found = (
                    needle in document.name
                    if mode == "name"
                    else needle in document.description
                    if mode == "description"
                    else needle in document.name or needle in document.description
                )
                if not found:
                    continue
            total += 1
            if sort_key is not None or len(matches) < limit:
                matches.append(document.record)
        if sort_key is not None:
            matches.sort(key=sort_key)
            matches = matches[:limit]
        return CatalogSearchResult(tuple(matches), total, total > len(matches))

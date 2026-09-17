"""Load reviewed class-family automation without coupling it to catalogs/UI."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Mapping

from app.class_packages.schemas import ClassFamilyPackage, class_family_package


PACKAGE_ROOT = Path(__file__).resolve().parent / "definitions"
CLASS_ROOT = PACKAGE_ROOT / "classes"
ARCHETYPE_ROOT = PACKAGE_ROOT / "archetypes"
ARCHETYPE_RUNTIME_ROOT = PACKAGE_ROOT / "archetype_runtime"
ARCHETYPE_PROFILE_ROOT = PACKAGE_ROOT / "archetype_profiles"
ARCHETYPE_SOURCE_ROOT = PACKAGE_ROOT / "archetype_sources"


@lru_cache(maxsize=1)
def supplemental_archetype_entries() -> tuple[dict, ...]:
    """Reviewed imports of archetypes embedded in a base class source page."""
    return tuple(dict(entry) for path in sorted(ARCHETYPE_SOURCE_ROOT.glob("*.json"))
                 for entry in _json(path).get("entries", ())
                 if isinstance(entry, Mapping) and entry.get("key"))


def _json(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"Class package must be an object: {path}")
    return value


@lru_cache(maxsize=1)
def all_class_packages() -> tuple[ClassFamilyPackage, ...]:
    if not CLASS_ROOT.exists():
        return ()
    return tuple(
        class_family_package(_json(path))
        for path in sorted(CLASS_ROOT.glob("*.json"))
    )


@lru_cache(maxsize=64)
def class_package(class_key: str) -> ClassFamilyPackage | None:
    normalized = (
        class_key
        if class_key == "prodigy" or class_key.startswith(("pathfinder-class:", "spheres-class:"))
        else f"pathfinder-class:{class_key}"
    )
    return next(
        (package for package in all_class_packages() if package.class_key == normalized),
        None,
    )


def enrich_class_from_package(entry: Mapping[str, object]) -> dict:
    """Layer reviewed class mechanics over immutable imported catalog prose.

    The import remains the source of documentation.  Packages supply only
    structured fields whose meaning has been reviewed, so runtime rules never
    need to scrape a class table or proficiency paragraph.
    """

    result = dict(entry)
    package = class_package(str(entry.get("key") or ""))
    if package is None:
        return result
    for field, value in package.catalog_profile.items():
        if field == "feature_descriptions" or value in (None, ""):
            continue
        result[field] = value
    descriptions = {
        str(key).casefold(): str(value)
        for key, value in dict(
            package.catalog_profile.get("feature_descriptions") or {}
        ).items()
        if str(key) and str(value)
    }
    if descriptions and result.get("features"):
        result["features"] = [
            {
                **dict(feature),
                "description": str(feature.get("description") or "")
                or descriptions.get(str(feature.get("name") or "").casefold(), ""),
            }
            for feature in result["features"]
            if isinstance(feature, Mapping)
        ]
    result["automation_package"] = package.class_key
    return result


@lru_cache(maxsize=1)
def _archetype_packages() -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not ARCHETYPE_ROOT.exists():
        return result
    for path in sorted(ARCHETYPE_ROOT.glob("*.json")):
        document = _json(path)
        for entry in document.get("entries", ()):
            if isinstance(entry, Mapping) and str(entry.get("key") or ""):
                result[str(entry["key"])] = dict(entry)
    return result


def archetype_package(key: str) -> dict | None:
    entry = _archetype_packages().get(str(key))
    return dict(entry) if entry is not None else None


@lru_cache(maxsize=1)
def _archetype_runtime_packages() -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not ARCHETYPE_RUNTIME_ROOT.exists():
        return result
    for path in sorted(ARCHETYPE_RUNTIME_ROOT.glob("*.json")):
        document = _json(path)
        for entry in document.get("entries", ()):
            if isinstance(entry, Mapping) and str(entry.get("key") or ""):
                result[str(entry["key"])] = dict(entry)
    return result


def archetype_runtime_package(key: str) -> dict | None:
    entry = _archetype_runtime_packages().get(str(key))
    return dict(entry) if entry is not None else None


@lru_cache(maxsize=1)
def _reviewed_archetype_profiles() -> dict[str, dict]:
    """Load hand-reviewed profile declarations kept outside generated files.

    ``definitions/archetypes`` is reproducible imported output.  Statistics,
    casting conversions, proficiency exchanges, and exact player choices need
    human review, so they live in a separate overlay directory that catalog
    regeneration can never overwrite.
    """

    result: dict[str, dict] = {}
    if not ARCHETYPE_PROFILE_ROOT.exists():
        return result
    for path in sorted(ARCHETYPE_PROFILE_ROOT.glob("*.json")):
        document = _json(path)
        for entry in document.get("entries", ()):
            if isinstance(entry, Mapping) and str(entry.get("key") or ""):
                result[str(entry["key"])] = dict(entry)
    return result


def reviewed_archetype_profile(key: str) -> dict | None:
    entry = _reviewed_archetype_profiles().get(str(key))
    return dict(entry) if entry is not None else None


def enrich_archetype_from_package(entry: Mapping[str, object]) -> dict:
    """Overlay build-time-normalized mechanics onto one catalog archetype.

    Full descriptions and source attribution remain catalog-owned.  Only the
    structured mechanics fields are overlaid, so catalog releases can update
    documentation without silently changing reviewed runtime behavior.
    """

    result = dict(entry)
    package = archetype_package(str(entry.get("key") or ""))
    reviewed = reviewed_archetype_profile(str(entry.get("key") or ""))
    if package is None and reviewed is None:
        return result
    if package is not None:
        for field in (
            "replaces_features",
            "removed_features",
            "removed_feature_clauses",
            "compatibility",
            "class_modifications",
            "choices",
            "features",
            "detected_systems",
        ):
            if package.get(field) not in (None, [], {}, ""):
                result[field] = package[field]
        result["automation_package"] = str(package.get("package") or "")
    if reviewed is not None:
        for field in (
            "class_modifications",
            "sphere_capabilities",
            "choices",
            "compatibility",
            "removed_features",
        ):
            if field in reviewed:
                result[field] = reviewed[field]
        level_overrides = {
            str(name).casefold(): max(1, int(level))
            for name, level in dict(
                reviewed.get("feature_level_overrides") or {}
            ).items()
        }
        if level_overrides and result.get("features"):
            result["features"] = [
                {
                    **dict(feature),
                    "level": level_overrides.get(
                        str(feature.get("name") or "").casefold(),
                        int(feature.get("level") or 1),
                    ),
                }
                for feature in result["features"]
                if isinstance(feature, Mapping)
            ]
        include_names = {
            str(name).casefold()
            for name in reviewed.get("feature_include_names", ())
            if str(name).strip()
        }
        exclude_names = {
            str(name).casefold()
            for name in reviewed.get("feature_exclude_names", ())
            if str(name).strip()
        }
        if (include_names or exclude_names) and result.get("features"):
            result["features"] = [
                feature
                for feature in result["features"]
                if isinstance(feature, Mapping)
                and (
                    not include_names
                    or str(feature.get("name") or "").casefold() in include_names
                )
                and str(feature.get("name") or "").casefold() not in exclude_names
            ]
        additions = tuple(
            dict(feature)
            for feature in reviewed.get("feature_additions", ())
            if isinstance(feature, Mapping)
            and str(feature.get("name") or "")
        )
        if additions:
            existing = {
                (
                    int(feature.get("level") or 1),
                    str(feature.get("name") or "").casefold(),
                )
                for feature in result.get("features", ())
                if isinstance(feature, Mapping)
            }
            result["features"] = list(result.get("features") or ()) + [
                feature
                for feature in additions
                if (
                    int(feature.get("level") or 1),
                    str(feature.get("name") or "").casefold(),
                )
                not in existing
            ]
            result["features"].sort(
                key=lambda feature: (
                    int(feature.get("level") or 1),
                    str(feature.get("name") or "").casefold(),
                )
            )
        result["reviewed_profile"] = True
    return result

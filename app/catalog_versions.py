"""Versioned, rollback-safe local rules-catalog releases."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import uuid
import zipfile

from app.paths import APP_DATA_DIR


BUNDLED_CATALOG_ROOT = Path(__file__).resolve().parent.parent / "data" / "pf1e"
MANIFEST_NAME = "catalog_manifest.json"
SUPPORTED_MANIFEST_SCHEMA = 1


@dataclass(frozen=True, slots=True)
class CatalogReleaseInfo:
    version: str
    schema_version: int
    created_utc: str
    root: Path
    source: str


@dataclass(frozen=True, slots=True)
class CatalogValidationResult:
    valid: bool
    release: CatalogReleaseInfo | None
    errors: tuple[str, ...] = ()


def _read_manifest(root: Path) -> dict:
    with (Path(root) / MANIFEST_NAME).open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("Catalog manifest must be a JSON object.")
    return value


def _safe_relative_path(value: object) -> Path:
    text = str(value or "").replace("\\", "/")
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"Unsafe catalog path: {text!r}")
    return Path(*pure.parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_catalog(root: Path, source: str, *, verify_hashes: bool = True) -> CatalogValidationResult:
    root = Path(root)
    errors: list[str] = []
    try:
        manifest = _read_manifest(root)
        schema = int(manifest.get("schema_version", 0))
        if schema != SUPPORTED_MANIFEST_SCHEMA:
            errors.append(
                f"Unsupported manifest schema {schema}; expected {SUPPORTED_MANIFEST_SCHEMA}."
            )
        version = str(manifest.get("catalog_version") or "").strip()
        if not version:
            errors.append("Catalog version is missing.")
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            errors.append("Catalog manifest contains no files.")
            files = []
        seen: set[Path] = set()
        for record in files:
            if not isinstance(record, dict):
                errors.append("Catalog file declaration is not an object.")
                continue
            relative = _safe_relative_path(record.get("path"))
            if relative in seen:
                errors.append(f"Duplicate catalog file: {relative.as_posix()}.")
                continue
            seen.add(relative)
            path = root / relative
            if not path.is_file():
                errors.append(f"Missing catalog file: {relative.as_posix()}.")
                continue
            try:
                expected_size = int(record.get("size", -1))
            except (TypeError, ValueError):
                expected_size = -1
            if expected_size >= 0 and path.stat().st_size != expected_size:
                errors.append(f"Size mismatch: {relative.as_posix()}.")
            if verify_hashes:
                expected_hash = str(record.get("sha256") or "").casefold()
                if len(expected_hash) != 64 or _sha256(path) != expected_hash:
                    errors.append(f"Hash mismatch: {relative.as_posix()}.")
            try:
                with path.open(encoding="utf-8") as stream:
                    json.load(stream)
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                errors.append(f"Invalid JSON in {relative.as_posix()}: {error}.")
        release = CatalogReleaseInfo(
            version or "unknown",
            schema,
            str(manifest.get("created_utc") or ""),
            root,
            source,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return CatalogValidationResult(False, None, (str(error),))
    return CatalogValidationResult(not errors, release, tuple(errors))


class CatalogVersionManager:
    def __init__(
        self,
        app_data_dir: Path = APP_DATA_DIR,
        bundled_root: Path = BUNDLED_CATALOG_ROOT,
    ) -> None:
        self.app_data_dir = Path(app_data_dir)
        self.bundled_root = Path(bundled_root)
        self.catalog_root = self.app_data_dir / "catalogs" / "pf1e"
        self.current_root = self.catalog_root / "current"
        self.history_root = self.catalog_root / "history"

    def bundled_release(self, *, verify_hashes: bool = False) -> CatalogValidationResult:
        return inspect_catalog(self.bundled_root, "Bundled", verify_hashes=verify_hashes)

    def installed_release(self, *, verify_hashes: bool = False) -> CatalogValidationResult:
        return inspect_catalog(self.current_root, "Installed update", verify_hashes=verify_hashes)

    def active_release(self, *, verify_hashes: bool = False) -> CatalogValidationResult:
        installed = self.installed_release(verify_hashes=verify_hashes)
        if installed.valid:
            return installed
        return self.bundled_release(verify_hashes=verify_hashes)

    def active_root(self) -> Path:
        result = self.active_release(verify_hashes=False)
        if not result.valid or result.release is None:
            raise RuntimeError("Neither the installed nor bundled rules catalog is valid.")
        return result.release.root

    def install_package(self, package: Path) -> CatalogReleaseInfo:
        package = Path(package)
        if not package.is_file():
            raise ValueError("Choose an existing catalog package.")
        self.catalog_root.mkdir(parents=True, exist_ok=True)
        staging = self.catalog_root / f"staging-{uuid.uuid4().hex}"
        staging.mkdir()
        try:
            with zipfile.ZipFile(package) as archive:
                members = {name.replace("\\", "/"): name for name in archive.namelist()}
                if MANIFEST_NAME not in members:
                    raise ValueError("The package has no root catalog_manifest.json.")
                manifest = json.loads(archive.read(members[MANIFEST_NAME]).decode("utf-8"))
                (staging / MANIFEST_NAME).write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                for record in manifest.get("files", ()):
                    relative = _safe_relative_path(record.get("path"))
                    member_name = relative.as_posix()
                    if member_name not in members:
                        raise ValueError(f"Package is missing {member_name}.")
                    target = staging / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(members[member_name]) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
            validation = inspect_catalog(staging, "Staged update", verify_hashes=True)
            if not validation.valid or validation.release is None:
                raise ValueError("Catalog validation failed: " + " ".join(validation.errors))
            self._archive_current()
            staging.replace(self.current_root)
            return CatalogReleaseInfo(
                validation.release.version,
                validation.release.schema_version,
                validation.release.created_utc,
                self.current_root,
                "Installed update",
            )
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)

    def _archive_current(self) -> Path | None:
        if not self.current_root.exists():
            return None
        self.history_root.mkdir(parents=True, exist_ok=True)
        try:
            version = _read_manifest(self.current_root).get("catalog_version", "unknown")
        except (OSError, ValueError, json.JSONDecodeError):
            version = "invalid"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target = self.history_root / f"{version}-{stamp}"
        if target.exists():
            target = self.history_root / f"{version}-{stamp}-{uuid.uuid4().hex[:8]}"
        self.current_root.replace(target)
        return target

    def restore_bundled(self) -> Path | None:
        """Deactivate an update without deleting its files or character data."""
        return self._archive_current()

    def activate_history(self, root: Path) -> CatalogReleaseInfo:
        """Make one validated rollback copy current while retaining the prior release."""
        root = Path(root).resolve()
        history_root = self.history_root.resolve()
        if root.parent != history_root or not root.is_dir():
            raise ValueError("Choose a catalog release from the rollback list.")
        validation = inspect_catalog(root, "Rollback copy", verify_hashes=True)
        if not validation.valid or validation.release is None:
            raise ValueError("Rollback validation failed: " + " ".join(validation.errors))
        self._archive_current()
        root.replace(self.current_root)
        return CatalogReleaseInfo(
            validation.release.version,
            validation.release.schema_version,
            validation.release.created_utc,
            self.current_root,
            "Installed update",
        )

    def create_package(self, destination: Path, root: Path | None = None) -> Path:
        root = Path(root or self.active_root())
        validation = inspect_catalog(root, "Export", verify_hashes=True)
        if not validation.valid:
            raise ValueError("Cannot export invalid catalog: " + " ".join(validation.errors))
        manifest = _read_manifest(root)
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(root / MANIFEST_NAME, MANIFEST_NAME)
            for record in manifest["files"]:
                relative = _safe_relative_path(record["path"])
                archive.write(root / relative, relative.as_posix())
        return destination

    def history(self) -> tuple[CatalogReleaseInfo, ...]:
        if not self.history_root.exists():
            return ()
        result = []
        for root in sorted(self.history_root.iterdir(), reverse=True):
            validation = inspect_catalog(root, "Rollback copy", verify_hashes=False)
            if validation.release is not None:
                result.append(validation.release)
        return tuple(result)


def active_catalog_root() -> Path:
    """Return a complete installed update or fall back to bundled data."""
    return CatalogVersionManager().active_root()

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.catalog_versions import CatalogVersionManager, inspect_catalog
from app.ui.catalog_manager_dialog import CatalogManagerDialog


def _catalog(root: Path, version: str, value: str = "base") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"entries": [{"key": value}]}, indent=2).encode()
    (root / "classes.json").write_bytes(payload)
    manifest = {
        "schema_version": 1,
        "catalog_version": version,
        "created_utc": "2026-07-29T00:00:00Z",
        "application_schema_min": 1,
        "files": [
            {
                "path": "classes.json",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        ],
    }
    (root / "catalog_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return root


class CatalogVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bundled = _catalog(self.root / "bundled", "1.0.0")
        self.manager = CatalogVersionManager(self.root / "app-data", self.bundled)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_validated_package_install_is_atomic_and_restorable(self) -> None:
        update = _catalog(self.root / "update", "2.0.0", "updated")
        package = self.manager.create_package(self.root / "update.zip", update)
        release = self.manager.install_package(package)
        self.assertEqual("2.0.0", release.version)
        self.assertEqual(self.manager.current_root, self.manager.active_root())
        self.assertTrue(self.manager.active_release(verify_hashes=True).valid)

        archived = self.manager.restore_bundled()
        self.assertIsNotNone(archived)
        self.assertEqual(self.bundled, self.manager.active_root())
        self.assertEqual("2.0.0", self.manager.history()[0].version)

    def test_invalid_update_does_not_replace_current_release(self) -> None:
        good = _catalog(self.root / "good", "2.0.0", "good")
        self.manager.install_package(
            self.manager.create_package(self.root / "good.zip", good)
        )
        before = self.manager.active_root()
        invalid = self.root / "invalid.zip"
        with zipfile.ZipFile(invalid, "w") as archive:
            archive.writestr(
                "catalog_manifest.json",
                json.dumps(
                    {
                        "schema_version": 1,
                        "catalog_version": "3.0.0",
                        "files": [
                            {"path": "../escape.json", "sha256": "0" * 64, "size": 2}
                        ],
                    }
                ),
            )
        with self.assertRaises(ValueError):
            self.manager.install_package(invalid)
        self.assertEqual(before, self.manager.active_root())
        self.assertEqual("2.0.0", self.manager.active_release().release.version)

    def test_validated_history_release_can_be_reactivated(self) -> None:
        first = _catalog(self.root / "first", "2.0.0", "first")
        second = _catalog(self.root / "second", "3.0.0", "second")
        self.manager.install_package(
            self.manager.create_package(self.root / "first.zip", first)
        )
        self.manager.install_package(
            self.manager.create_package(self.root / "second.zip", second)
        )
        previous = next(
            release for release in self.manager.history() if release.version == "2.0.0"
        )

        restored = self.manager.activate_history(previous.root)

        self.assertEqual("2.0.0", restored.version)
        self.assertEqual(
            "2.0.0", self.manager.active_release(verify_hashes=True).release.version
        )
        self.assertTrue(
            any(release.version == "3.0.0" for release in self.manager.history())
        )

    def test_dialog_projects_active_and_bundled_versions(self) -> None:
        self.assertTrue(inspect_catalog(self.bundled, "Bundled").valid)
        dialog = CatalogManagerDialog(self.manager)
        self.assertEqual("1.0.0", dialog.bundled.text())
        self.assertIn("1.0.0", dialog.active.text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()

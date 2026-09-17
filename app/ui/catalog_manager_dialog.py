"""Non-destructive catalog release manager."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.catalog_versions import CatalogVersionManager


class CatalogManagerDialog(QDialog):
    def __init__(self, manager: CatalogVersionManager | None = None, parent=None) -> None:
        super().__init__(parent)
        self.manager = manager or CatalogVersionManager()
        self.setWindowTitle("Rules Catalog Updates")
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        title = QLabel("RULES CATALOG RELEASES")
        title.setObjectName("heroTitle")
        layout.addWidget(title)
        note = QLabel(
            "Catalog files are versioned independently from characters. Updates are fully "
            "validated and staged before activation; existing updates become rollback copies. "
            "Restart the app after changing the active catalog."
        )
        note.setObjectName("mutedText")
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.bundled = QLabel()
        self.active = QLabel()
        self.location = QLabel()
        self.location.setWordWrap(True)
        form.addRow("Bundled release", self.bundled)
        form.addRow("Active release", self.active)
        form.addRow("Active location", self.location)
        layout.addLayout(form)

        verify = QPushButton("Verify active catalog")
        verify.clicked.connect(self._verify)
        install = QPushButton("Install catalog package…")
        install.setObjectName("primaryButton")
        install.clicked.connect(self._install)
        export = QPushButton("Export active catalog package…")
        export.clicked.connect(self._export)
        bundled = QPushButton("Restore bundled catalog…")
        bundled.clicked.connect(self._restore_bundled)
        for button in (verify, install, export, bundled):
            layout.addWidget(button)

        history_title = QLabel("ROLLBACK COPIES")
        history_title.setObjectName("sectionTitle")
        layout.addWidget(history_title)
        self.history = QListWidget()
        self.history.currentRowChanged.connect(self._update_rollback_action)
        layout.addWidget(self.history, 1)
        self.rollback = QPushButton("Activate selected rollback…")
        self.rollback.clicked.connect(self._activate_rollback)
        layout.addWidget(self.rollback)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()

    def refresh(self) -> None:
        bundled = self.manager.bundled_release()
        active = self.manager.active_release()
        self.bundled.setText(
            bundled.release.version if bundled.release is not None else "Invalid"
        )
        self.active.setText(
            f"{active.release.version} ({active.release.source})"
            if active.release is not None
            else "Invalid"
        )
        self.location.setText(
            str(active.release.root) if active.release is not None else "—"
        )
        self.history.clear()
        for release in self.manager.history():
            self.history.addItem(f"{release.version}  ·  {release.root.name}")
            self.history.item(self.history.count() - 1).setData(
                Qt.ItemDataRole.UserRole, str(release.root)
            )
        if self.history.count() == 0:
            self.history.addItem("No previous installed updates")
        self._update_rollback_action()

    def _update_rollback_action(self, _row: int = -1) -> None:
        item = self.history.currentItem()
        self.rollback.setEnabled(
            item is not None
            and bool(item.data(Qt.ItemDataRole.UserRole))
        )

    def _activate_rollback(self) -> None:
        item = self.history.currentItem()
        root = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not root:
            return
        answer = QMessageBox.question(
            self,
            "Activate rollback",
            f"Activate catalog {item.text()}? The current update will remain available as another rollback copy.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            release = self.manager.activate_history(Path(root))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Catalog rollback rejected", str(error))
            return
        self.refresh()
        QMessageBox.information(
            self,
            "Catalog rollback ready",
            f"Catalog {release.version} is active. Restart the app to complete the change.",
        )

    def _verify(self) -> None:
        result = self.manager.active_release(verify_hashes=True)
        if result.valid and result.release is not None:
            QMessageBox.information(
                self,
                "Catalog verified",
                f"Catalog {result.release.version} passed file, hash and JSON validation.",
            )
            return
        QMessageBox.warning(
            self, "Catalog validation failed", "\n".join(result.errors)
        )

    def _install(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Install rules catalog", "", "Catalog packages (*.zip)"
        )
        if not filename:
            return
        try:
            release = self.manager.install_package(Path(filename))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Catalog update rejected", str(error))
            return
        self.refresh()
        QMessageBox.information(
            self,
            "Catalog update installed",
            f"Catalog {release.version} is ready. Restart the app to activate it everywhere.",
        )

    def _export(self) -> None:
        active = self.manager.active_release()
        version = active.release.version if active.release is not None else "catalog"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export rules catalog",
            f"Character-Sheet-Catalog-{version}.zip",
            "Catalog packages (*.zip)",
        )
        if not filename:
            return
        if not filename.casefold().endswith(".zip"):
            filename += ".zip"
        try:
            path = self.manager.create_package(Path(filename))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Catalog export failed", str(error))
            return
        QMessageBox.information(self, "Catalog exported", str(path))

    def _restore_bundled(self) -> None:
        installed = self.manager.installed_release()
        if not installed.valid:
            QMessageBox.information(
                self, "Bundled catalog active", "There is no installed update to deactivate."
            )
            return
        answer = QMessageBox.question(
            self,
            "Restore bundled catalog",
            "Deactivate the installed update and retain it as a rollback copy? "
            "Character records will not be changed.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.manager.restore_bundled()
        self.refresh()
        QMessageBox.information(
            self, "Bundled catalog restored", "Restart the app to complete the change."
        )

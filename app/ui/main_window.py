from __future__ import annotations

import html
import json
import re
import urllib.parse
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QFont, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import CharacterRepository
from app.models import CHARACTER_TYPES, CharacterSummary
from app.ui.customization import SheetCustomizationController
from app.ui.dialogs import RestConfigurationDialog
from app.ui.sheet_types import (
    DEFAULT_SHEET_TYPE,
    SHEET_TYPE_REGISTRY,
    normalize_sheet_type,
    sheet_type_descriptors,
)
from app.presentation_storage import SheetStyleStore
from app.ui.sheet_layout_presets import layout_preset_for_character_type
from app.ui.theme import THEME_LABELS, normalize_theme, style_sheet
from app.ui.character_library import CharacterLibraryEntry, CharacterLibraryPage
from app.transfer import export_character, import_character
from app.prodigy_content import PRODIGY_SOURCE_URL, prodigy_codex_html
from app.catalogs import DEFAULT_CATALOG
from app.catalog_search import CatalogSearchIndex
from app.codex_index import build_codex_search_records, codex_name_search_key
from app.recovery import FullRestEngine
from app.formula_codex import FORMULA_CODEX_HTML, FORMULA_SEARCH_TEXT
from app.character_advancement_codex import (
    CHARACTER_ADVANCEMENT_SEARCH_TEXT,
    character_advancement_codex_html,
)
from app.building_blocks.persistence import BuildingBlockRepository
from app.building_blocks.registry import register_builtin_blocks
from app.building_blocks.runtime import BlockRuntimeController
from app.building_blocks.tabs import SheetTabManager
from app.building_blocks.catalog import BuildingBlocksDialog
from app.building_blocks.nested_editor import NestedCellEditor
from app.presentation_history import PresentationHistory, PresentationSnapshot
from app.runtime_paths import application_folder
from app.character_creation import apply_character_creation_draft
from app.archetype_presentation import archetype_collection_row_html, archetype_rules_html
from app.ui.character_creation_dialog import GuidedCharacterCreationDialog
from app.ui.catalog_manager_dialog import CatalogManagerDialog
from app.ui.floating_notes import FloatingNoteManager, FloatingNoteWidget
from app.text_cleanup import repair_mojibake


class CodexDialog(QDialog):
    def __init__(self, initial_page: str = "home", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rules Codex")
        self.resize(1120, 760)
        self._search_index: CatalogSearchIndex | None = None
        layout = QVBoxLayout(self)
        heading = QLabel("CODEX")
        heading.setObjectName("heroTitle")
        subtitle = QLabel("Pathfinder 1e and Spheres rules reference")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(heading)
        layout.addWidget(subtitle)

        search_row = QHBoxLayout()
        self.codex_search = QLineEdit()
        self.codex_search.setPlaceholderText("Search the entire Codex…")
        self.codex_search_mode = QComboBox()
        self.codex_search_mode.addItem("Name and description", "both")
        self.codex_search_mode.addItem("Name only", "name")
        self.codex_search_mode.addItem("Description only", "description")
        search_button = QPushButton("Search")
        search_button.setObjectName("primaryButton")
        search_row.addWidget(self.codex_search, 1)
        search_row.addWidget(self.codex_search_mode)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(245)
        self.tree.setMaximumWidth(340)
        home = QTreeWidgetItem(("Codex Home",))
        home.setData(0, Qt.ItemDataRole.UserRole, "home")
        self.tree.addTopLevelItem(home)
        bestiary = QTreeWidgetItem(("Bestiary",))
        bestiary.setData(0, Qt.ItemDataRole.UserRole, {"kind": "bestiary"})
        for kind, label in (("Monster", "Monsters"), ("NPC", "NPCs"), ("Unique", "Unique creatures"), ("Mythic", "Mythic creatures")):
            node = QTreeWidgetItem((label,))
            node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "bestiary", "entry_kind": kind})
            bestiary.addChild(node)
        classes = QTreeWidgetItem(("Classes",))
        pathfinder = QTreeWidgetItem(("Pathfinder",))
        spheres = QTreeWidgetItem(("Spheres",))
        pathfinder.setData(0, Qt.ItemDataRole.UserRole, "pathfinder")
        spheres.setData(0, Qt.ItemDataRole.UserRole, "spheres")
        prodigy = None
        for source_group, source_node, category_names in (
            ("Pathfinder", pathfinder, DEFAULT_CATALOG.pathfinder_class_categories()),
            ("Spheres", spheres, DEFAULT_CATALOG.spheres_class_categories()),
        ):
            for category_name in category_names:
                category_node = QTreeWidgetItem((category_name,))
                category_node.setData(0, Qt.ItemDataRole.UserRole, {
                    "kind": "classes", "source_group": source_group, "category": category_name,
                })
                for entry in DEFAULT_CATALOG.class_entries(source_group, category_name):
                    class_node = QTreeWidgetItem((str(entry["name"]),))
                    class_node.setData(
                        0,
                        Qt.ItemDataRole.UserRole,
                        "prodigy" if entry["key"] == "prodigy" else {"kind": "class", "key": entry["key"]},
                    )
                    if entry["key"] == "prodigy":
                        prodigy = class_node
                    for source_name in DEFAULT_CATALOG.archetype_sources(str(entry["key"])):
                        archetype_source = QTreeWidgetItem((f"{source_name} Archetypes",))
                        archetype_source.setData(0, Qt.ItemDataRole.UserRole, {
                            "kind": "archetypes", "class_key": entry["key"], "source": source_name,
                        })
                        for archetype in DEFAULT_CATALOG.archetype_entries(str(entry["key"]), source_name):
                            archetype_node = QTreeWidgetItem((str(archetype["name"]),))
                            archetype_node.setData(0, Qt.ItemDataRole.UserRole, {
                                "kind": "archetype", "key": archetype["key"],
                            })
                            archetype_source.addChild(archetype_node)
                        class_node.addChild(archetype_source)
                    category_node.addChild(class_node)
                source_node.addChild(category_node)
        classes.addChild(pathfinder)
        classes.addChild(spheres)
        class_choices = QTreeWidgetItem(("Class Feature Choices",))
        class_choices.setData(
            0, Qt.ItemDataRole.UserRole, {"kind": "class_choices"}
        )
        choice_family_labels = {
            "domain": "Domains & Subdomains",
            "inquisition": "Inquisitions",
            "bloodline": "Bloodlines",
            "mystery": "Mysteries",
            "arcane_school": "Arcane Schools",
        }
        choice_families = sorted(
            {
                str(entry.get("family") or "General")
                for entry in DEFAULT_CATALOG.class_choice_entries()
            },
            key=lambda value: choice_family_labels.get(value, value).casefold(),
        )
        for family in choice_families:
            family_node = QTreeWidgetItem(
                (choice_family_labels.get(family, family.replace("_", " ").title()),)
            )
            family_node.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"kind": "class_choices", "family": family},
            )
            for entry in DEFAULT_CATALOG.class_choice_entries(family):
                entry_node = QTreeWidgetItem((str(entry["name"]),))
                entry_node.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"kind": "class_choice", "key": entry["key"]},
                )
                family_node.addChild(entry_node)
            class_choices.addChild(family_node)
        classes.addChild(class_choices)
        class_powers = QTreeWidgetItem(("Class Powers",))
        class_powers.setData(0, Qt.ItemDataRole.UserRole, {"kind": "class_powers"})
        for family in sorted(
            {str(entry.get("family") or "General") for entry in DEFAULT_CATALOG.class_power_entries()},
            key=lambda value: DEFAULT_CATALOG.class_power_family_label(value).casefold(),
        ):
            family_node = QTreeWidgetItem((DEFAULT_CATALOG.class_power_family_label(family),))
            family_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "class_powers", "family": family})
            categories = sorted(
                {str(entry.get("category") or "General") for entry in DEFAULT_CATALOG.class_power_entries(family)},
                key=str.casefold,
            )
            for category in categories:
                category_node = QTreeWidgetItem((category,))
                category_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "class_powers", "family": family, "category": category})
                for entry in DEFAULT_CATALOG.class_power_entries(family, category=category):
                    entry_node = QTreeWidgetItem((str(entry["name"]),))
                    entry_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "class_power", "key": entry["key"]})
                    category_node.addChild(entry_node)
                family_node.addChild(category_node)
            class_powers.addChild(family_node)
        classes.addChild(class_powers)
        self.tree.addTopLevelItem(classes)
        self.tree.addTopLevelItem(bestiary)
        races_root = QTreeWidgetItem(("Races",))
        races_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "races"})
        for category_name in DEFAULT_CATALOG.race_categories():
            category_node = QTreeWidgetItem((f"{category_name} Races",))
            category_node.setData(0, Qt.ItemDataRole.UserRole, {
                "kind": "races", "category": category_name,
            })
            for entry in DEFAULT_CATALOG.race_entries(category_name):
                race_node = QTreeWidgetItem((str(entry["name"]),))
                race_node.setData(0, Qt.ItemDataRole.UserRole, {
                    "kind": "race", "key": entry["key"],
                })
                category_node.addChild(race_node)
            races_root.addChild(category_node)
        self.tree.addTopLevelItem(races_root)
        spells_root = QTreeWidgetItem(("Spells",))
        spells_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "spells"})
        for source_name in DEFAULT_CATALOG.spell_sources():
            source_node = QTreeWidgetItem((source_name,))
            source_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "spells", "source": source_name})
            for publisher_name in DEFAULT_CATALOG.spell_publishers(source_name):
                publisher_node = QTreeWidgetItem((publisher_name,))
                publisher_node.setData(0, Qt.ItemDataRole.UserRole, {
                    "kind": "spells", "source": source_name, "publisher": publisher_name,
                })
                source_node.addChild(publisher_node)
            spells_root.addChild(source_node)
        self.tree.addTopLevelItem(spells_root)
        items_root = QTreeWidgetItem(("Equipment & Items",))
        items_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "items"})
        for source_name in DEFAULT_CATALOG.item_sources():
            source_node = QTreeWidgetItem((source_name,))
            source_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "items", "source": source_name})
            for family_name in DEFAULT_CATALOG.item_families(source_name):
                family_node = QTreeWidgetItem((family_name,))
                family_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "items", "source": source_name, "family": family_name})
                for category_name in DEFAULT_CATALOG.item_categories(source_name, family_name):
                    category_node = QTreeWidgetItem((category_name,))
                    category_node.setData(0, Qt.ItemDataRole.UserRole, {
                        "kind": "items", "source": source_name, "family": family_name, "category": category_name,
                    })
                    family_node.addChild(category_node)
                source_node.addChild(family_node)
            items_root.addChild(source_node)
        self.tree.addTopLevelItem(items_root)
        enchantments_root = QTreeWidgetItem(("Enchantments",))
        enchantments_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "enchantments"})
        for family_name in DEFAULT_CATALOG.enchantment_families():
            family_node = QTreeWidgetItem((family_name,))
            family_node.setData(0, Qt.ItemDataRole.UserRole, {
                "kind": "enchantments", "family": family_name,
            })
            for category_name in DEFAULT_CATALOG.enchantment_categories(family_name):
                category_node = QTreeWidgetItem((category_name,))
                category_node.setData(0, Qt.ItemDataRole.UserRole, {
                    "kind": "enchantments", "family": family_name,
                    "category": category_name,
                })
                family_node.addChild(category_node)
            enchantments_root.addChild(family_node)
        self.tree.addTopLevelItem(enchantments_root)
        talents_root = QTreeWidgetItem(("Talents",))
        talents_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "feature_index", "title": "Talents"})
        for family, label, spheres_list, entries_provider in (
            ("martial", "Martial Talents", DEFAULT_CATALOG.martial_spheres(), DEFAULT_CATALOG.martial_entries),
            ("magic", "Magical Talents", DEFAULT_CATALOG.magic_spheres(), DEFAULT_CATALOG.magic_entries),
        ):
            family_node = QTreeWidgetItem((label,))
            family_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "feature_index", "title": label})
            for sphere in spheres_list:
                sphere_name = str(sphere["name"])
                sphere_node = QTreeWidgetItem((sphere_name,))
                sphere_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "features", "family": family, "sphere": sphere_name})
                categories = sorted({str(entry.get("category") or "General") for entry in entries_provider(sphere_name)}, key=str.casefold)
                for category_name in categories:
                    category_node = QTreeWidgetItem((category_name,))
                    category_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "features", "family": family, "sphere": sphere_name, "category": category_name})
                    sphere_node.addChild(category_node)
                family_node.addChild(sphere_node)
            talents_root.addChild(family_node)
        self.tree.addTopLevelItem(talents_root)

        feats_root = QTreeWidgetItem(("Feats",))
        feats_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "feature_index", "title": "Feats"})
        for source_name in sorted({str(entry["source_group"]) for entry in DEFAULT_CATALOG.feat_entries()}, key=str.casefold):
            source_node = QTreeWidgetItem((source_name,))
            source_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "features", "family": "feat", "source": source_name})
            categories = sorted({str(category) for entry in DEFAULT_CATALOG.feat_entries(source_name) for category in entry.get("categories", ("General",))}, key=str.casefold)
            for category_name in categories:
                category_node = QTreeWidgetItem((category_name,))
                category_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "features", "family": "feat", "source": source_name, "category": category_name})
                source_node.addChild(category_node)
            feats_root.addChild(source_node)
        self.tree.addTopLevelItem(feats_root)

        traits_root = QTreeWidgetItem(("Traits",))
        traits_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "feature_index", "title": "Traits"})
        for source_name in DEFAULT_CATALOG.trait_sources():
            source_node = QTreeWidgetItem((source_name,))
            source_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "features", "family": "trait", "source": source_name})
            categories = sorted({str(category) for entry in DEFAULT_CATALOG.trait_entries(source_name) for category in entry.get("categories", ("General",))}, key=str.casefold)
            for category_name in categories:
                category_node = QTreeWidgetItem((category_name,))
                category_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "features", "family": "trait", "source": source_name, "category": category_name})
                source_node.addChild(category_node)
            traits_root.addChild(source_node)
        self.tree.addTopLevelItem(traits_root)
        traditions_root = QTreeWidgetItem(("Traditions",))
        traditions_root.setData(0, Qt.ItemDataRole.UserRole, {"kind": "traditions"})
        for tradition_kind in ("Casting", "Martial", "Crafting", "Tinker"):
            kind_node = QTreeWidgetItem((f"{tradition_kind} Traditions",))
            kind_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "traditions", "tradition_kind": tradition_kind})
            packages_node = QTreeWidgetItem(("Tradition Packages",))
            packages_node.setData(0, Qt.ItemDataRole.UserRole, {
                "kind": "traditions", "tradition_kind": tradition_kind,
            })
            for entry in DEFAULT_CATALOG.tradition_entries(tradition_kind):
                entry_node = QTreeWidgetItem((str(entry["name"]),))
                entry_node.setData(0, Qt.ItemDataRole.UserRole, {"kind": "tradition", "key": entry["key"]})
                packages_node.addChild(entry_node)
            kind_node.addChild(packages_node)
            categories = tuple(dict.fromkeys(
                str(entry.get("category") or "Rule Option")
                for entry in DEFAULT_CATALOG.tradition_rule_entries(tradition_kind)
            ))
            for category_name in categories:
                category_node = QTreeWidgetItem((f"{category_name}s",))
                category_node.setData(0, Qt.ItemDataRole.UserRole, {
                    "kind": "tradition_rules", "tradition_kind": tradition_kind,
                    "category": category_name,
                })
                entries = DEFAULT_CATALOG.tradition_rule_entries(
                    tradition_kind, category_name
                )
                rule_spheres = tuple(sorted(
                    {str(entry.get("sphere") or "") for entry in entries if entry.get("sphere")},
                    key=str.casefold,
                ))
                if rule_spheres and len(rule_spheres) > 1:
                    for sphere_name in rule_spheres:
                        sphere_node = QTreeWidgetItem((sphere_name,))
                        sphere_node.setData(0, Qt.ItemDataRole.UserRole, {
                            "kind": "tradition_rules", "tradition_kind": tradition_kind,
                            "category": category_name, "sphere": sphere_name,
                        })
                        for rule in DEFAULT_CATALOG.tradition_rule_entries(
                            tradition_kind, category_name, sphere_name
                        ):
                            rule_node = QTreeWidgetItem((str(rule["name"]),))
                            rule_node.setData(0, Qt.ItemDataRole.UserRole, {
                                "kind": "tradition_rule", "key": rule["key"],
                            })
                            sphere_node.addChild(rule_node)
                        category_node.addChild(sphere_node)
                else:
                    for rule in entries:
                        rule_node = QTreeWidgetItem((str(rule["name"]),))
                        rule_node.setData(0, Qt.ItemDataRole.UserRole, {
                            "kind": "tradition_rule", "key": rule["key"],
                        })
                        category_node.addChild(rule_node)
                kind_node.addChild(category_node)
            traditions_root.addChild(kind_node)
        self.tree.addTopLevelItem(traditions_root)
        tools_root = QTreeWidgetItem(("Sheet Tools",))
        tools_root.setData(0, Qt.ItemDataRole.UserRole, "sheet_tools")
        advancement = QTreeWidgetItem(("Character Advancement",))
        advancement.setData(0, Qt.ItemDataRole.UserRole, "character_advancement")
        formulas = QTreeWidgetItem(("Formula Language",))
        formulas.setData(0, Qt.ItemDataRole.UserRole, "formulas")
        tools_root.addChild(advancement)
        tools_root.addChild(formulas)
        self.tree.addTopLevelItem(tools_root)
        from app.reference_rules import reference_catalog, REFERENCE_FAMILIES
        for family, title, prefix in REFERENCE_FAMILIES:
            root = QTreeWidgetItem((title,))
            root.setData(0, Qt.ItemDataRole.UserRole, "reference-index:" + family)
            groups = {}
            for entry in sorted(reference_catalog()[family], key=lambda e: (e.get("sphere", ""), e["name"])):
                parent = root
                if family != "skills":
                    group = entry["sphere"] or "Universal"
                    if group not in groups:
                        groups[group] = QTreeWidgetItem((group,))
                        root.addChild(groups[group])
                    parent = groups[group]
                node = QTreeWidgetItem((entry["name"],))
                node.setData(0, Qt.ItemDataRole.UserRole, prefix + ":" + entry["key"])
                parent.addChild(node)
            if family == "prodigy" and prodigy is not None:
                prodigy.addChild(root)
            else:
                self.tree.addTopLevelItem(root)
        classes.setExpanded(True)
        spheres.setExpanded(True)
        if prodigy is not None:
            prodigy.setExpanded(True)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setObjectName("codexBrowser")
        self.browser.anchorClicked.connect(self._open_codex_link)
        splitter.addWidget(self.tree)
        splitter.addWidget(self.browser)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.tree.currentItemChanged.connect(self._show_page)
        search_button.clicked.connect(self._search_codex)
        self.codex_search.returnPressed.connect(self._search_codex)
        target = {
            "home": home,
            "bestiary": bestiary,
            "prodigy": prodigy or spheres,
            "pathfinder": pathfinder,
            "spheres": spheres,
            "character_advancement": advancement,
            "formulas": formulas,
        }.get(initial_page, classes)
        self.tree.setCurrentItem(target)
        if initial_page.startswith("bestiary:"):
            self._open_codex_link(QUrl("codex:" + initial_page))

    def _show_page(self, item: QTreeWidgetItem | None, _previous=None) -> None:
        page = item.data(0, Qt.ItemDataRole.UserRole) if item else ""
        if isinstance(page, dict) and page.get("kind") == "bestiary":
            from app.bestiary import bestiary_index_html
            from app.ui.reference_details import reference_document_html
            self.browser.setHtml(reference_document_html(self, bestiary_index_html(DEFAULT_CATALOG, page.get("entry_kind", ""))))
            return
        from app.reference_rules import REFERENCE_FAMILIES
        if isinstance(page, str) and page.startswith(tuple(row[2] + ':' for row in REFERENCE_FAMILIES) + ('reference-index:',)):
            self._open_codex_link(QUrl("codex:" + page))
            return
        if isinstance(page, dict) and page.get("kind") == "race":
            entry = DEFAULT_CATALOG.race_entry(str(page.get("key", "")))
            self.browser.setHtml(self._race_html(entry) if entry else "<p>Race not found.</p>")
            return
        if isinstance(page, dict) and page.get("kind") == "races":
            category = str(page.get("category") or "") or None
            race_entries = DEFAULT_CATALOG.race_entries(category)
            title = f"{category} Races" if category else "Pathfinder Races"
            rows = "".join(
                f"<h3><a href='codex:race:{urllib.parse.quote(str(entry['key']), safe='')}'>{html.escape(str(entry['name']))}</a></h3>"
                f"<p>{html.escape(str(entry.get('description') or ''))}</p><hr>"
                for entry in race_entries
            )
            self.browser.setHtml(
                f"<h1>{html.escape(title)}</h1><p><b>{len(race_entries)} races</b></p>{rows}"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "class":
            entry = DEFAULT_CATALOG.class_entry(str(page.get("key", "")))
            self.browser.setHtml(self._class_html(entry) if entry else "<p>Class not found.</p>")
            return
        if isinstance(page, dict) and page.get("kind") == "archetype":
            entry = DEFAULT_CATALOG.archetype_entry(str(page.get("key", "")))
            self.browser.setHtml(
                self._archetype_html(entry) if entry else "<p>Archetype not found.</p>"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "archetypes":
            entries = DEFAULT_CATALOG.archetype_entries(
                str(page.get("class_key", "")), str(page.get("source", ""))
            )
            self.browser.setHtml(self._archetype_collection_html(entries, page))
            return
        if isinstance(page, dict) and page.get("kind") == "class_choice":
            entry = DEFAULT_CATALOG.class_choice_entry(str(page.get("key", "")))
            self.browser.setHtml(
                self._class_choice_html(entry)
                if entry else "<p>Class choice not found.</p>"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "class_power":
            entry = DEFAULT_CATALOG.class_power_entry(str(page.get("key", "")))
            self.browser.setHtml(
                self._class_power_html(entry) if entry else "<p>Class power not found.</p>"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "class_powers":
            family = str(page.get("family") or "") or None
            category = str(page.get("category") or "") or None
            entries = DEFAULT_CATALOG.class_power_entries(family, category=category)
            title = " · ".join(
                value for value in (
                    "Class Powers",
                    family.replace("_", " ").title() if family else "",
                    category or "",
                ) if value
            )
            rows = "".join(
                f"<h3><a href='codex:class-power:{urllib.parse.quote(str(entry['key']), safe='')}'>{html.escape(str(entry['name']))}</a></h3>"
                f"<p>{html.escape(str(entry.get('description') or 'No description available.'))}</p><hr>"
                for entry in entries
            )
            self.browser.setHtml(f"<h1>{html.escape(title)}</h1><p><b>{len(entries)} entries</b></p>{rows}")
            return
        if isinstance(page, dict) and page.get("kind") == "class_choices":
            family = str(page.get("family") or "") or None
            entries = DEFAULT_CATALOG.class_choice_entries(family)
            title = family.replace("_", " ").title() if family else "Class Feature Choices"
            rows = "".join(
                f"<h3><a href='codex:class-choice:{urllib.parse.quote(str(entry['key']), safe='')}'>{html.escape(str(entry['name']))}</a></h3>"
                f"<p>{html.escape(str(entry.get('description') or 'No description available.'))}</p><hr>"
                for entry in entries
            )
            self.browser.setHtml(
                f"<h1>{html.escape(title)}</h1><p><b>{len(entries)} entries</b></p>{rows}"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "classes":
            entries = DEFAULT_CATALOG.class_entries(
                str(page.get("source_group", "")) or None,
                str(page.get("category", "")) or None,
            )
            links = "".join(f"<li><b>{html.escape(str(entry['name']))}</b> — {html.escape(str(entry.get('summary', '')))}</li>" for entry in entries)
            self.browser.setHtml(f"<h1>{html.escape(str(page['category']))}</h1><ul>{links}</ul>")
            return
        if isinstance(page, dict) and page.get("kind") == "spells":
            entries = DEFAULT_CATALOG.spell_entries(
                str(page.get("source", "")) or None,
                str(page.get("publisher", "")) or None,
            )
            self.browser.setHtml(self._spell_collection_html(entries, page))
            return
        if isinstance(page, dict) and page.get("kind") == "feature_index":
            self.browser.setHtml(
                f"<h1>{html.escape(str(page.get('title', 'Rules features')))}</h1>"
                "<p>Choose a ruleset, sphere, or category on the left. Every entry is also available through the Codex search above.</p>"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "features":
            feature_entries = self._codex_feature_entries(page)
            from app.ui.reference_details import reference_document_html
            self.browser.setHtml(reference_document_html(self, self._feature_collection_html(page, feature_entries)))
            return
        if isinstance(page, dict) and page.get("kind") == "tradition":
            entry = DEFAULT_CATALOG.tradition_entry(str(page.get("key", "")))
            self.browser.setHtml(self._tradition_html(entry) if entry else "<p>Tradition not found.</p>")
            return
        if isinstance(page, dict) and page.get("kind") == "tradition_rule":
            entry = DEFAULT_CATALOG.tradition_rule_entry(str(page.get("key", "")))
            self.browser.setHtml(
                self._tradition_rule_html(entry)
                if entry else "<p>Tradition rule option not found.</p>"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "tradition_rules":
            kind = str(page.get("tradition_kind", "")) or None
            category = str(page.get("category", "")) or None
            sphere = str(page.get("sphere", "")) or None
            entries = DEFAULT_CATALOG.tradition_rule_entries(kind, category, sphere)
            title = " · ".join(value for value in (kind, category, sphere) if value)
            rows = "".join(
                f"<h3><a href='codex:tradition-rule:{urllib.parse.quote(str(entry['key']), safe='')}'>{html.escape(str(entry['name']))}</a></h3>"
                f"<p>{html.escape(str(entry.get('description') or 'No description available.'))}</p><hr>"
                for entry in entries
            )
            self.browser.setHtml(
                f"<h1>{html.escape(title or 'Tradition Rule Options')}</h1>"
                f"<p><b>{len(entries)} entries</b></p>{rows}"
            )
            return
        if isinstance(page, dict) and page.get("kind") == "traditions":
            kind = str(page.get("tradition_kind", "")) or None
            entries = DEFAULT_CATALOG.tradition_entries(kind)
            title = f"{kind} Traditions" if kind else "Traditions"
            rows = "".join(
                f"<h3>{html.escape(str(entry['name']))}</h3>"
                f"<p>{html.escape(str(entry.get('description', '')))}</p><hr>"
                for entry in entries
            )
            self.browser.setHtml(f"<h1>{html.escape(title)}</h1><p><b>{len(entries)} entries</b></p>{rows}")
            return
        if isinstance(page, dict) and page.get("kind") == "items":
            source = page.get("source"); family = page.get("family"); category = page.get("category")
            entries = DEFAULT_CATALOG.item_entries(source, family, category)
            title = " · ".join(value for value in (source, family, category) if value) or "Equipment & Items"
            groups = "Pathfinder and Spheres are kept in separate branches. Choose a family or category on the left to narrow the reference."
            rows = []
            for entry in entries:
                description = html.escape(str(entry.get("description") or "No description available."))
                source_link = html.escape(str(entry.get("source_url") or ""), quote=True)
                details = f"<p>{description}</p><p><b>Family:</b> {html.escape(str(entry['family']))} &nbsp; <b>Category:</b> {html.escape(str(entry['category']))}"
                if entry.get("subcategory"): details += f" &nbsp; <b>Subcategory:</b> {html.escape(str(entry['subcategory']))}"
                details += f"</p><p><b>Price:</b> {float(entry.get('price_gp') or 0):g} gp &nbsp; <b>Weight:</b> {float(entry.get('weight_lb') or 0):g} lb"
                if source_link: details += f" &nbsp; <a href='{source_link}'>Rules source</a>"
                details += "</p>"
                automation = entry.get("item_automation") or {}
                effects = automation.get("effects") or ()
                effect_text = "; ".join(
                    str(effect.get("label") or effect.get("key") or "")
                    for effect in effects
                ) or "No reviewed automatic effect"
                raw_status = str(automation.get("status") or "rules_only")
                status = "Requires Choice" if raw_status == "choice" else raw_status.replace("_", " ").title()
                details += (
                    f"<p><b>Sheet automation:</b> {html.escape(status)} &nbsp; "
                    f"<b>Resolved:</b> {html.escape(effect_text)}</p>"
                )
                rows.append(f"<h3>{html.escape(str(entry['name']))}</h3>{details}<hr>")
            self.browser.setHtml(
                f"<h1>{html.escape(title)}</h1><p>{groups}</p><p><b>{len(entries):,} entries</b>. Use Ctrl+F to search within this category.</p>" + "".join(rows)
            )
            return
        if isinstance(page, dict) and page.get("kind") == "enchantments":
            family = str(page.get("family") or "") or None
            category = str(page.get("category") or "") or None
            entries = DEFAULT_CATALOG.enchantment_entries(family, category)
            title = " · ".join(value for value in ("Enchantments", family, category) if value)
            self.browser.setHtml(self._enchantment_collection_html(title, entries))
            return
        page = str(page or "")
        if page == "home":
            self.browser.setHtml(
                "<h1>Pathfinder 1e &amp; Spheres Codex</h1>"
                "<p>This is the local rules reference used by the character sheet. "
                "Browse a category on the left or search names, descriptions, or both above.</p>"
                "<h2>Reference library</h2>"
                f"<p><b>Classes:</b> {len(DEFAULT_CATALOG.class_entries())} &nbsp; "
                f"<b>Races:</b> {len(DEFAULT_CATALOG.race_entries())} &nbsp; "
                f"<b>Spells:</b> {len(DEFAULT_CATALOG.spell_entries())} &nbsp; "
                f"<b>Items:</b> {len(DEFAULT_CATALOG.item_entries())} &nbsp; "
                f"<b>Bestiary:</b> {len(DEFAULT_CATALOG.bestiary_entries()):,}</p>"
                "<p>Pathfinder and Spheres classes are equal branches under Classes. "
                "Select a class there for its progression, features, archetypes, and complete imported rules.</p>"
                "<h2>Sheet tools</h2>"
                "<p>The Formula Language reference documents every supported value, including "
                "movement, resources, Prodigy sequences, and imbues.</p>"
            )
        elif page == "prodigy":
            self.browser.setHtml(prodigy_codex_html())
        elif page == "pathfinder":
            self.browser.setHtml(
                f"<h1>Pathfinder classes</h1><p>The Codex contains {len(DEFAULT_CATALOG.pathfinder_class_entries())} playable first-party classes, "
                "organized as Core, Base, Alternate, Hybrid, Occult, Unchained, and Later classes. Select a category or class on the left.</p>"
            )
        elif page == "spheres":
            self.browser.setHtml(
                f"<h1>Spheres classes</h1><p>The Codex contains {len(DEFAULT_CATALOG.spheres_class_entries())} selectable Spheres classes across Spherecasters, Practitioners, Operatives, Champions, and prestige classes. Select a family or class on the left.</p>"
            )
        elif page == "formulas":
            self.browser.setHtml(FORMULA_CODEX_HTML)
        elif page == "character_advancement":
            self.browser.setHtml(character_advancement_codex_html())
        elif page == "sheet_tools":
            self.browser.setHtml(
                "<h1>Sheet Tools</h1><p>Choose Character Advancement or Formula Language.</p>"
            )
        else:
            self.browser.setHtml(
                "<h1>Classes</h1><p>Choose Pathfinder or Spheres, then select a class.</p>"
            )

    def _open_codex_link(self, url: QUrl) -> None:
        target = url.toString()
        if target.startswith("codex:bestiary:"):
            from app.bestiary import creature_html
            from app.ui.reference_details import reference_document_html
            key = urllib.parse.unquote(target[len("codex:bestiary:"):])
            self.browser.setHtml(reference_document_html(self, creature_html(DEFAULT_CATALOG.bestiary_entry(key))))
            return
        from app.reference_rules import reference_catalog, reference_index_html, REFERENCE_FAMILIES
        from app.ui.reference_details import reference_details_html, reference_document_html
        if target.startswith("codex:reference-index:"):
            self.browser.setHtml(reference_document_html(self, reference_index_html(target.split(":", 2)[2])))
            return
        for family, _title, short_prefix in REFERENCE_FAMILIES:
            prefix = 'codex:' + short_prefix + ':'
            if target.startswith(prefix):
                key = urllib.parse.unquote(target[len(prefix):])
                entry = next((e for e in reference_catalog()[family] if e["key"] == key), None)
                self.browser.setHtml(reference_details_html(self, entry))
                return
        if target == "codex:prodigy":
            self.browser.setHtml(prodigy_codex_html())
            return
        if target == "codex:formulas":
            self.browser.setHtml(FORMULA_CODEX_HTML)
            return
        if target == "codex:character_advancement":
            self.browser.setHtml(character_advancement_codex_html())
            return
        class_prefix = "codex:class:"
        if target.startswith(class_prefix):
            key = urllib.parse.unquote(target[len(class_prefix) :])
            entry = DEFAULT_CATALOG.class_entry(key)
            self.browser.setHtml(
                self._class_html(entry) if entry else "<p>Class entry not found.</p>"
            )
            return
        archetype_prefix = "codex:archetype:"
        if target.startswith(archetype_prefix):
            key = urllib.parse.unquote(target[len(archetype_prefix) :])
            entry = DEFAULT_CATALOG.archetype_entry(key)
            self.browser.setHtml(
                self._archetype_html(entry)
                if entry else "<p>Archetype entry not found.</p>"
            )
            return
        race_prefix = "codex:race:"
        if target.startswith(race_prefix):
            key = urllib.parse.unquote(target[len(race_prefix) :])
            entry = DEFAULT_CATALOG.race_entry(key)
            self.browser.setHtml(
                self._race_html(entry) if entry else "<p>Race entry not found.</p>"
            )
            return
        item_prefix = "codex:item:"
        if target.startswith(item_prefix):
            key = urllib.parse.unquote(target[len(item_prefix) :])
            entry = DEFAULT_CATALOG.item_entry(key)
            self.browser.setHtml(
                self._item_html(entry) if entry else "<p>Item entry not found.</p>"
            )
            return
        feature_prefix = "codex:feature:"
        if target.startswith(feature_prefix):
            remainder = urllib.parse.unquote(target[len(feature_prefix) :])
            family, separator, key = remainder.partition(":")
            providers = {
                "martial": DEFAULT_CATALOG.martial_entry,
                "magic": DEFAULT_CATALOG.magic_entry,
                "feat": DEFAULT_CATALOG.feat_entry,
                "trait": DEFAULT_CATALOG.trait_entry,
            }
            entry = providers.get(family, lambda _key: None)(key) if separator else None
            if entry:
                page = {"family": family}
                if family in {"martial", "magic"}:
                    page["sphere"] = str(entry.get("sphere") or "")
                else:
                    page["source"] = str(entry.get("source_group") or "")
                self.browser.setHtml(reference_document_html(self, self._feature_collection_html(page, (entry,))))
            else:
                self.browser.setHtml("<p>Feature entry not found.</p>")
            return
        class_choice_prefix = "codex:class-choice:"
        if target.startswith(class_choice_prefix):
            key = urllib.parse.unquote(target[len(class_choice_prefix) :])
            entry = DEFAULT_CATALOG.class_choice_entry(key)
            self.browser.setHtml(
                self._class_choice_html(entry)
                if entry else "<p>Class choice entry not found.</p>"
            )
            return
        class_power_prefix = "codex:class-power:"
        if target.startswith(class_power_prefix):
            key = urllib.parse.unquote(target[len(class_power_prefix) :])
            entry = DEFAULT_CATALOG.class_power_entry(key)
            self.browser.setHtml(
                self._class_power_html(entry) if entry else "<p>Class power entry not found.</p>"
            )
            return
        enchantment_prefix = "codex:enchantment:"
        if target.startswith(enchantment_prefix):
            key = urllib.parse.unquote(target[len(enchantment_prefix) :])
            entry = DEFAULT_CATALOG.enchantment_entry(key)
            self.browser.setHtml(
                self._enchantment_html(entry) if entry else "<p>Enchantment entry not found.</p>"
            )
            return
        prefix = "codex:spell:"
        if target.startswith(prefix):
            key = urllib.parse.unquote(target[len(prefix) :])
            entry = DEFAULT_CATALOG.spell_entry(key)
            self.browser.setHtml(
                self._spell_html(entry) if entry else "<p>Spell entry not found.</p>"
            )
            return
        tradition_prefix = "codex:tradition:"
        if target.startswith(tradition_prefix):
            key = urllib.parse.unquote(target[len(tradition_prefix) :])
            entry = DEFAULT_CATALOG.tradition_entry(key)
            self.browser.setHtml(
                self._tradition_html(entry) if entry else "<p>Tradition entry not found.</p>"
            )
            return
        tradition_rule_prefix = "codex:tradition-rule:"
        if target.startswith(tradition_rule_prefix):
            key = urllib.parse.unquote(target[len(tradition_rule_prefix) :])
            entry = DEFAULT_CATALOG.tradition_rule_entry(key)
            self.browser.setHtml(
                self._tradition_rule_html(entry)
                if entry else "<p>Tradition rule option not found.</p>"
            )
            return
        QDesktopServices.openUrl(url)

    @staticmethod
    def _race_html(entry: dict) -> str:
        source_url = html.escape(str(entry.get("source_url") or ""), quote=True)
        adjustments = ", ".join(
            f"{int(value):+d} {str(ability).title()}"
            for ability, value in entry.get("adjustments", {}).items()
        )
        if entry.get("flexible_bonus"):
            adjustments = (adjustments + ", " if adjustments else "") + (
                f"+{int(entry['flexible_bonus'])} to one ability"
            )
        base_traits = "".join(
            f"<h3>{html.escape(str(trait['name']))}</h3>"
            f"<p>{html.escape(str(trait.get('description') or ''))}</p>"
            for trait in entry.get("racial_traits", ())
        ) or "<p>No separate base racial-trait block is published for this race.</p>"
        variants = "".join(
            f"<h3>{html.escape(str(variant['name']))}</h3>"
            f"<p>{html.escape(str(variant.get('description') or ''))}</p>"
            for variant in entry.get("variants", ())
        ) or "<p>None cataloged.</p>"
        alternates = "".join(
            f"<h3>{html.escape(str(trait['name']))}</h3>"
            f"<p><b>Replaces:</b> {html.escape(', '.join(str(value) for value in trait.get('replaces', ())) or 'Nothing')}</p>"
            f"<p>{html.escape(str(trait.get('description') or ''))}</p>"
            for trait in entry.get("alternate_racial_traits", ())
        ) or "<p>None cataloged.</p>"
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry.get('category') or 'Other'))} Race</b></p>"
            f"<p>{html.escape(str(entry.get('description') or ''))}</p>"
            f"<p><b>Ability modifiers:</b> {html.escape(adjustments or 'None')}<br>"
            f"<b>Size:</b> {html.escape(str(entry.get('size') or 'Medium'))}<br>"
            f"<b>Base speed:</b> {int(entry.get('base_speed') or 30)} feet</p>"
            f"<h2>Base racial traits</h2>{base_traits}"
            f"<h2>Subraces and heritages</h2>{variants}"
            f"<h2>Alternate racial traits</h2>{alternates}"
            + (f"<p><a href='{source_url}'>Official rules source</a></p>" if source_url else "")
        )

    @staticmethod
    def _item_html(entry: dict) -> str:
        source_url = html.escape(str(entry.get("source_url") or ""), quote=True)
        automation = entry.get("item_automation") or {}
        effects = "; ".join(
            str(effect.get("label") or effect.get("key") or "")
            for effect in automation.get("effects", ())
        ) or "No reviewed automatic effect"
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry.get('family') or 'Item'))}</b> · "
            f"{html.escape(str(entry.get('category') or 'General'))}</p>"
            f"<p><b>Price:</b> {float(entry.get('price_gp') or 0):g} gp &nbsp; "
            f"<b>Weight:</b> {float(entry.get('weight_lb') or 0):g} lb</p>"
            f"<p>{html.escape(str(entry.get('description') or 'No description available.'))}</p>"
            f"<p><b>Sheet automation:</b> {html.escape(effects)}</p>"
            + (f"<p><a href='{source_url}'>Rules source</a></p>" if source_url else "")
        )

    @staticmethod
    def _class_choice_html(entry: dict) -> str:
        source = html.escape(str(entry.get("source_url", "")), quote=True)
        source_link = f"<p><a href='{source}'>Rules source</a></p>" if source else ""
        grants = "".join(
            f"<h3>Level {int(feature.get('level', 1) or 1)} — "
            f"{html.escape(str(feature.get('name') or 'Feature'))}</h3>"
            f"<p>{html.escape(str(feature.get('description') or ''))}</p>"
            for feature in entry.get("granted_features", ())
        ) or "<p>No automatic level-gated grants are recorded for this choice.</p>"
        associations = ", ".join(str(value) for value in entry.get("classes", ())) or "—"
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry.get('family', '')).replace('_', ' ').title())}</b> · "
            f"{html.escape(str(entry.get('category') or 'General'))}</p>"
            f"<p><b>Classes:</b> {html.escape(associations)}</p>"
            f"<p>{html.escape(str(entry.get('description') or ''))}</p>"
            f"<h2>Granted features</h2>{grants}{source_link}"
        )

    @staticmethod
    def _class_power_html(entry: dict) -> str:
        source = html.escape(str(entry.get("source_url", "")), quote=True)
        prerequisites = ", ".join(str(value) for value in entry.get("prerequisite_names", ())) or "None"
        classes = ", ".join(str(value) for value in entry.get("classes", ())) or "—"
        family = DEFAULT_CATALOG.class_power_family_label(str(entry.get("family", "")))
        automatic = "".join(
            f"<li>{html.escape(str(effect.get('label') or effect.get('target') or 'Automatic effect'))}: "
            f"{int(effect.get('value') or 0):+d} {html.escape(str(effect.get('bonus_type') or 'untyped'))}</li>"
            for effect in entry.get("automatic_modifiers", ())
        )
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(family)}</b> · "
            f"{html.escape(str(entry.get('category') or 'General'))}</p>"
            f"<p><b>Classes:</b> {html.escape(classes)}<br>"
            f"<b>Minimum level:</b> {int(entry.get('minimum_level') or 1)}<br>"
            f"<b>Prerequisites:</b> {html.escape(prerequisites)}<br>"
            f"<b>Repeatable:</b> {'Yes' if entry.get('repeatable') else 'No'}</p>"
            f"<p>{html.escape(repair_mojibake(str(entry.get('description') or ''))).replace(chr(10), '<br>')}</p>"
            + (f"<h2>Automatic sheet effects</h2><ul>{automatic}</ul>" if automatic else "")
            + (f"<p><a href='{source}'>Rules source</a></p>" if source else "")
        )

    @staticmethod
    def _tradition_html(entry: dict) -> str:
        if entry.get('html'):
            from app.reference_rules import reference_html
            return reference_html(entry)
        grants = "".join(
            f"<li>{html.escape(str(grant.get('name', '')))}</li>"
            for grant in entry.get("fixed_grants", ())
        ) or "<li>None</li>"
        choices = "".join(
            f"<li>{html.escape(str(group.get('label', 'Choice')))}</li>"
            for group in entry.get("choice_groups", ())
        ) or "<li>None</li>"
        source = html.escape(str(entry.get("source_url", "")), quote=True)
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry.get('kind', '')))} Tradition</b></p>"
            f"<p>{html.escape(repair_mojibake(str(entry.get('description', ''))))}</p>"
            f"<p><b>Casting ability:</b> {html.escape(', '.join(entry.get('casting_ability_options', ())) or '—')}<br>"
            f"<b>Drawbacks:</b> {html.escape(str(entry.get('drawbacks', '')) or '—')}<br>"
            f"<b>Boons:</b> {html.escape(str(entry.get('boons', '')) or '—')}</p>"
            f"<h2>Fixed grants</h2><ul>{grants}</ul><h2>Choices</h2><ul>{choices}</ul>"
            f"<p>{html.escape(str(entry.get('rules_text', '')))}</p>"
            f"<p><a href='{source}'>Official rules source</a></p>"
        )

    @staticmethod
    def _tradition_rule_html(entry: dict) -> str:
        if entry.get('html'):
            from app.reference_rules import reference_html
            return reference_html(entry)
        source = html.escape(str(entry.get("source_url", "")), quote=True)
        source_link = (
            f"<p><a href='{source}'>Rules source</a></p>" if source else ""
        )
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry.get('kind', 'Spheres')))} · "
            f"{html.escape(str(entry.get('category', 'Rule Option')))}</b></p>"
            + (
                f"<p><b>Sphere:</b> {html.escape(str(entry.get('sphere')))}</p>"
                if entry.get("sphere") else ""
            )
            + (
                f"<p><b>Prerequisites:</b> {html.escape(str(entry.get('prerequisites')))}</p>"
                if entry.get("prerequisites") else ""
            )
            + f"<p>{html.escape(repair_mojibake(str(entry.get('description') or 'No description available.')))}</p>"
            + source_link
        )

    @staticmethod
    def _enchantment_collection_html(title: str, entries: tuple[dict, ...]) -> str:
        rows = []
        for entry in entries:
            target = urllib.parse.quote(str(entry["key"]), safe="")
            description = repair_mojibake(str(entry.get("description") or "No description available."))
            rows.append(
                f"<h3><a href='codex:enchantment:{target}'>{html.escape(str(entry['name']))}</a>"
                f" — {html.escape(str(entry.get('price_text') or '—'))}</h3>"
                f"<p>{html.escape(description[:700])}{'…' if len(description) > 700 else ''}</p><hr>"
            )
        return (
            f"<h1>{html.escape(title)}</h1><p><b>{len(entries):,} entries.</b> "
            "Select an entry for its full rules, construction requirements, and applicability.</p>"
            + "".join(rows)
        )

    @staticmethod
    def _enchantment_html(entry: dict) -> str:
        restrictions = "".join(
            f"<li>{html.escape(str(value))}</li>" for value in entry.get("restrictions", ())
        )
        restrictions_html = f"<h2>Applicability restrictions</h2><ul>{restrictions}</ul>" if restrictions else ""
        source_url = html.escape(str(entry.get("source_url") or ""), quote=True)
        automation = str(entry.get("automation_status") or "rules_only").replace("_", " ").title()
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry['family']))} · {html.escape(str(entry['category']))}</b></p>"
            f"<p><b>Price:</b> {html.escape(str(entry.get('price_text') or '—'))} &nbsp; "
            f"<b>Aura:</b> {html.escape(str(entry.get('aura') or '—'))} &nbsp; "
            f"<b>CL:</b> {html.escape(str(entry.get('caster_level') or '—'))}</p>"
            f"<p>{html.escape(repair_mojibake(str(entry.get('description') or 'No description available.')))}</p>"
            + restrictions_html
            + f"<h2>Construction</h2><p>{html.escape(str(entry.get('requirements') or 'No requirements recorded.'))}</p>"
            f"<p><b>Sheet automation:</b> {html.escape(automation)}. Rules-only entries are selectable and documented, "
            "but do not claim an automatic numerical effect when the rule is situational.</p>"
            f"<p><b>Source:</b> {html.escape(str(entry.get('source') or 'Pathfinder RPG'))} &nbsp; "
            f"<a href='{source_url}'>Archives of Nethys entry</a></p>"
        )

    @staticmethod
    def _class_html(entry: dict) -> str:
        feature_rows = "".join(
            f"<tr><td>{int(feature['level'])}</td><td><b>{html.escape(str(feature['name']))}</b></td>"
            f"<td>{html.escape(str(feature.get('description') or 'No description available.'))}</td></tr>"
            for feature in entry.get("features", ())
        )
        casting = entry.get("casting") or {}
        casting_text = ", ".join(
            str(value)
            for value in (casting.get("progression"), casting.get("type"), casting.get("spells"))
            if value
        ) or "None"
        complete_rules = str(entry.get("rules_text") or "")
        introduction = html.escape(
            str(entry.get("description") or entry.get("summary") or "")
        ).replace(chr(10), "<br>")
        complete_rules_html = (
            "<h2>Complete imported rules text</h2><p>"
            + html.escape(complete_rules).replace(chr(10), "<br>")
            + "</p>"
            if complete_rules
            else ""
        )
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1><p><b>{html.escape(str(entry['category']))}</b> · {html.escape(str(entry.get('source', 'Pathfinder RPG')))}</p>"
            f"<p>{introduction}</p>"
            f"<h2>Class statistics</h2><p><b>Hit Die:</b> d{entry.get('hit_die', 0)} &nbsp; <b>BAB:</b> {html.escape(str(entry.get('bab', '')))} &nbsp; "
            f"<b>Saves:</b> Fort {entry.get('fort')} / Ref {entry.get('reflex')} / Will {entry.get('will')} &nbsp; <b>Skills:</b> {entry.get('skill_points')} + Int</p>"
            f"<p><b>Class skills:</b> {html.escape(', '.join(entry.get('class_skills', ())))}</p><p><b>Casting:</b> {html.escape(casting_text)}</p>"
            f"<h2>Class features</h2><table cellspacing='6'><tr><th>Level</th><th>Feature</th><th>Description</th></tr>{feature_rows}</table>"
            + complete_rules_html
            + f"<p><a href='{html.escape(str(entry.get('source_url', '')), quote=True)}'>Class rules source</a></p>"
        )

    @staticmethod
    def _spell_collection_html(entries: tuple[dict, ...], page: dict) -> str:
        source = str(page.get("source") or "")
        publisher = str(page.get("publisher") or "")
        title = " · ".join(value for value in ("Spells", source, publisher) if value)
        visible = entries[:300]
        rows = []
        for entry in visible:
            levels = ", ".join(
                f"{name} {level}" for name, level in (entry.get("class_levels") or {}).items()
            )
            summary = str(entry.get("summary") or entry.get("description") or "")
            target = urllib.parse.quote(str(entry["key"]), safe="")
            rows.append(
                f"<h3><a href='codex:spell:{target}'>{html.escape(str(entry['name']))}</a></h3>"
                f"<p><b>{html.escape(str(entry.get('school') or 'Unspecified'))}</b> · {html.escape(levels)}<br>"
                f"{html.escape(summary[:700])}{'…' if len(summary) > 700 else ''}</p>"
                f"<p><a href='{html.escape(str(entry.get('source_url') or ''), quote=True)}'>Rules source</a></p><hr>"
            )
        suffix = " Showing the first 300; use Codex search for a specific spell." if len(entries) > 300 else ""
        return (
            f"<h1>{html.escape(title or 'Spells')}</h1>"
            f"<p><b>{len(entries):,} entries.</b>{suffix} Pathfinder and third-party spells remain explicitly labeled in separate branches.</p>"
            + "".join(rows)
        )

    @staticmethod
    def _spell_html(entry: dict) -> str:
        levels = ", ".join(
            f"{name} {level}" for name, level in (entry.get("class_levels") or {}).items()
        ) or "No class lists recorded"
        domains = ", ".join(
            f"{name} {level}" for name, level in (entry.get("domain_levels") or {}).items()
        )
        descriptors = ", ".join(str(value) for value in entry.get("descriptors", ()))
        school = str(entry.get("school") or "Unspecified")
        if entry.get("subschool"):
            school += f" ({entry['subschool']})"
        if descriptors:
            school += f" [{descriptors}]"
        source_url = html.escape(str(entry.get("source_url") or ""), quote=True)
        return (
            f"<h1>{html.escape(str(entry['name']))}</h1>"
            f"<p><b>{html.escape(str(entry.get('source_group') or 'Pathfinder'))} · "
            f"{html.escape(str(entry.get('publisher') or 'Unknown publisher'))}</b></p>"
            f"<p><b>School:</b> {html.escape(school)}<br>"
            f"<b>Class levels:</b> {html.escape(levels)}"
            + (f"<br><b>Domains:</b> {html.escape(domains)}" if domains else "")
            + f"<br><b>Components:</b> {html.escape(str(entry.get('components') or '—'))}"
            f"<br><b>Casting time:</b> {html.escape(str(entry.get('casting_time') or '—'))}"
            f"<br><b>Range / target:</b> {html.escape(str(entry.get('range') or '—'))} · "
            f"{html.escape(str(entry.get('target') or '—'))}"
            f"<br><b>Duration:</b> {html.escape(str(entry.get('duration') or '—'))}"
            f"<br><b>Save / spell resistance:</b> {html.escape(str(entry.get('saving_throw') or '—'))} · "
            f"{html.escape(str(entry.get('spell_resistance') or '—'))}</p>"
            f"<h2>Description</h2><p>{html.escape(str(entry.get('description') or 'No description available.')).replace(chr(10), '<br>')}</p>"
            f"<p><b>Source:</b> {html.escape(str(entry.get('source') or ''))}</p>"
            + (f"<p><a href='{source_url}'>Rules source</a></p>" if source_url else "")
        )

    @staticmethod
    def _archetype_html(entry: dict) -> str:
        return archetype_rules_html(entry)

    @staticmethod
    def _archetype_collection_html(entries: tuple[dict, ...], page: dict) -> str:
        class_name = str(entries[0]["class_name"]) if entries else "Class"
        source = str(page.get("source") or "Archetypes")
        rows = "".join(archetype_collection_row_html(entry) for entry in entries)
        return (
            f"<h1>{html.escape(class_name)} · {html.escape(source)} Archetypes</h1>"
            f"<p><b>{len(entries):,} entries</b>. Select an archetype on the left for its complete local rules text.</p>{rows}"
        )

    @staticmethod
    def _codex_feature_entries(page: dict) -> tuple[dict, ...]:
        family = str(page.get("family") or "")
        sphere = str(page.get("sphere") or "")
        source = str(page.get("source") or "")
        category = str(page.get("category") or "")
        if family == "martial":
            entries = DEFAULT_CATALOG.martial_entries(sphere or None)
        elif family == "magic":
            entries = DEFAULT_CATALOG.magic_entries(sphere or None)
        elif family == "feat":
            entries = DEFAULT_CATALOG.feat_entries(source or None)
        elif family == "trait":
            entries = DEFAULT_CATALOG.trait_entries(source or None)
        else:
            return ()
        if not category:
            return entries
        if family in {"feat", "trait"}:
            return tuple(entry for entry in entries if category in entry.get("categories", ()))
        return tuple(entry for entry in entries if str(entry.get("category") or "General") == category)

    @staticmethod
    def _feature_collection_html(page: dict, entries: tuple[dict, ...]) -> str:
        labels = {"martial": "Martial Talents", "magic": "Magical Talents", "feat": "Feats", "trait": "Traits"}
        family = str(page.get("family") or "")
        title = " · ".join(value for value in (labels.get(family, "Rules Features"), str(page.get("source") or ""), str(page.get("sphere") or ""), str(page.get("category") or "")) if value)
        rows = []
        for entry in entries:
            metadata = []
            if entry.get("sphere"): metadata.append(f"Sphere: {entry['sphere']}")
            category = entry.get("category") or ", ".join(entry.get("categories", ()))
            if category: metadata.append(f"Category: {category}")
            if entry.get("prerequisites"): metadata.append(f"Prerequisites: {entry['prerequisites']}")
            source_name = entry.get("source_name") or entry.get("source_book")
            if source_name: metadata.append(f"Source: {source_name}")
            source_url = html.escape(str(entry.get("source_url") or ""), quote=True)
            source_link = f"<p><a href='{source_url}'>Rules source</a></p>" if source_url else ""
            description = entry.get('rules_html') or f"<p>{html.escape(str(entry.get('description') or 'No description available.'))}</p>"
            rows.append(
                f"<h3>{html.escape(str(entry['name']))}</h3>"
                f"<p><b>{html.escape(' · '.join(str(value) for value in metadata))}</b></p>"
                f"{description}{source_link}<hr>"
            )
        return f"<h1>{html.escape(title)}</h1><p><b>{len(entries):,} entries</b>. Use Ctrl+F to search within this category.</p>{''.join(rows)}"
    def _search_codex(self) -> None:
        query = self.codex_search.text().strip().casefold()
        if len(query) < 2:
            self.browser.setHtml("<h1>Codex search</h1><p>Enter at least two characters.</p>")
            return
        mode = str(self.codex_search_mode.currentData() or "both")
        if self._search_index is None:
            prodigy_text = re.sub(r"<[^>]+>", " ", prodigy_codex_html())
            records = build_codex_search_records(
                DEFAULT_CATALOG,
                (
                    {
                        "name": "Prodigy",
                        "category": "Classes · Spheres",
                        "description": html.unescape(prodigy_text),
                        "source_url": PRODIGY_SOURCE_URL,
                        "target": "prodigy",
                        "hierarchy_rank": 0,
                    },
                    {
                        "name": "Formula Language",
                        "category": "Sheet Tools",
                        "description": FORMULA_SEARCH_TEXT,
                        "source_url": "",
                        "target": "formulas",
                        "hierarchy_rank": 0,
                    },
                    {
                        "name": "Character Advancement",
                        "category": "Sheet Tools · Pathfinder Rules",
                        "description": CHARACTER_ADVANCEMENT_SEARCH_TEXT,
                        "source_url": "",
                        "target": "character_advancement",
                        "hierarchy_rank": 0,
                    },
                ),
            )
            from app.reference_rules import reference_search_records
            records = (*records, *reference_search_records())
            self._search_index = CatalogSearchIndex(
                records, description_fields=("description",)
            )
        result = self._search_index.search(
            query,
            mode,
            sort_key=(
                (lambda record: codex_name_search_key(record, query))
                if mode == "name" else None
            ),
            limit=500,
        )
        hits = []
        for record in result.records:
            name = str(record["name"])
            category = str(record["category"])
            description = repair_mojibake(str(record["description"]))
            source_url = str(record.get("source_url") or "")
            target = str(record.get("target") or "")
            location = description.casefold().find(query)
            start = max(0, location - 100) if location >= 0 else 0
            snippet = description[start:start + 320].strip()
            if start: snippet = "…" + snippet
            if start + 320 < len(description): snippet += "…"
            hits.append((name, category, snippet, source_url, target))
        rows = []
        for name, category, snippet, source_url, target in hits[:500]:
            internal_url = (
                f"codex:{html.escape(urllib.parse.quote(target, safe=':'), quote=True)}"
                if target else ""
            )
            heading = (
                f"<h3><a href='{internal_url}'>{html.escape(name)}</a></h3>"
                if internal_url else f"<h3>{html.escape(name)}</h3>"
            )
            action = (
                f"<p><a href='{internal_url}'>Open complete Codex entry</a></p>"
                if internal_url
                else f"<p><a href='{html.escape(source_url, quote=True)}'>Rules source</a></p>"
                if source_url else ""
            )
            rows.append(
                f"{heading}<p><b>{html.escape(category)}</b></p>"
                f"<p>{html.escape(snippet or 'Name match.')}</p>{action}<hr>"
            )
        suffix = " Showing the first 500." if result.limited else ""
        self.browser.setHtml(
            f"<h1>Codex search</h1><p><b>{result.total} results</b> for "
            f"“{html.escape(self.codex_search.text().strip())}”.{suffix}</p>{''.join(rows)}"
        )


class MainWindow(QMainWindow):
    def __init__(self, repository: CharacterRepository) -> None:
        super().__init__()
        self.repository = repository
        self.block_repository = BuildingBlockRepository(
            repository.database_path,
            connection=repository.sqlite_connection,
        )
        self.block_registry = register_builtin_blocks()
        self.settings = QSettings("Georg", "Character Sheet App")
        self.theme = normalize_theme(
            str(self.settings.value("appearance/theme", "classic"))
        )
        self.sheet_type = normalize_sheet_type(
            DEFAULT_SHEET_TYPE
        )
        self.setWindowTitle("Character Sheet")
        self.resize(1440, 900)
        self.setMinimumSize(1020, 680)
        self.active_character_id: int | None = None
        self._build_ui()
        self._build_menu()
        from app.ui.dialog_theme import DialogThemeBoundary
        self.dialog_theme_boundary = DialogThemeBoundary(self)
        application = QApplication.instance()
        self._context_menu_application = application
        if application is not None:
            application.installEventFilter(self)
        # Startup always opens the library.  Explicit refreshes elsewhere retain
        # the established behavior of opening the requested character.
        self.refresh_characters(open_selected=False)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QDialog):
            self.dialog_theme_boundary.apply(watched)
        if (
            event.type() == QEvent.Type.ContextMenu
            and self.active_character_id is not None
            and self.pages.currentIndex() == 1
            and isinstance(watched, QWidget)
            and (watched is self or self.isAncestorOf(watched))
        ):
            if isinstance(watched, FloatingNoteWidget) or any(
                isinstance(parent, FloatingNoteWidget)
                for parent in self._widget_parents(watched)
            ):
                return super().eventFilter(watched, event)
            interactive = isinstance(
                watched,
                (
                    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
                    QAbstractSpinBox, QAbstractItemView, QPushButton, QToolButton,
                ),
            )
            if not interactive:
                menu = QMenu(self)
                notes = menu.addAction("Notes")
                menu.addSeparator()
                for label in ("Cut", "Copy", "Paste", "Delete"):
                    menu.addAction(label).setEnabled(False)
                formula = menu.addAction("Write Formula")
                chosen = menu.exec(event.globalPos())
                if chosen is notes:
                    self.floating_notes.create_or_show(event.globalPos())
                elif chosen is formula:
                    self.floating_notes.create_or_show(
                        event.globalPos(), formula=True
                    )
                return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _widget_parents(widget: QWidget):
        parent = widget.parentWidget()
        while parent is not None:
            yield parent
            parent = parent.parentWidget()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # Retain the mature list-selection model without dedicating permanent
        # screen space to it. File > Switch Character is the visible navigator.
        self.character_list = QListWidget(root)
        self.character_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.character_list.itemSelectionChanged.connect(self._show_selected)
        self.character_list.hide()
        self.pages = QStackedWidget()
        self.pages.addWidget(self._library_page())
        self.pages.addWidget(self._character_page())
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(self._style_sheet(self.theme))

    @staticmethod
    def _style_sheet(theme: str = "light") -> str:
        return style_sheet(theme)


    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.file_menu = file_menu
        library_action = QAction("Character &Library", self)
        library_action.setShortcut("Ctrl+L")
        library_action.triggered.connect(self.show_character_library)
        file_menu.addAction(library_action)
        file_menu.addSeparator()
        new_action = QAction("&New character", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.create_character)
        file_menu.addAction(new_action)
        self.guided_creation_action = QAction(
            "Use guided character creation", self, checkable=True
        )
        self.guided_creation_action.setChecked(
            str(self.settings.value("creation/guided", "true")).casefold()
            not in {"false", "0", "no"}
        )
        self.guided_creation_action.toggled.connect(
            lambda enabled: self.settings.setValue("creation/guided", enabled)
        )
        file_menu.addAction(self.guided_creation_action)
        self.switch_character_menu = file_menu.addMenu("Switch character")
        file_menu.addSeparator()
        save_action = QAction("&Save character", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_character)
        file_menu.addAction(save_action)
        save_as_action = QAction("Save character &as…", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_character_as)
        file_menu.addAction(save_as_action)
        self.save_layout_action = QAction("Save sheet arrangement to this character", self)
        self.save_layout_action.triggered.connect(self.save_sheet_arrangement)
        file_menu.addAction(self.save_layout_action)
        file_menu.addSeparator()
        export_action = QAction("&Export selected character…", self)
        export_action.triggered.connect(self.export_selected)
        file_menu.addAction(export_action)
        import_action = QAction("&Import character…", self)
        import_action.triggered.connect(self.import_from_file)
        file_menu.addAction(import_action)
        file_menu.addSeparator()
        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = self.menuBar().addMenu("&Edit")
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self.undo_action.triggered.connect(self.undo)
        edit_menu.addAction(self.undo_action)
        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcuts((
            QKeySequence("Ctrl+Y"),
            QKeySequence("Ctrl+Shift+Z"),
        ))
        self.redo_action.triggered.connect(self.redo)
        edit_menu.addAction(self.redo_action)
        self.presentation_history.on_changed = self._update_history_actions
        self._update_history_actions()

        build_menu = self.menuBar().addMenu("&Build Mode")
        self.build_menu = build_menu
        build_menu.addAction(self.undo_action)
        build_menu.addAction(self.redo_action)
        build_menu.addSeparator()
        build_action = QAction("Enable sheet layout editing", self, checkable=True)
        build_action.setShortcut("Ctrl+Shift+B")
        build_action.toggled.connect(self._set_build_mode)
        build_menu.addAction(build_action)
        scale_contents = QAction(
            "Scale contents proportionally while resizing", self, checkable=True
        )
        scale_contents.setShortcut("Ctrl+Alt+S")
        scale_contents.toggled.connect(self._set_content_scale_mode)
        build_menu.addAction(scale_contents)
        edit_cells = QAction("Edit cells inside boxes", self, checkable=True)
        edit_cells.setShortcut("Ctrl+Shift+E")
        edit_cells.toggled.connect(self._set_cell_edit_mode)
        build_menu.addAction(edit_cells)
        build_menu.addSeparator()
        instructions = QAction("How to arrange boxes", self)
        instructions.triggered.connect(
            lambda: QMessageBox.information(
                self,
                "Build Mode",
                "Enable Build Mode, then drag any sheet box freely with the mouse. "
                "Drag its right edge, bottom edge, or lower-right corner to resize it. "
                "Drag table headings to reorder columns, resize them at their dividing "
                "lines, or right-click a heading to add, remove, rename, or restore a column. "
                "Positions and sizes are remembered automatically. Turn on ‘Scale contents "
                "proportionally while resizing’ when the text, fields, buttons, spacing, and "
                "table rows inside the box should grow or shrink with it.",
            )
        )
        build_menu.addAction(instructions)
        reset_layout = QAction("Restore Default Sheet for this character…", self)
        reset_layout.triggered.connect(self.restore_default_sheet)
        build_menu.addAction(reset_layout)
        self.reset_layout_action = reset_layout
        self.build_mode_action = build_action
        self.content_scale_action = scale_contents
        self.cell_edit_action = edit_cells

        theme_menu = self.menuBar().addMenu("&Theme")
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for key, label in THEME_LABELS.items():
            action = QAction(label, self, checkable=True)
            action.setChecked(self.theme == key)
            action.triggered.connect(lambda _checked=False, name=key: self._set_theme(name))
            theme_group.addAction(action)
            theme_menu.addAction(action)
        self.theme_actions = theme_group

        sheet_type_menu = self.menuBar().addMenu("Sheet &Types")
        sheet_type_group = QActionGroup(self)
        sheet_type_group.setExclusive(True)
        for descriptor in sheet_type_descriptors():
            action = QAction(descriptor.label, self, checkable=True)
            action.setStatusTip(descriptor.description)
            action.setChecked(self.sheet_type == descriptor.key)
            action.triggered.connect(
                lambda _checked=False, key=descriptor.key: self._set_sheet_type(key)
            )
            sheet_type_group.addAction(action)
            sheet_type_menu.addAction(action)
        self.sheet_type_menu = sheet_type_menu
        self.sheet_type_actions = sheet_type_group

        color_menu = self.menuBar().addMenu("&Color")
        self.color_menu = color_menu
        choose_color = QAction("Choose color and paint a box…", self)
        choose_color.triggered.connect(lambda: self._active_customization().choose_paint_color())
        color_menu.addAction(choose_color)
        stop_color = QAction("Stop coloring", self)
        stop_color.triggered.connect(lambda: self._active_customization().stop_painting())
        color_menu.addAction(stop_color)
        color_menu.addSeparator()
        clear_colors = QAction("Clear all custom colors", self)
        clear_colors.triggered.connect(lambda: self._active_customization().clear_colors())
        color_menu.addAction(clear_colors)

        rest_menu = self.menuBar().addMenu("&Rest")
        full_rest = QAction("Take a Full Rest (8 hours)", self)
        full_rest.setShortcut("Ctrl+Shift+R")
        full_rest.triggered.connect(self.perform_full_rest)
        rest_menu.addAction(full_rest)
        configure_rest = QAction("Configure Full Rest…", self)
        configure_rest.triggered.connect(self.configure_full_rest)
        rest_menu.addAction(configure_rest)

        codex_menu = self.menuBar().addMenu("&Codex")
        open_codex = QAction("&Open Codex…", self)
        open_codex.setShortcut("F1")
        open_codex.triggered.connect(lambda: self._open_codex("home"))
        codex_menu.addAction(open_codex)
        codex_menu.addSeparator()
        classes_menu = codex_menu.addMenu("Classes")
        pathfinder_action = QAction("Pathfinder", self)
        pathfinder_action.triggered.connect(lambda: self._open_codex("pathfinder"))
        classes_menu.addAction(pathfinder_action)
        spheres_action = QAction("Spheres", self)
        spheres_action.triggered.connect(lambda: self._open_codex("spheres"))
        classes_menu.addAction(spheres_action)
        codex_menu.addSeparator()
        formula_action = QAction("Formula Language", self)
        formula_action.triggered.connect(lambda: self._open_codex("formulas"))
        codex_menu.addAction(formula_action)
        codex_menu.addSeparator()
        catalog_updates = QAction("Rules Catalog Updates…", self)
        catalog_updates.triggered.connect(self._open_catalog_manager)
        codex_menu.addAction(catalog_updates)

        bestiary_reference = QAction("Bestiary reference", self)
        bestiary_reference.triggered.connect(lambda: self._open_codex("bestiary"))
        codex_menu.addAction(bestiary_reference)
        bestiary_menu = QMenu("&Bestiary", self)
        bestiary_action = QAction("Bestiary & Encounters…", self)
        bestiary_action.triggered.connect(self._open_bestiary)
        bestiary_menu.addAction(bestiary_action)

        blocks_menu = self.menuBar().addMenu("Building &Blocks")
        self.blocks_menu = blocks_menu
        open_blocks = QAction("Open Building Blocks…", self)
        open_blocks.setShortcut("Ctrl+Shift+K")
        open_blocks.triggered.connect(self.open_building_blocks)
        blocks_menu.addAction(open_blocks)
        blocks_menu.addSeparator()
        for label, handler in (
            ("Add sheet tab…", self.add_sheet_tab),
            ("Rename current tab…", self.rename_current_tab),
            ("Duplicate current tab…", self.duplicate_current_tab),
            ("Remove or hide current tab…", self.remove_current_tab),
            ("Restore hidden tab…", self.restore_hidden_tab),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            blocks_menu.addAction(action)
        self._update_sheet_type_controls()

        self.menuBar().addMenu(bestiary_menu)

    def _open_codex(self, page: str = "home") -> None:
        dialog = CodexDialog(page, self)
        dialog.exec()

    def _open_catalog_manager(self) -> None:
        CatalogManagerDialog(parent=self).exec()

    def _open_bestiary(self) -> None:
        from app.encounters import EncounterRepository
        from app.ui.bestiary_dialog import BestiaryDialog
        dialog = BestiaryDialog(EncounterRepository(self.repository.sqlite_connection), self)
        dialog.open_codex.connect(lambda key: self._open_codex("bestiary:" + key))
        dialog.exec()

    def open_building_blocks(self) -> None:
        if self.sheet_type == "refined":
            self.refined_sheet.session.open_blocks()
            return
        character = self._selected_character()
        if character is None:
            QMessageBox.information(self, "No character", "Open a character first.")
            return
        dialog = BuildingBlocksDialog(
            self.repository,
            self.block_repository,
            self.block_registry,
            character.id,
            self.block_repository.list_tabs(character.id),
            self.block_runtime.add_block,
            self,
            remove_block=self.block_runtime.remove_block,
            current_tab_key=self.tab_manager.current_key(),
        )
        dialog.exec()
        self.block_runtime.refresh()

    def add_sheet_tab(self) -> None:
        if self.sheet_type == "refined":
            self.refined_sheet.session.add_tab()
            return
        if self._selected_character() is None:
            return
        name, accepted = QInputDialog.getText(
            self, "Add sheet tab", "Tab name", text="New Page"
        )
        if accepted and name.strip():
            self.presentation_history.record(
                "Add sheet tab",
                lambda: (
                    self.tab_manager.add_tab(name.strip()),
                    self._sync_runtime_canvases(),
                ),
            )

    def rename_current_tab(self) -> None:
        if self.sheet_type == "refined":
            self.refined_sheet.session.rename_tab()
            return
        if self._selected_character() is None:
            return
        key = self.tab_manager.current_key()
        current = self.sheet.page_tabs.tabText(self.sheet.page_tabs.currentIndex())
        name, accepted = QInputDialog.getText(
            self, "Rename sheet tab", "Tab name", text=current
        )
        if accepted and name.strip():
            self.presentation_history.record(
                "Rename sheet tab",
                lambda: self.tab_manager.rename(key, name.strip()),
            )

    def duplicate_current_tab(self) -> None:
        if self.sheet_type == "refined":
            session = self.refined_sheet.session
            name, ok = QInputDialog.getText(self, "Duplicate page", "New page name")
            if ok and name.strip():
                session.history.record("Duplicate page", lambda: (session.tabs.add_tab(name.strip(), source_key=session.tabs.current_key()), session._reload_tabs()))
            return
        if self._selected_character() is None:
            return
        source = self.tab_manager.current_key()
        current = self.sheet.page_tabs.tabText(self.sheet.page_tabs.currentIndex())
        name, accepted = QInputDialog.getText(
            self, "Duplicate sheet tab", "New tab name", text=f"{current} Copy"
        )
        if accepted and name.strip():
            self.presentation_history.record(
                "Duplicate sheet tab",
                lambda: (
                    self.tab_manager.add_tab(name.strip(), source_key=source),
                    self._sync_runtime_canvases(),
                    self.block_runtime.refresh(),
                ),
            )

    def remove_current_tab(self) -> None:
        if self.sheet_type == "refined":
            self.refined_sheet.session.hide_tab()
            return
        character = self._selected_character()
        if character is None:
            return
        key = self.tab_manager.current_key()
        tabs = self.block_repository.list_tabs(character.id)
        visible = [tab for tab in tabs if tab.visible and tab.key != key]
        if not visible:
            QMessageBox.information(
                self, "Keep one tab", "At least one visible sheet tab must remain."
            )
            return
        message = QMessageBox(self)
        message.setWindowTitle("Remove or hide tab")
        message.setText("What should happen to this tab and its visual blocks?")
        move_button = message.addButton(
            "Move blocks and remove tab", QMessageBox.ButtonRole.AcceptRole
        )
        hide_button = message.addButton(
            "Hide tab and retain contents", QMessageBox.ButtonRole.ActionRole
        )
        message.addButton(QMessageBox.StandardButton.Cancel)
        message.exec()
        hide = message.clickedButton() is hide_button
        move_to = ""
        if message.clickedButton() is move_button:
            labels = [tab.name for tab in visible]
            destination, accepted = QInputDialog.getItem(
                self, "Move tab contents", "Destination tab", labels, 0, False
            )
            if not accepted:
                return
            move_to = visible[labels.index(destination)].key
        elif not hide:
            return
        self.presentation_history.record(
            "Hide sheet tab" if hide else "Remove sheet tab",
            lambda: (
                self.block_repository.remove_tab(
                    character.id, key, move_to=move_to, hide=hide
                ),
                self.tab_manager.reload(),
                self._sync_runtime_canvases(),
                self.block_runtime.refresh(),
            ),
        )

    def restore_hidden_tab(self) -> None:
        if self.sheet_type == "refined":
            self.refined_sheet.session.restore_tab()
            return
        character = self._selected_character()
        if character is None:
            return
        hidden = [
            tab
            for tab in self.block_repository.list_tabs(character.id)
            if not tab.visible
        ]
        if not hidden:
            QMessageBox.information(
                self, "No hidden tabs", "This character has no hidden sheet tabs."
            )
            return
        labels = [tab.name for tab in hidden]
        selected, accepted = QInputDialog.getItem(
            self, "Restore sheet tab", "Hidden tab", labels, 0, False
        )
        if not accepted:
            return
        tab_key = hidden[labels.index(selected)].key
        self.presentation_history.record(
            "Restore hidden sheet tab",
            lambda: (
                self.block_repository.set_tab_visible(character.id, tab_key, True),
                self.tab_manager.reload(),
                self._sync_runtime_canvases(),
            ),
        )

    def restore_default_sheet(
        self, _checked: bool = False, *, confirm: bool = True
    ) -> bool:
        """Restore presentation defaults while retaining all character rules data."""
        if self.sheet_type == "refined":
            self.refined_sheet.session.reset(confirm=confirm)
            return self.active_character_id is not None
        character = self._selected_character()
        if character is None:
            return False
        preset = layout_preset_for_character_type(character.character_type)
        if confirm:
            answer = QMessageBox.question(
                self,
                f"Restore {preset.label} Sheet?",
                f"Restore the {preset.label} pages, built-in boxes, positions, sizes, "
                "columns, colors, and cell layouts for this character?\n\n"
                "Custom tabs and placed custom blocks will be removed from this "
                "character's sheet. Reusable Building Blocks templates and all "
                "Pathfinder character data will be preserved.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        history_started = self.presentation_history.begin("Restore Default Sheet")
        self.build_mode_action.setChecked(False)
        self.cell_edit_action.setChecked(False)
        self.content_scale_action.setChecked(False)
        self.repository.clear_character_sheet_layout(character.id)
        self.block_repository.reset_character_presentation(
            character.id, self.block_registry
        )
        default_state = preset.presentation_state()
        self.repository.save_character_sheet_layout(character.id, default_state)
        self.customization.apply_state(default_state)
        self.tab_manager.load_character(character.id)
        self._sync_runtime_canvases()
        self.block_runtime.load_character(character.id)
        self.nested_cell_editor.load_character(character.id)
        self.sheet.page_tabs.setCurrentIndex(0)
        self.pages.setCurrentIndex(1)
        QTimer.singleShot(0, self.customization.refresh_canvas_sizes)
        self.statusBar().showMessage(
            f"{preset.label} sheet restored. Character rules data was preserved.",
            7000,
        )
        if history_started:
            self.presentation_history.commit()
        return True

    def _sync_runtime_canvases(self) -> None:
        self.customization.set_canvases(self.tab_manager.canvases)
        self.block_runtime.set_canvases(self.tab_manager.canvases)

    def _capture_presentation_snapshot(self) -> PresentationSnapshot | None:
        character = self._selected_character()
        if character is None:
            return None
        return PresentationSnapshot(
            character.id,
            dict(self.customization.capture_state()),
            self.block_repository.export_character_state(character.id),
            self.tab_manager.current_key(),
        )

    def _apply_presentation_snapshot(self, snapshot: PresentationSnapshot) -> None:
        character = self._selected_character()
        if character is None or character.id != snapshot.character_id:
            return
        current_layout = dict(self.customization.capture_state())
        current_blocks = self.block_repository.export_character_state(character.id)
        layout_changed = current_layout != snapshot.layout
        blocks_changed = current_blocks != snapshot.building_blocks

        if snapshot.layout:
            self.repository.save_character_sheet_layout(
                character.id, snapshot.layout
            )
        else:
            self.repository.clear_character_sheet_layout(character.id)

        # A cell drag/resize changes only cell_overrides. Rebuilding every tab,
        # deleting/recreating all block instances, and reconstructing every
        # custom widget made Ctrl+Z unnecessarily expensive. Keep stable block
        # IDs and update those rows in one transaction instead.
        if blocks_changed and self._same_sheet_structure(
            current_blocks, snapshot.building_blocks
        ):
            self.block_repository.replace_character_cell_overrides(
                character.id, snapshot.building_blocks
            )
            self.nested_cell_editor.clear_selection()
            if layout_changed:
                self.customization.apply_state(snapshot.layout)
                self.block_runtime.refresh()
            self.nested_cell_editor.apply_overrides()
            self._select_presentation_tab(snapshot.current_tab)
            QTimer.singleShot(0, self.customization.refresh_canvas_sizes)
            return

        if not blocks_changed:
            if layout_changed:
                self.customization.apply_state(snapshot.layout)
                self.block_runtime.refresh()
                self.nested_cell_editor.apply_overrides()
            self._select_presentation_tab(snapshot.current_tab)
            QTimer.singleShot(0, self.customization.refresh_canvas_sizes)
            return

        self.block_repository.import_character_state(
            character.id, snapshot.building_blocks
        )
        self.tab_manager.load_character(character.id)
        self._sync_runtime_canvases()
        self.block_runtime.load_character(character.id)
        self.nested_cell_editor.load_character(character.id)
        self.customization.sync_sections()
        self.customization.apply_state(snapshot.layout)
        self.block_runtime.refresh()
        self.nested_cell_editor.apply_overrides()
        self._select_presentation_tab(snapshot.current_tab)
        QTimer.singleShot(0, self.customization.refresh_canvas_sizes)

    @staticmethod
    def _same_sheet_structure(left: dict, right: dict) -> bool:
        if left.get("tabs", ()) != right.get("tabs", ()):
            return False
        left_blocks = [
            {key: value for key, value in block.items() if key != "cell_overrides"}
            for block in left.get("blocks", ())
        ]
        right_blocks = [
            {key: value for key, value in block.items() if key != "cell_overrides"}
            for block in right.get("blocks", ())
        ]
        return left_blocks == right_blocks

    def _select_presentation_tab(self, tab_key: str) -> None:
        if not tab_key or self.tab_manager.current_key() == tab_key:
            return
        for index in range(self.sheet.page_tabs.count()):
            self.sheet.page_tabs.setCurrentIndex(index)
            if self.tab_manager.current_key() == tab_key:
                return

    def _native_text_history(self, *, redo: bool) -> bool:
        focus = QApplication.focusWidget()
        if focus is None:
            return False
        available_name = "isRedoAvailable" if redo else "isUndoAvailable"
        operation_name = "redo" if redo else "undo"
        available = getattr(focus, available_name, None)
        operation = getattr(focus, operation_name, None)
        if callable(available) and callable(operation) and available():
            operation()
            return True
        document = getattr(focus, "document", None)
        if callable(document) and callable(operation):
            document_value = document()
            checker = getattr(document_value, available_name, None)
            if callable(checker) and checker():
                operation()
                return True
        return False

    def undo(self) -> None:
        if self._native_text_history(redo=False):
            return
        if self.sheet_type == "refined":
            self.refined_sheet.session.history.undo(self.active_character_id)
            return
        character = self._selected_character()
        self.presentation_history.undo(None if character is None else character.id)

    def redo(self) -> None:
        if self._native_text_history(redo=True):
            return
        if self.sheet_type == "refined":
            self.refined_sheet.session.history.redo(self.active_character_id)
            return
        character = self._selected_character()
        self.presentation_history.redo(None if character is None else character.id)

    def _update_history_actions(self) -> None:
        if not hasattr(self, "undo_action"):
            return
        if self.sheet_type == "refined" and getattr(self, "refined_sheet", None) is not None:
            history = self.refined_sheet.session.history
            self.undo_action.setEnabled(history.can_undo(self.active_character_id))
            self.redo_action.setEnabled(history.can_redo(self.active_character_id))
            self.undo_action.setText("Undo " + history.undo_description(self.active_character_id))
            self.redo_action.setText("Redo " + history.redo_description(self.active_character_id))
            return
        if self.sheet_type != "customizable":
            self.undo_action.setText("Undo")
            self.redo_action.setText("Redo")
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
            return
        character = self._selected_character()
        character_id = None if character is None else character.id
        undo_label = self.presentation_history.undo_description(character_id)
        redo_label = self.presentation_history.redo_description(character_id)
        self.undo_action.setText(f"Undo {undo_label}" if undo_label else "Undo")
        self.redo_action.setText(f"Redo {redo_label}" if redo_label else "Redo")
        self.undo_action.setEnabled(self.presentation_history.can_undo(character_id))
        self.redo_action.setEnabled(self.presentation_history.can_redo(character_id))

    def configure_full_rest(self) -> None:
        character = self._selected_character()
        if character is None:
            QMessageBox.information(self, "No character", "Open a character first.")
            return
        engine = FullRestEngine(self.repository, character.id)
        dialog = RestConfigurationDialog(
            engine.targets(), engine.effective_preferences(), self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.repository.save_rest_preferences(character.id, dialog.preferences())
        self.statusBar().showMessage(
            f'Full Rest configuration saved for "{character.name}".', 5000
        )

    def perform_full_rest(self) -> None:
        character = self._selected_character()
        if character is None:
            QMessageBox.information(self, "No character", "Open a character first.")
            return
        engine = FullRestEngine(self.repository, character.id)
        enabled = engine.effective_preferences()
        selected = [target.name for target in engine.targets() if enabled.get(target.key)]
        if not selected:
            QMessageBox.information(
                self,
                "Full Rest",
                "No rest effects are enabled. Use Rest > Configure Full Rest first.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Take a Full Rest?",
            "Apply the configured eight-hour rest effects?\n\n"
            + "\n".join(f"• {name}" for name in selected),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        results = engine.perform(enabled)
        self._refresh_character_and_runtime()
        summary = "\n".join(f"• {item.name}: {item.summary}" for item in results)
        QMessageBox.information(
            self,
            "Full Rest complete",
            summary or "The rest completed without changing any tracked value.",
        )

    def _set_theme(self, theme: str) -> None:
        if theme not in THEME_LABELS:
            return
        self.theme = theme
        self.settings.setValue("appearance/theme", theme)
        self.setStyleSheet(self._style_sheet(theme))
        self.dialog_theme_boundary.refresh()
        if getattr(self, "refined_sheet", None) is not None:
            self.refined_sheet.set_theme(theme)
        if hasattr(self, "customization"):
            self.customization.content_scale.restore()

    def _set_sheet_type(self, sheet_type: str, *, remember: bool = True, reload_character: bool = True) -> None:
        if sheet_type not in SHEET_TYPE_REGISTRY:
            return
        if getattr(self, "refined_sheet", None) is not None and self.sheet_type == "refined":
            self.refined_sheet.session.save()
            self.refined_sheet.customize_button.setChecked(False)
        self.sheet_type = sheet_type
        if sheet_type == "refined":
            self._ensure_refined_sheet()
        elif sheet_type not in self.sheet_widgets:
            self._ensure_optional_sheet(sheet_type)
        if remember:
            if sheet_type != "refined":
                self.settings.setValue("appearance/sheetType", sheet_type)
            if self.active_character_id is not None:
                self.style_store.save(self.active_character_id, "selection", {"style": sheet_type})
        if hasattr(self, "sheet_type_actions"):
            for action, descriptor in zip(
                self.sheet_type_actions.actions(), sheet_type_descriptors()
            ):
                action.setChecked(descriptor.key == sheet_type)
        if hasattr(self, "sheet_stack"):
            widget = self.sheet_widgets[sheet_type]
            self.sheet_stack.setCurrentWidget(widget)
            if self.active_character_id is not None and reload_character:
                widget.load_character(self.active_character_id)
        self._update_sheet_type_controls()
        self._update_history_actions()

    def _update_sheet_type_controls(self) -> None:
        if not hasattr(self, "build_menu"):
            return
        customizable = (self.active_character_id is not None
                        and SHEET_TYPE_REGISTRY[self.sheet_type].supports_customization)
        if not customizable:
            self.build_mode_action.setChecked(False)
            self.cell_edit_action.setChecked(False)
            self.content_scale_action.setChecked(False)
        self.build_menu.setEnabled(customizable)
        self.color_menu.setEnabled(customizable)
        self.blocks_menu.setEnabled(customizable)
        self.save_layout_action.setEnabled(customizable)

    def _set_cell_edit_mode(self, enabled: bool) -> None:
        if enabled and not self.build_mode_action.isChecked():
            self.build_mode_action.setChecked(True)
        if self.sheet_type == "refined":
            self.refined_sheet.session.mode.setCurrentIndex(3 if enabled else 0)
        else:
            self._active_customization().set_cell_edit_mode(enabled)

    def _set_content_scale_mode(self, enabled: bool) -> None:
        if self.sheet_type == "refined":
            self.refined_sheet.session.mode.setCurrentIndex(2 if enabled else 0)
        else:
            self._active_customization().set_content_scale_mode(enabled)

    def _active_customization(self):
        if self.sheet_type == "refined":
            return self.refined_sheet.session.controller
        return self.customization

    def _set_build_mode(self, enabled):
        if self.sheet_type == "refined":
            self.refined_sheet.customize_button.setChecked(enabled)
        else:
            self.customization.set_build_mode(enabled)

    def _library_page(self) -> QWidget:
        self.character_library = CharacterLibraryPage()
        self.character_library.open_requested.connect(self._select_character)
        self.character_library.create_requested.connect(self.create_character)
        return self.character_library

    def _character_page(self) -> QWidget:
        page = QWidget()
        self.character_page_widget = page
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.sheet_widgets = {
            descriptor.key: descriptor.create(self.repository)
            for descriptor in sheet_type_descriptors()
            if descriptor.key == "customizable"
        }
        self.sheet = self.sheet_widgets["customizable"]
        self.original_spheres_sheet = None
        self.ultra_sheet = None
        self.refined_sheet = None
        self.style_store = SheetStyleStore(self.repository)
        for widget in self.sheet_widgets.values():
            renamed = getattr(widget, "character_renamed", None)
            if renamed is not None:
                renamed.connect(lambda character_id: self.refresh_characters(character_id))
            rest_requested = getattr(widget, "full_rest_requested", None)
            if rest_requested is not None:
                rest_requested.connect(self.perform_full_rest)
        self.sheet_stack = QStackedWidget()
        for descriptor in sheet_type_descriptors():
            if descriptor.key in self.sheet_widgets:
                self.sheet_stack.addWidget(self.sheet_widgets[descriptor.key])
        self.sheet_stack.setCurrentWidget(self.sheet_widgets.get(self.sheet_type, self.sheet))
        self.customization = SheetCustomizationController(
            self, self.sheet, self.sheet.custom_sections, self.sheet.custom_layouts
        )
        self.sheet.custom_sections_changed.connect(self.customization.sync_sections)
        self.tab_manager = SheetTabManager(self.sheet, self.block_repository)
        self.block_runtime = BlockRuntimeController(
            self.sheet,
            self.customization,
            self.repository,
            self.block_repository,
            self.block_registry,
            {
                "full_rest": self.perform_full_rest,
                "refresh": self._refresh_character_and_runtime,
            },
        )
        self.sheet.formula_values_changed.connect(self.block_runtime.refresh)
        self.nested_cell_editor = NestedCellEditor(
            self.sheet, self.block_repository, self.block_runtime, self.tab_manager
        )
        self.customization.set_nested_editor(self.nested_cell_editor)
        self.customization.set_geometry_saved_callback(
            self.block_runtime.save_widget_geometry
        )
        self.block_runtime.set_nested_editor(self.nested_cell_editor)
        self.presentation_history = PresentationHistory(
            self._capture_presentation_snapshot,
            self._apply_presentation_snapshot,
        )
        self.customization.set_history(self.presentation_history)
        self.nested_cell_editor.set_history(self.presentation_history)
        self.block_runtime.set_history(self.presentation_history)
        self.tab_manager.set_history(self.presentation_history)

        build_header = QWidget()
        build_header.setObjectName("buildCharacterHeader")
        self.build_header = build_header
        header_wrapper = QVBoxLayout(build_header)
        header_wrapper.setContentsMargins(10, 4, 10, 4)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        self.character_name = QLabel()
        self.character_name.setObjectName("heroTitle")
        self.character_type = QLabel()
        self.character_type.setObjectName("pageSubtitle")
        titles.addWidget(self.character_name)
        titles.addWidget(self.character_type)
        header.addLayout(titles)
        header.addStretch()
        rename_button = QPushButton("Rename")
        rename_button.clicked.connect(self.rename_selected)
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self.delete_selected)
        header.addWidget(rename_button)
        header.addWidget(delete_button)
        header_wrapper.addLayout(header)
        self.sheet.builder_layout.insertWidget(0, build_header)
        layout.addWidget(self.sheet_stack, 1)
        self.floating_notes = FloatingNoteManager(
            self.repository,
            page,
            self._current_note_page_key,
            lambda expression: self.sheet_widgets[self.sheet_type]._evaluate_character_formula(expression)
                if self.sheet_type == "refined" else self.sheet._evaluate_character_formula(expression),
            lambda: self.sheet_widgets[self.sheet_type]._character_formula_suggestions()
                if self.sheet_type == "refined" else self.sheet._character_formula_suggestions(),
        )
        self.sheet.formula_values_changed.connect(
            self.floating_notes.refresh_formulas
        )
        self.sheet.page_tabs.currentChanged.connect(
            lambda _index: self.floating_notes.page_changed()
        )
        self.sheet_stack.currentChanged.connect(
            lambda _index: self.floating_notes.page_changed()
        )
        return page

    def _ensure_refined_sheet(self):
        """Do not impose a fourth widget tree on users of the original styles."""
        if self.refined_sheet is not None:
            return self.refined_sheet
        widget = SHEET_TYPE_REGISTRY["refined"].create(self.repository)
        self.refined_sheet = widget
        self.sheet_widgets["refined"] = widget
        widget.attach_host(self)
        widget.set_theme(self.theme)
        renamed=getattr(widget,"character_renamed",None)
        if renamed is not None:
            renamed.connect(lambda character_id:self.refresh_characters(character_id))
        widget.full_rest_requested.connect(self.perform_full_rest)
        widget.notes_requested.connect(lambda: self.floating_notes.create_or_show(widget.mapToGlobal(widget.rect().center())))
        widget.formula_values_changed.connect(self.floating_notes.refresh_formulas)
        widget.page_tabs.currentChanged.connect(lambda _index: self.floating_notes.page_changed())
        self.sheet_stack.addWidget(widget)
        return widget

    def _ensure_optional_sheet(self, key):
        """Keep unused fixed sheet styles out of startup and refresh work."""
        if key in self.sheet_widgets:
            return self.sheet_widgets[key]
        widget = SHEET_TYPE_REGISTRY[key].create(self.repository)
        self.sheet_widgets[key] = widget
        setattr(self, "original_spheres_sheet" if key == "original_spheres" else "ultra_sheet", widget)
        renamed = getattr(widget, "character_renamed", None)
        if renamed is not None:
            renamed.connect(lambda character_id: self.refresh_characters(character_id))
        rest_requested = getattr(widget, "full_rest_requested", None)
        if rest_requested is not None:
            rest_requested.connect(self.perform_full_rest)
        self.sheet_stack.addWidget(widget)
        return widget

    def _current_note_page_key(self) -> str:
        if self.sheet_type == "refined":
            return "refined:" + (self.refined_sheet.session.tabs.current_key()
                                 if self.refined_sheet is not None else "core")
        if self.sheet_stack.currentWidget() is self.sheet:
            return self.tab_manager.current_key()
        return f"sheet-type:{self.sheet_type}"

    def _refresh_character_and_runtime(self) -> None:
        """Refresh sheet calculations and every formula-bearing runtime block."""

        # The legacy sheet supplies shared command adapters; other hidden
        # presentations reload from the repository when explicitly selected.
        for key in {"customizable", self.sheet_type}:
            self.sheet_widgets[key].refresh_all()
        if hasattr(self, "block_runtime"):
            self.block_runtime.refresh()

    def refresh_characters(
        self,
        select_id: int | None = None,
        *,
        open_selected: bool = True,
    ) -> None:
        if select_id is None and open_selected:
            selected = self._selected_character()
            select_id = None if selected is None else selected.id
        characters = self.repository.list_characters()
        available_ids = {character.id for character in characters}
        if open_selected and select_id not in available_ids:
            select_id = characters[0].id if characters else None
        if not open_selected:
            select_id = None
        self.character_list.blockSignals(True)
        self.character_list.clear()
        library_entries: list[CharacterLibraryEntry] = []
        for character in characters:
            item = QListWidgetItem(f"{character.name}\n{character.character_type}")
            item.setData(Qt.ItemDataRole.UserRole, character)
            self.character_list.addItem(item)
            library_entries.append(
                CharacterLibraryEntry.from_character(
                    character, self.repository.list_class_levels(character.id)
                )
            )
            if character.id == select_id:
                self.character_list.setCurrentItem(item)
        self.character_list.blockSignals(False)
        self.character_library.set_entries(library_entries)
        self._refresh_switch_character_menu()
        if not characters:
            self._clear_active_character()
        elif open_selected:
            self._show_selected()
        else:
            self.show_character_library()

    def show_character_library(self) -> None:
        """Return to the launcher without discarding the active sheet state."""

        self._save_active_arrangement()
        if hasattr(self, "floating_notes"):
            self.floating_notes.set_host_visible(False)
        self.pages.setCurrentWidget(self.character_library)

    def _clear_active_character(self) -> None:
        """Return to the library without retaining a deleted/stale active ID."""

        self.active_character_id = None
        if hasattr(self, "floating_notes"):
            self.floating_notes.clear()
        self.presentation_history.cancel()
        self.character_name.clear()
        self.character_type.clear()
        self.pages.setCurrentIndex(0)
        self._refresh_switch_character_menu()
        self._update_history_actions()

    def _save_active_arrangement(self) -> bool:
        """Persist the active layout only while its owning character still exists."""

        character_id = self.active_character_id
        if character_id is None or not self.repository.character_exists(character_id):
            return False
        if self.refined_sheet is not None:
            self.refined_sheet.session.save()
        self.repository.save_character_sheet_layout(
            character_id, self.customization.capture_state()
        )
        return True

    def _refresh_switch_character_menu(self) -> None:
        if not hasattr(self, "switch_character_menu"):
            return
        self.switch_character_menu.clear()
        current = self._selected_character()
        for character in self.repository.list_characters():
            action = QAction(character.name, self, checkable=True)
            action.setChecked(current is not None and current.id == character.id)
            action.setStatusTip(character.character_type)
            action.triggered.connect(
                lambda _checked=False, character_id=character.id: self._select_character(character_id)
            )
            self.switch_character_menu.addAction(action)
        self.switch_character_menu.setEnabled(bool(self.switch_character_menu.actions()))

    def _select_character(self, character_id: int) -> None:
        for row in range(self.character_list.count()):
            item = self.character_list.item(row)
            character = item.data(Qt.ItemDataRole.UserRole)
            if character is not None and character.id == character_id:
                if self.character_list.currentItem() is item:
                    self._show_selected()
                else:
                    self.character_list.setCurrentItem(item)
                self._refresh_switch_character_menu()
                return

    def create_character(self) -> None:
        guided = bool(
            getattr(self, "guided_creation_action", None)
            and self.guided_creation_action.isChecked()
        )
        dialog = (
            GuidedCharacterCreationDialog(self) if guided else NewCharacterDialog(self)
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        draft = dialog.draft if guided else None
        name = draft.name if draft is not None else dialog.name
        character_type = (
            draft.character_type if draft is not None else dialog.character_type
        )
        try:
            character_id = self.repository.create_character(name, character_type)
            if draft is not None:
                apply_character_creation_draft(
                    self.repository, character_id, draft
                )
        except ValueError as error:
            if "character_id" in locals() and self.repository.character_exists(character_id):
                self.repository.delete_character(character_id)
            QMessageBox.warning(self, "Cannot create character", str(error))
            return
        preset = layout_preset_for_character_type(character_type)
        default_state = preset.presentation_state()
        if default_state:
            self.repository.save_character_sheet_layout(character_id, default_state)
        self.refresh_characters(character_id)

    def rename_selected(self) -> None:
        character = self._selected_character()
        if character is None:
            return
        name, accepted = QInputDialog.getText(
            self, "Rename character", "Character name:", text=character.name
        )
        if accepted:
            try:
                self.repository.rename_character(character.id, name)
            except ValueError as error:
                QMessageBox.warning(self, "Cannot rename character", str(error))
                return
            self.refresh_characters(character.id)

    def export_selected(self) -> None:
        character = self._selected_character()
        if character is None:
            QMessageBox.information(self, "Select a character", "Select a character first.")
            return
        suggested = self._suggested_save_filename(character)
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export character", suggested, "Character files (*.character.json);;JSON (*.json)"
        )
        if not filename:
            return
        try:
            export_character(self.repository, character.id, Path(filename))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Export failed", str(error))
            return
        self._remember_save_directory(filename)
        QMessageBox.information(self, "Character exported", "The character file was saved.")

    def save_sheet_arrangement(self, _checked: bool = False, *, notify: bool = True) -> bool:
        if self.sheet_type == "refined":
            self.refined_sheet.session.save()
            if notify:
                self.statusBar().showMessage("Refined Sheet arrangement saved.", 4000)
            return self.active_character_id is not None
        character = self._selected_character()
        if character is None:
            if notify:
                QMessageBox.information(self, "No character", "Open a character first.")
            return False
        self.repository.save_character_sheet_layout(
            character.id, self.customization.capture_state()
        )
        if notify:
            self.statusBar().showMessage(
                f'Sheet arrangement saved to "{character.name}".', 5000
            )
        return True

    def save_character(self) -> None:
        character = self._selected_character()
        if character is None:
            QMessageBox.information(self, "No character", "Open a character first.")
            return
        paths = self._character_save_paths()
        filename = paths.get(str(character.id), "")
        if not filename:
            self.save_character_as()
            return
        self.save_sheet_arrangement(notify=False)
        try:
            export_character(self.repository, character.id, Path(filename))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Save failed", str(error))
            return
        self._remember_save_directory(filename)
        self.statusBar().showMessage(f'Character saved to "{filename}".', 5000)

    def save_character_as(self) -> None:
        character = self._selected_character()
        if character is None:
            QMessageBox.information(self, "No character", "Open a character first.")
            return
        paths = self._character_save_paths()
        suggested = self._suggested_save_filename(
            character, paths.get(str(character.id), "")
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save character as",
            suggested,
            "Character files (*.character.json);;JSON (*.json)",
        )
        if not filename:
            return
        self.save_sheet_arrangement(notify=False)
        try:
            export_character(self.repository, character.id, Path(filename))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Save failed", str(error))
            return
        paths[str(character.id)] = filename
        self.settings.setValue("files/characterPaths", json.dumps(paths))
        self._remember_save_directory(filename)
        self.statusBar().showMessage(f'Character saved to "{filename}".', 5000)

    @staticmethod
    def _application_folder() -> Path:
        """Folder containing the installed/source application entry point."""

        return application_folder()

    def _last_save_directory(self) -> Path:
        saved = str(self.settings.value("files/lastSaveDirectory", "") or "").strip()
        if saved:
            candidate = Path(saved).expanduser()
            if candidate.is_dir():
                return candidate.resolve()
        return self._application_folder()

    def _suggested_save_filename(
        self, character: CharacterSummary, existing_filename: str = ""
    ) -> str:
        if existing_filename:
            existing = Path(existing_filename).expanduser()
            if existing.parent.is_dir():
                return str(existing.resolve())
        return str(
            self._last_save_directory() / f"{character.name}.character.json"
        )

    def _remember_save_directory(self, filename: str | Path) -> None:
        folder = Path(filename).expanduser().resolve().parent
        if folder.is_dir():
            self.settings.setValue("files/lastSaveDirectory", str(folder))

    def _character_save_paths(self) -> dict[str, str]:
        raw = str(self.settings.value("files/characterPaths", "{}") or "{}")
        try:
            values = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return {
            str(key): str(value)
            for key, value in values.items()
        } if isinstance(values, dict) else {}

    def import_from_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import character", "", "Character files (*.character.json *.json)"
        )
        if not filename:
            return
        try:
            character_id = import_character(self.repository, Path(filename))
        except (OSError, ValueError, KeyError, TypeError) as error:
            QMessageBox.warning(self, "Import failed", str(error))
            return
        self.refresh_characters(character_id)

    def delete_selected(self) -> None:
        character = self._selected_character()
        if character is None:
            return
        answer = QMessageBox.question(
            self, "Delete character", f'Delete "{character.name}"? This cannot be undone.'
        )
        if answer == QMessageBox.StandardButton.Yes:
            deleted_id = character.id
            self.repository.delete_character(deleted_id)
            if self.active_character_id == deleted_id:
                self.active_character_id = None
            self.presentation_history.discard(deleted_id)
            save_paths = self._character_save_paths()
            if save_paths.pop(str(deleted_id), None) is not None:
                self.settings.setValue("files/characterPaths", json.dumps(save_paths))
            remaining = self.repository.list_characters()
            next_id = remaining[0].id if remaining else None
            self.refresh_characters(next_id)

    def _show_selected(self) -> None:
        character = self._selected_character()
        if character is None:
            return
        if self.active_character_id is not None and self.active_character_id != character.id:
            self._save_active_arrangement()
        self.active_character_id = character.id
        self.character_name.setText(character.name)
        self.character_type.setText(character.character_type)
        if hasattr(self, "reset_layout_action"):
            preset = layout_preset_for_character_type(character.character_type)
            self.reset_layout_action.setText(
                f"Restore {preset.label} Sheet for this character…"
            )
        self.sheet.load_character(character.id)
        self.block_repository.ensure_character(character.id, self.block_registry)
        self.tab_manager.load_character(character.id)
        self.customization.set_canvases(self.tab_manager.canvases)
        self.block_runtime.set_canvases(self.tab_manager.canvases)
        self.block_runtime.load_character(character.id)
        self.nested_cell_editor.load_character(character.id)
        self.customization.sync_sections()
        arrangement = self.repository.get_character_sheet_layout(character.id)
        if not arrangement:
            arrangement = layout_preset_for_character_type(
                character.character_type
            ).presentation_state()
            if arrangement:
                self.repository.save_character_sheet_layout(
                    character.id, arrangement
                )
        self.customization.apply_state(arrangement)
        self.block_runtime.refresh()
        self.nested_cell_editor.apply_overrides()
        preference = self.style_store.get(character.id, "selection")
        fallback = DEFAULT_SHEET_TYPE
        selected_style=normalize_sheet_type(preference.get("style", fallback))
        self._set_sheet_type(selected_style, remember=False, reload_character=selected_style!="customizable")
        self.floating_notes.load_character(character.id)
        self.pages.setCurrentIndex(1)
        self.floating_notes.set_host_visible(True)
        QTimer.singleShot(0, self.customization.refresh_canvas_sizes)
        self._refresh_switch_character_menu()
        self._update_history_actions()

    def closeEvent(self, event) -> None:
        self._save_active_arrangement()
        if hasattr(self, "floating_notes"):
            self.floating_notes.save_all()
        application = getattr(self, "_context_menu_application", None)
        if application is not None:
            application.removeEventFilter(self)
            self._context_menu_application = None
        self.customization.dispose()
        for widget in self.sheet_widgets.values():
            dispose = getattr(widget, "dispose", None)
            if callable(dispose):
                dispose()
        self.block_repository.close()
        super().closeEvent(event)

    def _selected_character(self) -> CharacterSummary | None:
        item = self.character_list.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)


class NewCharacterDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New character")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_input = QLineEdit()
        self.type_input = QComboBox()
        self.type_input.addItems(CHARACTER_TYPES)
        form.addRow("Name", self.name_input)
        form.addRow("Rules", self.type_input)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def name(self) -> str:
        return self.name_input.text().strip()

    @property
    def character_type(self) -> str:
        return self.type_input.currentText()

    def _accept_if_valid(self) -> None:
        if not self.name:
            QMessageBox.warning(self, "Name required", "Enter a character name.")
            return
        self.accept()

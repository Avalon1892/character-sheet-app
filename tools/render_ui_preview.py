from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QCheckBox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import CharacterRepository
from app.content import magic_entries, magic_sphere
from app.models import CastingProfile, ClassLevel
from app.ui.main_window import MainWindow
from app.ui.main_window import CodexDialog
from app.item_effects import automation_for_entry, automation_json
from app.ui.dialogs import (
    ArchetypeSelectionDialog, AttackDialog, ClassCatalogDialog, EquipmentDialog, ItemCatalogDialog,
    ItemChoiceDialog, ItemEnchantmentsDialog, RestConfigurationDialog,
    TraditionalSpellCatalogDialog,
)
from app.attack_profiles import UNARMED_ATTACK_TEMPLATE
from app.item_enchantments import AGILE, enchantment_spec
from app.recovery import FullRestEngine
from app.building_blocks.catalog import BuildingBlocksDialog
from app.building_blocks.designer import BlockDesignerDialog
from app.building_blocks.schemas import BlockDefinition, CellDefinition


def main() -> None:
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(
            QSettings.Format.IniFormat, QSettings.Scope.UserScope, directory
        )
        repository = CharacterRepository(Path(directory) / "preview.db")
        character_id = repository.create_character("Song, Disciple of the Incomplete Form", "Spheres")
        repository.update_ability_score(character_id, "strength", 13)
        repository.update_ability_score(character_id, "dexterity", 22)
        repository.update_ability_score(character_id, "constitution", 13)
        repository.update_ability_score(character_id, "intelligence", 13)
        repository.update_ability_score(character_id, "wisdom", 16)
        repository.update_ability_score(character_id, "charisma", 9)
        repository.add_class_level(
            character_id,
            "Prodigy",
            5,
            "3/4",
            "Poor",
            "Good",
            "Good",
            preset_key="prodigy",
            hit_die=8,
            hp_gained=30,
        )
        repository.add_custom_tracker(
            character_id,
            "house_spell_points",
            "House Spell Points",
            "pool",
            formula="floor(classes.prodigy.level / 3)",
            current_value=1,
            unit="SP",
            recovery_event="full_rest",
            recovery_operation="set_to_max",
        )
        repository.add_custom_tracker(
            character_id,
            "tactical_reserve",
            "Tactical Reserve",
            "calculated",
            formula="trackers.house_spell_points.maximum + abilities.wisdom.modifier",
        )
        repository.update_casting_profile(
            CastingProfile(
                character_id,
                casting_ability="wisdom",
                casting_class_levels=5,
                caster_level=5,
                spell_points_current=8,
                spell_points_misc=0,
                auto_spell_points=True,
                tradition_name="Traditional Magic",
            )
        )
        for index in range(6):
            repository.add_martial_talent(
                character_id,
                f"Sample Martial Talent {index + 1}",
                "Athletics" if index < 3 else "Fencing",
                "Talent",
                "A representative martial talent description used to verify the compact table and hover details.",
                catalog_category="Talent",
                prerequisites="Matching base sphere",
            )
        for index in range(5):
            repository.add_feat(
                character_id,
                f"Sample Feat {index + 1}",
                notes="A representative feat description used for visual layout verification.",
                catalog_category="Pathfinder · Combat",
            )
        repository.add_trait(
            character_id,
            "Reactionary",
            notes="You were bullied often as a child, but never quite developed an offensive response.",
            catalog_category="Pathfinder · Combat",
        )
        repository.add_trait(
            character_id,
            "Seeker",
            notes="You are always on the lookout for reward and danger.",
            catalog_category="Pathfinder · Magic",
        )
        wisdom_automation = automation_for_entry({"name": "Headband of Inspired Wisdom +6"})
        repository.add_equipment(
            character_id, "Headband of Inspired Wisdom +6", "Gear", 1, 1, True,
            0, "untyped", None, "Reviewed item automation preview", slot="Headband",
            state="worn", automation_json=automation_json(wisdom_automation),
        )
        cloak_automation = automation_for_entry({"name": "Cloak of Resistance +3"})
        repository.add_equipment(
            character_id, "Cloak of Resistance +3", "Gear", 1, 1, True,
            0, "untyped", None, "Three independent save effects", slot="Shoulders",
            state="worn", automation_json=automation_json(cloak_automation),
        )
        weapon_id = repository.add_equipment(
            character_id, "+2 Longsword", "Weapon", 1, 4, True, 0, "untyped",
            None, "Linked weapon preview", state="wielded", enhancement_bonus=2,
            masterwork=True, weapon_damage_dice="1d8", weapon_damage_type="slashing",
            weapon_critical="19-20/x2", weapon_range="Melee",
        )
        repository.add_attack(
            character_id, "Longsword", "Melee", "strength", 0, "1d8",
            "strength", 1.0, 0, "19-20/x2", "Linked to inventory weapon",
            equipment_id=weapon_id,
        )
        for key in (
            "pathfinder:enchantment:weapon:melee:keen",
            "pathfinder:enchantment:weapon:universal:flaming",
        ):
            property_spec = enchantment_spec(key)
            repository.add_item_enchantment(
                character_id, weapon_id, property_spec.key, property_spec.name,
                property_spec.bonus_equivalent, property_spec.description,
            )
        amulet_id = repository.add_equipment(
            character_id, "Amulet of Mighty Fists", "Gear", 1, 0, True,
            0, "untyped", None, "Composable property preview", slot="Neck",
            state="worn", catalog_key="reviewed:amulet-of-mighty-fists:customizable",
        )
        repository.add_item_enchantment(
            character_id, amulet_id, AGILE.key, AGILE.name,
            AGILE.bonus_equivalent, AGILE.description,
        )
        repository.add_feat(character_id, "Weapon Finesse")
        repository.add_attack(character_id, **UNARMED_ATTACK_TEMPLATE.values)
        warp = magic_sphere("Warp")
        repository.add_spell(
            character_id,
            "Warp Sphere",
            system="Sphere",
            school_or_sphere="Warp",
            notes=str(warp["description"]),
            catalog_key="warp:base",
            catalog_category="Base Sphere",
            source_url=str(warp["source_url"]),
        )
        for entry in (
            item
            for item in magic_entries("Warp")
            if item["category"] not in {"Base Sphere", "Drawback"}
        ):
            repository.add_spell(
                character_id,
                str(entry["name"]),
                system="Sphere",
                school_or_sphere="Warp",
                notes=str(entry["description"]),
                catalog_key=str(entry["key"]),
                catalog_category=str(entry["category"]),
                prerequisites=str(entry.get("prerequisites", "")),
                source_url=str(entry.get("source_url", "")),
            )
            if len(repository.list_spells(character_id)) >= 4:
                break
        life = magic_sphere("Life")
        repository.add_spell(
            character_id,
            "Life Sphere",
            system="Sphere",
            school_or_sphere="Life",
            notes=str(life["description"]),
            catalog_key="life:base",
            catalog_category="Base Sphere",
            source_url=str(life["source_url"]),
        )
        window = MainWindow(repository)
        window.resize(1440, 900)
        window.refresh_characters()
        window.character_list.setCurrentRow(0)
        window.show()
        application.processEvents()
        window.sheet.prodigy_imbue_combo.setCurrentIndex(
            window.sheet.prodigy_imbue_combo.findData("life_regenerate")
        )
        window.sheet._store_prodigy_sequence(True, 4)
        page_scrolls = (
            window.sheet.builder_scroll,
            window.sheet.core_scroll,
            window.sheet.inventory_scroll,
            window.sheet.magic_scroll,
        )
        for theme in ("classic", "dark"):
            window._set_theme(theme)
            for page in range(4):
                window.sheet.page_tabs.setCurrentIndex(page)
                page_scrolls[page].verticalScrollBar().setValue(0)
                application.processEvents()
                window.grab().save(str(output / f"{theme}-page-{page + 1}.png"))
                page_scrolls[page].verticalScrollBar().setValue(
                    page_scrolls[page].verticalScrollBar().maximum()
                )
                application.processEvents()
                window.grab().save(
                    str(output / f"{theme}-page-{page + 1}-bottom.png")
                )
        window._set_theme("classic")
        wizard_class_id = repository.add_class_level(
            character_id, "Wizard", 5, "1/2", "Poor", "Poor", "Good",
            preset_key="wizard", hit_die=6, hp_gained=18,
        )
        fireball_id = repository.add_spell(
            character_id, "Fireball", system="Prepared", level=3,
            school_or_sphere="Evocation", casting_time="1 standard action",
            range="Long", duration="Instantaneous",
            notes="A fireball spell is an explosion of flame that detonates with a low roar.",
        )
        repository.add_prepared_spell(
            character_id, wizard_class_id, fireball_id, prepared_count=1
        )
        window.sheet.refresh_all()
        window.sheet.page_tabs.setCurrentIndex(3)
        window.sheet.magic_scroll.verticalScrollBar().setValue(0)
        application.processEvents()
        window.grab().save(str(output / "traditional-spells-known.png"))
        item_dialog = ItemCatalogDialog(window)
        item_dialog.search.setText("Headband of Inspired Wisdom +6")
        item_dialog.search_debounce.flush()
        item_dialog.show(); application.processEvents()
        item_dialog.grab().save(str(output / "item-catalog.png")); item_dialog.close()
        vast = automation_for_entry({"name": "Headband of Vast Intelligence +4"})
        choice_dialog = ItemChoiceDialog("Headband of Vast Intelligence +4", vast, parent=window)
        choice_dialog.show(); application.processEvents()
        choice_dialog.grab().save(str(output / "item-choice.png")); choice_dialog.close()
        saved_weapon = next(item for item in repository.list_equipment(character_id) if item.id == weapon_id)
        equipment_dialog = EquipmentDialog(window, saved_weapon)
        equipment_dialog.show(); application.processEvents()
        equipment_dialog.grab().save(str(output / "item-editor.png")); equipment_dialog.close()
        saved_amulet = next(
            item for item in repository.list_equipment(character_id) if item.id == amulet_id
        )
        enchantment_dialog = ItemEnchantmentsDialog(
            repository, character_id, saved_amulet, window
        )
        enchantment_dialog.show(); application.processEvents()
        enchantment_dialog.grab().save(str(output / "item-enchantments.png"))
        enchantment_dialog.close()
        attack_dialog = AttackDialog(
            window, repository.list_attacks(character_id)[-1], repository.list_equipment(character_id)
        )
        attack_dialog.show(); application.processEvents()
        attack_dialog.grab().save(str(output / "attack-editor.png")); attack_dialog.close()
        codex = CodexDialog(parent=window)
        codex.show(); application.processEvents()
        equipment_root = codex.tree.topLevelItem(2)
        codex.tree.setCurrentItem(equipment_root.child(1).child(0))
        application.processEvents()
        codex.grab().save(str(output / "item-codex.png")); codex.close()
        enchantment_codex = CodexDialog(parent=window)
        enchantment_codex.show(); application.processEvents()
        enchantment_root = enchantment_codex.tree.topLevelItem(3)
        enchantment_codex.tree.setCurrentItem(enchantment_root.child(1).child(0))
        application.processEvents()
        enchantment_codex.grab().save(str(output / "enchantment-codex.png"))
        enchantment_codex.close()
        class_codex = CodexDialog(parent=window)
        class_codex.show(); application.processEvents()
        pathfinder_classes = class_codex.tree.topLevelItem(0).child(0)
        class_codex.tree.setCurrentItem(pathfinder_classes.child(0).child(0))
        application.processEvents()
        class_codex.grab().save(str(output / "class-codex.png"))
        class_codex.codex_search_mode.setCurrentIndex(class_codex.codex_search_mode.findData("both"))
        class_codex.codex_search.setText("arcane")
        class_codex._search_codex(); application.processEvents()
        class_codex.grab().save(str(output / "codex-search.png")); class_codex.close()
        class_picker = ClassCatalogDialog(parent=window)
        class_picker.show(); application.processEvents()
        class_picker.grab().save(str(output / "class-picker.png")); class_picker.close()
        archetype_picker = ArchetypeSelectionDialog("alchemist", parent=window)
        for row in range(archetype_picker.results.rowCount()):
            if archetype_picker.results.item(row, 1).text() == "Aerochemist":
                archetype_picker.results.cellWidget(row, 0).findChild(QCheckBox).click()
                break
        archetype_picker.show(); application.processEvents()
        archetype_picker.grab().save(str(output / "archetype-picker.png")); archetype_picker.close()
        spell_picker = TraditionalSpellCatalogDialog(("Wizard",), window)
        spell_picker.search.setText("Fireball")
        spell_picker._refresh()
        spell_picker.show(); application.processEvents()
        spell_picker.grab().save(str(output / "traditional-spell-picker.png")); spell_picker.close()
        feature_codex = CodexDialog(parent=window)
        feature_codex.show(); application.processEvents()
        feats_root = feature_codex.tree.topLevelItem(4)
        feature_codex.tree.setCurrentItem(feats_root.child(0).child(0))
        application.processEvents()
        feature_codex.grab().save(str(output / "feature-codex.png"))
        feature_codex.codex_search_mode.setCurrentIndex(feature_codex.codex_search_mode.findData("name"))
        feature_codex.codex_search.setText("Reactionary")
        feature_codex._search_codex(); application.processEvents()
        feature_codex.grab().save(str(output / "feature-search.png")); feature_codex.close()
        formula_codex = CodexDialog("formulas", parent=window)
        formula_codex.show(); application.processEvents()
        formula_codex.grab().save(str(output / "formula-codex.png")); formula_codex.close()
        blocks = BuildingBlocksDialog(
            repository,
            window.block_repository,
            window.block_registry,
            character_id,
            window.block_repository.list_tabs(character_id),
            window.block_runtime.add_block,
            window,
        )
        blocks.show(); application.processEvents()
        blocks.grab().save(str(output / "building-blocks-catalog.png")); blocks.close()
        designer = BlockDesignerDialog(repository, character_id, parent=window)
        for cell_type in ("label", "text", "number", "formula", "checkbox", "dropdown", "button", "table"):
            designer.canvas.add_cell(cell_type)
        designer.canvas.selected = [designer.canvas.cells[next(iter(designer.canvas.cells))]]
        designer._selection_changed()
        for theme in ("classic", "dark"):
            designer.theme.setCurrentIndex(designer.theme.findData(theme))
            designer.show(); application.processEvents()
            designer.grab().save(str(output / f"block-designer-{theme}.png"))
        designer.close()
        custom_tab = window.tab_manager.add_tab("Resources")
        window._sync_runtime_canvases()
        pool = BlockDefinition(
            "preview:pool", "House Spell Points", "Resources", width=460, height=210,
            cells=(
                CellDefinition("title", "label", "HOUSE SPELL POINTS", 18, 42, 420, 30),
                CellDefinition("maximum", "formula", "Maximum", 24, 88, 170, 42, formula="floor(classes.prodigy.level / 3)"),
                CellDefinition("current", "number", "Current", 240, 88, 170, 42, binding="trackers.house_spell_points.current"),
                CellDefinition("rest", "button", "Full Rest", 145, 148, 170, 34, action="full_rest"),
            ),
        )
        window.block_runtime.add_block(pool, custom_tab)
        window.sheet.page_tabs.setCurrentIndex(window.sheet.page_tabs.count() - 1)
        application.processEvents()
        window.grab().save(str(output / "custom-tab-formula-pool.png"))
        rest_engine = FullRestEngine(repository, character_id)
        rest_dialog = RestConfigurationDialog(
            rest_engine.targets(), rest_engine.effective_preferences(), window
        )
        rest_dialog.show(); application.processEvents()
        rest_dialog.grab().save(str(output / "full-rest-config.png")); rest_dialog.close()
        window.sheet.page_tabs.setCurrentIndex(2)
        window.customization.set_build_mode(True)
        application.processEvents(); application.processEvents()
        talent_section = window.sheet.martial_talents_section
        talent_section.resize(talent_section.width() + 180, talent_section.height() + 220)
        talent_header = window.sheet.martial_talent_table.horizontalHeader()
        talent_header.resizeSection(0, 330)
        talent_header.moveSection(talent_header.visualIndex(2), 1)
        application.processEvents()
        window.grab().save(str(output / "build-mode-table-layout.png"))
        window.customization.set_build_mode(False)
        window.close()
        repository.close()


if __name__ == "__main__":
    main()

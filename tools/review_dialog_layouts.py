"""Render the main dialog families using disposable data, never live characters."""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRect
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.ui import dialogs as d
from app.ui.optional_traditions import OptionalTraditionDialog
from app.ui.familiar_dialog import FamiliarCatalogDialog
from app.ui.race_dialog import RaceCatalogDialog
from app.models import CharacterDetails
from app.ui.class_choice_dialog import ClassChoiceDialog
from app.ui.class_power_dialog import ClassPowerDialog
from app.ui.character_audit_dialog import CharacterAuditDialog
from app.class_choice_rules import resolve_class_choice_slots
from app.class_power_rules import resolve_class_power_sets
from app.ui.dialog_theme import dialog_stylesheet, style_dialog_links
from app.ui.refined.theme import PALETTES
from app.ui.dialog_layout import apply_dialog_layout
from tools.render_refined_sheet import settle

app = QApplication([])
for font in ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'georgiab.ttf'):
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
app.setFont(QFont('Segoe UI', 10))
out = Path('artifacts/dialog-layout-review')
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    repo = CharacterRepository(Path(folder) / 'preview.db')
    cid = repo.create_character('Dialog previews', 'Spheres')
    repo.add_class_level(cid, 'Monk (Unchained)', 8, 'Full', 'Good', 'Good', 'Good', 'pathfinder-class:monk-unchained', 10, 50)
    repo.add_class_level(cid, 'Cleric', 1, '3/4', 'Good', 'Poor', 'Good', 'pathfinder-class:cleric', 8, 8)
    factories = [
        ('feats', lambda: d.FeatCatalogDialog([])),
        ('traits', lambda: d.TraitCatalogDialog([])),
        ('martial-talents', lambda: d.MartialTalentCatalogDialog([])),
        ('magic-talents', lambda: d.MagicTalentCatalogDialog([])),
        ('items', d.ItemCatalogDialog), ('spells', d.TraditionalSpellCatalogDialog),
        ('classes', d.ClassCatalogDialog), ('archetypes', lambda: d.ArchetypeSelectionDialog('pathfinder-class:inquisitor')),
        ('familiars', FamiliarCatalogDialog), ('races', lambda: RaceCatalogDialog(repo.get_character_details(cid))),
        ('class-choice', lambda: ClassChoiceDialog(resolve_class_choice_slots(repo, cid)[0])),
        ('class-powers', lambda: ClassPowerDialog(resolve_class_power_sets(repo, cid)[0])),
        ('audit', lambda: CharacterAuditDialog(repo, cid)),
        ('class-level', d.ClassLevelDialog), ('condition', d.ConditionDialog),
        ('modifier', lambda: d.ModifierDialog('Armor Class')),
        ('equipment', d.EquipmentDialog), ('attack', d.AttackDialog), ('spell-editor', d.SpellDialog),
        ('casting-traditions', lambda: d.TraditionCatalogDialog('Casting')),
        ('optional-traditions', lambda: OptionalTraditionDialog('Tinker')),
        ('special-ability', lambda: d.SpecialAbilityDialog(name='Special ability', description='Rules and notes remain fully editable.')),
        ('proficiencies', d.ProficiencyDialog), ('custom-pool', lambda: d.CustomTrackerDialog(repo, cid)),
        ('sphere-choice', lambda: d.SphereAcquisitionDialog(set())), ('worn-slots', lambda: d.WornSlotsDialog(('Armor', 'Belt', 'Body', 'Feet', 'Hands', 'Head', 'Neck', 'Ring'))),
    ]
    for name, factory in factories:
        if len(sys.argv) > 1 and name not in sys.argv[1:]:
            continue
        try:
            dialog = factory()
        except TypeError as error:
            print(name, 'FACTORY ERROR', error, flush=True)
            continue
        for theme in ('classic', 'dark'):
            dialog.theme = theme
            dialog.setStyleSheet(dialog_stylesheet(theme))
            dialog.setProperty('contentLayoutApplied', False)
            with patch.object(dialog, 'screen', return_value=SimpleNamespace(availableGeometry=lambda: QRect(0,0,1440,960))):
                apply_dialog_layout(dialog)
            dialog.show()
            table = getattr(dialog, 'results', None)
            if table is not None and hasattr(table, 'rowCount') and table.rowCount():
                table.setCurrentCell(0, 1 if table.columnCount() > 1 else 0)
            if name == 'races':
                dialog.races.setCurrentRow(6)  # Human choices and descriptions.
            style_dialog_links(dialog, PALETTES[theme].accent)
            settle(app)
            if hasattr(dialog, 'catalog_presentation'):
                dialog.catalog_presentation.refresh()
            dialog.grab().save(str(out / f'{theme}-{name}.png'))
        print(name, dialog.width(), dialog.height(), 'rendered in all themes', flush=True)
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
    repo.close()

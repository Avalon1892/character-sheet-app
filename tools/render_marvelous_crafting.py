"""Render the custom composer in both supported themes using a disposable DB."""
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QFont
from app.database import CharacterRepository
from app.ui.marvelous_crafting import MarvelousCraftingDialog, MarvelousItemUseDialog, MarvelousProjectDialog
from app.services.crafting import CraftingService
from app.ui.dialog_theme import dialog_stylesheet
from tools.render_refined_sheet import settle


def main():
    app = QApplication.instance() or QApplication([])
    for font in ('segoeui.ttf', 'segoeuib.ttf', 'georgia.ttf', 'georgiab.ttf'):
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/' + font)
    app.setFont(QFont('Segoe UI', 10))
    output = Path('artifacts/marvelous-crafting'); output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as folder:
        repository = CharacterRepository(Path(folder) / 'preview.db')
        cid = repository.create_character('Preview', 'Spheres')
        repository.add_feat(cid, 'Craft Marvelous Item')
        plan = dict(schema_version=1, sphere='Destruction', base_power='destruction:blast', caster_level=5,
            uses=2, activation='standard', range_steps=0, duration_steps=0, unique_changes=0,
            contributions=[], full_blast_damage=True)
        item_id = CraftingService(repository, cid).save_marvelous_design(plan,
            name='Thunderstone device', slot='', description='A crafted blast device.')
        for theme in ('classic', 'dark'):
            dialog = MarvelousCraftingDialog(repository, cid)
            dialog.setStyleSheet(dialog_stylesheet(theme))
            dialog.sphere.setCurrentText('Life')
            dialog.base_power.setCurrentIndex(2)
            dialog.cl.setValue(10)
            dialog.name.setText('Heart of the Dawn')
            dialog.description.setPlainText('A small crystal that grants a protective surge of vitality.')
            for _ in range(3): dialog.add_contribution()
            dialog.show(); settle(app)
            if not dialog.grab().save(str(output / f'{theme}.png')):
                raise RuntimeError('Could not render composer.')
            dialog.close(); dialog.deleteLater(); settle(app)
            for kind, window in [('activation', MarvelousItemUseDialog(repository, cid)),
                                 ('project', MarvelousProjectDialog(repository, cid, item_id))]:
                window.setStyleSheet(dialog_stylesheet(theme))
                window.show(); settle(app)
                if not window.grab().save(str(output / f'{theme}-{kind}.png')):
                    raise RuntimeError(f'Could not render {kind}.')
                window.close(); window.deleteLater(); settle(app)
        repository.close()


if __name__ == '__main__': main()

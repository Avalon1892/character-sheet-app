"""Populated capability and customization previews; temporary characters only."""
import os,sys,tempfile,json,argparse
from pathlib import Path
from dataclasses import replace
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase,QFont
from PySide6.QtWidgets import QApplication
from app.database import CharacterRepository
from app.content import class_entry
from app.models import AnimalCompanion,BondedCompanion,ProdigySequence
from app.ui.main_window import MainWindow
from tools.render_refined_sheet import settle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classes",nargs="+",default=[])
    parser.add_argument("--output",default="artifacts/refined-variants")
    args=parser.parse_args()
    app=QApplication.instance() or QApplication([])
    for font in ("segoeui.ttf","segoeuib.ttf","georgia.ttf","georgiab.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/"+font)
    app.setFont(QFont("Segoe UI",10))
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,temp)
        repo=CharacterRepository(Path(temp)/"variants.db")
        window=MainWindow(repo);window.resize(1400,1000);window.show()
        for name,key,kind,pages in (
            ("Wizard","pathfinder-class:wizard","Pathfinder 1e",("magic",)),
            ("Sorcerer","pathfinder-class:sorcerer","Pathfinder 1e",("magic",)),
            ("Prodigy","prodigy","Spheres",("core","abilities")),
            ("Hunter","pathfinder-class:hunter","Pathfinder 1e",("companion",)),
            ("Witch","pathfinder-class:witch","Pathfinder 1e",("familiar",)),
            ("Necros","spheres-class:necros","Spheres",("corpse_puppet",))):
            if args.classes and name not in args.classes:continue
            cid=repo.create_character("Preview · "+name,kind)
            definition=class_entry(key)
            level=6;hd=int(definition.get("hit_die",8))
            class_id=repo.add_class_level(cid,name,level,definition.get("bab","3/4"),definition.get("fort","Good"),definition.get("reflex","Poor"),definition.get("will","Good"),key,hd,hd+(hd//2+1)*5)
            for ability in ("intelligence","wisdom","charisma"):repo.update_ability_score(cid,ability,18)
            repo.update_hit_points(replace(repo.get_hit_points(cid),maximum=40,current=20,temporary=5,nonlethal=3,auto_calculate=True))
            if name in ("Wizard","Sorcerer"):
                repo.update_casting_profile(replace(repo.get_casting_profile(cid),caster_level=6,casting_class_levels=6,casting_ability="intelligence" if name=="Wizard" else "charisma"))
                for spell,level in (("Light",0),("Magic Missile",1),("Invisibility",2),("Fireball",3)):
                    sid=repo.add_spell(cid,spell,system="Prepared" if name=="Wizard" else "Spontaneous",level=level,school_or_sphere="Evocation",notes="A catalog-style preview description.")
                    if name=="Wizard":repo.add_prepared_spell(cid,class_id,sid,prepared_count=2)
            if name=="Prodigy":
                repo.update_prodigy_sequence(ProdigySequence(cid,True,3,6))
                for talent in ("Athletics","Swift Movement","A very long custom martial talent name that should wrap across more than one line without disappearing"):
                    repo.add_martial_talent(cid,talent,sphere="Athletics",notes="Readable rules and conditional-action details.")
            if name=="Hunter":repo.update_animal_companion(AnimalCompanion(cid,name="Sable",species_key="cat-big-lion-tiger",current_hp=28,skill_ranks_json=json.dumps({"perception":3,"stealth":3}),tricks_json=json.dumps(["Attack","Come","Defend"])))
            if name=="Witch":repo.update_bonded_companion(BondedCompanion(cid,"familiar","Ink","Raven",10,0,json.dumps({"familiar_key":"raven"})))
            window.refresh_characters(cid);window._set_sheet_type("refined")
            sheet=window.refined_sheet
            for theme in ("classic","dark"):
                window._set_theme(theme)
                for page in pages:
                    sheet.session.select_tab(page);settle(app)
                    window.grab().save(str(output/f"{name}-{theme}-{page}.png"))
                    if name=="Prodigy":
                        scroll=sheet.refined_pages[page][0]
                        target=sheet.prodigy_section if page=="core" else sheet.martial_talents_section
                        scroll.ensureWidgetVisible(target);settle(app)
                        window.grab().save(str(output/f"{name}-{theme}-{page}-lower.png"))
                        scroll.verticalScrollBar().setValue(0)
            if name=="Prodigy":
                sheet.session.select_tab("core");sheet.customize_button.setChecked(True);settle(app)
                window.grab().save(str(output/"customization.png"))
                sheet.customize_button.setChecked(False)
                sheet._show_ability_breakdown("strength","Strength");settle(app)
                window.grab().save(str(output/"details.png"))
        window.close();repo.close()
    print(output)


if __name__=="__main__":main()

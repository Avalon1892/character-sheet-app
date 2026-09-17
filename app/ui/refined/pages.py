"""Default Refined composition and stable extension-point mapping."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QLayout
from app.ui.components import sheet_page
from .components import ResponsiveRow

DEFAULT_TABS = (("core","Overview"),("skills","Skills"),("abilities","Abilities"),
                ("magic","Magic"),("inventory","Equipment"),("build","Character"),
                ("companion","Animal Companion"),("crafting","Crafting"))

PLACEMENTS = {
    "crafting": ("crafting",),
    "core": ("classic_statistics","attacks","conditions","martial_focus","spell_points","movement","inquisitor_features","imbue","prodigy_sequence"),
    "skills": ("skills","special_abilities"),
    "abilities": ("martial_talents","moldable_talents","feats","traits"),
    "magic": ("casting_play","spell_level_overview","spells_known","spells_prepared","magic_talents","magic_ranges","sphere_statistics"),
    "inventory": ("equipment","worn_items","equipment_figure","load","currency"),
    "build": ("overview","advancement_budgets","base_abilities","favored_class_bonuses","proficiencies","custom_trackers","traditional_casting","casting_profile","traditions","optional_traditions","sphere_drawbacks"),
    "companion": ("animal_identity","animal_statistics","animal_training"),
}

def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.layout():
            clear_layout(item.layout())
        elif item.widget():
            item.widget().setParent(None)

def compose(sheet):
    sheet.refined_pages = {}
    for key, attr in (("core","core"),("build","builder"),("inventory","inventory"),("magic","magic"),("companion","companion"),("crafting","crafting")):
        scroll=getattr(sheet,attr+"_scroll")
        canvas=getattr(sheet,attr+"_canvas")
        clear_layout(canvas.layout())
        sheet.refined_pages[key]=(scroll,canvas,canvas.layout())
    for key in ("skills","abilities"):
        sheet.refined_pages[key]=sheet_page("refined"+key.title())
    # Keep unmapped alternatives available in Building Blocks, not top-level windows.
    sheet.refined_hidden = QWidget(sheet)
    sheet.refined_hidden.hide()
    assigned=set()
    sheet.custom_layouts={}
    for key, (scroll,canvas,layout) in sheet.refined_pages.items():
        canvas.setObjectName("refinedCanvas")
        canvas.setMinimumWidth(0)
        scroll.setMinimumWidth(0)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.setContentsMargins(14,12,14,16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        sheet.custom_layouts[key+"_main"]=layout
        for section_key in PLACEMENTS[key]:
            section=sheet.custom_sections.get(section_key)
            if section is not None:
                layout.addWidget(section)
                section.show()
                assigned.add(section_key)
    for key, section in sheet.custom_sections.items():
        if key not in assigned:
            section.setParent(sheet.refined_hidden)
            section.hide()
    sheet.custom_layouts["build_fundamentals"]=sheet.refined_pages["build"][2]
    sheet.builder_layout=sheet.refined_pages["build"][2]
    # The skill roll/name columns need more room than the class-feature list.
    # These remain two independent blocks, not a combined gameplay widget.
    layout=sheet.refined_pages["skills"][2]
    skills=sheet.custom_sections["skills"]
    abilities=sheet.custom_sections["special_abilities"]
    layout.removeWidget(skills);layout.removeWidget(abilities)
    row=ResponsiveRow(skills,abilities,breakpoint=1200,stretches=(2,1))
    layout.addWidget(row)
    sheet.refined_skills_row=row
    sheet.custom_layouts["skills_reference_row"]=row.row
    # Useful play-facing pairs stack automatically on narrower windows.
    for page, left_key, right_key in (("core","attacks","conditions"),("abilities","feats","traits"),("inventory","worn_items","equipment_figure"),("inventory","load","currency")):
        layout=sheet.refined_pages[page][2]
        left=sheet.custom_sections[left_key]; right=sheet.custom_sections[right_key]
        index=layout.indexOf(left)
        layout.removeWidget(left); layout.removeWidget(right)
        row=ResponsiveRow(left,right,breakpoint=1200,
                          stretches=(2,1) if left_key in ("feats", "worn_items") else None)
        layout.insertWidget(index,row)
        sheet.custom_layouts[left_key+"_row"]=row.row
    # Movement and expendable resources are one scan-friendly band. The
    # sections remain independent registered blocks for customization.
    layout=sheet.refined_pages["core"][2]
    focus,points,movement=(sheet.custom_sections[k] for k in ("martial_focus","spell_points","movement"))
    index=layout.indexOf(focus)
    for section in (focus,points,movement):layout.removeWidget(section)
    resources=ResponsiveRow(focus,points,breakpoint=16777215)
    band=ResponsiveRow(movement,resources,breakpoint=1200)
    layout.insertWidget(index,band)
    sheet.refined_resource_group=resources
    sheet.custom_layouts["resource_stack"]=resources.row
    sheet.custom_layouts["movement_resource_row"]=band.row
    while sheet.page_tabs.count():
        sheet.page_tabs.removeTab(0)
    for key,title in DEFAULT_TABS:
        sheet.page_tabs.addTab(sheet.refined_pages[key][0],title)
    # Preserve additional companion panels created by the shared sheet.
    for attr,title in (("familiar","Familiar"),("corpse_puppet","Corpse Puppet"),("phantom","Phantom")):
        scroll=getattr(sheet,attr+"_scroll")
        canvas=getattr(sheet,attr+"_canvas")
        canvas.setObjectName("refinedCanvas");canvas.setMinimumWidth(0)
        canvas.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        sheet.page_tabs.addTab(scroll,title)
    sheet.sheet_masthead.setParent(sheet.refined_hidden)
    sheet.audit_status_bar.hide()
    sheet.page_tabs.setCurrentIndex(0)

"""Independent Refined layout workspace over the shared Building Blocks engine."""
from __future__ import annotations
from dataclasses import replace
from PySide6.QtCore import QRect, Qt, QTimer, QEvent, QPoint
from PySide6.QtWidgets import (QPushButton,QComboBox,QInputDialog,QMessageBox,QDialog,
    QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QAbstractItemView,QSpinBox,QLabel,QCheckBox,QToolButton,QMenu,QTableWidget,QSizePolicy,QLayout)
from app.presentation_storage import SheetStyleStore,StyleBlockRepository,MemorySettings
from app.presentation_history import PresentationHistory,PresentationSnapshot
from app.building_blocks.registry import register_builtin_blocks,BlockRegistry
from app.building_blocks.schemas import BlockDefinition
from app.building_blocks.runtime import BlockRuntimeController
from app.building_blocks.tabs import SheetTabManager
from app.building_blocks.nested_editor import NestedCellEditor
from app.building_blocks.catalog import BuildingBlocksDialog
from app.ui.customization import SheetCustomizationController
from app.ui.components import sheet_page
from .pages import DEFAULT_TABS,PLACEMENTS
from .guides import AlignmentGuides
from .components import ResponsiveRow
from .layout_migrations import migrate_skills_reference_layout, migrate_traditions_character_page, migrate_feats_traits_skills_page


class RefinedTabManager(SheetTabManager):
    def __init__(self,sheet,presentation):
        super().__init__(sheet,presentation)
        self.builtin_pages={key:parts[0] for key,parts in sheet.refined_pages.items()}
        self.canvases={key:parts[1] for key,parts in sheet.refined_pages.items()}
        for key in ("familiar","corpse_puppet","phantom"):
            self.builtin_pages[key]=getattr(sheet,key+"_scroll")
            self.canvases[key]=getattr(sheet,key+"_canvas")
    def _display_name(self,key,saved_name):
        return saved_name
    def current_key(self):
        return self._key_at(self.sheet.page_tabs.currentIndex()) or "core"

    def reload(self):
        if self.character_id is None:return
        previous=self.current_key()
        self.sheet.page_tabs.blockSignals(True)
        try:
            while self.sheet.page_tabs.count():self.sheet.page_tabs.removeTab(0)
            for tab in self.presentation.list_tabs(self.character_id):
                page=self.builtin_pages.get(tab.key)
                if page is None:
                    if tab.key not in self.custom_pages:
                        scroll,canvas,layout=sheet_page("refinedCanvas")
                        scroll.setProperty("sheetTabKey",tab.key);canvas.setProperty("sheetTabKey",tab.key)
                        canvas.setMinimumWidth(0);layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
                        self.custom_pages[tab.key]=(scroll,canvas,layout);self.canvases[tab.key]=canvas
                    page=self.custom_pages[tab.key][0]
                index=self.sheet.page_tabs.addTab(page,tab.name)
                self.sheet.page_tabs.tabBar().setTabData(index,tab.key)
                self.sheet.page_tabs.setTabVisible(index,tab.visible and self.sheet.is_sheet_tab_available(tab.key))
                if tab.key==previous:self.sheet.page_tabs.setCurrentIndex(index)
        finally:self.sheet.page_tabs.blockSignals(False)


class RefinedCustomization(SheetCustomizationController):
    snap=True
    guides_enabled=True
    resize_mode=0

    def restore_factory_layout(self):
        super().restore_factory_layout()
        # The shared restorer inserts widgets without the row's original
        # alignment/stretch. Reapply Refined's default top-aligned columns.
        for row in self.sheet.findChildren(ResponsiveRow):
            row.restore_column_layout()

    def set_skills_sidebar_default(self,enabled):
        section=self.sheet.custom_sections["special_abilities"]
        if not hasattr(self,"_skills_sidebar_placement"):
            self._skills_sidebar_placement=self.default_placements[section]
            self._abilities_page_placements={widget:placement
                for widget,placement in self.default_placements.items()
                if placement[0] is self.sheet.refined_pages["abilities"][2]}
        placement=self._skills_sidebar_placement
        self.default_placements[section]=(placement if enabled else
            (self.sheet.refined_pages["abilities"][2],1,placement[2],placement[3]))
        for widget,placement in self._abilities_page_placements.items():
            self.default_placements[widget]=(placement[0],placement[1]+(not enabled),placement[2],placement[3])

    def set_build_mode(self,enabled):
        if enabled and not self.build_mode:
            self._before_build_freeform=self.settings.value("customization/freeform",None)
            self._activated_freeform=None
        super().set_build_mode(enabled)
        if not enabled and getattr(self,"_activated_freeform",None) is not None:
            current=self.settings.value("customization/freeform",None)
            if current==self._activated_freeform:
                # Merely visiting Customize must not turn responsive defaults
                # into absolute rectangles. Other edits (columns/cells/colors)
                # still survive this restoration.
                state=self.capture_state()
                if self._before_build_freeform is None:state.pop("freeform",None)
                else:state["freeform"]=self._before_build_freeform
                self.apply_state(state)
            self._activated_freeform=None

    def _activate_current_page(self):
        # Do not lose track of a real drag when another page is visited.
        unchanged=(getattr(self,"_activated_freeform",None) is None or
            self.settings.value("customization/freeform",None)==self._activated_freeform)
        super()._activate_current_page()
        if unchanged:self._activated_freeform=self.settings.value("customization/freeform",None)

    def _prepare_resizable_section(self,section):
        super()._prepare_resizable_section(section)
        for table in section.findChildren(QTableWidget):
            table.setProperty("fillAvailableHeight",self.resize_mode in (1,2))
            if self.resize_mode==0:
                table.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
                for adapter in self.sheet.table_presentations:
                    if adapter.table is table:adapter.schedule()
    def eventFilter(self,watched,event):
        # A lazily created style must not add a second hierarchy walk to every
        # application event while the user is simply playing or using a dialog.
        if not self.build_mode and self.paint_color is None:
            return False
        result=super().eventFilter(watched,event)
        if self.drag_source is None:
            for overlay in getattr(self,"guide_overlays",{}).values():overlay.hide()
        return result

    def _bounded_geometry(self,canvas,geometry):
        result=super()._bounded_geometry(canvas,geometry)
        if self.snap and self.drag_source is not None and self.drag_operation=="move":
            result.moveLeft(round(result.x()/8)*8)
            result.moveTop(round(result.y()/8)*8)
        if self.drag_source is not None and self.drag_operation=="move":
            x_guide=y_guide=None
            for widget,owner in self.section_canvases.items():
                if owner is not canvas or widget is self.drag_source or widget.isHidden():continue
                peer=QRect(widget.mapTo(canvas,QPoint(0,0)),widget.size())
                for own,other in ((result.left(),peer.left()),(result.center().x(),peer.center().x()),(result.right(),peer.right())):
                    if abs(own-other)<=6:
                        x_guide=other
                        if self.snap:result.translate(other-own,0)
                        break
                for own,other in ((result.top(),peer.top()),(result.center().y(),peer.center().y()),(result.bottom(),peer.bottom())):
                    if abs(own-other)<=6:
                        y_guide=other
                        if self.snap:result.translate(0,other-own)
                        break
            if self.guides_enabled:
                if not hasattr(self,"guide_overlays"):self.guide_overlays={}
                overlay=self.guide_overlays.setdefault(canvas,AlignmentGuides(canvas)) if canvas not in self.guide_overlays else self.guide_overlays[canvas]
                overlay.display(x_guide,y_guide)
        return super()._bounded_geometry(canvas,result)


class RefinedSession:
    def __init__(self,host,sheet):
        self.host=host; self.sheet=sheet; self.loading=False; self.character_id=None
        self.store=SheetStyleStore(sheet.repository)
        defaults=DEFAULT_TABS+(("familiar","Familiar"),("corpse_puppet","Corpse Puppet"),("phantom","Phantom"))
        self.presentation=StyleBlockRepository(sheet.repository,"refined",defaults)
        self.registry=BlockRegistry()
        owners={section:page for page,sections in PLACEMENTS.items() for section in sections}
        for definition in register_builtin_blocks().all():
            if definition.section_key == 'ability_score_increases':
                continue
            if definition.section_key == 'base_abilities':
                definition = replace(definition, name='Ability Scores & Advancement')
            self.registry.register(replace(definition,default_tab=owners.get(definition.section_key,"build"),default_visible=definition.section_key in owners))
        known={d.section_key for d in self.registry.all()}
        for key in sheet.custom_sections:
            if key not in known:
                self.registry.register(BlockDefinition(key="builtin:"+key,name=key.replace("_"," ").title(),category="Sheet sections",builtin=True,section_key=key,default_tab=owners.get(key,"build"),default_visible=key in owners))
        self.controller=RefinedCustomization(host,sheet,sheet.custom_sections,sheet.custom_layouts,settings=MemorySettings())
        self.tabs=RefinedTabManager(sheet,self.presentation)
        sheet.page_tabs.setMovable(False)
        self.controller.set_canvases(self.tabs.canvases)
        self.runtime=BlockRuntimeController(sheet,self.controller,sheet.repository,self.presentation,self.registry,{"full_rest":host.perform_full_rest,"refresh":sheet.refresh_all})
        self.runtime.set_canvases(self.tabs.canvases)
        self.cells=NestedCellEditor(sheet,self.presentation,self.runtime,self.tabs)
        self.controller.set_nested_editor(self.cells)
        self.runtime.set_nested_editor(self.cells)
        self.controller.set_geometry_saved_callback(self.runtime.save_widget_geometry)
        self.history=PresentationHistory(self.capture,self.apply)
        for component in (self.controller,self.runtime,self.cells,self.tabs): component.set_history(self.history)
        self.history.on_changed=self._changed
        sheet.custom_sections_changed.connect(self.controller.sync_sections)
        sheet.formula_values_changed.connect(self._refresh_custom_values)
        self._toolbar()

    def _toolbar(self):
        root=self.sheet.customize_toolbar.layout()
        layout=QHBoxLayout();root.addLayout(layout)
        for label,callback in (("Blocks",self.open_blocks),("Properties",self.properties),("Undo",lambda:self.history.undo(self.character_id)),("Redo",lambda:self.history.redo(self.character_id)),("Reset",self.reset)):
            button=QPushButton(label); button.clicked.connect(callback); layout.addWidget(button)
        pages=QToolButton();pages.setText("Pages");pages.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu=QMenu(pages)
        for label,callback in (("Add page",self.add_tab),("Rename page",self.rename_tab),("Hide page",self.hide_tab),("Restore page",self.restore_tab)):menu.addAction(label,callback)
        pages.setMenu(menu);layout.addWidget(pages);layout.addStretch()
        layout=QHBoxLayout();root.addLayout(layout)
        self.mode=QComboBox(); self.mode.addItems(("Reflow contents","Resize container","Scale contents","Edit cells"))
        self.mode.currentIndexChanged.connect(self._mode_changed); layout.addWidget(self.mode)
        self.snap=QCheckBox("Snap"); self.snap.setChecked(True)
        self.snap.toggled.connect(lambda value:setattr(self.controller,"snap",value)); layout.addWidget(self.snap)
        self.guides=QCheckBox("Alignment guides");self.guides.setChecked(True)
        self.guides.toggled.connect(lambda value:setattr(self.controller,"guides_enabled",value));layout.addWidget(self.guides)
        self.group_buttons=[]
        for label,callback in (("Group cells",self.cells.group_selected),("Ungroup cells",self.cells.ungroup_selected)):
            button=QPushButton(label);button.clicked.connect(callback);button.setEnabled(False);layout.addWidget(button);self.group_buttons.append(button)
        layout.addStretch()

    def _mode_changed(self,index):
        self.controller.resize_mode=index
        self.controller.set_cell_edit_mode(index==3)
        self.controller.set_content_scale_mode(index==2)
        for section in self.sheet.custom_sections.values():
            for table in section.findChildren(QTableWidget):
                table.setProperty("fillAvailableHeight",index in (1,2))
                table.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding if index in (1,2) else QSizePolicy.Policy.Fixed)
        for adapter in self.sheet.table_presentations:adapter.schedule()
        for button in self.group_buttons:button.setEnabled(index==3)
        if self.host.sheet_type=="refined":
            for action,checked in ((self.host.cell_edit_action,index==3),(self.host.content_scale_action,index==2)):
                action.blockSignals(True);action.setChecked(checked);action.blockSignals(False)

    def set_build_mode(self,enabled):
        self.sheet.customize_toolbar.setVisible(enabled)
        self.controller.set_build_mode(enabled)
        if enabled:self._mode_changed(self.mode.currentIndex())
        if self.host.sheet_type=="refined":
            self.host.build_mode_action.blockSignals(True);self.host.build_mode_action.setChecked(enabled);self.host.build_mode_action.blockSignals(False)
        self.sheet.page_tabs.setMovable(enabled)
        if not enabled:
            self.controller.set_cell_edit_mode(False)
            self.save()

    def _refresh_custom_values(self):
        # Runtime custom widgets currently rebuild; do not rebuild unrelated pages.
        if self.runtime.widgets:
            self.runtime.refresh()

    def load(self,character_id):
        self.loading=True
        try:
            self.character_id=character_id
            self.history.cancel()
            self.presentation.ensure_character(character_id,self.registry)
            tabs=self.presentation.list_tabs(character_id)
            if any(t.key=="skills" and t.name=="Skills" for t in tabs):
                self.presentation.rename_tab(character_id,"skills","Skills and Abilities")
            if any(t.key=="abilities" and t.name in ("Ability", "Abilities") for t in tabs):
                self.presentation.rename_tab(character_id,"abilities","Martial")
            keys=[t.key for t in tabs]
            if "progression" in keys and "build" in keys and keys.index("progression")!=keys.index("build")+1:
                keys.remove("progression")
                keys.insert(keys.index("build")+1,"progression")
                self.presentation.reorder_tabs(character_id,keys)
            state=self.store.get(character_id,"refined")
            migrate_skills_reference_layout(self.presentation,character_id,state)
            migrate_feats_traits_skills_page(self.presentation,character_id,state)
            migrate_traditions_character_page(self.presentation,character_id)
            self._configure_default_composition()
            self.tabs.load_character(character_id)
            self.controller.set_canvases(self.tabs.canvases); self.runtime.set_canvases(self.tabs.canvases)
            # Restore the responsive baseline first; then honor explicit block
            # destinations. Reversing these steps discards cross-page moves.
            self.controller.apply_state(state.get("layout",{}))
            self.runtime.load_character(character_id)
            self.cells.load_character(character_id)
            self.cells.apply_overrides()
            self.sheet.set_density(state.get("density","comfortable"))
            self.sheet.density_control.setCurrentText(self.sheet.density.title())
            self.sheet.details_button.setChecked(state.get("details",False))
            self.sheet.pin_details.setChecked(state.get("pin_details",True))
            for key,control in self.sheet.refined_disclosures.items():
                control.set_expanded(key in state.get("expanded_sections",[]))
            if state.get("splitter"): self.sheet.refined_splitter.setSizes(state["splitter"])
            self.select_tab(state.get("page","core"))
            self.refresh_tab_visibility()
        finally:
            self.loading=False

    def _configure_default_composition(self):
        instance=next((i for i in self.presentation.list_instances(self.character_id)
                       if i.template_snapshot.get("section_key")=="special_abilities"),None)
        legacy=instance is not None and instance.template_snapshot.get("default_tab")=="abilities"
        self.controller.set_skills_sidebar_default(not legacy)

    def refresh_tab_visibility(self):
        if not self.character_id:return
        saved={tab.key:tab.visible for tab in self.presentation.list_tabs(self.character_id)}
        for index in range(self.sheet.page_tabs.count()):
            key=self.tabs._key_at(index)
            self.sheet.page_tabs.setTabVisible(index,saved.get(key,True) and self.sheet.is_sheet_tab_available(key))

    def select_tab(self,key):
        for index in range(self.sheet.page_tabs.count()):
            if self.tabs._key_at(index)==key and self.sheet.page_tabs.isTabVisible(index):
                self.sheet.page_tabs.setCurrentIndex(index);return

    def save(self):
        if self.loading or not self.character_id or not self.sheet.repository.character_exists(self.character_id): return
        self.store.save(self.character_id,"refined",{"layout":self.controller.capture_state(),"page":self.tabs.current_key(),"density":self.sheet.density,"details":self.sheet.details_button.isChecked(),"pin_details":self.sheet.pin_details.isChecked(),"splitter":self.sheet.refined_splitter.sizes(),"expanded_sections":[key for key,control in self.sheet.refined_disclosures.items() if control.adapter.expanded]})

    def capture(self):
        if not self.character_id or self.loading:return None
        return PresentationSnapshot(self.character_id,self.controller.capture_state(),self.presentation.export_character_state(self.character_id),self.tabs.current_key())

    def apply(self,snapshot):
        if snapshot.character_id!=self.character_id:return
        old=self.presentation.export_character_state(self.character_id)
        same_structure=self.host._same_sheet_structure(old,snapshot.building_blocks)
        if same_structure:
            self.presentation.replace_character_cell_overrides(self.character_id,snapshot.building_blocks)
            self.cells.apply_overrides()
        else:
            self.presentation.import_character_state(self.character_id,snapshot.building_blocks)
            self._configure_default_composition()
            self.tabs.reload(); self.runtime.set_canvases(self.tabs.canvases); self.controller.set_canvases(self.tabs.canvases)
        if not same_structure or self.controller.capture_state()!=snapshot.layout:
            self.controller.apply_state(snapshot.layout)
        if not same_structure:
            self.runtime.refresh(); self.cells.load_character(self.character_id)
        self.select_tab(snapshot.current_tab);self.save()

    def _changed(self):
        self.save()
        if hasattr(self.host,"undo_action"):self.host._update_history_actions()

    def open_blocks(self):
        if not self.character_id:return
        dialog=BuildingBlocksDialog(self.sheet.repository,self.presentation,self.registry,self.character_id,self.presentation.list_tabs(self.character_id),self.runtime.add_block,self.sheet,remove_block=self.runtime.remove_block,current_tab_key=self.tabs.current_key())
        dialog.exec(); self.save()

    def _reload_tabs(self):
        self.tabs.reload();self.controller.set_canvases(self.tabs.canvases);self.runtime.set_canvases(self.tabs.canvases);self.runtime.refresh()

    def add_tab(self):
        name,ok=QInputDialog.getText(self.sheet,"Add page","Page name")
        if ok and name.strip():self.history.record("Add page",lambda:(self.tabs.add_tab(name.strip()),self._reload_tabs()))
    def rename_tab(self):
        self.tabs._rename_at(self.sheet.page_tabs.currentIndex())
    def hide_tab(self):
        if sum(self.sheet.page_tabs.isTabVisible(i) for i in range(self.sheet.page_tabs.count()))<=1:return
        self.history.record("Hide page",lambda:(self.presentation.remove_tab(self.character_id,self.tabs.current_key(),hide=True),self._reload_tabs()))
    def restore_tab(self):
        hidden=[t for t in self.presentation.list_tabs(self.character_id) if not t.visible]
        if not hidden:return
        name,ok=QInputDialog.getItem(self.sheet,"Restore page","Page",[t.name for t in hidden],0,False)
        if ok:self.history.record("Restore page",lambda:(self.presentation.set_tab_visible(self.character_id,next(t.key for t in hidden if t.name==name),True),self._reload_tabs()))

    def reset(self, _checked=False, *, confirm=True):
        if not self.character_id:return
        if confirm and QMessageBox.question(self.sheet,"Reset Refined Sheet","Restore this style's default arrangement? Character data and all other sheet styles will remain unchanged.")!=QMessageBox.StandardButton.Yes:return
        def operation():
            self.presentation.import_character_state(self.character_id,{"tabs":[],"blocks":[]})
            # Import's compatibility fallback creates legacy tabs; replace them here.
            self.presentation.connection.execute("DELETE FROM sheet_tabs WHERE character_id=?",(self.character_id,))
            self.presentation.ensure_character(self.character_id,self.registry)
            self._configure_default_composition()
            self.controller.apply_state({});self._reload_tabs();self.cells.load_character(self.character_id)
            self.select_tab("core")
        self.history.record("Reset Refined layout",operation)

    def properties(self):
        dialog=QDialog(self.sheet);dialog.setWindowTitle("Layout properties");dialog.resize(520,570)
        root=QVBoxLayout(dialog)
        root.addWidget(QLabel("Select one or more blocks. These controls change presentation only."))
        listing=QListWidget();listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for key,section in self.sheet.custom_sections.items():
            item=QListWidgetItem(key.replace("_"," ").title());item.setData(Qt.ItemDataRole.UserRole,key);listing.addItem(item)
        root.addWidget(listing)
        target=QComboBox()
        for tab in self.presentation.list_tabs(self.character_id):target.addItem(tab.name,tab.key)
        root.addWidget(target)
        fields=[];row=QHBoxLayout()
        for label,value in (("X",16),("Y",16),("Width",600),("Height",300)):
            column=QVBoxLayout();column.addWidget(QLabel(label));field=QSpinBox();field.setRange(0,10000);field.setValue(value);column.addWidget(field);row.addLayout(column);fields.append(field)
        root.addLayout(row)
        def selected():return [self.sheet.custom_sections[i.data(Qt.ItemDataRole.UserRole)] for i in listing.selectedItems()]
        def selection_changed():
            if not selected():return
            first=selected()[0];canvas=self.controller.section_canvases.get(first)
            geometry=QRect(first.mapTo(canvas,QPoint()),first.size()) if canvas else first.geometry()
            for field,value in zip(fields,(geometry.x(),geometry.y(),geometry.width(),geometry.height())):field.setValue(value)
            if canvas:
                key=next((k for k,v in self.tabs.canvases.items() if v is canvas),None)
                target.setCurrentIndex(max(0,target.findData(key)))
        listing.itemSelectionChanged.connect(selection_changed)
        def apply():
            def operation():
                x,y,w,h=[f.value() for f in fields]
                canvas=self.tabs.canvases[target.currentData()]
                for offset,section in enumerate(selected()):
                    self.controller.place_section_freeform(section,canvas,QRect(x,y+offset*(h+12),max(160,w),max(90,h)))
                    if section.property("blockInstanceId"):self.presentation.move_instance(int(section.property("blockInstanceId")),target.currentData())
                    self.controller._save_geometry(section)
            self.history.record("Arrange blocks",operation)
        actions=QHBoxLayout()
        for label,callback in (("Apply / stack",apply),("Hide",lambda:self.history.record("Hide blocks",lambda:[self.runtime.set_visible(int(s.property("blockInstanceId")),False) for s in selected() if s.property("blockInstanceId")])),("Show",lambda:self.history.record("Show blocks",lambda:[self.runtime.set_visible(int(s.property("blockInstanceId")),True) for s in selected() if s.property("blockInstanceId")]))):
            button=QPushButton(label);button.clicked.connect(callback);actions.addWidget(button)
        root.addLayout(actions)
        alignment=QHBoxLayout()
        for label,operation in (("Align left","left"),("Align top","top"),("Equal widths","width"),("12 px spacing","spacing")):
            button=QPushButton(label);button.clicked.connect(lambda _checked=False,op=operation:self.align_blocks(selected(),op));alignment.addWidget(button)
        root.addLayout(alignment)
        close=QPushButton("Close");close.clicked.connect(dialog.accept);root.addWidget(close);dialog.exec()

    def align_blocks(self,sections,operation):
        if len(sections)<2:return
        canvas=self.controller.section_canvases.get(sections[0])
        if canvas is None:return
        sections=[s for s in sections if self.controller.section_canvases.get(s) is canvas]
        rectangles=[QRect(s.mapTo(canvas,QPoint()),s.size()) for s in sections]
        if not rectangles:return
        left=min(r.x() for r in rectangles);top=min(r.y() for r in rectangles)
        width=max(r.width() for r in rectangles)
        def apply():
            y=top
            for section,rect in sorted(zip(sections,rectangles),key=lambda pair:pair[1].y()):
                if operation=="left":rect.moveLeft(left)
                elif operation=="top":rect.moveTop(top)
                elif operation=="width":rect.setWidth(width)
                elif operation=="spacing":rect.moveTop(y);y=rect.bottom()+13
                self.controller.place_section_freeform(section,canvas,rect)
                self.controller._save_geometry(section)
        self.history.record("Align blocks",apply)

    def dispose(self):
        self.save();self.controller.dispose();self.presentation.close()

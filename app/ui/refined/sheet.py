"""Refined presentation: inherits proven workflows, not their page geometry."""
from __future__ import annotations
import html
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (QWidget,QLabel,QPushButton,QHBoxLayout,QVBoxLayout,
    QSplitter,QComboBox,QTableWidget,QSizePolicy,QHeaderView,QMenu,QToolButton,QAbstractButton,QLineEdit)
from app.ui.character_sheet import CharacterSheetWidget
from app.ui.components import fit_table_rows, FormulaNumberEdit
from app.bonded_companion_rules import bonded_companion_grants
from .overview import build_statistics
from .pages import compose, clear_layout
from .components import TablePresentation, TableDisclosure
from .table_tools import PageSearchBar, skill_filter_choice
from .theme import stylesheet
from .actions import compact_actions
from .companions import decorate_companions
from .stat_cards import decorate_metric
from .item_colors import RefinedItemDelegate


class RefinedSheetWidget(CharacterSheetWidget):
    full_rest_requested = Signal()
    notes_requested = Signal()

    def __init__(self, repository, parent=None):
        self.refined_ready = False
        self.theme = "classic"
        self.density = "comfortable"
        self.session = None
        super().__init__(repository,parent)
        self.setObjectName("refinedSheet")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.custom_sections["sphere_statistics"]=self.sphere_statistics_section
        from .character_panels import combine_ability_advancement, create_equipment_figure_section, separate_class_levels
        combine_ability_advancement(self)
        separate_class_levels(self)
        create_equipment_figure_section(self)
        from .class_progression import GroupedTabBar, ClassProgressionPage
        # Qt requires an empty tab widget when replacing its tab bar; otherwise
        # the old stacked pages survive with indices unrelated to the new tabs.
        while self.page_tabs.count():
            self.page_tabs.removeTab(0)
        self.page_tabs.setTabBar(GroupedTabBar())
        compose(self)
        self.class_progression_page=ClassProgressionPage(self)
        self.refined_pages["progression"][2].addWidget(self.class_progression_page)
        self._make_header_and_details()
        # Details are a single optional side panel, never a second empty block.
        self.custom_sections.pop("feature_details",None)
        self.table_presentations=[]
        self.refined_disclosures={}
        self.refined_page_searches={}
        self._pending_table_reflow = set()
        self._table_reflow_timer = QTimer(self)
        self._table_reflow_timer.setSingleShot(True)
        self._table_reflow_timer.timeout.connect(self._reflow_changed_tables)
        self._decorate_sections()
        from app.ui.search_navigation import install_search_shortcut
        self.search_shortcut = install_search_shortcut(self, lambda:
            self.page_tabs.currentWidget().findChild(QLineEdit,'refinedPageSearch')
            if self.page_tabs.currentWidget() is not None else None)
        decorate_companions(self)
        self.refined_ready=True
        self.set_theme("classic")

    def _classic_statistics_section(self):
        return build_statistics(self)

    def _focus_advancement_section(self, page, section):
        # Blocks may live on a different page after splitting or customization.
        for scroll, canvas, _ in self.refined_pages.values():
            if canvas.isAncestorOf(section):
                return super()._focus_advancement_section(scroll, section)
        return super()._focus_advancement_section(page, section)

    @staticmethod
    def _section_title(text):
        label=QLabel(text.capitalize())
        label.setObjectName("refinedSectionTitle")
        label.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        return label

    @staticmethod
    def _sheet_subtitle(text):
        label=QLabel(text.capitalize())
        label.setObjectName("refinedMuted")
        return label

    @staticmethod
    def _fit_feature_table(table,row_count,minimum_rows,maximum_rows):
        # Refined's table adapter owns sizing; never stretch a section shell.
        if not table.property("refinedTable"):
            fit_table_rows(table,row_count,0,maximum_rows)

    def _make_header_and_details(self):
        root=self.layout()
        root.removeWidget(self.page_tabs)
        root.removeWidget(self.audit_status_bar)
        self.audit_status_bar.hide()
        header=QWidget()
        h=QHBoxLayout(header); h.setContentsMargins(16,12,16,8)
        titles=QVBoxLayout(); titles.setSpacing(2)
        self.refined_name=QLabel("Refined Sheet"); self.refined_name.setObjectName("refinedCharacterName")
        self.refined_classes=QLabel(); self.refined_classes.setObjectName("refinedMuted")
        titles.addWidget(self.refined_name); titles.addWidget(self.refined_classes)
        h.addLayout(titles,1)
        for text,callback in (("Rest",self.full_rest_requested.emit),("Review",self._review_advancement),("Notes",self.notes_requested.emit)):
            button=QPushButton(text); button.clicked.connect(callback); h.addWidget(button)
            if text=="Review": self.refined_review=button
        self.customize_button=QPushButton("Customize"); self.customize_button.setCheckable(True)
        self.customize_button.toggled.connect(lambda enabled: self.session and self.session.set_build_mode(enabled))
        h.addWidget(self.customize_button)
        self.density_control=QComboBox(); self.density_control.addItems(("Comfortable","Compact"))
        self.density_control.currentTextChanged.connect(lambda value: self.set_density(value.casefold()))
        h.addWidget(self.density_control)
        self.details_button=QPushButton("Details"); self.details_button.setCheckable(True)
        h.addWidget(self.details_button)
        root.addWidget(header)
        self.customize_toolbar=QWidget(); self.customize_toolbar.setLayout(QVBoxLayout())
        self.customize_toolbar.layout().setContentsMargins(16,0,16,8)
        self.customize_toolbar.hide(); root.addWidget(self.customize_toolbar)
        self.refined_splitter=QSplitter(Qt.Orientation.Horizontal)
        self.refined_splitter.addWidget(self.page_tabs)
        panel=QWidget(); panel.setObjectName("refinedCard")
        panel.setMinimumWidth(280); panel.setMaximumWidth(600)
        pr=QVBoxLayout(panel); ph=QHBoxLayout()
        ph.addWidget(QLabel("Details"),1)
        self.pin_details=QPushButton("Pin"); self.pin_details.setCheckable(True); self.pin_details.setChecked(True)
        ph.addWidget(self.pin_details)
        close=QPushButton("Close"); close.clicked.connect(lambda: self.details_button.setChecked(False)); ph.addWidget(close)
        pr.addLayout(ph)
        self.feature_details.setParent(panel); pr.addWidget(self.feature_details,1)
        self.refined_detail_actions=QHBoxLayout(); pr.addLayout(self.refined_detail_actions)
        self._detail_action_timer=QTimer(self)
        self._detail_action_timer.setSingleShot(True)
        self._detail_action_timer.timeout.connect(lambda:self._show_table_actions(self._pending_detail_table))
        self.refined_splitter.addWidget(panel)
        self.refined_splitter.setStretchFactor(0,1); self.refined_splitter.setStretchFactor(1,0)
        self.refined_splitter.setSizes([1150,350])
        self.details_panel=panel; panel.hide()
        self.details_button.toggled.connect(panel.setVisible)
        self.feature_details.textChanged.connect(self._details_changed)
        self.page_tabs.currentChanged.connect(self._page_changed)
        root.addWidget(self.refined_splitter,1)

    def _details_changed(self):
        while self.refined_detail_actions.count():
            item=self.refined_detail_actions.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if self.refined_ready and self.feature_details.toPlainText().strip() and self.pin_details.isChecked() and self.details_button.isChecked():
            self.details_panel.show()

    def _page_changed(self,*_):
        if self.refined_ready and self.page_tabs.currentWidget() is self.refined_pages["progression"][0]:
            self.class_progression_page.refresh()
        if (self.refined_ready and self.session
                and self.page_tabs.currentWidget() is self.refined_pages['skills'][0]):
            # Finish the Skills geometry before its first paint, rather than
            # briefly exposing the inherited, shorter legacy-sheet rectangle.
            for adapter in self.table_presentations:
                if adapter.table in (self.skill_table,self.special_ability_table):
                    adapter.fit()
            self._reflow_changed_tables()
        if self.refined_ready and not self.pin_details.isChecked():
            self.details_button.setChecked(False)
        if self.session:
            self.session.save()

    def _decorate_sections(self):
        for key,section in self.custom_sections.items():
            section.setMinimumWidth(0); section.setMaximumWidth(16777215)
            section.setMinimumHeight(0); section.setMaximumHeight(16777215)
            section.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Maximum)
            if section.layout():
                section.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
                section.layout().setSpacing(7)
            for title in section.findChildren(QLabel):
                if title.objectName() in ("sectionTitle","sheetSubTitle"):
                    title.setObjectName("refinedSectionTitle")
                    title.setText(title.text().capitalize())
            for table in section.findChildren(QTableWidget):
                if table.property("refinedTable"):
                    continue
                table.setProperty("refinedTable",True)
                table.setProperty("fillAvailableHeight",False)
                name_column=0
                headers=[table.horizontalHeaderItem(c).text().casefold() if table.horizontalHeaderItem(c) else "" for c in range(table.columnCount())]
                for candidate in ("name","spell","talent","feat","trait","item","skill","ability","attack","feature"):
                    if candidate in headers:
                        name_column=headers.index(candidate); break
                if table.horizontalHeaderItem(name_column):
                    table.horizontalHeaderItem(name_column).setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                summary = table is self.spell_level_overview_table
                # Companion training removal uses semantic row order. Do not
                # make that existing editor sortable without stable record IDs.
                ordered = table in self.companion_training_tabs.values()
                adapter=TablePresentation(table,self,name_column,50 if key=="skills" else 18,
                    balanced=summary, sortable=not (summary or ordered),
                    row_visible=self._available_spell_summary_row if summary else None)
                self.table_presentations.append(adapter)
                table.setItemDelegate(RefinedItemDelegate(table, lambda: self.theme))
                adapter.geometry_changed.connect(lambda t=table: self._schedule_table_reflow(t))
                if table is self.skill_table:
                    # Shared skill refreshes can set the same final height
                    # before this page becomes visible. Reflow after fitting,
                    # once Qt has invalidated its enclosing layout hints.
                    adapter.fitted.connect(lambda _visible, _total, t=table: self._schedule_table_reflow(t))
                if key=="skills" and table is self.skill_table:
                    # Put the roll beside the skill name, while keeping the
                    # underlying column identities used by existing editors.
                    table.setProperty("defaultColumnOrder",[2,0,1,3,4,5,6,7])
                hidden=[]
                for c,label in enumerate(headers):
                    if c==name_column: continue
                    if "description" in label or label in ("notes","rules basis / note","defense / notes","bonus / notes","calculation","action / current effect","selection / current effect"):
                        table.setColumnHidden(c,True)
                        hidden.append(f"builtin:{c}")
                    elif label in ("class","bonus","rk.","ranks","qty","acp","misc","level","sr"):
                        table.setColumnWidth(c,60)
                    elif key in ("martial_talents","moldable_talents","feats","traits"):
                        if label in ("type","category"):table.setColumnWidth(c,180)
                        elif label=="sphere":table.setColumnWidth(c,140)
                    elif key=="equipment" and label in ("state / slot","value / weight"):
                        table.setColumnWidth(c,145)
                table.setProperty("defaultHiddenColumns",hidden)
                if key == "martial_talents":
                    table.setProperty("refinedCategory","martial")
                elif key in ("magic_talents","spells_known","spells_prepared"):
                    table.setProperty("refinedCategory","magic")
                if table is self.spell_table:
                    table.setColumnWidth(4,130); table.setColumnWidth(5,125); table.setColumnWidth(6,110)
                table.setMinimumHeight(0); table.setMaximumHeight(16777215)
            if section.findChildren(QTableWidget):
                compact_actions(section)
            for button in section.findChildren(QAbstractButton):
                if "⋯" in button.text():
                    button.setText(button.text().replace("⋯", "").strip())
            if key=="special_abilities":
                adapter=next(c for c in self.table_presentations if c.table is self.special_ability_table)
                self.refined_disclosures[key]=TableDisclosure(adapter,section,noun="abilities")
        for key in ("skills","abilities","magic","inventory"):
            # Resolve ownership when searching so moved blocks and preserved
            # older arrangements use the search field on their actual page.
            controllers=lambda page=key:[c for c in self.table_presentations
                if self.refined_pages[page][1].isAncestorOf(c.table)]
            placeholder={"skills":"Search skills, abilities, feats and traits…",
                         "abilities":"Search talents…",
                         "magic":"Search spells and sphere effects…",
                         "inventory":"Search equipment and worn items…"}[key]
            tools=PageSearchBar(controllers,placeholder=placeholder)
            if key=="skills":
                adapter=next(c for c in self.table_presentations if c.table is self.skill_table)
                self.refined_skill_filter=skill_filter_choice(adapter)
                tools.add_filter(self.refined_skill_filter)
            self.refined_page_searches[key]=tools
            self.refined_pages[key][2].insertWidget(0,tools)
        self.refined_skills_row.geometry_changed.connect(
            lambda:self._schedule_table_reflow(self.skill_table))
        self._compact_movement()
        self.quick_spell_points.setObjectName("refinedNumber")
        self._compact_resources()
        from .character_panels import compact_martial_focus
        compact_martial_focus(self)
        self._compact_magic_summary()
        self._decorate_formula_fields()
        for adapter in self.table_presentations:
            table=adapter.table
            table.cellClicked.connect(lambda _r,_c,t=table:self._queue_table_actions(t))
            table.currentCellChanged.connect(lambda _r,_c,_pr,_pc,t=table:
                self._queue_table_actions(t) if t.hasFocus() else None)

    def _queue_table_actions(self,table):
        self._pending_detail_table=table
        self._detail_action_timer.start(0)

    def _schedule_table_reflow(self, table):
        self._pending_table_reflow.add(table)
        if not self._table_reflow_timer.isActive():
            self._table_reflow_timer.start(0)

    def _reflow_changed_tables(self):
        tables, self._pending_table_reflow = self._pending_table_reflow, set()
        if not self.session:
            return
        canvases = {canvas for canvas in self.session.tabs.canvases.values()
                    if canvas.isVisible() and any(canvas.isAncestorOf(table) for table in tables)}
        for canvas in canvases:
            # Tables can reveal rows after the page's last layout pass. Grow
            # the page and reflow sibling boxes instead of clipping those rows.
            self.session.controller._fit_canvas(canvas)
            if canvas.layout():
                canvas.layout().activate()

    def _show_table_actions(self,table):
        if table.currentRow()<0:return
        section=table.parentWidget()
        while section is not None and not hasattr(section,"_refined_actions_menu"):
            section=section.parentWidget()
        if section is None:return
        while self.refined_detail_actions.count():
            item=self.refined_detail_actions.takeAt(0)
            if item.widget():item.widget().deleteLater()
        button=QToolButton()
        button.setText("Selected entry actions")
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(section._refined_actions_menu)
        self.refined_detail_actions.addWidget(button)

    @staticmethod
    def _available_spell_summary_row(table,row):
        # Present already calculated capacities; no spell progression rules here.
        return any(table.item(row,c) and table.item(row,c).text().strip() not in ("", "0", "—", "-")
                   for c in (0,3,4))

    def _compact_magic_summary(self):
        section=self.casting_play_section
        cards=[value.parentWidget() for value in self._play_casting_labels.values()]
        for card in cards: card.setParent(None)
        clear_layout(section.layout())
        heading=QHBoxLayout();heading.addWidget(self.casting_play_title,1)
        heading.addWidget(self.open_spell_book_button)
        section.layout().addLayout(heading)
        row=QHBoxLayout()
        for card in cards:
            card.setObjectName("refinedStat")
            row.addWidget(card,1)
        section.layout().addLayout(row)
        for value in self._play_casting_labels.values():value.setObjectName("refinedNumber")

    def _compact_resources(self):
        section=self.spell_point_summary_section
        buttons=section.findChildren(QPushButton)
        title=next(w for w in section.findChildren(QLabel) if w.objectName()=="refinedSectionTitle")
        clear_layout(section.layout())
        heading=QHBoxLayout();heading.addWidget(title,1)
        for button in buttons: heading.addWidget(button)
        section.layout().addLayout(heading)
        readout=QHBoxLayout();readout.addWidget(self.quick_spell_points)
        readout.addWidget(self.quick_spell_temp);readout.addStretch()
        section.layout().addLayout(readout)
        self.martial_focus_counter.setObjectName("refinedNumber")

    def _decorate_formula_fields(self):
        for field in self.findChildren(FormulaNumberEdit):
            if not field.property("showFormulaIndicator"):
                field.setProperty("showFormulaIndicator",True)
                field._refresh_preview()

    def _compact_movement(self):
        cards=self.movement_totals["land_speed"].parentWidget().parentWidget().layout().itemAt(1).layout()
        cards.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.refined_movement_grid=cards
        self.refined_movement_cards={key:label.parentWidget() for key,label in self.movement_totals.items()}
        for column in range(cards.columnCount()): cards.setColumnStretch(column,0)
        for key,label in self.movement_totals.items():
            card=label.parentWidget()
            title=next(w for w in card.findChildren(QLabel) if w.objectName()=="movementMode")
            title.setText(title.text().title())
            decorate_metric(card,label,title.text(),lambda k=key:self._show_movement_metric(k))
            label.setMinimumSize(0,0); label.setMaximumHeight(40)
            card.setFixedWidth(130)
            card.setMinimumHeight(0)
        for label in self.movement_sources.values():
            label.hide()
        self.movement_edit_toggle.setText("Edit movement…")

    def set_theme(self,theme):
        self.theme=theme
        value = stylesheet(theme,self.density)
        if self.styleSheet() == value:
            return
        self.setStyleSheet(value)
        if getattr(self, 'refined_equipment_figure', None) is not None:
            self.refined_equipment_figure.refresh()
        for adapter in getattr(self,"table_presentations",()): adapter.schedule()

    def set_density(self,density):
        self.density=density if density in ("compact","comfortable") else "comfortable"
        self.set_theme(self.theme)
        if self.session: self.session.save()

    def attach_host(self,host):
        from .customization import RefinedSession
        self.session=RefinedSession(host,self)
        self._attach_column_controls()

    def _attach_column_controls(self):
        for section in self.custom_sections.values():
            menu=getattr(section,"_refined_actions_menu",None)
            if menu is None: continue
            tables=section.findChildren(QTableWidget)
            columns=menu.addMenu("Columns")
            def populate(target=columns,owned=tables):
                target.clear()
                for table in owned:
                    table_id=str(table.property("tableLayoutId") or "")
                    if not table_id:continue
                    parent=target if len(owned)==1 else target.addMenu(table.horizontalHeaderItem(0).text() or "Table")
                    controller=self.session.controller.table_layout
                    for c in range(table.columnCount()):
                        item=table.horizontalHeaderItem(c)
                        if item is None:continue
                        key=controller._column_key(table,c)
                        action=parent.addAction(item.text());action.setCheckable(True);action.setChecked(not table.isColumnHidden(c))
                        action.triggered.connect(lambda checked,tid=table_id,k=key: controller.restore_column(tid,k) if checked else controller.remove_column(tid,k))
                    parent.addSeparator()
                    parent.addAction("Add custom column…",lambda _checked=False,tid=table_id:controller.add_custom_column(tid))
            columns.aboutToShow.connect(populate)

    def load_character(self,character_id):
        if self.session and self.character_id != character_id:
            self.session.save()
        if self.character_id != character_id and self.refined_ready:
            for search in self.refined_page_searches.values():search.reset()
        super().load_character(character_id)
        if self.session: self.session.load(character_id)

    def refresh_all(self):
        super().refresh_all()
        if not self.refined_ready or self.character_id is None: return
        character=next((c for c in self.repository.list_characters() if c.id==self.character_id),None)
        self.refined_name.setText(character.name if character else "Character")
        classes=self.repository.list_class_levels(self.character_id)
        self.refined_classes.setText(" · ".join(f"{c.class_name} {c.level}" for c in classes) or "No class levels")
        self._decorate_formula_fields()
        for adapter in self.table_presentations: adapter.schedule()
        self._refresh_refined_visibility()
        if self.page_tabs.currentWidget() is self.refined_pages["progression"][0]:
            self.class_progression_page.refresh()

    def _refresh_worn_items(self, *args, **kwargs):
        super()._refresh_worn_items(*args, **kwargs)
        if hasattr(self, 'refined_equipment_figure'):
            from .character_panels import refresh_equipment_figure
            refresh_equipment_figure(self)

    def _update_martial_focus_status(self):
        super()._update_martial_focus_status()
        if hasattr(self, '_refined_focus_buttons'):
            spend, regain = self._refined_focus_buttons
            spend.setEnabled(self.martial_focus_current.value() > 0)
            regain.setEnabled(self.martial_focus_current.value() < self.martial_focus_maximum.value())

    def _refresh_refined_visibility(self):
        self.audit_status_bar.hide()
        self.refined_magic_maneuvers.setVisible(self._class_capabilities.magic)
        self._set_section_rule_available("sphere_statistics",self._class_capabilities.magic)
        for title in self.findChildren(QLabel,"refinedSectionTitle"):
            if title.text().isupper():title.setText(title.text().capitalize())
        visible_modes=[]
        for key,label in self.movement_totals.items():
            card=self.refined_movement_cards[key]
            if self.refined_movement_grid.indexOf(card)<0:
                # A freely moved cell belongs to the player's arrangement;
                # refreshing movement must not pull it into the default grid.
                continue
            shown=label.text() not in ("—","0 ft") or key=="land_speed"
            if key=="armor_speed" and label.text()==self.movement_totals["land_speed"].text(): shown=False
            card.setVisible(shown)
            if shown:visible_modes.append(card)
        # Pack eligible modes from the left; hidden modes leave no grid holes.
        # Keep hidden cards in the grid so they can become eligible again.
        for card in self.refined_movement_cards.values():
            if self.refined_movement_grid.indexOf(card)>=0 and card not in visible_modes:
                visible_modes.append(card)
        for index,card in enumerate(visible_modes):
            self.refined_movement_grid.removeWidget(card)
            self.refined_movement_grid.addWidget(card,index//4,index%4)
        group=self.refined_resource_group
        group.setVisible(any(group.isAncestorOf(self.custom_sections[key]) and
                             not self.custom_sections[key].isHidden()
                             for key in ("martial_focus","spell_points")))
        if self.session: self.session.refresh_tab_visibility()

    def _refresh_movement(self,*args,**kwargs):
        super()._refresh_movement(*args,**kwargs)
        if self.refined_ready: self._refresh_refined_visibility()

    def _refresh_character_audit(self):
        super()._refresh_character_audit()
        if hasattr(self,"refined_review") and self._audit_report:
            count=len(self._audit_report.findings)
            self.refined_review.setText(f"Review ({count})" if count else "Review")

    def default_sheet_tab_name(self,key):
        return "Magic" if key=="magic" else ""

    def is_sheet_tab_available(self,key):
        if key in ("familiar","corpse_puppet","phantom"):
            grant=bonded_companion_grants(self.repository,self.character_id).get(key) if self.character_id else None
            return bool(grant and grant.level>0)
        return super().is_sheet_tab_available(key)

    def _show_ability_breakdown(self,key,name):
        if not self.refined_ready: return
        result=self._ability_result(key)
        self._show_calculation_details(name,result,lambda: super(RefinedSheetWidget,self)._show_ability_breakdown(key,name))

    def _show_combat_breakdown(self,key,name):
        if not self.refined_ready or (self.session and self.session.controller.build_mode): return
        self._show_calculation_details(name,self._combat_results()[key],lambda: super(RefinedSheetWidget,self)._show_combat_breakdown(key,name))

    def _show_movement_metric(self,key):
        if not self.refined_ready or (self.session and self.session.controller.build_mode):return
        title=key.removesuffix("_speed").replace("_"," ").title()+" movement"
        self.feature_details.setHtml(f"<h2>{html.escape(title)}</h2><p>Current: <b>{html.escape(self.movement_totals[key].text())}</b></p><p>{html.escape(self.movement_sources[key].text())}</p>")
        button=QPushButton("Edit movement…")
        def edit():
            self.movement_edit_toggle.setChecked(True)
            self.movement_controls[key].editor.setFocus()
            self.movement_controls[key].editor.selectAll()
        button.clicked.connect(edit)
        self.refined_detail_actions.addWidget(button)
        self.details_button.setChecked(True)

    def _show_magic_metric(self,key):
        if not self.refined_ready or (self.session and self.session.controller.build_mode):return
        title="Magic Skill Bonus" if key=="msb" else "Magic Skill Defense"
        value=self._classic_magic_skill_labels[key]
        calculator=self._calculator()
        if key=="msb":
            profile=calculator.resolved_casting_profile()
            inputs=[("Casting class levels",profile.casting_class_levels),("Miscellaneous adjustment",profile.msb_misc)]
        else:
            inputs=[("Current MSB",self._classic_magic_skill_labels["msb"].text())]
        from app.rules import calculate_stat
        target="magic_skill_bonus" if key=="msb" else "magic_skill_defense"
        result=calculate_stat([],calculator.automatic_modifier_map().get(target,[]))
        inputs.extend((c.source,c.value) for c in result.contributions if c.applied)
        rows="".join(f"<tr><td>{html.escape(source)}</td><td>{html.escape(str(amount))}</td></tr>" for source,amount in inputs)
        explanation=self.casting_msd.toolTip() if key=="msd" else ""
        self.feature_details.setHtml(f"<h2>{title}</h2><p>Current: <b>{html.escape(value.text())}</b></p><p>{html.escape(explanation)}</p><table>{rows}</table>")
        self.details_button.setChecked(True)

    def _show_calculation_details(self,name,result,edit):
        rows="".join(f"<tr><td>{html.escape(c.source)}</td><td>{c.value:+g}</td></tr>" for c in result.contributions if c.applied)
        self.feature_details.setHtml(f"<h2>{html.escape(name)}</h2><p>Current total: <b>{result.total}</b></p><table>{rows}</table>")
        while self.refined_detail_actions.count():
            item=self.refined_detail_actions.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        button=QPushButton("Edit adjustments…"); button.clicked.connect(edit)
        self.refined_detail_actions.addWidget(button)
        self.details_button.setChecked(True)

    def dispose(self):
        self._detail_action_timer.stop()
        if self.session:
            self.session.dispose(); self.session=None
        super().dispose()

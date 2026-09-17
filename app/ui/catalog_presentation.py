"""Shared catalog layout and viewport-only sizing, independent of selection/rules."""
from PySide6.QtCore import QObject, QEvent, QTimer, Qt, Slot
from PySide6.QtWidgets import QSplitter, QHeaderView, QLabel
from shiboken6 import isValid
from app.ui.search_navigation import install_search_shortcut


class CatalogPresentation(QObject):
    def __init__(self, dialog, browser):
        super().__init__(dialog)
        self.dialog = dialog
        self.table = dialog.results
        self._fitting = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self.refresh)
        self.splitter = self._compose(browser)
        self.splitter.setObjectName('catalogBrowserSplitter')
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(7)
        sizes=[]
        for i in range(self.splitter.count()):
            widget=self.splitter.widget(i)
            if widget is dialog.selection_basket:
                widget.setMinimumWidth(215);widget.setMaximumWidth(420);size=280;stretch=1
            elif widget is self.table or widget.isAncestorOf(self.table):
                widget.setMinimumWidth(440);size=900;stretch=4
            else:
                widget.setMinimumWidth(140);widget.setMaximumWidth(225);size=180;stretch=0
            self.splitter.setStretchFactor(i,stretch);sizes.append(size)
        self.splitter.setSizes(sizes)
        for i in range(1,self.splitter.count()):
            self.splitter.handle(i).setToolTip('Drag to resize the catalog and selection queue')
        header=self.table.horizontalHeader()
        self.table.setMinimumWidth(420)
        self.table.verticalHeader().hide()
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.verticalHeader().setDefaultSectionSize(32)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        for c in range(self.table.columnCount()):
            item=self.table.horizontalHeaderItem(c)
            name=item.text().casefold() if item else ''
            header.setSectionResizeMode(c,QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(c, {'owned':58,'price':85,'source':100,'ruleset':100,'sheet behavior':112}.get(name,120))
            if name in ('name','feat','talent','trait','item'):
                header.setSectionResizeMode(c,QHeaderView.ResizeMode.Stretch)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
            if name=='prerequisites':
                # Full prerequisites remain in the selected-entry preview.
                self.table.setColumnHidden(c,True)
        self.table.viewport().installEventFilter(self)
        self._base_hidden = {c for c in range(self.table.columnCount()) if self.table.isColumnHidden(c)}
        self._responsive_hidden = set()
        self._metadata_widths = {}
        dialog.installEventFilter(self)
        self.table.verticalScrollBar().valueChanged.connect(self.schedule)
        header.sectionResized.connect(self.schedule)
        self.table.itemSelectionChanged.connect(self.schedule)
        self.table.model().rowsInserted.connect(self.schedule)
        self.table.model().modelReset.connect(self.schedule)
        behavior=getattr(dialog,'detail_automation',None)
        if behavior is not None:behavior.setObjectName('catalogBehaviorNote')
        dialog.search.setClearButtonEnabled(True)
        self.search_shortcut=install_search_shortcut(dialog,dialog.search)
        self.schedule()

    def _compose(self,browser):
        if isinstance(browser,QSplitter):
            return browser
        widgets=[]
        while browser.count():
            item=browser.takeAt(0)
            if item.widget():widgets.append(item.widget())
        splitter=QSplitter(Qt.Orientation.Horizontal,self.dialog)
        index=widgets.index(self.table)
        details=widgets.pop(index+1)
        details.setMinimumWidth(0)
        center=QSplitter(Qt.Orientation.Vertical,splitter)
        center.setChildrenCollapsible(False)
        center.setHandleWidth(7)
        center.addWidget(self.table);center.addWidget(details)
        center.setStretchFactor(0,3);center.setStretchFactor(1,2)
        center.setSizes([490,260])
        widgets[index]=center
        for widget in widgets:splitter.addWidget(widget)
        browser.addWidget(splitter)
        return splitter

    def eventFilter(self,watched,event):
        if event.type() not in (QEvent.Type.Show,QEvent.Type.Resize,QEvent.Type.Hide,QEvent.Type.Close):return False
        if not self._usable():return False
        if event.type() in (QEvent.Type.Show,QEvent.Type.Resize):self.schedule()
        if watched is self.dialog and event.type() in (QEvent.Type.Hide,QEvent.Type.Close):self.timer.stop()
        return False

    @Slot()
    def schedule(self,*_):
        if not self._usable():return
        if not self._fitting and not self.timer.isActive():self.timer.start()

    @Slot()
    def refresh(self):
        if not self._usable():return
        if not self.table.isVisible():return
        self._fitting=True
        try:
            self._balance_columns()
            for name in ('detail_meta','detail_prerequisites','detail_automation','detail_source'):
                label=getattr(self.dialog,name,None)
                if isinstance(label,QLabel):label.setVisible(bool(label.text().strip()))
            self._style_source_link()
            # Never measure thousands of off-screen catalog rows during search.
            first=max(0,self.table.rowAt(0))
            last=self.table.rowAt(self.table.viewport().height()-1)
            if last<0:last=min(self.table.rowCount()-1,first+40)
            for row in range(first,min(self.table.rowCount(),last+3)):
                self.table.resizeRowToContents(row)
                self.table.setRowHeight(row,max(32,self.table.rowHeight(row)))
        finally:
            self._fitting=False

    def _balance_columns(self):
        """Keep names readable; secondary metadata remains in the preview."""
        table = self.table
        width = table.viewport().width()
        candidates = []
        fixed = 0
        for c in range(table.columnCount()):
            name = table.horizontalHeaderItem(c).text().casefold()
            if c in self._base_hidden or name in ('name', 'feat', 'talent', 'trait', 'item'):
                continue
            if not table.isColumnHidden(c):
                self._metadata_widths[c] = table.columnWidth(c)
            fixed += self._metadata_widths.get(c, 120)
            if name in ('sheet behavior', 'source', 'ruleset', 'family', 'category', 'sphere', 'type'):
                candidates.append((c, name))
        priority = ('sheet behavior', 'source', 'ruleset', 'family', 'category', 'sphere', 'type')
        hidden = set()
        for c, name in sorted(candidates, key=lambda item: priority.index(item[1])):
            if width - fixed >= 280:
                break
            hidden.add(c)
            fixed -= self._metadata_widths.get(c, 120)
        for c in self._responsive_hidden | hidden:
            table.setColumnHidden(c, c in hidden)
        self._responsive_hidden = hidden

    def _usable(self):
        # Qt may deliver final layout/model events while Python cycle cleanup
        # has already released a dialog's wrapper attributes or child widgets.
        timer=getattr(self,'timer',None)
        table=getattr(self,'table',None)
        return timer is not None and table is not None and isValid(timer) and isValid(table)

    def _style_source_link(self):
        label=getattr(self.dialog,'detail_source',None)
        if label is None or '<a ' not in label.text():return
        from app.ui.refined.theme import PALETTES
        context=self.dialog
        while context is not None and not hasattr(context,'theme'):context=context.parentWidget()
        p=PALETTES.get(getattr(context,'theme','classic'),PALETTES['classic'])
        original=(label.property('catalogLinkOriginal') if label.text()==label.property('catalogLinkRendered') else label.text())
        rendered=f'<style>a {{ color: {p.accent}; }}</style>{original}'
        label.setProperty('catalogLinkOriginal',original)
        label.setProperty('catalogLinkRendered',rendered)
        if label.text()!=rendered:label.setText(rendered)

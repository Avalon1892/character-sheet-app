"""Reuse catalog browsing/basket for known item-design effects, not learning talents."""
from app.ui.dialogs import MagicTalentCatalogDialog


class MarvelousEffectPicker(MagicTalentCatalogDialog):
    def __init__(self, entries, parent=None):
        super().__init__([], parent, catalog_entries=entries)
        self.setWindowTitle('Add accessible effects')
        self.catalog_heading.setText('ACCESSIBLE ITEM EFFECTS')
        self.catalog_heading.setToolTip('Includes current Moldable and other effective talents. Permanent construction eligibility is checked separately.')
        self.custom_button.hide()
        self.available_only.hide(); self.not_owned.hide()

    def _entry_selectable(self, entry):
        # The supplied entries are already effective choices, not unlearned talents.
        return True

    def _availability(self, entry):
        return 'No known restriction.'

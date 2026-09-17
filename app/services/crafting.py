"""Character-aware, read-only prerequisite checks for crafting planners."""
from dataclasses import dataclass
from app.class_feature_context import resolved_class_features_for_level
from app.crafting_catalog import creation_feats
from app.crafting_rules import magical_base_price


@dataclass(frozen=True)
class RequirementCheck:
    status: str
    missing_feats: tuple[str, ...]
    missing_spells: tuple[str, ...]
    review: str
    missing_conditions: tuple[str, ...] = ()


class CraftingService:
    def __init__(self, repository, character_id):
        self.repository, self.character_id = repository, character_id
        self.details = repository.get_character_details(character_id)
        self.cost_traits = tuple(t.name for t in repository.list_traits(character_id)
                                 if t.enabled and t.name.casefold() in {'hedge magician','spark of creation'})
        self.feats = {f.name.casefold() for f in repository.list_feats(character_id) if f.enabled}
        for level in repository.list_class_levels(character_id):
            self.feats.update(f.name.casefold() for f in resolved_class_features_for_level(repository, character_id, level))
        self.spells = {s.name.casefold() for s in repository.list_spells(character_id) if s.enabled and s.system.casefold() not in {'sphere', 'spheres'}}
        from app.traditional_spellcasting import traditional_casting_classes, traditional_spellbook_blocked_by_archetype
        self.casters = traditional_casting_classes(repository, character_id)
        if traditional_spellbook_blocked_by_archetype(repository, character_id):
            self.spells.clear()
        purse = repository.get_currency_purse(character_id)
        self.gold = purse.gold + purse.platinum * 10 + purse.silver / 10 + purse.copper / 100

    def available_feats(self):
        return tuple(sorted(f for f in creation_feats() if f.casefold() in self.feats))

    def spell_crafting_levels(self, recipe):
        """Standard progression providers only; unusual profiles remain reviewable."""
        from app.prepared_spell_rules import HIGH_PREPARED, MED_PREPARED, LOW_PREPARED
        from app.spontaneous_spell_rules import HIGH_SPONTANEOUS
        level = recipe.get('spell_level')
        if level is None: return ()
        matches = []
        for row, casting in self.casters:
            if row.class_name.casefold() not in {'wizard','witch','cleric','druid','shaman','sorcerer','oracle','psychic','bard','skald','magus','inquisitor','summoner','unchained summoner','hunter','warpriest','paladin','ranger','antipaladin'}: continue
            if row.class_name.casefold() not in {s.casefold() for s in recipe.get('spell_classes', ())}: continue
            progression = str(casting.get('progression', 'high')).casefold()
            spontaneous = str(casting.get('type', '')).casefold() == 'spontaneous'
            if progression in {'high', 'full'}:
                table = HIGH_SPONTANEOUS if spontaneous else HIGH_PREPARED
                offset = 0 if spontaneous else 1
                cl_offset = 0
            elif progression in {'med', 'mid', 'medium', '3/4'}:
                table, offset, cl_offset = MED_PREPARED, 0, 0
            elif progression in {'low', '1/2'}:
                # Paladin/ranger CL is level - 3; other low casters need a provider.
                if row.class_name.casefold() not in {'paladin', 'ranger', 'antipaladin'}: continue
                table, offset, cl_offset = LOW_PREPARED, 0, 3
            else: continue
            if level == 0:
                if row.class_name.casefold() in {'paladin','ranger','antipaladin','alchemist','investigator'}: continue
                first = 1
            else:
                first = next((i for i, slots in enumerate(table, 1) if len(slots) >= level + offset), None)
            if first is not None and row.level >= first:
                matches.append((row.class_name, max(1, first-cl_offset), max(1,row.level-cl_offset)))
        return tuple(matches)

    def planning_defaults(self, recipe):
        result = dict(recipe)
        if recipe.get('price_per_cl'):
            levels = self.spell_crafting_levels(recipe)
            if levels:
                result['caster_level'] = min(v[1] for v in levels)
                result['price_gp'] = recipe['price_per_cl'] * result['caster_level']
                result['creation_cost_gp'] = result['price_gp']/2
        result['base_price_gp'] = magical_base_price(result.get('price_gp'),result.get('creation_cost_gp'))
        return result

    def requirements(self, recipe):
        missing_feats = tuple(f for f in recipe['feats'] if f.casefold() not in self.feats)
        alternatives = recipe.get('spell_any', [])
        alternative_names = {s.casefold() for group in alternatives for s in group}
        missing_spells = tuple(s for s in recipe['spells'] if s.casefold() not in self.spells and s.casefold() not in alternative_names)
        missing_spells += tuple(' or '.join(group) for group in alternatives if not any(s.casefold() in self.spells for s in group))
        review = recipe.get('review', '')
        missing_conditions = ()
        if recipe.get('alignment'):
            alignment = self.details.alignment.upper()
            letter = {'good':'G','evil':'E','lawful':'L','chaotic':'C'}[recipe['alignment']]
            if not alignment: review += ' Choose an alignment to verify the creator restriction.'
            elif letter not in alignment: missing_conditions = ('Creator must be ' + recipe['alignment'],)
        if recipe.get('price_per_cl') and not self.spell_crafting_levels(recipe):
            review += ' No supported active class progression currently grants this spell level; confirm an external spell provider or custom rule.'
        if recipe.get('construction_skill'):
            review += ' Additional construction check: ' + recipe['construction_skill']
        if any(recipe.get(key) is None for key in ('price_gp', 'creation_cost_gp', 'caster_level')):
            review += ' Variable price, construction cost, or caster level requires item-specific confirmation.'
        status = 'Missing requirements' if missing_feats or missing_spells or missing_conditions else ('Needs review' if review else 'Listed requirements met')
        return RequirementCheck(status, missing_feats, missing_spells, review, missing_conditions)

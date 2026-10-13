"""Character-aware, read-only prerequisite checks for crafting planners."""
from dataclasses import dataclass
from functools import cached_property
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
        return tuple(sorted(f for f in creation_feats() if f.casefold() in self.feats
                            or (f == 'Craft Marvelous Item' and 'craft wondrous item' in self.feats)))

    @cached_property
    def magic_entries_by_key(self):
        from app.catalogs import DEFAULT_CATALOG
        return {entry['key']: entry for entry in DEFAULT_CATALOG.magic_entries()}

    def marvelous_requirements(self, **construction_access):
        """Check a composer plan using saved feats and explicit permanent access.

        Do not substitute live casting statistics: those include temporary
        Sequence, implement and other bonuses ineligible for construction.
        """
        from app.marvelous_item_rules import marvelous_requirements
        return marvelous_requirements(feats=self.feats, **construction_access)

    def permanent_marvelous_access(self):
        """Collect baseline crafting access without live/temporary modifiers.

        Class progression is archetype/choice-aware. Additional permanent bonuses
        and cooperative sources remain explicit construction inputs; do not guess
        permanence from a live modifier's positive value.
        """
        from app.content import entries, archetype_entry
        from app.archetype_rules import archetype_choice_selections_from_records
        from app.rules import automatic_sphere_casting
        classes = self.repository.list_class_levels(self.character_id)
        keys = self.repository.list_class_archetype_keys(self.character_id)
        archetypes = {key: entry for group in keys.values() for key in group
                      if (entry := archetype_entry(key)) is not None}
        selections = self.repository.list_class_feature_selections(self.character_id)
        casting = automatic_sphere_casting(classes, {entry['key']: entry for entry in entries('classes')},
            keys, archetypes, {row.id: archetype_choice_selections_from_records(selections, row.id) for row in classes})
        level = casting[1] if casting is not None else 0
        spells = [spell for spell in self.repository.list_spells(self.character_id)
                  if spell.enabled and spell.system.casefold() in {'sphere', 'spheres'}]
        spheres = {spell.school_or_sphere for spell in spells
                   if spell.catalog_category.casefold() == 'base sphere' or spell.catalog_key.endswith(':base')}
        talents = tuple((entry['name'] if (entry := self.magic_entries_by_key.get(spell.catalog_key)) else spell.name)
                        for spell in spells)
        return dict(sphere_levels={sphere: level for sphere in spheres},
                    available_talents=talents)

    def marvelous_plan_requirements(self, plan, *, access=None):
        """Resolve selected catalog identities and feed the shared eligibility check."""
        from app.marvelous_base_powers import resolve_base_power
        resolve_base_power(plan)
        required, advanced = [], []
        for contribution in plan['contributions']:
            entry = self.magic_entries_by_key.get(contribution['catalog_key'])
            if entry is None or str(entry.get('sphere', '')).casefold() != plan['sphere'].casefold():
                raise ValueError('Selected talent is not part of the blueprint base sphere.')
            required.append(entry['name'])
            if 'advanced' in str(entry.get('category', '')).casefold(): advanced.append(entry['name'])
        return self.marvelous_requirements(caster_level=plan['caster_level'],
            required_spheres=(plan['sphere'],), required_talents=required,
            advanced_talents=advanced, **(access if access is not None else self.permanent_marvelous_access()))

    def save_marvelous_design(self, plan, *, name, slot, description, item_id=None):
        """Save a reviewed blueprint without claiming completion of a craft project.

        Unknown construction effects remain rules-only; do not attach passive
        modifiers to a device whose power requires activation.
        """
        import json
        from copy import deepcopy
        from uuid import uuid4
        from app.marvelous_item_rules import quote_marvelous_blueprint
        from app.marvelous_base_powers import resolve_base_power
        if not self.feats.intersection({'craft marvelous item', 'craft wondrous item'}):
            raise ValueError('A Marvelous Item creation feat is required.')
        plan = deepcopy(plan)
        for extra in plan.get('extra_effects', []):
            extra.setdefault('effect_id', str(uuid4()))
        identities = [extra['effect_id'] for extra in plan.get('extra_effects', [])]
        if any(not isinstance(identity, str) or not identity for identity in identities) or len(set(identities)) != len(identities):
            raise ValueError('Additional powers must have unique identities.')
        _, price, _ = quote_marvelous_blueprint(plan)
        effect = resolve_base_power(plan)
        metadata = dict(status='rules_only', provider='marvelous-composer',
                        rules_only=['Custom activated effect; activation automation pending.'],
                        marvelous_blueprint=plan, marvelous_base_effect=effect)
        if item_id is not None:
            item = next((item for item in self.repository.list_equipment(self.character_id) if item.id == item_id), None)
            if item is None:
                raise ValueError('This item does not belong to the active character.')
            previous = json.loads(item.automation_json or '{}')
            if previous.get('provider') != 'marvelous-composer':
                raise ValueError('Only custom Marvelous designs can be edited here.')
            if item.quantity != 1:
                raise ValueError('Split stacked devices before editing a design.')
            old_powers = previous.get('marvelous_blueprint', {}).get('extra_effects', [])
            old_counts = previous.get('marvelous_extra_uses_used', {})
            spent_by_id = {power.get('effect_id', f'legacy:{index}'): old_counts.get(str(index), 0)
                           for index, power in enumerate(old_powers, 1)}
            previous['marvelous_extra_uses_used'] = {str(index): spent_by_id.get(power['effect_id'], 0)
                for index, power in enumerate(plan.get('extra_effects', []), 1)}
            previous.update(metadata)
            self.repository.update_equipment(self.character_id, item_id,
                name=name, category=item.category, quantity=item.quantity, weight=item.weight,
                equipped=item.equipped, ac_bonus=item.ac_bonus, bonus_type=item.bonus_type,
                max_dex_bonus=item.max_dex_bonus, notes=description,
                armor_check_penalty=item.armor_check_penalty, slot=slot,
                value_gp=float(price.market_price_gp), automation_json=json.dumps(previous))
            return item_id
        return self.repository.add_equipment(self.character_id,
            name=name, category='Gear', quantity=1, weight=0, equipped=False,
            ac_bonus=0, bonus_type='untyped', max_dex_bonus=None, notes=description,
            slot=slot, value_gp=float(price.market_price_gp),
            catalog_source='Custom Spheres Marvelous Item', state='stored',
            automation_json=json.dumps(metadata))

    def activate_marvelous_item(self, item_id, *, apply_to_self=False, effect_index=0):
        return self.repository.consume_marvelous_item_use(self.character_id, item_id,
                                                          apply_to_self=apply_to_self, effect_index=effect_index)

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
        missing_feats = tuple(f for f in recipe['feats'] if f.casefold() not in self.feats
                              and not (f == 'Craft Marvelous Item' and 'craft wondrous item' in self.feats))
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

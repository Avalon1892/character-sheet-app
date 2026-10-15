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

    @cached_property
    def integration_feats(self):
        from app.catalogs import DEFAULT_CATALOG
        names = {feat.name.casefold(): feat.name for feat in self.repository.list_feats(self.character_id) if feat.enabled}
        for entry in DEFAULT_CATALOG.feat_entries():
            if entry['name'].casefold() in self.feats: names.setdefault(entry['name'].casefold(), entry['name'])
        return names

    def marvelous_requirements(self, **construction_access):
        """Check a composer plan using saved feats and explicit permanent access.

        Do not substitute live casting statistics: those include temporary
        Sequence, implement and other bonuses ineligible for construction.
        """
        from app.marvelous_item_rules import marvelous_requirements
        return marvelous_requirements(feats=self.feats, **construction_access)

    def accessible_marvelous_effects(self, sphere=None):
        """Current effective choices, including flexible talents; not permanent eligibility."""
        from app.exploitant_rules import effective_magic_talents
        keys = {spell.catalog_key for spell in effective_magic_talents(self.repository, self.character_id)
                if spell.enabled and spell.system.casefold() in {'sphere', 'spheres'}}
        # Warping Structures is a shared reference heading, not another talent.
        return tuple(sorted((entry for key in keys if (entry := self.magic_entries_by_key.get(key))
            and (sphere is None or entry['sphere'].casefold() == sphere.casefold())
            and key != 'warp:advanced-talent:warping-structures-store-and-teleport-structure'
            and entry.get('category') != 'Base Sphere' and 'drawback' not in entry.get('category', '').casefold()),
            key=lambda entry: (entry['sphere'].casefold(), entry['name'].casefold())))

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
        from app.marvelous_base_powers import resolve_base_power, talent_effect_choices
        from app.marvelous_item_rules import advanced_construction_blockers, CROSS_SPHERE_CONSTRUCTION_REQUIREMENTS
        construction_access = access if access is not None else self.permanent_marvelous_access()
        known_talents = {name.casefold() for name in construction_access.get('available_talents', ())}
        known_spheres = {name.casefold() for name, level in construction_access.get('sphere_levels', {}).items() if level > 0}
        required, advanced, spheres, construction_blockers = [], [], [], []
        from app.marvelous_item_rules import educated_required_spheres
        if educated_required_spheres(plan) == ():
            construction_blockers.append('Educated: choose required spheres.')
        from app.marvelous_item_rules import complex_required_skill
        if complex_required_skill(plan) == '':
            construction_blockers.append('Complex: choose the required skill.')
        from app.marvelous_item_rules import complex_crafting_skills
        if required_skills := complex_crafting_skills(plan):
            from app.models import SKILLS
            from app.services.character_calculations import CharacterCalculationService
            ranks = CharacterCalculationService(self.repository, self.character_id).effective_skill_ranks()
            keys = {skill.name.casefold(): skill.key for skill in SKILLS}
            construction_blockers.extend(f'Complex: crafter must be trained in {name}.'
                for name in required_skills if ranks.get(keys[name.casefold()], 0) < 1)
        from app.marvelous_item_rules import marvelous_area_bound_mode
        if marvelous_area_bound_mode(plan) == '':
            construction_blockers.append('Area-Bound: choose distance-limited use or location recharge.')
        for power in [plan, *plan.get('extra_effects', [])]:
            resolve_base_power(power)
            if power['caster_level'] != plan['caster_level']:
                raise ValueError('All item effects must have the same caster level.')
            spheres.append(power['sphere'])
            for feat in power.get('feat_integrations', []):
                if feat['name'].casefold() not in self.integration_feats:
                    construction_blockers.append(f'Integrated feat must be possessed: {feat["name"]}.')
            construction_blockers.extend(advanced_construction_blockers(power['contributions'], power['caster_level'],
                display_names={key: entry['name'] for key, entry in self.magic_entries_by_key.items()}))
            for contribution in power['contributions']:
                entry = self.magic_entries_by_key.get(contribution['catalog_key'])
                if entry is None or str(entry.get('sphere', '')).casefold() != power['sphere'].casefold():
                    raise ValueError('Selected talent is not part of the blueprint base sphere.')
                required.append(entry['name'])
                for sphere, talent_key in CROSS_SPHERE_CONSTRUCTION_REQUIREMENTS.get(entry['key'], ()):
                    if sphere.casefold() not in known_spheres:
                        construction_blockers.append(f'{entry["name"]}: requires the {sphere} base sphere as a construction prerequisite.')
                    if talent_key and (talent := self.magic_entries_by_key[talent_key]['name']).casefold() not in known_talents:
                        construction_blockers.append(f'{entry["name"]}: requires {talent} as a construction prerequisite.')
                if talent_effect_choices(entry['key']) and not contribution.get('effect_choice'):
                    construction_blockers.append(f'{entry["name"]}: choose the effect mode before construction.')
                if 'advanced' in str(entry.get('category', '')).casefold(): advanced.append(entry['name'])
            from app.marvelous_item_rules import spell_selectivity_options
            if options := spell_selectivity_options(power):
                if not options['mode'] or not options['spheres']:
                    construction_blockers.append('Spell Selectivity: choose affected spheres and a mode.')
                known = {entry['sphere'] for entry in self.magic_entries_by_key.values()}
                if any(sphere not in known for sphere in options['spheres']):
                    raise ValueError('Spell Selectivity contains an unknown magic sphere.')
        result = self.marvelous_requirements(caster_level=plan['caster_level'],
            required_spheres=spheres, required_talents=required,
            advanced_talents=advanced, **construction_access)
        from dataclasses import replace
        return replace(result, blockers=result.blockers + tuple(construction_blockers))

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
        from app.marvelous_item_rules import drawback_complexity
        from app.optional_traditions import crafting_drawbacks
        item_drawbacks = {entry['key']: entry for entry in crafting_drawbacks()}
        drawback_complexity(plan.get('drawbacks', []))
        from app.marvelous_item_rules import educated_required_spheres
        educated = educated_required_spheres(plan)
        if educated:
            from app.catalogs import DEFAULT_CATALOG
            known = {entry['name'].casefold() for entry in (*DEFAULT_CATALOG.magic_spheres(), *DEFAULT_CATALOG.martial_spheres())}
            if any(sphere.casefold() not in known for sphere in educated):
                raise ValueError('Educated contains an unknown sphere.')
        for record in plan.get('drawbacks', []):
            if record['source'] == 'published':
                entry = self.magic_entries_by_key.get(record['catalog_key']) or item_drawbacks.get(record['catalog_key'])
                if entry is None or 'drawback' not in entry.get('category', '').casefold():
                    raise ValueError('Unknown published item drawback.')
                if entry['sphere'] not in {plan['sphere'], 'Universal'}:
                    raise ValueError('A sphere drawback must match the item effect.')
                record.update(name=entry['name'], description=entry.get('description', ''))
        if plan.get('crafting_tradition') is not None:
            from app.optional_traditions import catalog
            selected = plan['crafting_tradition']
            entry = next((entry for entry in catalog()['entries'] if entry['kind'] == 'Crafting'
                          and isinstance(selected, dict) and entry['key'] == selected.get('key')), None)
            if entry is None: raise ValueError('Unknown crafting tradition.')
            plan['crafting_tradition'] = dict(entry, notes=str(selected.get('notes', '')))
        from app.marvelous_item_presentation import validate_display_overrides
        validate_display_overrides(plan.get('display_overrides', {}))
        from app.marvelous_item_rules import spell_selectivity_options
        known_spheres = {entry['sphere'] for entry in self.magic_entries_by_key.values()}
        for power in [plan, *plan.get('extra_effects', [])]:
            if options := spell_selectivity_options(power):
                if any(sphere not in known_spheres for sphere in options['spheres']):
                    raise ValueError('Spell Selectivity contains an unknown magic sphere.')
        for extra in plan.get('extra_effects', []):
            validate_display_overrides(extra.get('display_overrides', {}))
            if any(not isinstance(extra.get(field, ''), str) for field in ('effect_name', 'effect_description')):
                raise ValueError('Additional power name and description must be text.')
        for extra in plan.get('extra_effects', []):
            extra.setdefault('effect_id', str(uuid4()))
        identities = [extra['effect_id'] for extra in plan.get('extra_effects', [])]
        if any(not isinstance(identity, str) or not identity for identity in identities) or len(set(identities)) != len(identities):
            raise ValueError('Additional powers must have unique identities.')
        _, price, _ = quote_marvelous_blueprint(plan)
        from app.marvelous_item_rules import marvelous_item_weight
        weight = marvelous_item_weight(plan)
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
            if previous.get('marvelous_project'):
                raise ValueError('A construction project locks its design; create a new design for changes.')
            old_powers = previous.get('marvelous_blueprint', {}).get('extra_effects', [])
            old_counts = previous.get('marvelous_extra_uses_used', {})
            spent_by_id = {power.get('effect_id', f'legacy:{index}'): old_counts.get(str(index), 0)
                           for index, power in enumerate(old_powers, 1)}
            previous['marvelous_extra_uses_used'] = {str(index): spent_by_id.get(power['effect_id'], 0)
                for index, power in enumerate(plan.get('extra_effects', []), 1)}
            previous.update(metadata)
            self.repository.update_equipment(self.character_id, item_id,
                name=name, category=item.category, quantity=item.quantity, weight=item.weight if weight is None else weight,
                equipped=item.equipped, ac_bonus=item.ac_bonus, bonus_type=item.bonus_type,
                max_dex_bonus=item.max_dex_bonus, notes=description,
                armor_check_penalty=item.armor_check_penalty, slot=slot,
                value_gp=float(price.market_price_gp), automation_json=json.dumps(previous))
            return item_id
        return self.repository.add_equipment(self.character_id,
            name=name, category='Gear', quantity=1, weight=0 if weight is None else weight, equipped=False,
            ac_bonus=0, bonus_type='untyped', max_dex_bonus=None, notes=description,
            slot=slot, value_gp=float(price.market_price_gp),
            catalog_source='Custom Spheres Marvelous Item', state='stored',
            automation_json=json.dumps(metadata))

    def activate_marvelous_item(self, item_id, *, apply_to_self=False, effect_index=0, target_character_id=None):
        return self.repository.consume_marvelous_item_use(self.character_id, item_id,
                                                          apply_to_self=apply_to_self, effect_index=effect_index,
                                                          target_character_id=target_character_id)

    def start_marvelous_construction(self, item_id):
        import json
        from app.marvelous_projects import start_project
        item = next((item for item in self.repository.list_equipment(self.character_id) if item.id == item_id), None)
        if item is None: raise ValueError('Item does not belong to this character.')
        plan = json.loads(item.automation_json or '{}')['marvelous_blueprint']
        project = start_project(plan, self.marvelous_plan_requirements(plan))
        self.repository.start_marvelous_project(self.character_id, item_id, project)
        return project

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

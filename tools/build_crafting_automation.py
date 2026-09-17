"""Compile narrowly recognized construction conditions, never at UI runtime."""
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def compile_recipe(recipe):
    review = recipe.get('review', '').strip()
    result = {}
    if review in {'APG', 'UM', 'UC', '( )'}: result['review'] = ''
    alignment = re.fullmatch(r'(?:the )?(?:creator|caster) must be (good|evil|lawful|chaotic)', review, re.I)
    if alignment: result.update(alignment=alignment[1].lower(), review='')
    spells = recipe.get('spells', [])
    if review == 'or' and len(spells) == 2:
        pattern = re.escape(spells[0]) + r'\s+or\s+' + re.escape(spells[1])
        if re.search(pattern, recipe.get('requirements',''), re.I):
            result.update(spell_any=[spells], review='')
    return result

def main():
    data = json.loads((ROOT/'data/pf1e/crafting_catalog.json').read_text(encoding='utf-8'))
    entries = {r['key']: patch for r in data['recipes'] if (patch := compile_recipe(r))}
    (ROOT/'data/pf1e/crafting_automation.json').write_text(json.dumps({'version':1,'entries':entries},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Compiled {len(entries)} structured crafting overrides.')

if __name__ == '__main__': main()

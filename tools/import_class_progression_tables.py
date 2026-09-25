"""Import display-only class tables; never fetch or parse HTML in the sheet."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bs4 import BeautifulSoup
from app.content import class_entries
from tools.import_spheres_class_catalog import _class_table, _split_features, slug


def extract(page):
    soup = BeautifulSoup(page, "html.parser")
    for table in soup.find_all("table"):
        if table.find("table"):
            continue
        grid = {}
        for r, row in enumerate(table.find_all("tr")):
            c = 0
            for cell in row.find_all(("td", "th"), recursive=False):
                while (r, c) in grid:
                    c += 1
                text = cell.get_text(" ", strip=True)
                for dy in range(int(cell.get("rowspan", 1))):
                    for dx in range(int(cell.get("colspan", 1))):
                        grid[r + dy, c + dx] = text
                c += int(cell.get("colspan", 1))
        if not grid:
            continue
        width = max(c for r, c in grid) + 1
        rows = [[grid.get((r, c), "") for c in range(width)]
                for r in range(max(r for r, c in grid) + 1)]
        first = next((i for i, row in enumerate(rows)
                      if re.fullmatch(r"1(?:st)?", row[0])), None)
        if first is None or "special" not in " ".join(sum(rows[:first], [])).lower():
            continue
        headers = [" · ".join(dict.fromkeys(row[c] for row in rows[:first] if row[c]))
                   for c in range(width)]
        data = [row for row in rows[first:] if re.fullmatch(r"\d+(?:st|nd|rd|th)?", row[0])]
        if data and [int(re.match(r"\d+", row[0])[0]) for row in data] == list(range(1, len(data) + 1)):
            return headers, data
    return [], []


def load(entry):
    key = entry["key"]
    if key.startswith("pathfinder-class:"):
        url = f"https://aonprd.com/ClassDisplay.aspx?ItemName={quote(entry['name'])}"
        cache = ROOT / ".archetype-source" / "progression" / (key.split(":")[-1] + ".html")
    else:
        url = entry.get("source_url", "")
        cache = ROOT / ".archetype-source" / "spheres" / "classes" / (slug(entry["name"]) + ".html")
    try:
        if cache.exists():
            page = cache.read_text(encoding="utf-8")
        else:
            page = urlopen(Request(url, headers={"User-Agent": "CharacterSheetReferenceImporter/1.0"}), timeout=45).read().decode("utf-8")
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(page, encoding="utf-8")
        headers, rows = extract(page)
        if not rows:
            headers, rows = _class_table(page)
            rows = [r for r in rows if r and re.fullmatch(r"\d+(?:st|nd|rd|th)?", r[0])]
        if not rows or len(rows) > 20 or any(len(r) != len(headers) for r in rows):
            raise ValueError("No rectangular class table")
        return key, {"source_url": url, "headers": headers, "rows": rows,
                     "features": [{"level": int(re.match(r"\d+", row[0])[0]), "name": name}
                                  for row in rows for name in _split_features(row[5])
                                  if name.strip() not in ("-", "—", "–", "") ]}
    except Exception as error:
        print(f"Needs review: {key}: {error}", flush=True)
        return key, None


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = dict(pool.map(load, class_entries()))
    document = {key: value for key, value in results.items() if value}
    (ROOT / "data/pf1e/class_progression_tables.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(document)}/{len(results)} class tables.")

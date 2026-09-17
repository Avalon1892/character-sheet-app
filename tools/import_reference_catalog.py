"""Import attributed PF1 skill and Prodigy rules; never used at app runtime."""
from __future__ import annotations
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools-deps"))
from bs4 import BeautifulSoup

SKILLS = ("Acrobatics", "Appraise", "Bluff", "Climb", "Craft", "Diplomacy",
          "Disable Device", "Disguise", "Escape Artist", "Fly", "Handle Animal",
          "Heal", "Intimidate", "Knowledge", "Linguistics", "Perception", "Perform",
          "Profession", "Ride", "Sense Motive", "Sleight of Hand", "Spellcraft",
          "Stealth", "Survival", "Swim", "Use Magic Device")

def fetch(url):
    request = Request(url, headers={"User-Agent": "Character Sheet rules reference importer"})
    return BeautifulSoup(urlopen(request, timeout=60).read(), "html.parser")

def clean(fragment, url):
    soup = BeautifulSoup(str(fragment), "html.parser")
    for node in soup.select("script, style, img, input, button, iframe, #toc"):
        node.decompose()
    allowed = {"p", "br", "b", "strong", "i", "em", "ul", "ol", "li", "table",
               "tr", "td", "th", "h1", "h2", "h3", "h4", "a", "sup", "sub", "hr"}
    for node in list(soup.find_all(True)):
        if node.name not in allowed:
            node.unwrap()
            continue
        href = node.get("href", "")
        node.attrs = {}
        if node.name == "a" and href:
            target = urljoin(url, href)
            if target.startswith(("http://", "https://")):
                node["href"] = target
        if node.name == "table":
            node.attrs = {"width": "100%", "cellpadding": "5", "cellspacing": "0", "border": "1"}
    return str(soup)

def skill(name):
    url = "https://aonprd.com/Skills.aspx?ItemName=" + quote(name)
    soup = fetch(url)
    root = soup.find(id="MainContent_DataListTalentsAll_LabelName_0")
    if root is None or name not in root.get_text():
        raise ValueError("Missing skill: " + name)
    rendered = clean(root, url)
    text = root.get_text(" ", strip=True)
    if len(text) < 300:
        raise ValueError("Incomplete skill: " + name)
    print("Imported skill:", name, flush=True)
    return {"key": name.lower().replace(" ", "_"), "name": name,
            "html": rendered, "description": text, "source_url": url}

def prodigy():
    url = "https://spheresofpower.wikidot.com/prodigy"
    root = fetch(url).select_one("#page-content")
    if root is None:
        raise ValueError("Missing Prodigy page")
    section = ""
    group = ""
    entries = []
    for node in root.find_all(["h2", "h3", "h4", "p", "li"]):
        if node.find_parent(id="toc"):
            continue
        if node.name == "h2":
            section = node.get_text(" ", strip=True)
            group = ""
        elif node.name in {"h3", "h4"}:
            group = node.get_text(" ", strip=True)
        elif section in {"Sequence (Ex)", "Integrated Techniques", "Imbue Sequence (Su)"}:
            if node.name == "p" and node.find_parent("li"):
                continue
            strong = node.find(["strong", "b"])
            if strong is None:
                continue
            label = strong.get_text(" ", strip=True)
            if ":" not in label and not re.search(r"\((?:opener|link|finish|imbue)\)", label, re.I):
                continue
            name = re.split(r"\s*[(:\[]", label)[0].strip()
            if name in {"Source", "Note", "Special", "Prerequisites"}:
                continue
            kind = ("Opener" if "opener" in label.lower() or group == "Openers" else
                    "Link" if "link" in label.lower() or group == "Link Components" else
                    "Imbue" if "imbue" in label.lower() else "Finisher")
            fragment = str(node)
            for following in node.next_siblings:
                if getattr(following, "name", None) not in {"p", "table", "ul", "ol"}:
                    if getattr(following, "name", None):
                        break
                    continue
                if following.find(["strong", "b"]):
                    break
                fragment += str(following)
            html = clean(fragment, url)
            entries.append({"key": re.sub(r"[^a-z0-9]+", "-", group.lower()+"-"+name.lower()).strip("-"),
                            "name": name, "sphere": "" if section == "Sequence (Ex)" else re.sub(r"\s*\[[^]]+\]", "", group),
                            "kind": kind, "html": html,
                            "description": BeautifulSoup(html, "html.parser").get_text(" ", strip=True),
                            "source_url": url})
    if not any(e["name"] == "Arcane Apocalypse" for e in entries):
        raise ValueError("Missing universal finishers")
    return entries

def main():
    if "--licenses" in sys.argv:
        notices = []
        for url in ("https://aonprd.com/Licenses.aspx", "https://spheresofpower.wikidot.com/legal:start"):
            soup = fetch(url)
            root = soup.select_one("#page-content") or soup
            text = root.get_text("\n", strip=True)
            start = text.upper().find("OPEN GAME LICENSE")
            if start < 0:
                raise ValueError("Missing license notice: " + url)
            notices.append(url + "\n\n" + text[start:])
        (ROOT / "data/pf1e/reference_rules_LICENSE.txt").write_text(
            "Reference rules are Open Game Content. No artwork or site branding is included.\n\n"
            + "\n\n".join(notices), encoding="utf-8")
        return
    with ThreadPoolExecutor(max_workers=3) as pool:
        skills = list(pool.map(skill, SKILLS))
    abilities = prodigy()
    result = {"schema": 1, "attribution": "Pathfinder skill rules: Paizo Inc., via Archives of Nethys. Prodigy rules: Drop Dead Studios and credited contributors, via Spheres of Power Wiki. Open Game Content; see linked source licenses. No artwork or site branding imported.",
              "skills": skills, "prodigy": abilities}
    output = ROOT / "data" / "pf1e" / "reference_rules.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved", len(skills), "skills and", len(abilities), "Prodigy abilities")

if __name__ == "__main__":
    main()

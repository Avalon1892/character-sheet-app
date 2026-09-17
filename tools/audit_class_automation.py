"""Generate the unified original-class and archetype automation audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.catalogs import RulesCatalog  # noqa: E402
from app.class_mechanics_audit import build_audit, markdown_summary  # noqa: E402


DEFAULT_JSON = ROOT / "data" / "pf1e" / "class_automation_audit.json"
DEFAULT_MARKDOWN = ROOT / "CLASS_AUTOMATION_AUDIT.md"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit documentation and runtime automation for every class and archetype."
    )
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    args = parser.parse_args()

    catalog = RulesCatalog()
    document = build_audit(catalog.class_entries(), catalog.archetype_entries())
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    args.markdown.write_text(markdown_summary(document), encoding="utf-8")
    print(
        f"Audited {document['summary']['classes']['total']} classes and "
        f"{document['summary']['archetypes']['total']} archetypes."
    )
    print(args.json)
    print(args.markdown)


if __name__ == "__main__":
    main()

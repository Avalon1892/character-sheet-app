from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from app.catalogs import DEFAULT_CATALOG


DEFAULT_OUTPUT = Path("data/pf1e/item_automation_audit.json")


def build_audit() -> dict:
    records = []
    status_counts: Counter[str] = Counter()
    choice_count = 0
    ambiguous = []
    missing_structure = []
    for entry in DEFAULT_CATALOG.item_entries():
        automation = dict(entry.get("item_automation") or {})
        status = str(automation.get("status") or "unsupported")
        status_counts[status] += 1
        choices = list(automation.get("choices") or ())
        if choices:
            choice_count += 1
        rules_only = list(automation.get("rules_only") or ())
        if status in {"partial", "unsupported"}:
            ambiguous.append(
                {
                    "key": entry["key"],
                    "name": entry["name"],
                    "status": status,
                    "review_notes": rules_only,
                }
            )
        if str(entry.get("item_type") or "").casefold() in {"weapon", "ammo"}:
            weapon = entry.get("weapon") or {}
            missing = [field for field in ("damage_dice", "critical") if not weapon.get(field)]
            if missing:
                missing_structure.append(
                    {"key": entry["key"], "name": entry["name"], "missing": missing}
                )
        records.append(
            {
                "key": entry["key"],
                "name": entry["name"],
                "status": status,
                "requires_choice": bool(choices),
                "provider": automation.get("provider", "catalog-default"),
            }
        )
    return {
        "catalog_records": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "requires_choice": choice_count,
        "ambiguous_records": ambiguous,
        "missing_structured_information": missing_structure,
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit reviewed stage 1–3 item automation.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    audit = build_audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({key: value for key, value in audit.items() if key not in {"records", "ambiguous_records", "missing_structured_information"}}, indent=2))
    print(f"Audit written to {args.output}")


if __name__ == "__main__":
    main()

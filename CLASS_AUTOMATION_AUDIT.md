# Class & Archetype Automation Audit

This report distinguishes rules documentation from actual sheet automation. It is generated from the same bundled catalogs and provider registry used by the application.

## Original Classes

Total: 102

| Status | Count |
|---|---:|
| Fully Automated | 71 |
| Partially Automated | 31 |

## Archetypes

Total: 1830

| Status | Count |
|---|---:|
| Fully Automated | 1627 |
| Manual Review | 65 |
| Partially Automated | 138 |

## Highest-priority reusable systems

| System | Affected records |
|---|---:|
| Bane | 1 |
| Favored Terrain | 1 |
| Vigilante Social Talent | 1 |
| Revelation | 1 |
| Arcane Pool | 1 |

## How to use this audit

1. Implement one recurring system as a shared provider.
2. Register that provider once in `app/class_mechanics_audit.py`.
3. Add declarative class or archetype data instead of class-named UI branches.
4. Regenerate the report; every affected record is reclassified automatically.

The JSON report contains per-entry coverage axes, detected systems, exact gaps, and source links.
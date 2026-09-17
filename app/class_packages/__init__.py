"""Modular automation packages for individual class families.

Rules prose remains in the versioned Pathfinder/Spheres catalogs.  These
packages contain only reviewed runtime declarations: resources, deterministic
effects, optional sheet blocks, and structured archetype overlays.
"""

from app.class_packages.loader import (
    all_class_packages,
    enrich_class_from_package,
    archetype_package,
    archetype_runtime_package,
    class_package,
    enrich_archetype_from_package,
)
from app.class_packages.schemas import (
    ClassFamilyPackage,
    PackageEffect,
    PackagePowerProvider,
    PackageResource,
    PackageResourceModule,
)

__all__ = (
    "ClassFamilyPackage",
    "PackageEffect",
    "PackagePowerProvider",
    "PackageResource",
    "PackageResourceModule",
    "all_class_packages",
    "enrich_class_from_package",
    "archetype_package",
    "archetype_runtime_package",
    "class_package",
    "enrich_archetype_from_package",
)

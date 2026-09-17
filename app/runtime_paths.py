"""Runtime-location helpers shared by source and frozen distributions."""

from __future__ import annotations

import sys
from pathlib import Path


def application_folder() -> Path:
    """Return the folder users perceive as the application folder.

    In a PyInstaller one-folder build, Python modules live below ``_internal``;
    saving beside those modules would be surprising and may fail after a normal
    installation.  ``sys.executable`` points to the visible application folder.
    """

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


def create_database_backup(database_path: Path, keep: int = 10) -> Path | None:
    if not database_path.exists():
        return None
    backup_directory = database_path.parent / "backups"
    backup_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
    destination = backup_directory / f"characters-{timestamp}.db"
    shutil.copy2(database_path, destination)
    backups = sorted(backup_directory.glob("characters-*.db"), reverse=True)
    for old_backup in backups[keep:]:
        old_backup.unlink()
    return destination

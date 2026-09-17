"""Consistent read-only SQLite source backup with integrity verification."""
import sqlite3
import sys
from pathlib import Path


def backup(source, destination):
    with sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(destination) as copied:
            original.backup(copied)
            if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Database backup integrity check failed')


if __name__ == '__main__':
    backup(sys.argv[1], sys.argv[2])

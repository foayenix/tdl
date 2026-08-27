"""Schema migrations.

Python owns the schema; Rust reads `PRAGMA user_version`, refuses to start if
it does not match what it was compiled against, and never migrates
(BUILD.md §3, ownership rule).

A migration is a file `NNN_name.sql` in `schema/`. Applying `NNN` stamps
`user_version = NNN + 1`, so the four migrations of schema v4 leave the
database at version 4.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from .db import user_version


def _schema_dir() -> Path:
    """Where the .sql files are.

    Frozen by PyInstaller they sit beside the executable's bundle root, which
    `sys._MEIPASS` names; from source they sit next to the package. The frozen
    sidecar must carry them, because Rust never migrates (BUILD.md §3) and a
    binary with no schema could not migrate either.
    """
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled is not None:
        return Path(bundled) / "schema"
    return Path(__file__).resolve().parent.parent / "schema"


SCHEMA_DIR = _schema_dir()

_FILENAME = re.compile(r"^(\d{3})_[a-z0-9_]+\.sql$")


@dataclass(frozen=True)
class Migration:
    version: int  # the user_version this migration leaves behind
    path: Path

    @property
    def name(self) -> str:
        return self.path.name


def discover(schema_dir: Path | str = SCHEMA_DIR) -> list[Migration]:
    """Every migration in `schema_dir`, in the order it must be applied."""
    schema_dir = Path(schema_dir)
    found: list[Migration] = []

    for path in sorted(schema_dir.glob("*.sql")):
        match = _FILENAME.match(path.name)
        if match is None:
            raise ValueError(
                f"{path.name} is not a migration filename; expected NNN_name.sql"
            )
        found.append(Migration(version=int(match.group(1)) + 1, path=path))

    expected = list(range(1, len(found) + 1))
    if [m.version for m in found] != expected:
        got = ", ".join(m.name for m in found)
        raise ValueError(f"migrations are not a contiguous ladder from 000: {got}")

    return found


def pending(conn: sqlite3.Connection, schema_dir: Path | str = SCHEMA_DIR) -> list[Migration]:
    """The migrations this database has not had applied yet."""
    at = user_version(conn)
    return [m for m in discover(schema_dir) if m.version > at]


def apply(conn: sqlite3.Connection, migration: Migration) -> None:
    """Run one migration and stamp its version, both or neither."""
    sql = migration.path.read_text()
    conn.executescript(
        f"BEGIN;\n{sql}\nPRAGMA user_version = {migration.version};\nCOMMIT;"
    )


def migrate(conn: sqlite3.Connection, schema_dir: Path | str = SCHEMA_DIR) -> list[Migration]:
    """Bring the database up to the newest migration. Returns what it applied."""
    applied = []
    for migration in pending(conn, schema_dir):
        apply(conn, migration)
        applied.append(migration)
    return applied

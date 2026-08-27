"""Connections to the single SQLite file.

Both the Rust core and this CLI may hold the database open at once, so every
connection on both sides opens WAL and a busy timeout (BUILD.md §3).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / "Documents" / "ledger.sqlite"

BUSY_TIMEOUT_MS = 5000


def connect(path: Path | str) -> sqlite3.Connection:
    """Open `path`, creating it if absent, with the pragmas the design requires."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def user_version(conn: sqlite3.Connection) -> int:
    """The schema version stamped by the last migration to run."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])

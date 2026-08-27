"""The text dump that sits beside the database and is the thing actually committed.

The `.db` is binary and is never committed; `dump/ledger.sql` is the historical
source of truth, and any commit has to rebuild from it (BUILD.md §4).

Objects come out in **creation order**, not alphabetical order. That is the
whole reason this is not `Connection.iterdump()`: alphabetically, `constituent`
restores before `monograph` exists, which trips both the foreign keys and the
sourcing triggers' `SELECT status FROM monograph`. In creation order every
parent precedes its children, and triggers are created last — after the data
they would otherwise fire on.

The FTS5 index is **not dumped**. It is derived from the tables around it, and
its shadow tables (`search_data`, `search_idx`, …) cannot be restored by
replaying their `CREATE TABLE` statements — creating the virtual table has
already made them. `restore()` rebuilds the index instead, by touching every
indexed row so the triggers repopulate it. The dump holds truth; the index is
rebuilt from truth.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from .db import user_version
from .find import KINDS


def _literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return f"X'{value.hex()}'"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def _rows_of(conn: sqlite3.Connection, table: str) -> Iterator[str]:
    cursor = conn.execute(f'SELECT * FROM "{table}"')
    columns = ", ".join(f'"{description[0]}"' for description in cursor.description)
    for row in cursor:
        values = ", ".join(_literal(value) for value in row)
        yield f'INSERT INTO "{table}" ({columns}) VALUES ({values});'


def _derived_tables(conn: sqlite3.Connection) -> set[str]:
    """Virtual tables and the shadow tables they own.

    Their content is rebuilt on restore, and their shadow tables come into
    existence with the `CREATE VIRTUAL TABLE` statement rather than from a
    `CREATE TABLE` of their own.
    """
    virtual = [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND sql LIKE 'CREATE VIRTUAL TABLE%'"
        )
    ]

    derived = set()
    for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"):
        name = row["name"]
        if any(name == table or name.startswith(f"{table}_") for table in virtual):
            derived.add(name)
    return derived


def rebuild_search(conn: sqlite3.Connection) -> None:
    """Repopulate the FTS index from the tables it indexes.

    The rebuild runs through the sync triggers rather than repeating their
    expressions here — a no-op update fires `search_<table>_update`, which is by
    definition the right answer. Duplicating the trigger bodies in Python would
    be a second definition of what "indexed" means, and the two would drift.
    """
    conn.execute("DELETE FROM search")
    for table in KINDS:
        conn.execute(f'UPDATE "{table}" SET id = id')


def dump(conn: sqlite3.Connection) -> Iterator[str]:
    """The database as SQL, one statement per line-group, restorable as-is."""
    objects = conn.execute(
        "SELECT type, name, sql FROM sqlite_master"
        " WHERE name NOT LIKE 'sqlite_%' ORDER BY rowid"
    ).fetchall()
    derived = _derived_tables(conn)

    yield "BEGIN TRANSACTION;"
    # iterdump drops this, and losing it means a restored file cannot tell the
    # Rust core which schema it is.
    yield f"PRAGMA user_version = {user_version(conn)};"

    for obj in objects:
        if obj["type"] != "table":
            continue
        if obj["name"] in derived:
            # The virtual table's own CREATE is kept; a shadow table's is not,
            # and neither one's rows are.
            if obj["sql"] and obj["sql"].startswith("CREATE VIRTUAL TABLE"):
                yield f"{obj['sql']};"
            continue
        yield f"{obj['sql']};"
        yield from _rows_of(conn, obj["name"])

    for obj in objects:
        # Indexes, views and triggers last: the data is already valid, and a
        # trigger created before the rows land would fire on all of them.
        if obj["type"] == "table" or obj["sql"] is None:
            continue
        yield f"{obj['sql']};"

    yield "COMMIT;"


def dump_text(conn: sqlite3.Connection) -> str:
    return "\n".join(dump(conn)) + "\n"


def restore(conn: sqlite3.Connection, sql: str) -> None:
    """Rebuild a database from a dump. The connection must be to an empty file."""
    conn.executescript(sql)
    rebuild_search(conn)

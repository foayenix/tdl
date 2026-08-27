"""The text dump that sits beside the database and is the thing actually committed.

The `.db` is binary and is never committed; `dump/ledger.sql` is the historical
source of truth, and any commit has to rebuild from it (BUILD.md §4).

Objects come out in **creation order**, not alphabetical order. That is the
whole reason this is not `Connection.iterdump()`: alphabetically, `constituent`
restores before `monograph` exists, which trips both the foreign keys and the
sourcing triggers' `SELECT status FROM monograph`. In creation order every
parent precedes its children, and triggers are created last — after the data
they would otherwise fire on.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from .db import user_version


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


def dump(conn: sqlite3.Connection) -> Iterator[str]:
    """The database as SQL, one statement per line-group, restorable as-is."""
    objects = conn.execute(
        "SELECT type, name, sql FROM sqlite_master"
        " WHERE name NOT LIKE 'sqlite_%' ORDER BY rowid"
    ).fetchall()

    yield "BEGIN TRANSACTION;"
    # iterdump drops this, and losing it means a restored file cannot tell the
    # Rust core which schema it is.
    yield f"PRAGMA user_version = {user_version(conn)};"

    for obj in objects:
        if obj["type"] != "table":
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

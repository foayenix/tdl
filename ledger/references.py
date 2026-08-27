"""The library — reference rows, and what happens when Crossref cannot answer."""

from __future__ import annotations

import sqlite3
from typing import Any

READ_STATES = ("queued", "reading", "read")

# What `added_from` records. `offline` marks a row that is only a DOI because
# the network did not answer; `ledger ref` on the same DOI fills it in later.
OFFLINE = "offline"
CROSSREF = "crossref"

FIELDS = ("doi", "isbn", "title", "authors", "journal", "volume", "year", "type", "access")


def by_doi(conn: sqlite3.Connection, doi: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM reference WHERE doi = ?", (doi,)).fetchone()


def is_unresolved(row: sqlite3.Row) -> bool:
    """True for a row that is still just a DOI waiting for the network."""
    return row["added_from"] == OFFLINE


def save(conn: sqlite3.Connection, fields: dict[str, Any], *, added_from: str) -> sqlite3.Row:
    """Insert a reference, or fill in one that was recorded offline.

    A row the researcher has already edited is not overwritten — only a row
    still marked `offline` is filled in, so a retry cannot clobber a title that
    was fixed by hand.
    """
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise ValueError(f"not a reference field: {', '.join(sorted(unknown))}")

    doi = fields.get("doi")
    existing = by_doi(conn, doi) if doi else None

    if existing is not None:
        if not is_unresolved(existing):
            return existing
        assignments = ", ".join(f'"{field}" = ?' for field in fields)
        conn.execute(
            f"UPDATE reference SET {assignments}, added_from = ? WHERE id = ?",
            (*fields.values(), added_from, existing["id"]),
        )
        return conn.execute(
            "SELECT * FROM reference WHERE id = ?", (existing["id"],)
        ).fetchone()

    columns = ", ".join(f'"{field}"' for field in fields)
    placeholders = ", ".join("?" for _ in fields)
    cursor = conn.execute(
        f"INSERT INTO reference ({columns}, added_from) VALUES ({placeholders}, ?)",
        (*fields.values(), added_from),
    )
    return conn.execute("SELECT * FROM reference WHERE id = ?", (cursor.lastrowid,)).fetchone()


def record_unresolved(conn: sqlite3.Connection, doi: str) -> sqlite3.Row:
    """Keep the DOI even though the network did not answer.

    Capture friction kills systems like this (BUILD.md §5). Losing the paste
    because Crossref was unreachable is worse than a row whose title is its own
    DOI for an afternoon.
    """
    existing = by_doi(conn, doi)
    if existing is not None:
        return existing
    return save(conn, {"doi": doi, "title": doi}, added_from=OFFLINE)


def cite(row: sqlite3.Row) -> str:
    """The one-line citation the record and the library show."""
    bits = [row["title"]]
    if row["journal"]:
        bits.append(row["journal"])
    if row["volume"]:
        bits.append(row["volume"])
    if row["year"]:
        bits.append(str(row["year"]))
    return " · ".join(str(bit) for bit in bits)


def counts_by_read_state(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT read_state, count(*) AS n FROM reference GROUP BY read_state"
    ).fetchall()
    found = {row["read_state"]: row["n"] for row in rows}
    return {state: found.get(state, 0) for state in READ_STATES}

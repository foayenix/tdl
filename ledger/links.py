"""The edges: references bound to records, outputs bound to plants, tags."""

from __future__ import annotations

import sqlite3

# Where in a record a reference is cited. NULL means bound but not yet placed.
SECTIONS = (
    "summary",
    "vernacular",
    "indication",
    "constituent",
    "safety",
    "preparation",
    "benefit_sharing",
)


def bind_reference(
    conn: sqlite3.Connection,
    monograph_id: int,
    reference_id: int,
    section: str | None = None,
) -> bool:
    """Bind a reference to a record. Returns False if that binding already exists."""
    if section is not None and section not in SECTIONS:
        raise ValueError(f"{section} is not a section; expected one of {', '.join(SECTIONS)}")

    cursor = conn.execute(
        "INSERT OR IGNORE INTO monograph_reference (monograph_id, reference_id, section)"
        " VALUES (?, ?, ?)",
        (monograph_id, reference_id, section),
    )
    return cursor.rowcount == 1


def bind_output(conn: sqlite3.Connection, output_id: int, monograph_id: int) -> bool:
    cursor = conn.execute(
        "INSERT OR IGNORE INTO output_monograph (output_id, monograph_id) VALUES (?, ?)",
        (output_id, monograph_id),
    )
    return cursor.rowcount == 1


def tag(conn: sqlite3.Connection, reference_id: int, name: str) -> bool:
    name = name.strip()
    if not name:
        raise ValueError("a tag needs a name")
    cursor = conn.execute(
        "INSERT OR IGNORE INTO reference_tag (reference_id, tag) VALUES (?, ?)",
        (reference_id, name),
    )
    return cursor.rowcount == 1


def references_bound_to(conn: sqlite3.Connection, monograph_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT r.*, mr.section FROM reference r"
        " JOIN monograph_reference mr ON mr.reference_id = r.id"
        " WHERE mr.monograph_id = ? ORDER BY r.id",
        (monograph_id,),
    ).fetchall()


def never_published_on(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """The gap query. Permanently visible in the corpus footer (BUILD.md §4)."""
    return conn.execute(
        "SELECT m.id, m.accepted_name, m.status FROM monograph m"
        " LEFT JOIN output_monograph om ON om.monograph_id = m.id"
        " WHERE om.output_id IS NULL AND m.status IN ('sourced', 'reviewed')"
        " ORDER BY m.first_written"
    ).fetchall()


def cited_by_nothing(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """References that exist in the library but are bound to no record."""
    return conn.execute(
        "SELECT r.id, r.title FROM reference r"
        " LEFT JOIN monograph_reference mr ON mr.reference_id = r.id"
        " WHERE mr.monograph_id IS NULL ORDER BY r.id"
    ).fetchall()

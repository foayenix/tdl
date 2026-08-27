"""Claim rows — vernaculars, indications, constituents, safety findings.

Every one of them carries a source, and a row without one is the rule the
whole record is built around (DESIGN.md §6).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# Evidence, weakest to strongest. Do not rename these values (BUILD.md §4).
# They display as E1–E6; a monograph's headline evidence is the maximum across
# its indications.
EVIDENCE = (
    "traditional_only",
    "in_vitro",
    "in_vivo",
    "human_uncontrolled",
    "rct",
    "meta_analysis",
)

EVIDENCE_CODE = {level: f"E{n}" for n, level in enumerate(EVIDENCE, start=1)}

# Six levels on a four-step ramp — the eye reads four bands of confidence, not
# six, and the code sits beside the colour so the exact level stays
# recoverable (DESIGN.md §5).
EVIDENCE_RAMP = {
    "traditional_only": 0,
    "in_vitro": 1,
    "in_vivo": 1,
    "human_uncontrolled": 2,
    "rct": 3,
    "meta_analysis": 3,
}

SEVERITY = ("critical", "caution", "note")

# table -> the columns that are the claim itself, in the order the record shows
# them (DESIGN.md §8, artboard 05).
CLAIM_TABLES = {
    "vernacular": ("name", "language", "region"),
    "indication": ("condition", "tradition", "region", "evidence"),
    "constituent": ("compound", "class", "inchikey"),
    "safety": ("kind", "finding", "severity"),
}


@dataclass(frozen=True)
class Source:
    """Where a claim came from: a reference, free text, or nothing yet."""

    reference_id: int | None = None
    note: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.reference_id is None and not (self.note or "").strip()

    def __str__(self) -> str:
        if self.reference_id is not None:
            return f"R{self.reference_id}"
        return (self.note or "").strip() or "⚠ source needed"


def evidence_code(level: str) -> str:
    return EVIDENCE_CODE[level]


def add(
    conn: sqlite3.Connection,
    table: str,
    monograph_id: int,
    *,
    source: Source | None = None,
    **fields: object,
) -> int:
    """Add one claim row. Returns its id."""
    if table not in CLAIM_TABLES:
        raise ValueError(f"{table} is not a claim table")

    unknown = set(fields) - set(CLAIM_TABLES[table])
    if unknown:
        raise ValueError(f"not a {table} field: {', '.join(sorted(unknown))}")

    source = source or Source()
    columns = ["monograph_id", *fields, "source_reference_id", "source_note"]
    placeholders = ", ".join("?" for _ in columns)
    quoted = ", ".join(f'"{column}"' for column in columns)

    cursor = conn.execute(
        f"INSERT INTO {table} ({quoted}) VALUES ({placeholders})",
        (monograph_id, *fields.values(), source.reference_id, source.note),
    )
    return int(cursor.lastrowid)


def set_source(conn: sqlite3.Connection, table: str, claim_id: int, source: Source) -> None:
    if table not in CLAIM_TABLES:
        raise ValueError(f"{table} is not a claim table")
    conn.execute(
        f"UPDATE {table} SET source_reference_id = ?, source_note = ? WHERE id = ?",
        (source.reference_id, source.note, claim_id),
    )


def unsourced_count(conn: sqlite3.Connection, monograph_id: int) -> int:
    """How many rows of this record read `⚠ source needed`."""
    return int(
        conn.execute(
            "SELECT count(*) FROM unsourced_claim WHERE monograph_id = ?", (monograph_id,)
        ).fetchone()[0]
    )


def unsourced_by_table(conn: sqlite3.Connection, monograph_id: int) -> dict[str, int]:
    """The per-section counts that sit in the section headers, in `secondary`."""
    rows = conn.execute(
        "SELECT claim_table, count(*) AS n FROM unsourced_claim"
        " WHERE monograph_id = ? GROUP BY claim_table",
        (monograph_id,),
    ).fetchall()
    found = {row["claim_table"]: row["n"] for row in rows}
    return {table: found.get(table, 0) for table in CLAIM_TABLES}


def headline_evidence(conn: sqlite3.Connection, monograph_id: int) -> str | None:
    """The maximum evidence across a record's indications, or None if it has none."""
    levels = [
        row["evidence"]
        for row in conn.execute(
            "SELECT evidence FROM indication WHERE monograph_id = ?", (monograph_id,)
        )
    ]
    if not levels:
        return None
    return max(levels, key=EVIDENCE.index)

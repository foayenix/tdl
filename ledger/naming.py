"""Applying a GBIF match to a record, and the review queue of what would not resolve.

Invariant 2 lives here: never let an unresolved name into
`monograph.accepted_name`. Below the threshold the record stays `skeleton` and
enters the review queue.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .gbif import CONFIDENCE_THRESHOLD, Match


@dataclass(frozen=True)
class Resolution:
    monograph_id: int
    name: str
    accepted: bool
    reason: str
    match: Match | None = None
    candidates: list[Match] = field(default_factory=list)

    @property
    def confidence(self) -> float | None:
        return None if self.match is None else self.match.confidence


def queue(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Records whose name has never resolved: artboard 08's `queue 3 of 7`.

    A skeleton with no GBIF key is exactly a name nobody has confirmed. That is
    why there is no separate queue table.
    """
    return conn.execute(
        "SELECT id, accepted_name, gbif_confidence, last_touched FROM monograph"
        " WHERE status = 'skeleton' AND gbif_key IS NULL"
        " ORDER BY first_written, id"
    ).fetchall()


def _apply(conn: sqlite3.Connection, monograph_id: int, best: Match) -> None:
    """Write a match that cleared the threshold onto the record.

    Family and authority only fill blanks — a value the researcher typed is not
    overwritten by a lookup.
    """
    conn.execute(
        "UPDATE monograph SET"
        " accepted_name = ?,"
        " gbif_key = ?,"
        " gbif_confidence = ?,"
        " family = coalesce(nullif(trim(coalesce(family, '')), ''), ?),"
        " authority = coalesce(nullif(trim(coalesce(authority, '')), ''), ?),"
        " last_touched = datetime('now')"
        " WHERE id = ?",
        (
            best.canonical_name,
            best.key,
            best.confidence,
            best.family,
            best.authority,
            monograph_id,
        ),
    )


def _record_refusal(conn: sqlite3.Connection, monograph_id: int, confidence: float) -> None:
    """Note how close it got, and nothing else.

    `accepted_name` is not touched — that is the invariant. `gbif_key` stays
    NULL, which is what keeps the record in the queue. `last_touched` is the
    `checked …` stamp artboard 08 state 4 shows.
    """
    conn.execute(
        "UPDATE monograph SET gbif_confidence = ?, last_touched = datetime('now')"
        " WHERE id = ?",
        (confidence, monograph_id),
    )


def resolve(
    conn: sqlite3.Connection,
    monograph_id: int,
    best: Match,
    candidates: list[Match] | None = None,
    *,
    threshold: float = CONFIDENCE_THRESHOLD,
) -> Resolution:
    """Apply a match, or refuse it and leave the record in the queue."""
    row = conn.execute(
        "SELECT accepted_name FROM monograph WHERE id = ?", (monograph_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"no monograph {monograph_id}")

    name = row["accepted_name"] or ""
    candidates = candidates or []

    if not best.is_a_match:
        _record_refusal(conn, monograph_id, best.confidence)
        return Resolution(
            monograph_id, name, False, "GBIF returned no match", best, candidates
        )

    if not best.clears(threshold):
        _record_refusal(conn, monograph_id, best.confidence)
        return Resolution(
            monograph_id,
            name,
            False,
            f"below the {threshold:.2f} threshold",
            best,
            candidates,
        )

    _apply(conn, monograph_id, best)
    return Resolution(monograph_id, name, True, "resolved", best, candidates)


def accept(conn: sqlite3.Connection, monograph_id: int, best: Match) -> Resolution:
    """Take a candidate the researcher chose, whatever its score.

    Artboard 08 state 4's `Accept top match`. A person deciding is not the
    machine guessing, which is what invariant 2 guards against.
    """
    if not best.is_a_match:
        raise ValueError("there is no match to accept")

    _apply(conn, monograph_id, best)
    row = conn.execute(
        "SELECT accepted_name FROM monograph WHERE id = ?", (monograph_id,)
    ).fetchone()
    return Resolution(monograph_id, row["accepted_name"], True, "accepted by hand", best)

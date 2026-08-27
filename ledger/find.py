"""`find` — FTS5 across the corpus, the library and the wall."""

from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass

# What `search.kind` can hold, and how a hit is attributed back to a plant.
CLAIM_KINDS = ("vernacular", "indication", "constituent", "safety")
KINDS = ("monograph", "reference", "output", *CLAIM_KINDS)

_TOKEN = re.compile(r"[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class Hit:
    kind: str
    row_id: int
    monograph_id: int | None
    title: str
    snippet: str
    rank: float


@dataclass(frozen=True)
class Results:
    query: str
    hits: list[Hit]
    searched: dict[str, int]
    milliseconds: float

    def of(self, kind: str) -> list[Hit]:
        return [hit for hit in self.hits if hit.kind == kind]

    @property
    def monograph_ids(self) -> list[int]:
        """Plants the query touched, whether by name or through a claim row."""
        seen: list[int] = []
        for hit in self.hits:
            if hit.monograph_id is not None and hit.monograph_id not in seen:
                seen.append(hit.monograph_id)
        return seen


def to_match(query: str) -> str:
    """Turn what someone typed into an FTS5 MATCH expression.

    Every token is quoted, so a hyphen, a colon in a DOI or a stray quote is
    searched for rather than parsed as syntax. Tokens are ANDed: `antimalarial
    bark` means both words.
    """
    tokens = _TOKEN.findall(query or "")
    if not tokens:
        raise ValueError("nothing to search for")
    return " AND ".join(f'"{token}"' for token in tokens)


def corpus_size(conn: sqlite3.Connection) -> dict[str, int]:
    """What was searched — the figures artboard 08 state 6 reports."""
    return {
        "monographs": conn.execute("SELECT count(*) FROM monograph").fetchone()[0],
        "references": conn.execute("SELECT count(*) FROM reference").fetchone()[0],
        "outputs": conn.execute("SELECT count(*) FROM output").fetchone()[0],
    }


def find(conn: sqlite3.Connection, query: str, *, limit: int = 50) -> Results:
    expression = to_match(query)
    started = time.perf_counter()

    rows = conn.execute(
        "SELECT kind, row_id, monograph_id, title,"
        " snippet(search, 4, '', '', '…', 12) AS snippet, rank"
        " FROM search WHERE search MATCH ? ORDER BY rank LIMIT ?",
        (expression, limit),
    ).fetchall()

    elapsed = (time.perf_counter() - started) * 1000.0

    hits = [
        Hit(
            kind=row["kind"],
            row_id=row["row_id"],
            monograph_id=row["monograph_id"],
            title=row["title"],
            snippet=row["snippet"],
            rank=row["rank"],
        )
        for row in rows
    ]

    return Results(query, hits, corpus_size(conn), elapsed)


def nearest(conn: sqlite3.Connection, query: str) -> tuple[str, int] | None:
    """The nearest accepted name and its edit distance.

    Artboard 08 state 6 shows this beside a query that found nothing, so the
    answer to "did I spell it wrong" is on screen rather than in your head.
    """
    names = [
        row[0]
        for row in conn.execute(
            "SELECT accepted_name FROM monograph WHERE accepted_name IS NOT NULL"
        )
    ]
    if not names:
        return None

    best = min(names, key=lambda name: _distance(query.lower(), name.lower()))
    return best, _distance(query.lower(), best.lower())


def _distance(a: str, b: str) -> int:
    """Levenshtein, two rows at a time."""
    if len(a) < len(b):
        a, b = b, a

    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, start=1):
        current = [i]
        for j, right in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (left != right),
                )
            )
        previous = current

    return previous[-1]

"""Outputs — what was published, and the day it was deposited against."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

# paper · talk · long-form · release · note (DESIGN.md §5, and the counts
# across the top of artboard 04).
KINDS = ("paper", "talk", "long-form", "release", "note")


@dataclass(frozen=True)
class Output:
    id: int
    kind: str
    title: str
    venue: str | None
    date: str
    url: str | None
    entry_id: int | None


def entry_for(conn: sqlite3.Connection, day: str) -> tuple[int, bool]:
    """The id of `day`'s entry, opening the day if it is not open yet.

    Depositing an output is work, so it opens the day it lands on rather than
    hanging off nothing.
    """
    row = conn.execute("SELECT id FROM entry WHERE date = ?", (day,)).fetchone()
    if row is not None:
        return row["id"], False

    cursor = conn.execute("INSERT INTO entry (date) VALUES (?)", (day,))
    return cursor.lastrowid, True


def record(
    conn: sqlite3.Connection,
    kind: str,
    title: str,
    *,
    venue: str | None = None,
    on: date | str | None = None,
    deposited: date | str | None = None,
    url: str | None = None,
) -> tuple[Output, bool]:
    """Record an output. Returns it and whether recording it opened a day.

    `on` is when the output went out; `deposited` is the day it is logged
    against, which is today — artboard 02 says "deposit — attach to today", and
    a paper published in June does not retroactively make June a day worked.
    """
    if kind not in KINDS:
        raise ValueError(f"{kind} is not an output kind; expected one of {', '.join(KINDS)}")

    title = title.strip()
    if not title:
        raise ValueError("an output needs a title")

    on = on or date.today()
    day = on if isinstance(on, str) else on.isoformat()

    deposited = deposited or date.today()
    deposited_day = deposited if isinstance(deposited, str) else deposited.isoformat()

    entry_id, opened = entry_for(conn, deposited_day)
    cursor = conn.execute(
        "INSERT INTO output (kind, title, venue, date, url, entry_id)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (kind, title, venue, day, url, entry_id),
    )
    row = conn.execute("SELECT * FROM output WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return Output(**{field: row[field] for field in Output.__dataclass_fields__}), opened


def counts_by_kind(conn: sqlite3.Connection) -> dict[str, int]:
    """The counts across the top of The Wall, in ramp order, zeroes included."""
    rows = conn.execute("SELECT kind, count(*) AS n FROM output GROUP BY kind").fetchall()
    found = {row["kind"]: row["n"] for row in rows}
    return {kind: found.get(kind, 0) for kind in KINDS}


def total(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT count(*) FROM output").fetchone()[0])

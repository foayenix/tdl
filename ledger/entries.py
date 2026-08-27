"""The daily entry — logging a day's work and counting the streak."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta

# The floor is 20 minutes. A floor day is a success and the interface must
# never render one as a shortfall (DESIGN.md §8, artboard 02).
FLOOR_MINUTES = 20

# The streak query in BUILD.md §4, verbatim: the length of the most recent
# unbroken run of entries. Whether that run is still live is decided above it.
_RUN_LENGTH = """
SELECT count(*) FROM entry
WHERE date >= (SELECT max(date) FROM entry
               WHERE date NOT IN (SELECT date(date,'+1 day') FROM entry))
"""


@dataclass(frozen=True)
class Entry:
    date: str
    minutes: int
    note: str
    floor_day: bool
    created: bool  # True when this call opened the day, False when it added to it

    @property
    def met_floor(self) -> bool:
        return self.minutes >= FLOOR_MINUTES


def run_length(conn: sqlite3.Connection) -> int:
    """How many days the most recent unbroken run of entries covers."""
    return int(conn.execute(_RUN_LENGTH).fetchone()[0])


def last_entry_date(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT max(date) FROM entry").fetchone()[0]


def current_streak(conn: sqlite3.Connection, today: date | None = None) -> int:
    """The streak as the interface reports it: 0 once the run has been broken.

    A run counts as live while it reaches today or yesterday — an unlogged
    morning is not a broken streak. Artboard 08 state 5 is the specification
    for the broken case: three days without an entry reads 0.
    """
    last = last_entry_date(conn)
    if last is None:
        return 0

    today = today or date.today()
    if last < (today - timedelta(days=1)).isoformat():
        return 0

    return run_length(conn)


def log(
    conn: sqlite3.Connection,
    *,
    on: date | str | None = None,
    minutes: int = 0,
    note: str | None = None,
    floor_day: bool | None = None,
) -> Entry:
    """Open the day, or add a work block to a day already open.

    Minutes accumulate and notes append — `ledger log` records a block of work,
    and a day usually holds more than one.
    """
    if minutes < 0:
        raise ValueError("minutes cannot be negative")

    on = on or date.today()
    day = on if isinstance(on, str) else on.isoformat()

    existing = conn.execute(
        "SELECT minutes, note, floor_day FROM entry WHERE date = ?", (day,)
    ).fetchone()

    if existing is None:
        conn.execute(
            "INSERT INTO entry (date, minutes, note, floor_day) VALUES (?, ?, ?, ?)",
            (day, minutes, note or "", int(bool(floor_day))),
        )
        return Entry(day, minutes, note or "", bool(floor_day), created=True)

    total = existing["minutes"] + minutes
    merged = existing["note"]
    if note:
        merged = f"{merged}\n{note}" if merged else note
    flag = existing["floor_day"] if floor_day is None else int(bool(floor_day))

    conn.execute(
        "UPDATE entry SET minutes = ?, note = ?, floor_day = ?,"
        " updated_at = datetime('now') WHERE date = ?",
        (total, merged, flag, day),
    )
    return Entry(day, total, merged, bool(flag), created=False)

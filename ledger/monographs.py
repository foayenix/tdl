"""The monograph record — creating a skeleton, editing it, moving its status."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# skeleton → drafted → sourced → reviewed. Do not rename these (BUILD.md §4).
STATUSES = ("skeleton", "drafted", "sourced", "reviewed")

# Header fields the $EDITOR template carries, in the order it writes them.
HEADER_FIELDS = ("authority", "family", "part", "habitat_note")

# Prose sections, in the order the record shows them (DESIGN.md §8, artboard 05).
PROSE_SECTIONS = ("summary", "preparation")

_HEADER_LABELS = {"habitat_note": "habitat"}
_HEADER_KEYS = {label: field for field, label in _HEADER_LABELS.items()}


@dataclass(frozen=True)
class Monograph:
    id: int
    accepted_name: str | None
    authority: str | None
    family: str | None
    part: str | None
    habitat_note: str | None
    status: str
    summary: str | None
    preparation: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Monograph:
        return cls(**{field: row[field] for field in cls.__dataclass_fields__})


def _fetch(conn: sqlite3.Connection, monograph_id: int) -> Monograph:
    row = conn.execute("SELECT * FROM monograph WHERE id = ?", (monograph_id,)).fetchone()
    return Monograph.from_row(row)


def by_name(conn: sqlite3.Connection, name: str) -> Monograph | None:
    row = conn.execute(
        "SELECT * FROM monograph WHERE accepted_name = ?", (name,)
    ).fetchone()
    return None if row is None else Monograph.from_row(row)


def create(conn: sqlite3.Connection, name: str, **fields: str | None) -> Monograph:
    """Open a skeleton for a name typed by hand.

    A hand-entered name is a resolved name — invariant 2 guards against a
    *below-threshold GBIF match* being written here, not against the
    researcher's own typing. `wfo_id` and `gbif_key` stay NULL until session
    09's resolver fills them, which is what puts this record in the queue.
    """
    name = name.strip()
    if not name:
        raise ValueError("a monograph needs a name")

    unknown = set(fields) - set(HEADER_FIELDS)
    if unknown:
        raise ValueError(f"not a monograph field: {', '.join(sorted(unknown))}")

    columns = ["accepted_name", *fields]
    placeholders = ", ".join("?" for _ in columns)
    cursor = conn.execute(
        f"INSERT INTO monograph ({', '.join(columns)}) VALUES ({placeholders})",
        (name, *fields.values()),
    )
    return _fetch(conn, cursor.lastrowid)


def touch(conn: sqlite3.Connection, monograph_id: int) -> None:
    conn.execute(
        "UPDATE monograph SET last_touched = datetime('now') WHERE id = ?", (monograph_id,)
    )


def set_status(conn: sqlite3.Connection, monograph_id: int, status: str) -> Monograph:
    """Move a record along the status ramp.

    Reaching `reviewed` is additionally guarded by the sourcing invariant, which
    lives in the database as a trigger from session 06 — not here.
    """
    if status not in STATUSES:
        raise ValueError(f"{status} is not a status; expected one of {', '.join(STATUSES)}")

    conn.execute(
        "UPDATE monograph SET status = ?, last_touched = datetime('now') WHERE id = ?",
        (status, monograph_id),
    )
    return _fetch(conn, monograph_id)


def update(conn: sqlite3.Connection, monograph_id: int, fields: dict[str, str | None]) -> Monograph:
    """Write edited fields back. Rewriting the summary stamps its own date."""
    allowed = set(HEADER_FIELDS) | set(PROSE_SECTIONS)
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"not a monograph field: {', '.join(sorted(unknown))}")

    before = _fetch(conn, monograph_id)
    assignments = [f"{field} = ?" for field in fields]
    values: list[str | None] = list(fields.values())

    if "summary" in fields and (fields["summary"] or None) != (before.summary or None):
        assignments.append("summary_rewritten_at = date('now')")

    assignments.append("last_touched = datetime('now')")
    conn.execute(
        f"UPDATE monograph SET {', '.join(assignments)} WHERE id = ?",
        (*values, monograph_id),
    )
    return _fetch(conn, monograph_id)


def render_template(monograph: Monograph) -> str:
    """The text handed to `$EDITOR`."""
    lines = [f"# {monograph.accepted_name or ''}"]
    for field in HEADER_FIELDS:
        label = _HEADER_LABELS.get(field, field)
        lines.append(f"{label}: {getattr(monograph, field) or ''}")

    for section in PROSE_SECTIONS:
        lines.extend(["", f"## {section}", "", (getattr(monograph, section) or "").rstrip()])

    lines.extend(
        [
            "",
            "# Lines above are the record. `# name` is fixed — rename with a",
            "# resolver, not by hand. Leave a field blank to clear it.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_template(text: str) -> dict[str, str | None]:
    """Read an edited template back into fields. Unknown keys are an error."""
    fields: dict[str, str | None] = {}
    section: str | None = None
    prose: dict[str, list[str]] = {name: [] for name in PROSE_SECTIONS}

    for raw in text.splitlines():
        line = raw.rstrip()

        if line.startswith("## "):
            name = line[3:].strip().lower()
            if name not in PROSE_SECTIONS:
                raise ValueError(f"{name} is not a section of the record")
            section = name
            continue

        if line.startswith("#"):
            continue  # the title line and the trailing guidance

        if section is not None:
            prose[section].append(line)
            continue

        if not line.strip():
            continue

        if ":" not in line:
            raise ValueError(f"cannot read {line!r}; expected `field: value`")
        label, _, value = line.partition(":")
        label = label.strip().lower()
        field = _HEADER_KEYS.get(label, label)
        if field not in HEADER_FIELDS:
            raise ValueError(f"{label} is not a field of the record")
        fields[field] = value.strip() or None

    for name, body in prose.items():
        fields[name] = "\n".join(body).strip() or None

    return fields

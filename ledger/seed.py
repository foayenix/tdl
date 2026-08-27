"""`ledger seed` — open skeletons in bulk from a CSV of plants you already know.

Not a general importer: it reads a `name` column and four optional ones, and
that is the whole contract. Anything else is a throwaway script, run once and
deleted (BUILD.md §5).
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .monographs import by_name, create

COLUMNS = ("name", "authority", "family", "part", "habitat_note")

# What a column may be called in the file. `habitat` is the header the $EDITOR
# template uses, so a seed file written from one reads back.
ALIASES = {
    "name": "name",
    "accepted_name": "name",
    "binomial": "name",
    "species": "name",
    "authority": "authority",
    "author": "authority",
    "family": "family",
    "part": "part",
    "part_used": "part",
    "habitat": "habitat_note",
    "habitat_note": "habitat_note",
}


@dataclass
class SeedReport:
    opened: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)

    @property
    def read(self) -> int:
        return len(self.opened) + len(self.already_present) + len(self.skipped)


def read_rows(path: Path | str) -> list[dict[str, str]]:
    """Read the file into `name`-keyed rows, refusing a file with no name column."""
    with Path(path).expanduser().open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("the file is empty")

        mapping = {}
        for header in reader.fieldnames:
            key = ALIASES.get((header or "").strip().lower())
            if key is not None:
                mapping[header] = key

        if "name" not in mapping.values():
            known = ", ".join(sorted(set(ALIASES)))
            raise ValueError(f"no name column in {path}; expected one of: {known}")

        rows = []
        for raw in reader:
            row = {}
            for header, key in mapping.items():
                value = (raw.get(header) or "").strip()
                if value:
                    row[key] = value
            rows.append(row)

    return rows


def seed(conn: sqlite3.Connection, path: Path | str, *, dry_run: bool = False) -> SeedReport:
    """Open a skeleton for every named plant that does not already have one."""
    report = SeedReport()

    for line_number, row in enumerate(read_rows(path), start=2):  # row 1 is the header
        name = row.pop("name", "")
        if not name:
            report.skipped.append((line_number, "no name"))
            continue

        if by_name(conn, name) is not None:
            report.already_present.append(name)
            continue

        if not dry_run:
            create(conn, name, **row)
        report.opened.append(name)

    return report

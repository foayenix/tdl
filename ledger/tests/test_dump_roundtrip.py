"""§7 test 1 — dump round-trip. Never delete this test.

The .db is binary and is never committed; the text dump beside it is the
historical source of truth (BUILD.md §4). That only holds if a dump restores
into a file identical to the one it came from.

The dump is `ledger.dump`, not the sqlite3 CLI, so the test runs on a machine
that has Python and nothing else. `just dump` arrives in session 11 and must be
checked against this same assertion.
"""

from __future__ import annotations

from ledger.db import connect, user_version
from ledger.dump import dump_text, restore
from ledger.migrate import migrate


def table_names(conn) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def rows_of(conn, table) -> list[tuple]:
    return [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]


def unsourced(conn) -> list[tuple]:
    return [
        tuple(row)
        for row in conn.execute(
            "SELECT claim_table, claim_id, monograph_id FROM unsourced_claim"
            " ORDER BY claim_table, claim_id"
        )
    ]


def schema_of(conn) -> list[tuple]:
    return [
        tuple(row)
        for row in conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master"
            " WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        )
    ]


def populate(conn) -> None:
    """One row in every table the migrations create, with the links wired up."""
    conn.execute(
        "INSERT INTO entry (date, minutes, note, floor_day) VALUES (?, ?, ?, ?)",
        ("2026-08-24", 96, "Reworked the indication list.", 0),
    )
    entry_id = conn.execute("SELECT id FROM entry").fetchone()["id"]
    conn.execute(
        "INSERT INTO monograph (accepted_name, authority, family, part, status,"
        " wfo_id, gbif_key, gbif_confidence, first_written)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "Khaya senegalensis",
            "(Desr.) A.Juss.",
            "Meliaceae",
            "stem bark",
            "sourced",
            "wfo-0000651773",
            3190368,
            0.98,
            "2024-03-11",
        ),
    )
    conn.execute(
        "INSERT INTO reference (doi, title, journal, year, read_state)"
        " VALUES (?, ?, ?, ?, ?)",
        (
            "10.1016/j.jep.2019.112202",
            "Journal of Ethnopharmacology article",
            "J Ethnopharmacol",
            2019,
            "read",
        ),
    )
    conn.execute(
        "INSERT INTO output (kind, title, venue, date, entry_id) VALUES (?, ?, ?, ?, ?)",
        ("note", "Evidence grading for traditional-use claims", None, "2026-08-24", entry_id),
    )

    monograph_id = conn.execute("SELECT id FROM monograph").fetchone()["id"]
    reference_id = conn.execute("SELECT id FROM reference").fetchone()["id"]

    conn.execute(
        "INSERT INTO vernacular (monograph_id, name, language, region, source_reference_id)"
        " VALUES (?, ?, ?, ?, ?)",
        (monograph_id, "kuka", "Hausa", "northern Nigeria", reference_id),
    )
    conn.execute(
        "INSERT INTO indication (monograph_id, condition, tradition, region, evidence,"
        " source_note) VALUES (?, ?, ?, ?, ?, ?)",
        (monograph_id, "malarial fever", "Hausa", "Sahel", "rct", "field notes 2025-11"),
    )
    # Left deliberately unsourced — the dump has to carry the row that holds the
    # record back from `reviewed`, NULLs and all.
    conn.execute(
        "INSERT INTO constituent (monograph_id, compound, class) VALUES (?, ?, ?)",
        (monograph_id, "khayanthone", "limonoid"),
    )
    conn.execute(
        "INSERT INTO safety (monograph_id, kind, finding, severity, source_reference_id)"
        " VALUES (?, ?, ?, ?, ?)",
        (monograph_id, "interaction", "additive hypotension", "caution", reference_id),
    )
    conn.execute(
        "INSERT INTO benefit_sharing (monograph_id, narrative, agreement_ref, expires,"
        " consent_recorded_at) VALUES (?, ?, ?, ?, ?)",
        (
            monograph_id,
            "Recorded with consent in 2025 under a Nagoya-aligned agreement.",
            "MTA-2025-014",
            "2028-06",
            "2025-11-14",
        ),
    )


def test_dump_restores_into_an_identical_database(tmp_path):
    original_path = tmp_path / "ledger.sqlite"
    restored_path = tmp_path / "restored.sqlite"

    original = connect(original_path)
    try:
        migrate(original)
        populate(original)
        dump = dump_text(original)

        expected_version = user_version(original)
        expected_schema = schema_of(original)
        expected_tables = table_names(original)
        expected_rows = {name: rows_of(original, name) for name in expected_tables}
        expected_unsourced = unsourced(original)
    finally:
        original.close()

    restored = connect(restored_path)
    try:
        restore(restored, dump)

        # Nothing is stamped by hand here: the dump carries user_version itself,
        # and the restore runs with foreign keys on and the triggers in place.
        assert restored.execute("PRAGMA foreign_key_check").fetchall() == []

        assert table_names(restored) == expected_tables
        assert schema_of(restored) == expected_schema
        assert user_version(restored) == expected_version

        for name in expected_tables:
            assert rows_of(restored, name) == expected_rows[name], name

        assert expected_rows["entry"], "the fixture wrote no rows — the test proves nothing"
        assert all(expected_rows[name] for name in expected_tables), (
            "a table was left empty; the round trip does not prove anything about it"
        )
        # The unsourced constituent has to come back unsourced — a source_note
        # restored as '' instead of NULL would silently mend the row.
        assert unsourced(restored) == expected_unsourced
        assert expected_unsourced, "no unsourced row in the fixture; that case is untested"
    finally:
        restored.close()


def test_the_dump_is_text_and_carries_every_table(tmp_path):
    conn = connect(tmp_path / "ledger.sqlite")
    try:
        migrate(conn)
        populate(conn)
        dump = dump_text(conn)
    finally:
        conn.close()

    for table in (
        "entry", "monograph", "reference", "output",
        "vernacular", "indication", "constituent", "safety", "benefit_sharing",
    ):
        assert f"CREATE TABLE {table}" in dump
    assert "Khaya senegalensis" in dump
    assert "MTA-2025-014" in dump

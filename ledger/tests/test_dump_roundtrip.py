"""§7 test 1 — dump round-trip. Never delete this test.

The .db is binary and is never committed; the text dump beside it is the
historical source of truth (BUILD.md §4). That only holds if a dump restores
into a file identical to the one it came from.

The dump is produced with `Connection.iterdump()` rather than the sqlite3 CLI
so the test runs on a machine that has Python and nothing else. `just dump`
arrives in session 11 and must be checked against this same assertion.
"""

from __future__ import annotations

from ledger.db import connect, user_version
from ledger.migrate import migrate


def dump_sql(conn) -> str:
    return "\n".join(conn.iterdump())


def table_names(conn) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row["name"] for row in rows]


def rows_of(conn, table) -> list[tuple]:
    return [tuple(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid")]


def schema_of(conn) -> list[tuple]:
    return [
        tuple(row)
        for row in conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master"
            " WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        )
    ]


def populate(conn) -> None:
    """One row in every table 000_init creates, with the links wired up."""
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


def test_dump_restores_into_an_identical_database(tmp_path):
    original_path = tmp_path / "ledger.sqlite"
    restored_path = tmp_path / "restored.sqlite"

    original = connect(original_path)
    try:
        migrate(original)
        populate(original)
        dump = dump_sql(original)

        expected_version = user_version(original)
        expected_schema = schema_of(original)
        expected_tables = table_names(original)
        expected_rows = {name: rows_of(original, name) for name in expected_tables}
    finally:
        original.close()

    restored = connect(restored_path)
    try:
        restored.executescript(dump)
        # iterdump does not carry pragmas; the version is stamped alongside the
        # dump the same way `just dump` will have to (session 11).
        restored.execute(f"PRAGMA user_version = {expected_version}")

        assert table_names(restored) == expected_tables
        assert schema_of(restored) == expected_schema
        assert user_version(restored) == expected_version

        for name in expected_tables:
            assert rows_of(restored, name) == expected_rows[name], name

        assert expected_rows["entry"], "the fixture wrote no rows — the test proves nothing"
    finally:
        restored.close()


def test_the_dump_is_text_and_carries_every_table(tmp_path):
    conn = connect(tmp_path / "ledger.sqlite")
    try:
        migrate(conn)
        populate(conn)
        dump = dump_sql(conn)
    finally:
        conn.close()

    for table in ("entry", "monograph", "reference", "output"):
        assert f"CREATE TABLE {table}" in dump
    assert "Khaya senegalensis" in dump

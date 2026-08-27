"""The migration ladder — §7 test 3, as far as the migrations that exist.

The ladder assertions are written against `discover()` rather than a hard-coded
list, so sessions 06, 07 and 10 extend this test by adding their .sql file.
"""

from __future__ import annotations

import pytest

from ledger.db import connect, user_version
from ledger.migrate import SCHEMA_DIR, discover, migrate, pending


def table_names(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return {row["name"] for row in rows}


def test_schema_dir_holds_a_contiguous_ladder_from_000():
    versions = [m.version for m in discover()]
    assert versions == list(range(1, len(versions) + 1))
    assert versions, "no migrations found in schema/"


def test_a_fresh_database_starts_at_version_zero(conn):
    assert user_version(conn) == 0
    assert pending(conn) == discover()


def test_each_migration_stamps_its_own_version(conn):
    from ledger.migrate import apply

    for migration in discover():
        apply(conn, migration)
        assert user_version(conn) == migration.version


def test_migrate_applies_everything_and_is_idempotent(conn):
    applied = migrate(conn)
    assert [m.version for m in applied] == [m.version for m in discover()]
    assert user_version(conn) == discover()[-1].version

    assert migrate(conn) == []
    assert user_version(conn) == discover()[-1].version


def test_000_init_creates_the_four_tables(migrated):
    assert {"entry", "monograph", "reference", "output"} <= table_names(migrated)


def test_the_ladder_ends_at_the_schema_version_the_artboards_show(migrated):
    """Artboard 08's footer reads `schema v4`."""
    from ledger import SCHEMA_VERSION

    assert user_version(migrated) == SCHEMA_VERSION == 4


def test_pragmas_are_set_on_every_connection(db_path):
    conn = connect(db_path)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


def test_a_stray_filename_in_schema_is_refused(tmp_path):
    (tmp_path / "000_init.sql").write_text("CREATE TABLE t (id INTEGER);")
    (tmp_path / "notes.sql").write_text("-- not a migration")
    with pytest.raises(ValueError, match="not a migration filename"):
        discover(tmp_path)


def test_a_gap_in_the_ladder_is_refused(tmp_path):
    (tmp_path / "000_init.sql").write_text("CREATE TABLE t (id INTEGER);")
    (tmp_path / "002_links.sql").write_text("CREATE TABLE u (id INTEGER);")
    with pytest.raises(ValueError, match="contiguous ladder"):
        discover(tmp_path)


def test_the_real_schema_dir_is_where_the_package_expects_it():
    assert SCHEMA_DIR.is_dir()
    assert (SCHEMA_DIR / "000_init.sql").is_file()

"""Any commit rebuilds. BUILD.md §4: "proven by a test".

The dump beside the database is only the historical source of truth if a dump
taken at *any* point in history still restores. This walks every commit that
touched `dump/ledger.sql`, restores each one into a fresh file, and checks it.

Until there are such commits the walk has nothing to do. It says so out loud
rather than passing quietly — a test that reports success over zero cases is
how this stops being checked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ledger.db import connect, user_version
from ledger.dump import dump_text, restore
from ledger.migrate import discover

REPO = Path(__file__).resolve().parents[2]
DUMP = "dump/ledger.sql"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout


def commits_touching_the_dump() -> list[str]:
    try:
        out = git("log", "--format=%H", "--", DUMP)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    return [line for line in out.splitlines() if line]


def restore_into(path: Path, sql: str):
    conn = connect(path)
    restore(conn, sql)
    return conn


@pytest.mark.parametrize("commit", commits_touching_the_dump())
def test_the_dump_at_this_commit_still_restores(commit, tmp_path):
    sql = git("show", f"{commit}:{DUMP}")

    conn = restore_into(tmp_path / f"{commit[:8]}.sqlite", sql)
    try:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert 1 <= user_version(conn) <= discover()[-1].version

        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"entry", "monograph", "reference", "output"} <= tables
    finally:
        conn.close()


def test_there_is_a_dump_in_history_to_check():
    """Fails loudly once the habit starts and then stops."""
    if not (REPO / DUMP).exists():
        pytest.skip(
            f"no {DUMP} committed yet — the git habit (BUILD.md §4) has not started."
            " This test begins checking history the first time `just dump` runs."
        )
    assert commits_touching_the_dump(), (
        f"{DUMP} exists in the tree but no commit has ever carried it"
    )


def test_a_dump_taken_now_restores_through_the_same_path(migrated, tmp_path):
    """The mechanism the history walk relies on, proven without needing history."""
    from ledger.monographs import create

    create(migrated, "Khaya senegalensis", family="Meliaceae")
    sql = dump_text(migrated)

    conn = restore_into(tmp_path / "restored.sqlite", sql)
    try:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert user_version(conn) == discover()[-1].version
        assert (
            conn.execute("SELECT accepted_name FROM monograph").fetchone()[0]
            == "Khaya senegalensis"
        )
        # Restoring rebuilds the index, so the restored file is searchable.
        assert conn.execute("SELECT count(*) FROM search").fetchone()[0] == 1
    finally:
        conn.close()

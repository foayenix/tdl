"""`ledger dump` and `ledger restore` at the command layer."""

from __future__ import annotations

from pathlib import Path

from ledger.cli import main
from ledger.db import connect
from ledger.migrate import migrate
from ledger.monographs import create

HOOK = Path(__file__).resolve().parents[2] / ".githooks" / "pre-commit"


def a_database(path: Path) -> None:
    conn = connect(path)
    try:
        migrate(conn)
        create(conn, "Khaya senegalensis", family="Meliaceae")
    finally:
        conn.close()


def test_dump_writes_a_text_file_and_restore_reads_it(tmp_path, capsys):
    source = tmp_path / "ledger.sqlite"
    a_database(source)
    dump = tmp_path / "ledger.sql"

    assert main(["--db", str(source), "dump", "--to", str(dump)]) == 0
    assert "CREATE TABLE monograph" in dump.read_text()

    target = tmp_path / "restored.sqlite"
    assert main(["--db", str(target), "restore", "--from", str(dump)]) == 0
    assert "schema v4" in capsys.readouterr().out

    conn = connect(target)
    try:
        assert conn.execute("SELECT accepted_name FROM monograph").fetchone()[0] == (
            "Khaya senegalensis"
        )
    finally:
        conn.close()


def test_dumping_a_database_that_is_not_there_says_so(tmp_path, capsys):
    missing = tmp_path / "nothing.sqlite"
    assert main(["--db", str(missing), "dump", "--to", str(tmp_path / "out.sql")]) == 1
    assert "no database at" in capsys.readouterr().out
    assert not missing.exists()


def test_restore_refuses_to_overwrite_without_being_told_to(tmp_path, capsys):
    source = tmp_path / "ledger.sqlite"
    a_database(source)
    dump = tmp_path / "ledger.sql"
    main(["--db", str(source), "dump", "--to", str(dump)])
    capsys.readouterr()

    assert main(["--db", str(source), "restore", "--from", str(dump)]) == 1
    assert "pass --force" in capsys.readouterr().out


def test_restore_force_replaces_the_file(tmp_path):
    source = tmp_path / "ledger.sqlite"
    a_database(source)
    dump = tmp_path / "ledger.sql"
    main(["--db", str(source), "dump", "--to", str(dump)])

    conn = connect(source)
    try:
        create(conn, "Prunus africana")
    finally:
        conn.close()

    assert main(["--db", str(source), "restore", "--from", str(dump), "--force"]) == 0

    conn = connect(source)
    try:
        names = [row[0] for row in conn.execute("SELECT accepted_name FROM monograph")]
        assert names == ["Khaya senegalensis"]
    finally:
        conn.close()


def test_a_missing_dump_file_is_reported(tmp_path, capsys):
    assert main(["--db", str(tmp_path / "x.sqlite"), "restore", "--from", "nowhere.sql"]) == 2
    assert "No such file" in capsys.readouterr().out


def test_dump_to_stdout(tmp_path, capsys):
    source = tmp_path / "ledger.sqlite"
    a_database(source)

    assert main(["--db", str(source), "dump", "--to", "-"]) == 0
    assert "BEGIN TRANSACTION;" in capsys.readouterr().out


class TestTheHook:
    def test_it_exists_and_is_executable(self):
        assert HOOK.is_file()
        assert HOOK.stat().st_mode & 0o111, "the hook is not executable"

    def test_it_does_nothing_when_there_is_no_database(self, tmp_path):
        import subprocess

        result = subprocess.run(
            ["bash", str(HOOK)],
            cwd=HOOK.parents[1],
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(tmp_path),
                "LEDGER_DB": str(tmp_path / "no.sqlite"),
            },
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

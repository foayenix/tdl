"""`ledger dump` and `ledger restore` — the text file that is actually committed."""

from __future__ import annotations

import argparse
from pathlib import Path

from ..db import connect
from ..dump import dump_text, restore

DEFAULT_DUMP = Path("dump/ledger.sql")


def register(subparsers: argparse._SubParsersAction) -> None:
    out = subparsers.add_parser(
        "dump",
        help="write the database out as SQL",
        description="Write the database out as text. This file is the one committed.",
    )
    out.add_argument(
        "--to",
        dest="path",
        type=Path,
        default=DEFAULT_DUMP,
        metavar="FILE",
        help=f"where to write (default: {DEFAULT_DUMP}); - for stdout",
    )
    out.set_defaults(handler=run_dump)

    back = subparsers.add_parser(
        "restore",
        help="rebuild a database from a dump",
        description="Rebuild a database from a dump, and rebuild its search index.",
    )
    back.add_argument("--from", dest="path", type=Path, required=True, metavar="FILE")
    back.add_argument(
        "--force",
        action="store_true",
        help="overwrite the target database if it already exists",
    )
    back.set_defaults(handler=run_restore)


def run_dump(args: argparse.Namespace) -> int:
    database = Path(args.db).expanduser()
    if not database.exists():
        print(f"no database at {database}")
        return 1

    conn = connect(database)
    try:
        text = dump_text(conn)
    finally:
        conn.close()

    if str(args.path) == "-":
        print(text, end="")
        return 0

    args.path.parent.mkdir(parents=True, exist_ok=True)
    args.path.write_text(text, encoding="utf-8")

    lines = text.count("\n")
    print(f"{args.path} · {lines} lines · {len(text.encode()) / 1024:.1f} KB")
    return 0


def run_restore(args: argparse.Namespace) -> int:
    target = Path(args.db).expanduser()

    if target.exists():
        if not args.force:
            print(f"{target} already exists; pass --force to overwrite it")
            return 1
        for suffix in ("", "-wal", "-shm"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)

    try:
        sql = args.path.read_text(encoding="utf-8")
    except OSError as error:
        print(error)
        return 2

    conn = connect(target)
    try:
        restore(conn, sql)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        broken = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()

    if broken:
        print(f"restored {target}, but {len(broken)} foreign key violations remain")
        return 1

    print(f"restored {target} · schema v{version}")
    return 0

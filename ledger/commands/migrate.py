"""`ledger migrate` — bring the schema up to date and report where it landed."""

from __future__ import annotations

import argparse

from .. import SCHEMA_VERSION
from ..db import connect, user_version
from ..migrate import migrate


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "migrate",
        help="apply pending schema migrations",
        description="Apply pending schema migrations and stamp PRAGMA user_version.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        applied = migrate(conn)
        version = user_version(conn)
    finally:
        conn.close()

    for migration in applied:
        print(f"applied {migration.name} → user_version {migration.version}")

    if not applied:
        print(f"nothing to apply · schema v{version}")
    else:
        print(f"{args.db} · schema v{version}")

    if version > SCHEMA_VERSION:
        print(
            f"warning: schema v{version} is newer than the v{SCHEMA_VERSION}"
            " this build knows about",
        )

    return 0

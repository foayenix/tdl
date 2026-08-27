"""Argument parsing and subcommand dispatch for `ledger`.

Subcommands are registered one per build session. The spine is here; the
verbs arrive with the sessions that need them (BUILD.md §6).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .commands import link as link_command
from .commands import log as log_command
from .commands import migrate as migrate_command
from .commands import mono as mono_command
from .commands import ref as ref_command
from .commands import resolve as resolve_command
from .commands import seed as seed_command
from .commands import win as win_command
from .db import DEFAULT_DB_PATH


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ledger",
        description="The Deposit Ledger — daily log and materia medica corpus.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ledger {__version__}",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        metavar="PATH",
        help=f"the ledger file (default: {DEFAULT_DB_PATH})",
    )
    parser.set_defaults(handler=None)

    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # Registered as sessions land them: find (10), inbox.
    migrate_command.register(subparsers)
    log_command.register(subparsers)
    mono_command.register(subparsers)
    win_command.register(subparsers)
    link_command.register(subparsers)
    seed_command.register(subparsers)
    ref_command.register(subparsers)
    resolve_command.register(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.handler is None:
        parser.print_help()
        return 1

    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())

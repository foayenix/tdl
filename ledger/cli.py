"""Argument parsing and subcommand dispatch for `ledger`.

Subcommands are registered one per build session. The spine is here; the
verbs arrive with the sessions that need them (BUILD.md §6).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__


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
    parser.set_defaults(handler=None)

    # Subcommands are added here as sessions land them: migrate (02), log (03),
    # mono (04), win (05), link/seed (07), ref (08), find (10), inbox.
    parser.add_subparsers(dest="command", metavar="command")

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

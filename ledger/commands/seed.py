"""`ledger seed` — open skeletons in bulk from a CSV."""

from __future__ import annotations

import argparse

from ..db import connect
from ..seed import seed


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "seed",
        help="open monograph skeletons from a CSV",
        description="Open a skeleton for every plant named in a CSV you already have.",
    )
    parser.add_argument("--from", dest="path", required=True, metavar="FILE")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be opened without writing anything",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        try:
            report = seed(conn, args.path, dry_run=args.dry_run)
        except (OSError, ValueError) as error:
            print(error)
            return 2
    finally:
        conn.close()

    verb = "would open" if args.dry_run else "opened"
    print(f"{report.read} read · {verb} {len(report.opened)}")

    if report.already_present:
        print(f"{len(report.already_present)} already in the corpus")
    for line_number, why in report.skipped:
        print(f"line {line_number} skipped — {why}")

    return 0

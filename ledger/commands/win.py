"""`ledger win` — record an output against today's entry."""

from __future__ import annotations

import argparse
from datetime import date

from ..db import connect
from ..outputs import KINDS, record, total


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "win",
        help="record a published output",
        description="Record an output and attach it to the day it was deposited.",
    )
    parser.add_argument("kind", choices=KINDS)
    parser.add_argument("title")
    parser.add_argument("--venue", help="journal, conference, publication")
    parser.add_argument("--url")
    parser.add_argument(
        "--date",
        dest="on",
        default=None,
        metavar="YYYY-MM-DD",
        help="the day it went out (default: today); it is logged against today either way",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    if args.on is not None:
        try:
            date.fromisoformat(args.on)
        except ValueError:
            print(f"{args.on} is not a date; expected YYYY-MM-DD")
            return 2

    conn = connect(args.db)
    try:
        try:
            output, opened = record(
                conn,
                args.kind,
                args.title,
                venue=args.venue,
                on=args.on,
                url=args.url,
            )
        except ValueError as error:
            print(error)
            return 2
        published = total(conn)
    finally:
        conn.close()

    if opened:
        print(f"opened {date.today().isoformat()}")

    line = [output.kind, output.date, output.title]
    if output.venue:
        line.append(output.venue)
    print(" · ".join(line))
    print(f"{published} {'output' if published == 1 else 'outputs'} on the wall")

    return 0

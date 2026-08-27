"""`ledger log` — write a work block against a day and report the streak."""

from __future__ import annotations

import argparse
from datetime import date

from ..db import connect
from ..entries import FLOOR_MINUTES, current_streak, log


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "log",
        help="log minutes worked against a day",
        description="Log a block of work. Minutes accumulate; notes append.",
    )
    parser.add_argument("--minutes", type=int, default=0, help="minutes worked in this block")
    parser.add_argument("--note", help="what the block was")
    parser.add_argument(
        "--date",
        dest="on",
        default=None,
        metavar="YYYY-MM-DD",
        help="the day to log against (default: today)",
    )
    parser.add_argument(
        "--floor",
        dest="floor_day",
        action="store_true",
        default=None,
        help=f"mark this as a {FLOOR_MINUTES}-minute floor day",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    if args.minutes < 0:
        print("minutes cannot be negative")
        return 2

    if args.on is not None:
        try:
            date.fromisoformat(args.on)
        except ValueError:
            print(f"{args.on} is not a date; expected YYYY-MM-DD")
            return 2

    conn = connect(args.db)
    try:
        entry = log(
            conn,
            on=args.on,
            minutes=args.minutes,
            note=args.note,
            floor_day=args.floor_day,
        )
        streak = current_streak(conn)
    finally:
        conn.close()

    day_name = date.fromisoformat(entry.date).strftime("%A").lower()
    parts = [entry.date, day_name, f"{entry.minutes} min"]
    if entry.floor_day:
        parts.append("floor")
    parts.append(f"streak {streak} {'day' if streak == 1 else 'days'}")
    print(" · ".join(parts))

    return 0

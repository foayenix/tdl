"""`ledger mono` — open a monograph skeleton, edit it, move its status."""

from __future__ import annotations

import argparse

from ..db import connect
from ..editor import edit
from ..monographs import (
    HEADER_FIELDS,
    STATUSES,
    by_name,
    create,
    parse_template,
    render_template,
    set_status,
    update,
)


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "mono",
        help="open or edit a monograph",
        description="Open a monograph skeleton for a name, edit it, or move its status.",
    )
    parser.add_argument("name", help="the binomial, as you would write it")
    parser.add_argument("--part", help="the part used, e.g. 'stem bark'")
    parser.add_argument("--family", help="the botanical family")
    parser.add_argument("--authority", help="the authority string, never italic")
    parser.add_argument("--habitat", dest="habitat_note", help="a one-line habitat note")
    parser.add_argument(
        "--status",
        choices=STATUSES,
        help="move the record along the ramp",
    )
    parser.add_argument(
        "--no-edit",
        dest="open_editor",
        action="store_false",
        help="create or update without opening $EDITOR",
    )
    parser.set_defaults(handler=run, open_editor=True)


def run(args: argparse.Namespace) -> int:
    given = {field: getattr(args, field) for field in HEADER_FIELDS}
    given = {field: value for field, value in given.items() if value is not None}

    conn = connect(args.db)
    try:
        monograph = by_name(conn, args.name)

        if monograph is None:
            monograph = create(conn, args.name, **given)
            print(f"opened monograph {monograph.id} · {monograph.accepted_name} · skeleton")
        elif given:
            monograph = update(conn, monograph.id, given)

        if args.status:
            monograph = set_status(conn, monograph.id, args.status)
            print(f"monograph {monograph.id} · {monograph.accepted_name} · {monograph.status}")

        if args.open_editor:
            edited = edit(render_template(monograph))
            if edited is None:
                print("unchanged")
            else:
                try:
                    fields = parse_template(edited)
                except ValueError as error:
                    print(f"{error} — nothing written")
                    return 2
                monograph = update(conn, monograph.id, fields)
                print(f"saved monograph {monograph.id} · {monograph.accepted_name}")
        elif not args.status and given:
            print(f"monograph {monograph.id} · {monograph.accepted_name} · {monograph.status}")

    finally:
        conn.close()

    return 0

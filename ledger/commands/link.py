"""`ledger link` — bind a reference to a record, an output to a plant, a tag to a reference."""

from __future__ import annotations

import argparse
import sqlite3

from ..db import connect
from ..links import SECTIONS, bind_output, bind_reference, tag
from ..monographs import by_name


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "link",
        help="bind two records together",
        description="Bind a reference to a monograph, an output to a plant, or a tag.",
    )
    kinds = parser.add_subparsers(dest="link_kind", metavar="what", required=True)

    to_record = kinds.add_parser("ref", help="bind a reference to a monograph")
    to_record.add_argument("reference", help="a DOI, or the reference's id")
    to_record.add_argument("monograph", help="the accepted name")
    to_record.add_argument("--section", choices=SECTIONS, help="where in the record it is cited")
    to_record.set_defaults(handler=run_ref)

    to_plant = kinds.add_parser("output", help="record which plant an output was about")
    to_plant.add_argument("output", type=int, help="the output's id")
    to_plant.add_argument("monograph", help="the accepted name")
    to_plant.set_defaults(handler=run_output)

    to_tag = kinds.add_parser("tag", help="tag a reference")
    to_tag.add_argument("reference", help="a DOI, or the reference's id")
    to_tag.add_argument("tag", help="the tag")
    to_tag.set_defaults(handler=run_tag)


def _reference_id(conn: sqlite3.Connection, token: str) -> int | None:
    if token.isdigit():
        row = conn.execute("SELECT id FROM reference WHERE id = ?", (int(token),)).fetchone()
    else:
        row = conn.execute("SELECT id FROM reference WHERE doi = ?", (token,)).fetchone()
    return None if row is None else row["id"]


def _monograph(conn: sqlite3.Connection, name: str):
    found = by_name(conn, name)
    if found is None:
        print(f"no monograph named {name!r}")
    return found


def run_ref(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        reference_id = _reference_id(conn, args.reference)
        if reference_id is None:
            print(f"no reference matching {args.reference!r}")
            return 1

        monograph = _monograph(conn, args.monograph)
        if monograph is None:
            return 1

        placed = f" · {args.section}" if args.section else ""
        if bind_reference(conn, monograph.id, reference_id, args.section):
            print(f"bound R{reference_id} → {monograph.accepted_name}{placed}")
        else:
            print(f"R{reference_id} was already bound to {monograph.accepted_name}{placed}")
    finally:
        conn.close()
    return 0


def run_output(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        row = conn.execute(
            "SELECT id, kind, title FROM output WHERE id = ?", (args.output,)
        ).fetchone()
        if row is None:
            print(f"no output {args.output}")
            return 1

        monograph = _monograph(conn, args.monograph)
        if monograph is None:
            return 1

        if bind_output(conn, row["id"], monograph.id):
            print(f"{row['kind']} {row['id']} → {monograph.accepted_name}")
        else:
            print(f"{row['kind']} {row['id']} was already about {monograph.accepted_name}")
    finally:
        conn.close()
    return 0


def run_tag(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        reference_id = _reference_id(conn, args.reference)
        if reference_id is None:
            print(f"no reference matching {args.reference!r}")
            return 1

        if tag(conn, reference_id, args.tag):
            print(f"R{reference_id} · {args.tag}")
        else:
            print(f"R{reference_id} was already tagged {args.tag}")
    finally:
        conn.close()
    return 0

"""`ledger ref` — resolve a DOI against Crossref and put it in the library."""

from __future__ import annotations

import argparse
import json

from ..crossref import CrossrefError, NotFound, Offline, lookup, normalise_doi
from ..db import connect
from ..references import CROSSREF, by_doi, cite, is_unresolved, record_unresolved, save


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "ref",
        help="add a reference by DOI",
        description="Resolve a DOI against Crossref and add it to the library.",
    )
    parser.add_argument("doi", help="a DOI, with or without a resolver prefix")
    parser.add_argument("--json", action="store_true", help="print the record as JSON")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="how long to wait for Crossref",
    )
    parser.set_defaults(handler=run)


def _report(row, *, as_json: bool, note: str | None = None) -> None:
    if as_json:
        record = dict(zip(row.keys(), tuple(row), strict=True))
        if note:
            record["note"] = note
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return

    print(f"R{row['id']} · {cite(row)}")
    print(f"{row['doi']} · {row['read_state']}")
    if note:
        print(note)


def run(args: argparse.Namespace) -> int:
    try:
        doi = normalise_doi(args.doi)
    except ValueError as error:
        if args.json:
            print(json.dumps({"error": str(error)}, ensure_ascii=False))
        else:
            print(error)
        return 2

    timeout = {} if args.timeout is None else {"timeout": args.timeout}

    conn = connect(args.db)
    try:
        existing = by_doi(conn, doi)
        if existing is not None and not is_unresolved(existing):
            _report(existing, as_json=args.json, note="already in the library")
            return 0

        try:
            fields = lookup(doi, **timeout)
        except NotFound as error:
            if args.json:
                print(json.dumps({"doi": doi, "error": str(error)}, ensure_ascii=False))
            else:
                print(error)
            return 1
        except (Offline, CrossrefError) as error:
            # The network failed; the tool stays usable. Keep the DOI.
            row = record_unresolved(conn, doi)
            _report(row, as_json=args.json, note=f"{error} — kept as unresolved, run again later")
            return 1

        row = save(conn, fields, added_from=CROSSREF)
        _report(row, as_json=args.json)
    finally:
        conn.close()

    return 0

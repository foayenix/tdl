"""`ledger find` — search the corpus, the library and the wall."""

from __future__ import annotations

import argparse
import json

from ..db import connect
from ..find import find, nearest


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "find",
        help="search everything",
        description="Full-text search across monographs, references, outputs and claims.",
    )
    parser.add_argument("query", help="what to look for")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    conn = connect(args.db)
    try:
        try:
            results = find(conn, args.query, limit=args.limit)
        except ValueError as error:
            print(error)
            return 2

        searched = results.searched
        counted = " · ".join(
            f"{count} {noun if count == 1 else f'{noun}s'}"
            for noun, count in (
                ("monograph", searched["monographs"]),
                ("reference", searched["references"]),
                ("output", searched["outputs"]),
            )
        )
        line = f"searched {counted} · {results.milliseconds:.0f} ms"

        if args.json:
            print(
                json.dumps(
                    {
                        "query": results.query,
                        "searched": searched,
                        "ms": round(results.milliseconds, 1),
                        "hits": [
                            {
                                "kind": hit.kind,
                                "id": hit.row_id,
                                "monograph_id": hit.monograph_id,
                                "title": hit.title,
                            }
                            for hit in results.hits
                        ],
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0 if results.hits else 1

        if not results.hits:
            # Artboard 08 state 6, word for word.
            print("No monograph, no reference, no output mentions this name.")
            print(line)
            closest = nearest(conn, args.query)
            if closest is not None:
                name, distance = closest
                print(f"nearest in corpus: {name} · edit distance {distance}")
            return 1

        for hit in results.hits:
            where = "" if hit.monograph_id is None else f" → monograph {hit.monograph_id}"
            snippet = f"  {hit.snippet}" if hit.snippet.strip() else ""
            print(f"{hit.kind:12} {hit.title}{where}{snippet}")

        found = len(results.hits)
        print(f"{found} {'hit' if found == 1 else 'hits'} · {line}")
    finally:
        conn.close()

    return 0

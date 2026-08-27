"""`ledger resolve` — work the review queue against GBIF."""

from __future__ import annotations

import argparse
import json

from ..db import connect
from ..gbif import CONFIDENCE_THRESHOLD, GbifError, Offline, match
from ..monographs import by_name
from ..naming import accept, queue, resolve


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "resolve",
        help="resolve monograph names against GBIF",
        description="Resolve names against GBIF. Below the threshold, the record stays "
        "a skeleton and stays in the queue.",
    )
    parser.add_argument("name", nargs="?", help="the record to resolve (default: the queue)")
    parser.add_argument("--queue", action="store_true", help="list the queue and stop")
    parser.add_argument(
        "--accept",
        action="store_true",
        help="take the top match whatever its score — your decision, not GBIF's",
    )
    parser.add_argument(
        "--threshold", type=float, default=CONFIDENCE_THRESHOLD, metavar="0.90"
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=float, default=None, metavar="SECONDS")
    parser.set_defaults(handler=run)


def _as_dict(resolution) -> dict:
    return {
        "monograph_id": resolution.monograph_id,
        "name": resolution.name,
        "accepted": resolution.accepted,
        "reason": resolution.reason,
        "confidence": resolution.confidence,
        "gbif_key": None if resolution.match is None else resolution.match.key,
        "candidates": [
            {
                "name": candidate.canonical_name,
                "gbif_key": candidate.key,
                "confidence": candidate.confidence,
            }
            for candidate in resolution.candidates
        ],
    }


def _print(resolution) -> None:
    if resolution.accepted:
        best = resolution.match
        print(f"{resolution.name} · gbif {best.key} · confidence {best.confidence:.2f}")
        return

    print(f"{resolution.name} — name not resolved · {resolution.reason}")
    if resolution.confidence is not None:
        print(f"confidence {resolution.confidence:.2f}")
    for candidate in resolution.candidates:
        print(f"  {candidate.canonical_name} · {candidate.key} · {candidate.confidence:.2f}")


def _targets(conn, name):
    if name is None:
        return [(row["id"], row["accepted_name"]) for row in queue(conn)]

    found = by_name(conn, name)
    if found is None:
        return None
    return [(found.id, found.accepted_name)]


def run(args: argparse.Namespace) -> int:
    timeout = {} if args.timeout is None else {"timeout": args.timeout}

    conn = connect(args.db)
    try:
        if args.queue:
            rows = queue(conn)
            if args.json:
                print(
                    json.dumps(
                        [dict(zip(row.keys(), tuple(row), strict=True)) for row in rows],
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                for position, row in enumerate(rows, start=1):
                    seen = "" if row["gbif_confidence"] is None else (
                        f" · confidence {row['gbif_confidence']:.2f}"
                    )
                    print(f"{position} of {len(rows)} · {row['accepted_name']}{seen}")
                if not rows:
                    print("the queue is empty")
            return 0

        targets = _targets(conn, args.name)
        if targets is None:
            print(f"no monograph named {args.name!r}")
            return 1
        if not targets:
            print("the queue is empty")
            return 0

        results = []
        for monograph_id, name in targets:
            try:
                best, candidates = match(name, **timeout)
            except (Offline, GbifError) as error:
                print(f"{name} — {error}")
                return 1

            if args.accept:
                if not best.is_a_match:
                    print(f"{name} — GBIF returned no match to accept")
                    return 1
                results.append(accept(conn, monograph_id, best))
            else:
                results.append(
                    resolve(conn, monograph_id, best, candidates, threshold=args.threshold)
                )

        if args.json:
            print(json.dumps([_as_dict(r) for r in results], indent=2, ensure_ascii=False))
        else:
            for resolution in results:
                _print(resolution)

        return 0 if all(r.accepted for r in results) else 1
    finally:
        conn.close()

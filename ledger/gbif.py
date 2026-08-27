"""GBIF name resolution.

One bad name propagates into every query and paper and is not noticed for two
years (BUILD.md §4). So this module resolves, scores, and — below the
threshold — refuses. It never guesses.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

API = "https://api.gbif.org/v1/species/match"

USER_AGENT = "ledger/0.1 (https://github.com/foayenix/tdl)"

TIMEOUT_SECONDS = 10.0

# Below this, the record stays a skeleton and waits in the review queue.
# Artboard 08 state 4 states it as 0.90 and shows a refusal at 0.42.
CONFIDENCE_THRESHOLD = 0.90


class GbifError(Exception):
    """GBIF could not answer."""


class Offline(GbifError):
    """The network did not answer."""


@dataclass(frozen=True)
class Match:
    key: int | None
    scientific_name: str | None
    canonical_name: str | None
    authority: str | None
    family: str | None
    rank: str | None
    status: str | None
    confidence: float
    match_type: str
    synonym: bool

    @property
    def is_a_match(self) -> bool:
        return self.match_type != "NONE" and self.key is not None

    def clears(self, threshold: float = CONFIDENCE_THRESHOLD) -> bool:
        return self.is_a_match and self.confidence >= threshold


def _authority_of(scientific_name: str | None, canonical_name: str | None) -> str | None:
    """The bit of the scientific name that is not the binomial.

    Botanical names are always italic and the authority string never is
    (DESIGN.md §2), so the two are stored apart.
    """
    if not scientific_name or not canonical_name:
        return None
    if not scientific_name.startswith(canonical_name):
        return None
    return scientific_name[len(canonical_name) :].strip() or None


def _match_from(payload: dict[str, Any]) -> Match:
    canonical = payload.get("canonicalName")
    scientific = payload.get("scientificName")
    # GBIF scores 0–100; everything else in the design talks in 0–1.
    confidence = float(payload.get("confidence") or 0) / 100.0

    return Match(
        key=payload.get("usageKey"),
        scientific_name=scientific,
        canonical_name=canonical,
        authority=_authority_of(scientific, canonical),
        family=payload.get("family"),
        rank=payload.get("rank"),
        status=payload.get("status"),
        confidence=confidence,
        match_type=payload.get("matchType") or "NONE",
        synonym=bool(payload.get("synonym")),
    )


def parse(payload: dict[str, Any]) -> tuple[Match, list[Match]]:
    """The best match, and the candidates the review queue shows beside it."""
    if not isinstance(payload, dict):
        raise GbifError("GBIF did not answer with a match")

    best = _match_from(payload)
    candidates = [_match_from(item) for item in payload.get("alternatives") or []]
    candidates.sort(key=lambda candidate: candidate.confidence, reverse=True)
    return best, candidates


def fetch(name: str, *, timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise ValueError("a name is needed to resolve")

    query = urllib.parse.urlencode({"name": name, "verbose": "true"})
    request = urllib.request.Request(
        f"{API}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise GbifError(f"GBIF answered {error.code} for {name!r}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise Offline(f"could not reach GBIF: {error}") from error

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise GbifError("GBIF did not answer with JSON") from error


def match(name: str, *, timeout: float = TIMEOUT_SECONDS) -> tuple[Match, list[Match]]:
    return parse(fetch(name, timeout=timeout))

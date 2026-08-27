"""Crossref lookup and DOI normalisation.

Enrichment lives in exactly one language, and this is it (BUILD.md §3). Rust
has no HTTP client; the app calls this through the sidecar.

Name resolution, confidence thresholds and DOI normalisation are where bugs are
expensive and silent, so the normalisation is strict and the failure modes are
named rather than swallowed.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.crossref.org/works/"

# Crossref asks for a contact address so it can route you to the polite pool.
USER_AGENT = "ledger/0.1 (https://github.com/foayenix/tdl)"

TIMEOUT_SECONDS = 10.0

# A DOI is `10.` a registrant code of 4+ digits, a slash, then a suffix.
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")

_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi.org/",
    "doi:",
)


class CrossrefError(Exception):
    """Crossref could not answer for this DOI."""


class NotFound(CrossrefError):
    """Crossref has no record of this DOI."""


class Offline(CrossrefError):
    """The network did not answer. Not the same as a DOI that does not exist."""


def normalise_doi(raw: str) -> str:
    """A DOI in the one form the library stores.

    Resolver prefixes are stripped and the whole thing is lowercased — DOIs are
    case-insensitive, and two casings of one DOI in the library is two rows for
    one paper.
    """
    doi = (raw or "").strip()

    lowered = doi.lower()
    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            doi = doi[len(prefix) :]
            break

    doi = doi.strip().rstrip(".,;").lower()

    if not _DOI.match(doi):
        raise ValueError(f"{raw!r} is not a DOI")

    return doi


def _authors(message: dict[str, Any]) -> str | None:
    people = []
    for author in message.get("author") or []:
        name = " ".join(
            part for part in (author.get("given"), author.get("family")) if part
        ).strip()
        people.append(name or author.get("name") or "")
    people = [person for person in people if person]
    return "; ".join(people) or None


def _year(message: dict[str, Any]) -> int | None:
    for key in ("issued", "published-print", "published-online", "created"):
        parts = (message.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return int(parts[0][0])
    return None


def _first(message: dict[str, Any], key: str) -> str | None:
    values = message.get(key) or []
    if isinstance(values, str):
        return values or None
    return (values[0] if values else None) or None


def parse(payload: dict[str, Any]) -> dict[str, Any]:
    """A Crossref work as the fields the library stores.

    `access` is deliberately absent: Crossref has no dependable open/closed
    field, and guessing one from the licence block would put a wrong answer in
    the record. See STATE.md, session 08.
    """
    message = payload.get("message")
    if not isinstance(message, dict):
        raise CrossrefError("no work in the response")

    doi = message.get("DOI")
    if not doi:
        raise CrossrefError("the response carries no DOI")

    return {
        "doi": normalise_doi(doi),
        "title": _first(message, "title") or doi,
        "authors": _authors(message),
        "journal": _first(message, "container-title"),
        "volume": message.get("volume"),
        "year": _year(message),
        "type": message.get("type"),
    }


def fetch(doi: str, *, timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    """Ask Crossref about one DOI. Raises NotFound, Offline or CrossrefError."""
    doi = normalise_doi(doi)
    request = urllib.request.Request(
        API + urllib.parse.quote(doi, safe="/"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise NotFound(f"Crossref has no record of {doi}") from error
        raise CrossrefError(f"Crossref answered {error.code} for {doi}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise Offline(f"could not reach Crossref: {error}") from error

    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise CrossrefError("Crossref did not answer with JSON") from error


def lookup(doi: str, *, timeout: float = TIMEOUT_SECONDS) -> dict[str, Any]:
    return parse(fetch(doi, timeout=timeout))

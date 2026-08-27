"""§7 test 5 — name resolution. Never delete this test.

A below-threshold GBIF match leaves `status = 'skeleton'` and writes nothing to
`accepted_name`.

The fixtures are shape fixtures, not recordings — `api.gbif.org` is refused by
this environment's egress proxy. See `fixtures/README.md`.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from ledger.gbif import CONFIDENCE_THRESHOLD, GbifError, Offline, fetch, match, parse
from ledger.monographs import create
from ledger.naming import accept, queue, resolve

FIXTURES = Path(__file__).parent / "fixtures"

LIVE_NAME = "Khaya senegalensis"


def load(name):
    return json.loads((FIXTURES / f"gbif_shape_{name}.json").read_text())


@pytest.fixture
def high():
    return parse(load("high"))


@pytest.fixture
def low():
    return parse(load("low"))


@pytest.fixture
def none():
    return parse(load("none"))


@pytest.fixture
def mono(migrated):
    return create(migrated, "Khaya senegalensis")


class TestParsing:
    def test_a_clean_match_carries_its_key_family_and_authority(self, high):
        best, candidates = high
        assert best.key == 3190368
        assert best.canonical_name == "Khaya senegalensis"
        assert best.authority == "(Desr.) A.Juss."
        assert best.family == "Meliaceae"
        assert candidates == []

    def test_gbifs_hundred_point_score_becomes_a_fraction(self, high, low):
        assert high[0].confidence == 0.97
        assert low[0].confidence == 0.42

    def test_the_threshold_is_the_one_the_artboard_states(self):
        assert CONFIDENCE_THRESHOLD == 0.90

    def test_candidates_come_back_strongest_first(self, low):
        _, candidates = low
        assert [candidate.confidence for candidate in candidates] == [0.38, 0.31]

    def test_a_no_match_is_not_a_match_however_confident_it_says_it_is(self, none):
        best, _ = none
        assert best.confidence == 1.0
        assert best.is_a_match is False
        assert best.clears() is False

    def test_a_name_with_no_authority_string_parses(self, high):
        payload = load("high")
        payload["scientificName"] = payload["canonicalName"]
        best, _ = parse(payload)
        assert best.authority is None


class TestTheInvariant:
    def test_a_below_threshold_match_writes_nothing_to_accepted_name(self, migrated, mono, low):
        best, candidates = low
        resolution = resolve(migrated, mono.id, best, candidates)

        assert resolution.accepted is False
        assert "below the 0.90 threshold" in resolution.reason

        row = migrated.execute(
            "SELECT accepted_name, status, gbif_key, gbif_confidence FROM monograph"
        ).fetchone()
        assert row["accepted_name"] == "Khaya senegalensis"  # untouched, not the candidate
        assert row["status"] == "skeleton"
        assert row["gbif_key"] is None
        assert row["gbif_confidence"] == 0.42

    def test_no_match_at_all_writes_nothing_either(self, migrated, mono, none):
        best, candidates = none
        resolution = resolve(migrated, mono.id, best, candidates)

        assert resolution.accepted is False
        assert resolution.reason == "GBIF returned no match"

        row = migrated.execute(
            "SELECT accepted_name, status, gbif_key FROM monograph"
        ).fetchone()
        assert row["accepted_name"] == "Khaya senegalensis"
        assert row["status"] == "skeleton"
        assert row["gbif_key"] is None

    def test_a_refused_record_stays_in_the_queue(self, migrated, mono, low):
        best, candidates = low
        resolve(migrated, mono.id, best, candidates)
        assert [row["id"] for row in queue(migrated)] == [mono.id]

    def test_a_match_that_clears_writes_the_key_and_leaves_the_queue(self, migrated, mono, high):
        best, _ = high
        resolution = resolve(migrated, mono.id, best)

        assert resolution.accepted is True
        row = migrated.execute(
            "SELECT accepted_name, authority, family, gbif_key, gbif_confidence, status"
            " FROM monograph"
        ).fetchone()
        assert row["gbif_key"] == 3190368
        assert row["gbif_confidence"] == 0.97
        assert row["authority"] == "(Desr.) A.Juss."
        assert row["family"] == "Meliaceae"
        # Resolving a name says nothing about how written the record is.
        assert row["status"] == "skeleton"

        assert queue(migrated) == []

    def test_a_lookup_never_overwrites_what_the_researcher_typed(self, migrated, high):
        mono = create(
            migrated, "Khaya senegalensis", family="Meliaceae s.l.", authority="Juss."
        )
        resolve(migrated, mono.id, high[0])

        row = migrated.execute("SELECT family, authority FROM monograph").fetchone()
        assert row["family"] == "Meliaceae s.l."
        assert row["authority"] == "Juss."

    def test_the_threshold_can_be_moved_for_one_call(self, migrated, mono, low):
        best, candidates = low
        assert resolve(migrated, mono.id, best, candidates, threshold=0.40).accepted is True

    def test_a_person_may_accept_a_match_the_threshold_refused(self, migrated, mono, low):
        """Artboard 08 state 4's `Accept top match`. A decision is not a guess."""
        best, _ = low
        resolution = accept(migrated, mono.id, best)

        assert resolution.accepted is True
        row = migrated.execute("SELECT accepted_name, gbif_key FROM monograph").fetchone()
        assert row["accepted_name"] == "PLACEHOLDER CANDIDATE ONE"
        assert row["gbif_key"] == 5000001
        assert queue(migrated) == []

    def test_there_is_nothing_to_accept_when_gbif_found_nothing(self, migrated, mono, none):
        with pytest.raises(ValueError, match="no match to accept"):
            accept(migrated, mono.id, none[0])

    def test_resolving_a_record_that_is_not_there(self, migrated, high):
        with pytest.raises(ValueError, match="no monograph 999"):
            resolve(migrated, 999, high[0])


class TestTheQueue:
    def test_a_new_skeleton_is_in_the_queue(self, migrated, mono):
        assert [row["accepted_name"] for row in queue(migrated)] == ["Khaya senegalensis"]

    def test_a_resolved_record_is_not(self, migrated, mono, high):
        resolve(migrated, mono.id, high[0])
        assert queue(migrated) == []

    def test_a_record_past_skeleton_is_not_in_the_queue(self, migrated, mono):
        from ledger.monographs import set_status

        set_status(migrated, mono.id, "drafted")
        assert queue(migrated) == []

    def test_the_queue_is_ordered_by_when_the_work_started(self, migrated):
        for name, written in (
            ("Prunus africana", "2025-01-04"),
            ("Warburgia ugandensis", "2024-03-11"),
        ):
            created = create(migrated, name)
            migrated.execute(
                "UPDATE monograph SET first_written = ? WHERE id = ?", (written, created.id)
            )
        assert [row["accepted_name"] for row in queue(migrated)] == [
            "Warburgia ugandensis",
            "Prunus africana",
        ]

    def test_a_refusal_records_when_it_was_last_checked(self, migrated, mono, low):
        migrated.execute("UPDATE monograph SET last_touched = '2020-01-01 00:00:00'")
        resolve(migrated, mono.id, low[0], low[1])
        assert queue(migrated)[0]["last_touched"] > "2020-01-01 00:00:00"


class TestFailureModes:
    def test_no_network_raises_offline(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise urllib.error.URLError("Name or service not known")

        monkeypatch.setattr("ledger.gbif.urllib.request.urlopen", raiser)
        with pytest.raises(Offline, match="could not reach GBIF"):
            fetch("Khaya senegalensis")

    def test_a_server_error_is_not_offline(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise urllib.error.HTTPError("url", 503, "Service Unavailable", {}, None)

        monkeypatch.setattr("ledger.gbif.urllib.request.urlopen", raiser)
        with pytest.raises(GbifError, match="503"):
            fetch("Khaya senegalensis")

    def test_an_empty_name_never_reaches_the_network(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise AssertionError("the network should not have been touched")

        monkeypatch.setattr("ledger.gbif.urllib.request.urlopen", raiser)
        with pytest.raises(ValueError, match="a name is needed"):
            fetch("   ")


@pytest.mark.network
def test_the_resolver_holds_against_the_live_api():
    """The one live test. Excluded from `just check` by the `network` marker."""
    best, _ = match(LIVE_NAME)

    assert best.is_a_match
    assert best.canonical_name == LIVE_NAME
    assert best.clears()

"""The library rows, and what a failed network call leaves behind."""

from __future__ import annotations

import pytest

from ledger.references import (
    CROSSREF,
    OFFLINE,
    by_doi,
    cite,
    counts_by_read_state,
    is_unresolved,
    record_unresolved,
    save,
)

DOI = "10.1016/j.jep.2019.112202"

RECORD = {
    "doi": DOI,
    "title": "PLACEHOLDER TITLE",
    "authors": "A. PLACEHOLDER-ONE",
    "journal": "PLACEHOLDER JOURNAL",
    "volume": "241",
    "year": 2019,
    "type": "journal-article",
}


def test_a_resolved_reference_is_saved_whole(migrated):
    row = save(migrated, RECORD, added_from=CROSSREF)

    assert row["doi"] == DOI
    assert row["added_from"] == CROSSREF
    assert row["read_state"] == "queued"
    assert row["opened_count"] == 0
    assert is_unresolved(row) is False


def test_an_unreachable_network_still_keeps_the_doi(migrated):
    row = record_unresolved(migrated, DOI)

    assert row["doi"] == DOI
    assert row["title"] == DOI
    assert is_unresolved(row) is True


def test_retrying_later_fills_the_row_in(migrated):
    unresolved = record_unresolved(migrated, DOI)
    resolved = save(migrated, RECORD, added_from=CROSSREF)

    assert resolved["id"] == unresolved["id"]
    assert resolved["title"] == "PLACEHOLDER TITLE"
    assert is_unresolved(resolved) is False
    assert migrated.execute("SELECT count(*) FROM reference").fetchone()[0] == 1


def test_a_row_edited_by_hand_is_never_clobbered_by_a_retry(migrated):
    save(migrated, RECORD, added_from=CROSSREF)
    migrated.execute("UPDATE reference SET title = 'Corrected by hand' WHERE doi = ?", (DOI,))

    save(migrated, {**RECORD, "title": "PLACEHOLDER TITLE"}, added_from=CROSSREF)

    assert by_doi(migrated, DOI)["title"] == "Corrected by hand"


def test_recording_the_same_unresolved_doi_twice_is_one_row(migrated):
    first = record_unresolved(migrated, DOI)
    second = record_unresolved(migrated, DOI)

    assert first["id"] == second["id"]
    assert migrated.execute("SELECT count(*) FROM reference").fetchone()[0] == 1


def test_an_unknown_field_is_refused(migrated):
    with pytest.raises(ValueError, match="not a reference field"):
        save(migrated, {"doi": DOI, "title": "x", "abstract": "..."}, added_from=CROSSREF)


class TestCitation:
    def test_a_full_record_reads_as_one_line(self, migrated):
        row = save(migrated, RECORD, added_from=CROSSREF)
        assert cite(row) == "PLACEHOLDER TITLE · PLACEHOLDER JOURNAL · 241 · 2019"

    def test_a_bare_row_reads_as_its_title(self, migrated):
        row = record_unresolved(migrated, DOI)
        assert cite(row) == DOI


class TestReadStates:
    def test_every_state_is_counted_even_when_empty(self, migrated):
        save(migrated, RECORD, added_from=CROSSREF)
        assert counts_by_read_state(migrated) == {"queued": 1, "reading": 0, "read": 0}

    def test_the_counts_follow_the_rows(self, migrated):
        save(migrated, RECORD, added_from=CROSSREF)
        save(migrated, {"doi": "10.1016/other", "title": "Another"}, added_from=CROSSREF)
        migrated.execute("UPDATE reference SET read_state = 'read' WHERE doi = ?", (DOI,))

        assert counts_by_read_state(migrated) == {"queued": 1, "reading": 0, "read": 1}


def test_an_unresolved_row_is_cited_by_nothing_like_any_other(migrated):
    from ledger.links import cited_by_nothing

    record_unresolved(migrated, DOI)
    assert [row["id"] for row in cited_by_nothing(migrated)] == [1]


def test_the_offline_marker_is_the_only_thing_distinguishing_the_two(migrated):
    assert OFFLINE != CROSSREF

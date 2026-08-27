"""§7 test 4 — the sourcing invariant. Never delete this test.

`monograph.status` cannot become `reviewed` while any claim row belonging to it
has an empty source. Enforced in the database, not only in the UI — so these
tests go at the SQL, not through the Python helpers, wherever the point is that
the *database* refuses.
"""

from __future__ import annotations

import sqlite3

import pytest

from ledger.claims import CLAIM_TABLES, Source, add, set_source, unsourced_count
from ledger.monographs import create, set_status

REQUIRED = {
    "vernacular": {"name": "kuka"},
    "indication": {"condition": "malarial fever"},
    "constituent": {"compound": "khayanthone"},
    "safety": {"kind": "interaction", "finding": "additive hypotension"},
}


@pytest.fixture
def mono(migrated):
    return create(migrated, "Khaya senegalensis", part="stem bark")


@pytest.mark.parametrize("table", sorted(CLAIM_TABLES))
def test_one_unsourced_row_of_any_kind_blocks_reviewed(migrated, mono, table):
    add(migrated, table, mono.id, **REQUIRED[table])
    assert unsourced_count(migrated, mono.id) == 1

    with pytest.raises(sqlite3.IntegrityError, match="unsourced claim rows"):
        set_status(migrated, mono.id, "reviewed")

    assert migrated.execute("SELECT status FROM monograph").fetchone()[0] == "skeleton"


@pytest.mark.parametrize("table", sorted(CLAIM_TABLES))
def test_sourcing_the_row_then_allows_reviewed(migrated, mono, table):
    claim_id = add(migrated, table, mono.id, **REQUIRED[table])

    with pytest.raises(sqlite3.IntegrityError):
        set_status(migrated, mono.id, "reviewed")

    set_source(migrated, table, claim_id, Source(note="field notes 2025-11"))
    assert unsourced_count(migrated, mono.id) == 0

    assert set_status(migrated, mono.id, "reviewed").status == "reviewed"


def test_a_reference_is_a_source_too(migrated, mono):
    migrated.execute("INSERT INTO reference (id, doi, title) VALUES (7, '10.1/x', 'A paper')")
    add(migrated, "indication", mono.id, condition="dysentery", source=Source(reference_id=7))

    assert unsourced_count(migrated, mono.id) == 0
    assert set_status(migrated, mono.id, "reviewed").status == "reviewed"


def test_blank_and_whitespace_notes_do_not_count_as_sources(migrated, mono):
    add(migrated, "indication", mono.id, condition="dysentery", source=Source(note="   "))
    assert unsourced_count(migrated, mono.id) == 1

    with pytest.raises(sqlite3.IntegrityError):
        set_status(migrated, mono.id, "reviewed")


def test_the_other_three_statuses_are_unaffected(migrated, mono):
    add(migrated, "indication", mono.id, condition="dysentery")
    for status in ("drafted", "sourced", "skeleton"):
        assert set_status(migrated, mono.id, status).status == status


def test_only_this_record_holds_itself_back(migrated, mono):
    other = create(migrated, "Prunus africana")
    add(migrated, "indication", other.id, condition="benign prostatic hyperplasia")

    assert set_status(migrated, mono.id, "reviewed").status == "reviewed"
    with pytest.raises(sqlite3.IntegrityError):
        set_status(migrated, other.id, "reviewed")


def test_a_record_with_no_claims_at_all_can_be_reviewed(migrated, mono):
    assert set_status(migrated, mono.id, "reviewed").status == "reviewed"


def test_a_monograph_cannot_be_inserted_straight_into_reviewed_over_unsourced_rows(migrated):
    """The insert trigger only matters when the cascade did not run.

    `ON DELETE CASCADE` normally takes a record's claim rows with it, so this
    case cannot arise while foreign keys are on. They are per-connection, and
    the Rust side has to set the pragma for itself — this proves the invariant
    still holds for a connection that forgot.
    """
    migrated.execute("PRAGMA foreign_keys = OFF")
    migrated.execute("INSERT INTO monograph (id, accepted_name) VALUES (42, 'Khaya')")
    add(migrated, "indication", 42, condition="dysentery")
    migrated.execute("DELETE FROM monograph WHERE id = 42")
    assert migrated.execute("SELECT count(*) FROM indication").fetchone()[0] == 1

    with pytest.raises(sqlite3.IntegrityError, match="unsourced claim rows"):
        migrated.execute(
            "INSERT INTO monograph (id, accepted_name, status)"
            " VALUES (42, 'Khaya', 'reviewed')"
        )


class TestTheWallHoldsFromTheOtherSide:
    """A doorway is not a wall: a reviewed record must stay sourced."""

    @pytest.mark.parametrize("table", sorted(CLAIM_TABLES))
    def test_an_unsourced_row_cannot_be_added_to_a_reviewed_record(self, migrated, mono, table):
        set_status(migrated, mono.id, "reviewed")

        with pytest.raises(sqlite3.IntegrityError, match="cannot take an unsourced row"):
            add(migrated, table, mono.id, **REQUIRED[table])

        assert unsourced_count(migrated, mono.id) == 0

    @pytest.mark.parametrize("table", sorted(CLAIM_TABLES))
    def test_a_source_cannot_be_stripped_off_a_reviewed_record(self, migrated, mono, table):
        claim_id = add(
            migrated, table, mono.id, source=Source(note="field notes"), **REQUIRED[table]
        )
        set_status(migrated, mono.id, "reviewed")

        with pytest.raises(sqlite3.IntegrityError, match="cannot take an unsourced row"):
            set_source(migrated, table, claim_id, Source())

        assert unsourced_count(migrated, mono.id) == 0

    def test_a_sourced_row_can_still_be_added_to_a_reviewed_record(self, migrated, mono):
        set_status(migrated, mono.id, "reviewed")
        add(migrated, "indication", mono.id, condition="dysentery", source=Source(note="R2"))
        assert unsourced_count(migrated, mono.id) == 0

"""Outputs and the day they attach to."""

from __future__ import annotations

import pytest

from ledger.entries import log
from ledger.outputs import KINDS, counts_by_kind, record, total


def test_an_output_attaches_to_the_day_it_was_deposited(migrated):
    log(migrated, on="2026-08-24", minutes=96)
    output, opened = record(
        migrated,
        "note",
        "Evidence grading for traditional-use claims",
        on="2026-08-24",
        deposited="2026-08-24",
        url="https://example.org/note",
    )

    assert opened is False
    entry_id = migrated.execute("SELECT id FROM entry WHERE date = '2026-08-24'").fetchone()[0]
    assert output.entry_id == entry_id


def test_a_back_dated_output_still_attaches_to_the_day_it_was_logged(migrated):
    """A paper that went out in June does not make June a day worked."""
    output, _ = record(
        migrated, "paper", "Limonoid bitters", on="2026-06-18", deposited="2026-08-24"
    )

    assert output.date == "2026-06-18"
    days = [row[0] for row in migrated.execute("SELECT date FROM entry")]
    assert days == ["2026-08-24"]
    assert output.entry_id == migrated.execute("SELECT id FROM entry").fetchone()[0]


def test_depositing_on_an_unlogged_day_opens_it(migrated):
    output, opened = record(migrated, "paper", "A paper", deposited="2026-08-24")

    assert opened is True
    row = migrated.execute("SELECT id, minutes FROM entry WHERE date = '2026-08-24'").fetchone()
    assert row["minutes"] == 0
    assert output.entry_id == row["id"]


def test_a_second_output_on_the_same_day_reuses_the_entry(migrated):
    first, _ = record(migrated, "note", "First", deposited="2026-08-24")
    second, opened = record(migrated, "talk", "Second", deposited="2026-08-24")

    assert opened is False
    assert first.entry_id == second.entry_id
    assert migrated.execute("SELECT count(*) FROM entry").fetchone()[0] == 1


def test_every_kind_the_wall_counts_is_accepted(migrated):
    for kind in KINDS:
        record(migrated, kind, f"A {kind}", deposited="2026-08-24")
    assert counts_by_kind(migrated) == dict.fromkeys(KINDS, 1)
    assert total(migrated) == len(KINDS)


def test_kinds_with_nothing_in_them_still_count_zero(migrated):
    record(migrated, "note", "A note", deposited="2026-08-24")
    assert counts_by_kind(migrated) == {
        "paper": 0,
        "talk": 0,
        "long-form": 0,
        "release": 0,
        "note": 1,
    }


def test_an_invented_kind_is_refused(migrated):
    with pytest.raises(ValueError, match="not an output kind"):
        record(migrated, "tweet", "A tweet", deposited="2026-08-24")


def test_a_title_is_required(migrated):
    with pytest.raises(ValueError, match="needs a title"):
        record(migrated, "note", "   ", deposited="2026-08-24")


def test_the_wall_is_empty_before_anything_is_published(migrated):
    assert total(migrated) == 0
    assert counts_by_kind(migrated) == dict.fromkeys(KINDS, 0)

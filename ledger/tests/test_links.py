"""§7 test 8 — the gap queries. Never delete those two.

A monograph with an output does not appear; one without does. A reference bound
to nothing appears in `cited by nothing`.
"""

from __future__ import annotations

import sqlite3

import pytest

from ledger.links import (
    bind_output,
    bind_reference,
    cited_by_nothing,
    never_published_on,
    references_bound_to,
    tag,
)
from ledger.monographs import create, set_status
from ledger.outputs import record


@pytest.fixture
def mono(migrated):
    return create(migrated, "Khaya senegalensis", part="stem bark")


@pytest.fixture
def ref(migrated):
    cursor = migrated.execute(
        "INSERT INTO reference (doi, title) VALUES ('10.1016/j.jep.2019.112202', 'A paper')"
    )
    return cursor.lastrowid


class TestBindingReferences:
    def test_a_reference_binds_to_a_record_in_a_section(self, migrated, mono, ref):
        assert bind_reference(migrated, mono.id, ref, "indication") is True
        bound = references_bound_to(migrated, mono.id)
        assert [(row["id"], row["section"]) for row in bound] == [(ref, "indication")]

    def test_the_same_binding_twice_is_not_an_error(self, migrated, mono, ref):
        assert bind_reference(migrated, mono.id, ref, "summary") is True
        assert bind_reference(migrated, mono.id, ref, "summary") is False
        assert len(references_bound_to(migrated, mono.id)) == 1

    def test_one_reference_can_be_cited_in_two_sections(self, migrated, mono, ref):
        bind_reference(migrated, mono.id, ref, "summary")
        bind_reference(migrated, mono.id, ref, "preparation")
        assert len(references_bound_to(migrated, mono.id)) == 2

    def test_an_invented_section_is_refused(self, migrated, mono, ref):
        with pytest.raises(ValueError, match="is not a section"):
            bind_reference(migrated, mono.id, ref, "conclusions")

    def test_a_binding_to_nothing_is_refused(self, migrated, ref):
        with pytest.raises(sqlite3.IntegrityError):
            bind_reference(migrated, 999, ref)

    def test_bindings_go_when_the_record_goes(self, migrated, mono, ref):
        bind_reference(migrated, mono.id, ref)
        migrated.execute("DELETE FROM monograph WHERE id = ?", (mono.id,))
        assert migrated.execute("SELECT count(*) FROM monograph_reference").fetchone()[0] == 0
        assert migrated.execute("SELECT count(*) FROM reference").fetchone()[0] == 1


class TestNeverPublishedOn:
    def test_a_record_with_no_output_appears(self, migrated, mono):
        set_status(migrated, mono.id, "sourced")
        assert [row["accepted_name"] for row in never_published_on(migrated)] == [
            "Khaya senegalensis"
        ]

    def test_a_record_with_an_output_does_not(self, migrated, mono):
        set_status(migrated, mono.id, "sourced")
        output, _ = record(migrated, "paper", "A paper", deposited="2026-08-24")
        bind_output(migrated, output.id, mono.id)

        assert never_published_on(migrated) == []

    def test_a_skeleton_is_not_a_gap_yet(self, migrated, mono):
        """Only `sourced` and `reviewed` records count — an unwritten one is not a gap."""
        assert never_published_on(migrated) == []

        set_status(migrated, mono.id, "drafted")
        assert never_published_on(migrated) == []

        set_status(migrated, mono.id, "reviewed")
        assert len(never_published_on(migrated)) == 1

    def test_the_gap_is_ordered_by_when_the_work_started(self, migrated):
        for name, written in (
            ("Prunus africana", "2025-01-04"),
            ("Khaya senegalensis", "2024-03-11"),
            ("Warburgia ugandensis", "2026-02-20"),
        ):
            mono = create(migrated, name)
            migrated.execute(
                "UPDATE monograph SET first_written = ? WHERE id = ?", (written, mono.id)
            )
            set_status(migrated, mono.id, "sourced")

        assert [row["accepted_name"] for row in never_published_on(migrated)] == [
            "Khaya senegalensis",
            "Prunus africana",
            "Warburgia ugandensis",
        ]


class TestCitedByNothing:
    def test_an_unbound_reference_appears(self, migrated, ref):
        assert [row["id"] for row in cited_by_nothing(migrated)] == [ref]

    def test_a_bound_reference_does_not(self, migrated, mono, ref):
        bind_reference(migrated, mono.id, ref, "summary")
        assert cited_by_nothing(migrated) == []

    def test_it_is_still_bound_after_one_of_two_bindings_goes(self, migrated, mono, ref):
        other = create(migrated, "Prunus africana")
        bind_reference(migrated, mono.id, ref)
        bind_reference(migrated, other.id, ref)

        migrated.execute("DELETE FROM monograph WHERE id = ?", (mono.id,))
        assert cited_by_nothing(migrated) == []

        migrated.execute("DELETE FROM monograph WHERE id = ?", (other.id,))
        assert [row["id"] for row in cited_by_nothing(migrated)] == [ref]


class TestOutputsAndTags:
    def test_an_output_can_be_about_several_plants(self, migrated, mono):
        other = create(migrated, "Prunus africana")
        output, _ = record(migrated, "paper", "A paper", deposited="2026-08-24")

        assert bind_output(migrated, output.id, mono.id) is True
        assert bind_output(migrated, output.id, other.id) is True
        assert bind_output(migrated, output.id, mono.id) is False

        count = migrated.execute("SELECT count(*) FROM output_monograph").fetchone()[0]
        assert count == 2

    def test_an_output_about_no_plant_is_allowed(self, migrated):
        """The Wall's `whole corpus` / `method, no plant` case."""
        record(migrated, "note", "Evidence grading", deposited="2026-08-24")
        assert migrated.execute("SELECT count(*) FROM output_monograph").fetchone()[0] == 0

    def test_a_tag_is_recorded_once(self, migrated, ref):
        assert tag(migrated, ref, "antimalarial") is True
        assert tag(migrated, ref, "antimalarial") is False

    def test_an_empty_tag_is_refused(self, migrated, ref):
        with pytest.raises(ValueError, match="needs a name"):
            tag(migrated, ref, "   ")


class TestInbox:
    def test_a_line_is_recorded_once(self, migrated):
        migrated.execute(
            "INSERT INTO inbox_line (captured_at, raw) VALUES (?, ?)",
            ("2026-08-24T07:42", "mono Warburgia ugandensis bark"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            migrated.execute(
                "INSERT INTO inbox_line (captured_at, raw) VALUES (?, ?)",
                ("2026-08-24T07:42", "mono Warburgia ugandensis bark"),
            )

    def test_an_unclassified_line_keeps_kind_null(self, migrated):
        migrated.execute(
            "INSERT INTO inbox_line (captured_at, raw) VALUES (?, ?)",
            ("2026-08-24T18:57", "bissilon?"),
        )
        row = migrated.execute("SELECT kind, consumed_at FROM inbox_line").fetchone()
        assert tuple(row) == (None, None)

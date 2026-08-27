"""FTS5 and `ledger find`, including the half of §7 test 3 about delete triggers.

"assert FTS triggers fire on insert, update **and** delete" — the delete half is
the one that rots quietly, so it is tested for every indexed table.
"""

from __future__ import annotations

import pytest

from ledger.claims import Source, add
from ledger.find import find, nearest, to_match
from ledger.monographs import create, update
from ledger.outputs import record
from ledger.references import CROSSREF, save


@pytest.fixture
def mono(migrated):
    return create(
        migrated,
        "Khaya senegalensis",
        family="Meliaceae",
        part="stem bark",
        habitat_note="African mahogany, dry-savanna belt",
    )


def titles(results):
    return sorted(hit.title for hit in results.hits)


class TestMatchExpressions:
    def test_tokens_are_anded(self):
        assert to_match("antimalarial bark") == '"antimalarial" AND "bark"'

    @pytest.mark.parametrize(
        "query",
        ['bark"', "bark - stem", "10.1016/j.jep", "NEAR(a b)", "stem*", "a OR b"],
    )
    def test_syntax_in_the_query_is_searched_for_not_executed(self, migrated, query):
        find(migrated, query)  # must not raise a MATCH syntax error

    def test_a_query_with_no_words_is_refused(self):
        with pytest.raises(ValueError, match="nothing to search for"):
            to_match("   ---   ")

    def test_diacritics_do_not_hide_a_row(self, migrated, mono):
        add(migrated, "vernacular", mono.id, name="caïlcédrat", source=Source(note="R1"))
        assert titles(find(migrated, "cailcedrat")) == ["caïlcédrat"]


class TestTriggersFireOnInsert:
    def test_a_monograph_is_findable_by_name_and_by_prose(self, migrated, mono):
        assert titles(find(migrated, "Khaya")) == ["Khaya senegalensis"]
        assert titles(find(migrated, "savanna")) == ["Khaya senegalensis"]
        assert titles(find(migrated, "Meliaceae")) == ["Khaya senegalensis"]

    def test_a_reference_is_findable_by_title_author_and_doi(self, migrated):
        save(
            migrated,
            {
                "doi": "10.1016/j.jep.2019.112202",
                "title": "PLACEHOLDER TITLE",
                "authors": "A. PLACEHOLDER-ONE",
            },
            added_from=CROSSREF,
        )
        assert titles(find(migrated, "PLACEHOLDER TITLE")) == ["PLACEHOLDER TITLE"]
        assert titles(find(migrated, "PLACEHOLDER-ONE")) == ["PLACEHOLDER TITLE"]

    def test_an_output_is_findable(self, migrated):
        record(migrated, "note", "Evidence grading", deposited="2026-08-24")
        assert titles(find(migrated, "Evidence grading")) == ["Evidence grading"]

    @pytest.mark.parametrize(
        ("table", "fields", "query", "expected"),
        [
            ("vernacular", {"name": "kuka"}, "kuka", "kuka"),
            ("indication", {"condition": "malarial fever"}, "malarial", "malarial fever"),
            ("constituent", {"compound": "khayanthone"}, "khayanthone", "khayanthone"),
            (
                "safety",
                {"kind": "interaction", "finding": "additive hypotension"},
                "hypotension",
                "additive hypotension",
            ),
        ],
    )
    def test_every_claim_kind_is_indexed(self, migrated, mono, table, fields, query, expected):
        add(migrated, table, mono.id, source=Source(note="R1"), **fields)
        results = find(migrated, query)
        assert titles(results) == [expected]
        assert results.monograph_ids == [mono.id]


class TestTriggersFireOnUpdate:
    def test_a_renamed_record_is_found_under_the_new_name_only(self, migrated, mono):
        migrated.execute(
            "UPDATE monograph SET accepted_name = 'Khaya grandifoliola' WHERE id = ?",
            (mono.id,),
        )
        assert titles(find(migrated, "grandifoliola")) == ["Khaya grandifoliola"]
        assert find(migrated, "senegalensis").hits == []

    def test_rewritten_prose_is_indexed(self, migrated, mono):
        assert find(migrated, "limonoid").hits == []
        update(migrated, mono.id, {"summary": "Limonoid bitters are the presumed actives."})
        assert titles(find(migrated, "limonoid")) == ["Khaya senegalensis"]

    def test_an_update_does_not_leave_a_duplicate_behind(self, migrated, mono):
        update(migrated, mono.id, {"summary": "First pass."})
        update(migrated, mono.id, {"summary": "Second pass."})
        assert len(find(migrated, "Khaya").hits) == 1

    def test_a_reference_retitled_after_a_late_lookup_is_reindexed(self, migrated):
        from ledger.references import record_unresolved

        record_unresolved(migrated, "10.1016/j.jep.2019.112202")
        save(
            migrated,
            {"doi": "10.1016/j.jep.2019.112202", "title": "PLACEHOLDER TITLE"},
            added_from=CROSSREF,
        )
        assert titles(find(migrated, "PLACEHOLDER TITLE")) == ["PLACEHOLDER TITLE"]
        assert len(find(migrated, "PLACEHOLDER").hits) == 1


class TestTriggersFireOnDelete:
    """A search that returns records you deleted is worse than no search."""

    def test_a_deleted_monograph_leaves_the_index(self, migrated, mono):
        migrated.execute("DELETE FROM monograph WHERE id = ?", (mono.id,))
        assert find(migrated, "Khaya").hits == []

    def test_a_deleted_reference_leaves_the_index(self, migrated):
        save(migrated, {"doi": "10.1/x", "title": "PLACEHOLDER TITLE"}, added_from=CROSSREF)
        migrated.execute("DELETE FROM reference")
        assert find(migrated, "PLACEHOLDER").hits == []

    def test_a_deleted_output_leaves_the_index(self, migrated):
        output, _ = record(migrated, "note", "Evidence grading", deposited="2026-08-24")
        migrated.execute("DELETE FROM output WHERE id = ?", (output.id,))
        assert find(migrated, "Evidence").hits == []

    def test_a_deleted_claim_row_leaves_the_index(self, migrated, mono):
        claim_id = add(
            migrated, "indication", mono.id, condition="malarial fever",
            source=Source(note="R1"),
        )
        migrated.execute("DELETE FROM indication WHERE id = ?", (claim_id,))
        assert find(migrated, "malarial").hits == []

    def test_deleting_a_record_sweeps_its_claim_rows_out_of_the_index(self, migrated, mono):
        """The cascade does not fire per-row delete triggers, so the sweep must."""
        add(migrated, "indication", mono.id, condition="malarial fever", source=Source(note="R1"))
        add(migrated, "vernacular", mono.id, name="kuka", source=Source(note="R1"))

        migrated.execute("DELETE FROM monograph WHERE id = ?", (mono.id,))

        assert find(migrated, "malarial").hits == []
        assert find(migrated, "kuka").hits == []
        assert migrated.execute("SELECT count(*) FROM search").fetchone()[0] == 0


class TestTheBackfill:
    def test_003_indexes_records_that_were_already_there(self, conn):
        from ledger.migrate import apply, discover

        migrations = discover()
        for migration in migrations[:-1]:
            apply(conn, migration)

        mono = create(conn, "Khaya senegalensis", family="Meliaceae")
        add(conn, "indication", mono.id, condition="malarial fever", source=Source(note="R1"))

        apply(conn, migrations[-1])

        assert titles(find(conn, "Khaya")) == ["Khaya senegalensis"]
        assert titles(find(conn, "malarial")) == ["malarial fever"]


class TestWhatWasSearched:
    def test_the_counts_are_the_ones_the_state_reports(self, migrated, mono):
        save(migrated, {"doi": "10.1/x", "title": "A paper"}, added_from=CROSSREF)
        record(migrated, "note", "A note", deposited="2026-08-24")

        results = find(migrated, "Khaya")
        assert results.searched == {"monographs": 1, "references": 1, "outputs": 1}
        assert results.milliseconds >= 0

    def test_a_query_that_finds_nothing_finds_nothing(self, migrated, mono):
        assert find(migrated, "Sutherlandia").hits == []

    def test_the_nearest_name_is_offered_when_nothing_matched(self, migrated, mono):
        name, distance = nearest(migrated, "Khaya senegalensis")
        assert (name, distance) == ("Khaya senegalensis", 0)

        name, distance = nearest(migrated, "Khaya senegalense")
        assert name == "Khaya senegalensis"
        assert distance == 2

    def test_there_is_no_nearest_name_in_an_empty_corpus(self, migrated):
        assert nearest(migrated, "Sutherlandia frutescens") is None

    def test_one_plant_hit_through_several_claims_is_listed_once(self, migrated, mono):
        add(migrated, "indication", mono.id, condition="bark decoction", source=Source(note="R1"))
        add(migrated, "constituent", mono.id, compound="bark limonoid", source=Source(note="R1"))

        results = find(migrated, "bark")
        assert results.monograph_ids == [mono.id]
        assert len(results.hits) == 3  # the record itself plus the two claims

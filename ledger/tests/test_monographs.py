"""The monograph record: skeletons, the $EDITOR template, status transitions."""

from __future__ import annotations

import pytest

from ledger.monographs import (
    STATUSES,
    by_name,
    create,
    parse_template,
    render_template,
    set_status,
    update,
)


class TestSkeletons:
    def test_a_new_monograph_is_a_skeleton_with_no_identifiers(self, migrated):
        mono = create(migrated, "Khaya senegalensis", part="stem bark")
        assert mono.status == "skeleton"
        assert mono.accepted_name == "Khaya senegalensis"
        assert mono.part == "stem bark"

        row = migrated.execute("SELECT wfo_id, gbif_key, gbif_confidence FROM monograph").fetchone()
        assert tuple(row) == (None, None, None)

    def test_it_is_found_again_by_name(self, migrated):
        created = create(migrated, "Prunus africana")
        assert by_name(migrated, "Prunus africana") == created
        assert by_name(migrated, "Warburgia ugandensis") is None

    def test_a_name_is_required(self, migrated):
        with pytest.raises(ValueError, match="needs a name"):
            create(migrated, "   ")

    def test_an_unknown_field_is_refused(self, migrated):
        with pytest.raises(ValueError, match="not a monograph field"):
            create(migrated, "Khaya senegalensis", genus="Khaya")


class TestStatus:
    def test_every_named_status_is_reachable(self, migrated):
        mono = create(migrated, "Khaya senegalensis")
        for status in STATUSES:
            assert set_status(migrated, mono.id, status).status == status

    def test_an_invented_status_is_refused(self, migrated):
        mono = create(migrated, "Khaya senegalensis")
        with pytest.raises(ValueError, match="is not a status"):
            set_status(migrated, mono.id, "published")

    def test_a_transition_touches_the_record(self, migrated):
        mono = create(migrated, "Khaya senegalensis")
        migrated.execute("UPDATE monograph SET last_touched = '2020-01-01 00:00:00'")
        set_status(migrated, mono.id, "drafted")
        touched = migrated.execute("SELECT last_touched FROM monograph").fetchone()[0]
        assert touched > "2020-01-01 00:00:00"


class TestTemplate:
    def test_a_skeleton_renders_an_empty_template(self, migrated):
        text = render_template(create(migrated, "Khaya senegalensis"))
        assert text.startswith("# Khaya senegalensis\n")
        for label in ("authority:", "family:", "part:", "habitat:"):
            assert f"\n{label} \n" in text or text.rstrip().endswith(f"{label} ")
        assert "## summary" in text and "## preparation" in text

    def test_a_filled_record_round_trips_through_the_template(self, migrated):
        mono = create(
            migrated,
            "Khaya senegalensis",
            authority="(Desr.) A.Juss.",
            family="Meliaceae",
            part="stem bark",
            habitat_note="African mahogany, dry-savanna belt",
        )
        mono = update(
            migrated,
            mono.id,
            {"summary": "Stem bark is widely traded.", "preparation": "Boiled, reduced by half."},
        )

        parsed = parse_template(render_template(mono))
        assert parsed == {
            "authority": "(Desr.) A.Juss.",
            "family": "Meliaceae",
            "part": "stem bark",
            "habitat_note": "African mahogany, dry-savanna belt",
            "summary": "Stem bark is widely traded.",
            "preparation": "Boiled, reduced by half.",
        }

    def test_multi_paragraph_prose_survives(self, migrated):
        body = "First paragraph.\n\nSecond paragraph, longer.\n\nThird."
        mono = update(migrated, create(migrated, "Khaya senegalensis").id, {"summary": body})
        assert parse_template(render_template(mono))["summary"] == body

    def test_a_blank_field_clears_it(self):
        parsed = parse_template("# Khaya senegalensis\nfamily: \npart: stem bark\n")
        assert parsed["family"] is None
        assert parsed["part"] == "stem bark"

    def test_an_invented_field_is_refused(self):
        with pytest.raises(ValueError, match="not a field of the record"):
            parse_template("# Khaya\ngenus: Khaya\n")

    def test_an_invented_section_is_refused(self):
        with pytest.raises(ValueError, match="not a section of the record"):
            parse_template("# Khaya\n\n## conclusions\n\nProse.\n")

    def test_a_line_that_is_not_a_field_is_refused(self):
        with pytest.raises(ValueError, match="expected `field: value`"):
            parse_template("# Khaya\nthis is just prose\n")


class TestUpdate:
    def test_rewriting_the_summary_stamps_its_date(self, migrated):
        mono = create(migrated, "Khaya senegalensis")
        assert migrated.execute("SELECT summary_rewritten_at FROM monograph").fetchone()[0] is None

        update(migrated, mono.id, {"summary": "First pass."})
        stamped = migrated.execute("SELECT summary_rewritten_at FROM monograph").fetchone()[0]
        assert stamped is not None

    def test_writing_the_same_summary_again_does_not_restamp(self, migrated):
        mono = create(migrated, "Khaya senegalensis")
        update(migrated, mono.id, {"summary": "First pass."})
        migrated.execute("UPDATE monograph SET summary_rewritten_at = '2020-01-01'")

        update(migrated, mono.id, {"summary": "First pass."})
        assert (
            migrated.execute("SELECT summary_rewritten_at FROM monograph").fetchone()[0]
            == "2020-01-01"
        )

    def test_an_unknown_field_is_refused(self, migrated):
        mono = create(migrated, "Khaya senegalensis")
        with pytest.raises(ValueError, match="not a monograph field"):
            update(migrated, mono.id, {"status": "reviewed"})

"""Claim rows, their sources, and the evidence ramp."""

from __future__ import annotations

import sqlite3

import pytest

from ledger.claims import (
    EVIDENCE,
    EVIDENCE_CODE,
    EVIDENCE_RAMP,
    Source,
    add,
    headline_evidence,
    unsourced_by_table,
)
from ledger.monographs import create


@pytest.fixture
def mono(migrated):
    return create(migrated, "Khaya senegalensis", part="stem bark")


class TestEvidence:
    def test_the_six_levels_display_as_e1_to_e6_in_order(self):
        assert [EVIDENCE_CODE[level] for level in EVIDENCE] == [
            "E1", "E2", "E3", "E4", "E5", "E6"
        ]

    def test_six_levels_collapse_onto_four_ramp_steps(self):
        assert [EVIDENCE_RAMP[level] for level in EVIDENCE] == [0, 1, 1, 2, 3, 3]

    def test_the_headline_is_the_maximum_across_indications(self, migrated, mono):
        for level in ("in_vitro", "meta_analysis", "traditional_only"):
            add(migrated, "indication", mono.id, condition=level, evidence=level)
        assert headline_evidence(migrated, mono.id) == "meta_analysis"

    def test_a_record_with_no_indications_has_no_headline(self, migrated, mono):
        assert headline_evidence(migrated, mono.id) is None

    def test_indications_default_to_traditional_only(self, migrated, mono):
        add(migrated, "indication", mono.id, condition="malarial fever")
        assert headline_evidence(migrated, mono.id) == "traditional_only"

    def test_an_invented_evidence_level_is_refused(self, migrated, mono):
        with pytest.raises(sqlite3.IntegrityError):
            add(migrated, "indication", mono.id, condition="x", evidence="anecdote")


class TestSources:
    def test_an_empty_source_reads_the_warning_the_row_shows(self):
        assert str(Source()) == "⚠ source needed"
        assert Source().is_empty is True
        assert Source(note="  ").is_empty is True

    def test_a_reference_source_reads_as_its_row_id(self):
        assert str(Source(reference_id=7)) == "R7"
        assert Source(reference_id=7).is_empty is False

    def test_a_field_record_is_a_source(self):
        assert str(Source(note="field notes 2025-11")) == "field notes 2025-11"
        assert Source(note="field notes 2025-11").is_empty is False


class TestCounts:
    def test_unsourced_counts_are_reported_per_section(self, migrated, mono):
        add(migrated, "vernacular", mono.id, name="kuka")
        add(migrated, "vernacular", mono.id, name="caïlcédrat", source=Source(note="R2"))
        add(migrated, "indication", mono.id, condition="malarial fever")
        add(migrated, "indication", mono.id, condition="dysentery")

        assert unsourced_by_table(migrated, mono.id) == {
            "vernacular": 1,
            "indication": 2,
            "constituent": 0,
            "safety": 0,
        }

    def test_every_section_is_reported_even_when_empty(self, migrated, mono):
        assert unsourced_by_table(migrated, mono.id) == {
            "vernacular": 0,
            "indication": 0,
            "constituent": 0,
            "safety": 0,
        }


class TestFields:
    def test_a_constituent_carries_its_class_and_inchikey(self, migrated, mono):
        add(
            migrated,
            "constituent",
            mono.id,
            compound="khayanthone",
            **{"class": "limonoid"},
            inchikey="ABCDEFGHIJKLMN-OPQRSTUVWX-Y",
            source=Source(note="R5"),
        )
        row = migrated.execute("SELECT compound, class, inchikey FROM constituent").fetchone()
        assert tuple(row) == ("khayanthone", "limonoid", "ABCDEFGHIJKLMN-OPQRSTUVWX-Y")

    def test_an_indication_records_who_used_it_for_what_where(self, migrated, mono):
        add(
            migrated,
            "indication",
            mono.id,
            condition="malarial fever",
            tradition="Hausa",
            region="northern Nigeria",
            source=Source(note="R1"),
        )
        row = migrated.execute("SELECT condition, tradition, region FROM indication").fetchone()
        assert tuple(row) == ("malarial fever", "Hausa", "northern Nigeria")

    def test_severity_is_restricted_to_the_three_chips(self, migrated, mono):
        for severity in ("critical", "caution", "note"):
            add(
                migrated,
                "safety",
                mono.id,
                kind="interaction",
                finding="additive effect",
                severity=severity,
                source=Source(note="R3"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            add(
                migrated, "safety", mono.id, kind="x", finding="y", severity="fatal",
                source=Source(note="R3"),
            )

    def test_an_unknown_field_is_refused(self, migrated, mono):
        with pytest.raises(ValueError, match="not a vernacular field"):
            add(migrated, "vernacular", mono.id, name="kuka", dialect="Kano")

    def test_an_unknown_table_is_refused(self, migrated, mono):
        with pytest.raises(ValueError, match="not a claim table"):
            add(migrated, "folklore", mono.id, name="x")


class TestBenefitSharing:
    def test_one_row_per_monograph(self, migrated, mono):
        migrated.execute(
            "INSERT INTO benefit_sharing (monograph_id, narrative, agreement_ref, expires)"
            " VALUES (?, ?, ?, ?)",
            (mono.id, "Recorded with consent in 2025.", "MTA-2025-014", "2028-06"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            migrated.execute(
                "INSERT INTO benefit_sharing (monograph_id, narrative) VALUES (?, ?)",
                (mono.id, "A second agreement."),
            )

    def test_it_goes_when_the_record_goes(self, migrated, mono):
        migrated.execute(
            "INSERT INTO benefit_sharing (monograph_id, agreement_ref) VALUES (?, ?)",
            (mono.id, "MTA-2025-014"),
        )
        migrated.execute("DELETE FROM monograph WHERE id = ?", (mono.id,))
        assert migrated.execute("SELECT count(*) FROM benefit_sharing").fetchone()[0] == 0


def test_claim_rows_go_when_the_record_goes(migrated, mono):
    add(migrated, "vernacular", mono.id, name="kuka")
    add(migrated, "indication", mono.id, condition="malarial fever")
    migrated.execute("DELETE FROM monograph WHERE id = ?", (mono.id,))

    for table in ("vernacular", "indication"):
        assert migrated.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0

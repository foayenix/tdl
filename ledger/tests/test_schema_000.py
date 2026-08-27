"""What 000_init.sql refuses. The three enums are contract (BUILD.md §4)."""

from __future__ import annotations

import sqlite3

import pytest


def test_status_is_restricted_to_the_four_named_values(migrated):
    for status in ("skeleton", "drafted", "sourced", "reviewed"):
        migrated.execute("INSERT INTO monograph (status) VALUES (?)", (status,))

    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute("INSERT INTO monograph (status) VALUES ('published')")


def test_a_new_monograph_is_a_skeleton(migrated):
    migrated.execute("INSERT INTO monograph (id) VALUES (1)")
    row = migrated.execute("SELECT status, accepted_name FROM monograph").fetchone()
    assert row["status"] == "skeleton"
    assert row["accepted_name"] is None


def test_read_state_is_restricted_and_defaults_to_queued(migrated):
    migrated.execute("INSERT INTO reference (title) VALUES ('A paper')")
    assert migrated.execute("SELECT read_state FROM reference").fetchone()[0] == "queued"

    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(
            "INSERT INTO reference (title, read_state) VALUES ('B', 'skimmed')"
        )


def test_output_kind_is_restricted_to_the_five_the_wall_counts(migrated):
    for kind in ("paper", "talk", "long-form", "release", "note"):
        migrated.execute(
            "INSERT INTO output (kind, title, date) VALUES (?, ?, ?)",
            (kind, f"{kind} title", "2026-08-24"),
        )

    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(
            "INSERT INTO output (kind, title, date) VALUES ('tweet', 'x', '2026-08-24')"
        )


def test_a_day_is_logged_once(migrated):
    migrated.execute("INSERT INTO entry (date) VALUES ('2026-08-24')")
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute("INSERT INTO entry (date) VALUES ('2026-08-24')")


def test_minutes_cannot_go_negative(migrated):
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute("INSERT INTO entry (date, minutes) VALUES ('2026-08-25', -1)")


def test_a_doi_is_recorded_once(migrated):
    migrated.execute(
        "INSERT INTO reference (doi, title) VALUES ('10.1016/j.jep.2019.112202', 'A')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(
            "INSERT INTO reference (doi, title) VALUES ('10.1016/j.jep.2019.112202', 'B')"
        )


def test_references_without_an_identifier_are_allowed_for_now(migrated):
    """See STATE.md session 02 — whether this should be refused is an open question."""
    migrated.execute("INSERT INTO reference (title) VALUES ('A field notebook')")
    migrated.execute("INSERT INTO reference (title) VALUES ('Another field notebook')")
    assert migrated.execute("SELECT count(*) FROM reference").fetchone()[0] == 2


def test_an_output_points_at_the_entry_it_was_deposited_against(migrated):
    with pytest.raises(sqlite3.IntegrityError):
        migrated.execute(
            "INSERT INTO output (kind, title, date, entry_id)"
            " VALUES ('note', 'x', '2026-08-24', 999)"
        )

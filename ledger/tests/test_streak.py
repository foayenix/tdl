"""§7 test 7 — the streak query. Never delete this test.

No entries · one entry · gap yesterday · gap today · entries out of order.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from ledger.entries import current_streak, log, run_length

TODAY = date(2026, 8, 24)


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


def write(conn, *offsets: int) -> None:
    """Log entries by how many days back they are, in the order given."""
    for offset in offsets:
        log(conn, on=days_ago(offset), minutes=30)


def test_no_entries(migrated):
    assert run_length(migrated) == 0
    assert current_streak(migrated, today=TODAY) == 0


def test_one_entry_today(migrated):
    write(migrated, 0)
    assert current_streak(migrated, today=TODAY) == 1


def test_an_unbroken_run_ending_today(migrated):
    write(migrated, 4, 3, 2, 1, 0)
    assert current_streak(migrated, today=TODAY) == 5


def test_gap_yesterday(migrated):
    """Logged today, nothing yesterday, a long run before that. Streak is 1."""
    write(migrated, 6, 5, 4, 3, 2, 0)
    assert current_streak(migrated, today=TODAY) == 1


def test_gap_today(migrated):
    """Logged through yesterday, nothing yet today. The run is still live."""
    write(migrated, 3, 2, 1)
    assert current_streak(migrated, today=TODAY) == 3


def test_the_streak_is_zero_once_the_run_is_broken(migrated):
    """Artboard 08 state 5: three days without an entry reads 0, not 41."""
    write(migrated, *range(6, 3, -1))
    assert run_length(migrated) == 3
    assert current_streak(migrated, today=TODAY) == 0


def test_entries_out_of_order(migrated):
    write(migrated, 0, 3, 1, 4, 2)
    assert current_streak(migrated, today=TODAY) == 5


def test_a_run_before_a_gap_does_not_count_toward_the_current_one(migrated):
    write(migrated, 10, 9, 8, 7, 1, 0)
    assert current_streak(migrated, today=TODAY) == 2


def test_a_single_entry_long_ago(migrated):
    write(migrated, 90)
    assert run_length(migrated) == 1
    assert current_streak(migrated, today=TODAY) == 0


class TestLogging:
    def test_a_day_opens_once_then_accumulates(self, migrated):
        first = log(migrated, on="2026-08-24", minutes=40, note="Khaya bark")
        assert first.created is True
        assert first.minutes == 40

        second = log(migrated, on="2026-08-24", minutes=56, note="three refs")
        assert second.created is False
        assert second.minutes == 96
        assert second.note == "Khaya bark\nthree refs"

        assert migrated.execute("SELECT count(*) FROM entry").fetchone()[0] == 1

    def test_the_floor_is_twenty_minutes(self, migrated):
        assert log(migrated, on="2026-08-24", minutes=20).met_floor is True
        assert log(migrated, on="2026-08-23", minutes=19).met_floor is False

    def test_the_floor_flag_sticks_until_it_is_changed(self, migrated):
        assert log(migrated, on="2026-08-24", minutes=20, floor_day=True).floor_day is True
        assert log(migrated, on="2026-08-24", minutes=5).floor_day is True
        assert log(migrated, on="2026-08-24", floor_day=False).floor_day is False

    def test_negative_minutes_are_refused(self, migrated):
        with pytest.raises(ValueError, match="negative"):
            log(migrated, on="2026-08-24", minutes=-5)

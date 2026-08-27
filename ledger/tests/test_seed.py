"""`ledger seed` — bulk skeletons from a CSV, and nothing more general than that."""

from __future__ import annotations

import pytest

from ledger.monographs import by_name, create
from ledger.seed import read_rows, seed


@pytest.fixture
def csv_file(tmp_path):
    def write(text: str):
        path = tmp_path / "plants.csv"
        path.write_text(text, encoding="utf-8")
        return path

    return write


def test_a_skeleton_is_opened_for_every_named_plant(migrated, csv_file):
    path = csv_file(
        "name,family,part\n"
        "Khaya senegalensis,Meliaceae,stem bark\n"
        "Prunus africana,Rosaceae,stem bark\n"
    )
    report = seed(migrated, path)

    assert report.opened == ["Khaya senegalensis", "Prunus africana"]
    assert report.read == 2

    mono = by_name(migrated, "Khaya senegalensis")
    assert (mono.family, mono.part, mono.status) == ("Meliaceae", "stem bark", "skeleton")


def test_a_plant_already_in_the_corpus_is_left_alone(migrated, csv_file):
    create(migrated, "Khaya senegalensis", family="Meliaceae")
    path = csv_file("name,family\nKhaya senegalensis,WRONG\nPrunus africana,Rosaceae\n")

    report = seed(migrated, path)

    assert report.opened == ["Prunus africana"]
    assert report.already_present == ["Khaya senegalensis"]
    assert by_name(migrated, "Khaya senegalensis").family == "Meliaceae"


def test_a_dry_run_writes_nothing(migrated, csv_file):
    path = csv_file("name\nKhaya senegalensis\n")
    report = seed(migrated, path, dry_run=True)

    assert report.opened == ["Khaya senegalensis"]
    assert migrated.execute("SELECT count(*) FROM monograph").fetchone()[0] == 0


def test_a_row_with_no_name_is_skipped_and_reported(migrated, csv_file):
    path = csv_file("name,family\n,Meliaceae\nPrunus africana,Rosaceae\n")
    report = seed(migrated, path)

    assert report.opened == ["Prunus africana"]
    assert report.skipped == [(2, "no name")]


def test_headers_the_editor_template_writes_are_understood(migrated, csv_file):
    path = csv_file(
        "species,author,habitat\n"
        "Khaya senegalensis,(Desr.) A.Juss.,dry-savanna belt\n"
    )
    seed(migrated, path)

    mono = by_name(migrated, "Khaya senegalensis")
    assert mono.authority == "(Desr.) A.Juss."
    assert mono.habitat_note == "dry-savanna belt"


def test_columns_it_does_not_know_are_ignored_not_refused(migrated, csv_file):
    path = csv_file("name,my_own_note\nKhaya senegalensis,check the trade figures\n")
    seed(migrated, path)
    assert by_name(migrated, "Khaya senegalensis") is not None


def test_a_file_with_no_name_column_is_refused(migrated, csv_file):
    path = csv_file("family,part\nMeliaceae,stem bark\n")
    with pytest.raises(ValueError, match="no name column"):
        seed(migrated, path)


def test_an_empty_file_is_refused(migrated, csv_file):
    with pytest.raises(ValueError, match="empty"):
        read_rows(csv_file(""))


def test_a_missing_file_is_an_oserror(migrated, tmp_path):
    with pytest.raises(OSError):
        seed(migrated, tmp_path / "nothing.csv")


def test_whitespace_around_values_is_trimmed(migrated, csv_file):
    path = csv_file("name, family \n  Khaya senegalensis  , Meliaceae \n")
    seed(migrated, path)
    assert by_name(migrated, "Khaya senegalensis").family == "Meliaceae"

"""§7 test 6 — Crossref parsing, never against the live network. Never delete this.

One live test sits at the bottom marked `@pytest.mark.network`; `pyproject.toml`
excludes that marker, so `just check` never touches the network.

**The fixture is a shape fixture, not a recording** — see
`fixtures/README.md`. This environment's egress proxy refuses
`api.crossref.org` (403 on CONNECT, an organisation policy denial), and
inventing a paper and a DOI is exactly what §8 forbids. It uses Crossref's own
`10.5555` test prefix and placeholder strings, and must be replaced with a real
recording before v0.1.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from ledger.crossref import (
    CrossrefError,
    NotFound,
    Offline,
    fetch,
    lookup,
    normalise_doi,
    parse,
)

FIXTURES = Path(__file__).parent / "fixtures"

# The DOI from BUILD.md §5, used only by the live test.
LIVE_DOI = "10.1016/j.jep.2019.112202"


@pytest.fixture
def shape():
    return json.loads((FIXTURES / "crossref_shape.json").read_text())


class TestNormalisation:
    @pytest.mark.parametrize(
        "raw",
        [
            "10.1016/j.jep.2019.112202",
            "  10.1016/j.jep.2019.112202  ",
            "10.1016/J.JEP.2019.112202",
            "doi:10.1016/j.jep.2019.112202",
            "DOI: 10.1016/j.jep.2019.112202",
            "https://doi.org/10.1016/j.jep.2019.112202",
            "http://dx.doi.org/10.1016/j.jep.2019.112202",
            "doi.org/10.1016/j.jep.2019.112202",
            "10.1016/j.jep.2019.112202.",
        ],
    )
    def test_every_way_a_doi_gets_pasted_lands_on_one_string(self, raw):
        assert normalise_doi(raw) == "10.1016/j.jep.2019.112202"

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "not a doi", "10.1/x", "11.1016/j.jep.2019.112202", "10.1016", None],
    )
    def test_what_is_not_a_doi_is_refused(self, raw):
        with pytest.raises(ValueError, match="is not a DOI"):
            normalise_doi(raw)

    def test_case_only_differences_do_not_make_two_papers(self):
        assert normalise_doi("10.1016/ABC") == normalise_doi("10.1016/abc")


class TestParsing:
    def test_the_fields_the_library_stores_come_out(self, shape):
        assert parse(shape) == {
            "doi": "10.5555/shape.fixture.001",
            "title": "PLACEHOLDER TITLE — not a real paper",
            "authors": "A. PLACEHOLDER-ONE; B. PLACEHOLDER-TWO",
            "journal": "PLACEHOLDER JOURNAL",
            "volume": "241",
            "year": 2019,
            "type": "journal-article",
        }

    def test_the_parsed_doi_is_normalised(self, shape):
        assert parse(shape)["doi"] == shape["message"]["DOI"].lower()

    def test_access_is_not_guessed(self, shape):
        """Crossref has no dependable open/closed field; a guess would be a wrong answer."""
        assert "access" not in parse(shape)

    def test_a_work_with_no_authors_parses(self, shape):
        del shape["message"]["author"]
        assert parse(shape)["authors"] is None

    def test_an_author_with_only_an_organisation_name_parses(self, shape):
        shape["message"]["author"] = [{"name": "PLACEHOLDER CONSORTIUM"}]
        assert parse(shape)["authors"] == "PLACEHOLDER CONSORTIUM"

    def test_the_year_falls_back_when_issued_is_missing(self, shape):
        del shape["message"]["issued"]
        assert parse(shape)["year"] == 2019

    def test_a_work_with_no_date_at_all_parses(self, shape):
        for key in ("issued", "published-print", "created"):
            shape["message"].pop(key, None)
        assert parse(shape)["year"] is None

    def test_a_work_with_no_title_falls_back_to_its_doi(self, shape):
        shape["message"]["title"] = []
        assert parse(shape)["title"] == "10.5555/SHAPE.FIXTURE.001"

    def test_a_response_with_no_work_is_an_error(self):
        with pytest.raises(CrossrefError, match="no work"):
            parse({"status": "ok"})

    def test_a_work_with_no_doi_is_an_error(self, shape):
        del shape["message"]["DOI"]
        with pytest.raises(CrossrefError, match="carries no DOI"):
            parse(shape)


class TestFailureModes:
    """Network calls fail; the tool has to say which way (BUILD.md §3)."""

    def _urlopen(self, monkeypatch, raiser):
        monkeypatch.setattr("ledger.crossref.urllib.request.urlopen", raiser)

    def test_a_missing_doi_is_not_the_same_as_being_offline(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise urllib.error.HTTPError("url", 404, "Not Found", {}, None)

        self._urlopen(monkeypatch, raiser)
        with pytest.raises(NotFound):
            fetch("10.1016/j.jep.2019.112202")

    def test_no_network_raises_offline(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise urllib.error.URLError("Name or service not known")

        self._urlopen(monkeypatch, raiser)
        with pytest.raises(Offline, match="could not reach Crossref"):
            fetch("10.1016/j.jep.2019.112202")

    def test_a_timeout_raises_offline(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise TimeoutError("timed out")

        self._urlopen(monkeypatch, raiser)
        with pytest.raises(Offline):
            fetch("10.1016/j.jep.2019.112202")

    def test_a_server_error_is_neither(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise urllib.error.HTTPError("url", 503, "Service Unavailable", {}, None)

        self._urlopen(monkeypatch, raiser)
        with pytest.raises(CrossrefError, match="503"):
            fetch("10.1016/j.jep.2019.112202")

    def test_a_non_json_answer_is_an_error(self, monkeypatch):
        class Response:
            def read(self):
                return b"<html>maintenance</html>"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        self._urlopen(monkeypatch, lambda *a, **k: Response())
        with pytest.raises(CrossrefError, match="did not answer with JSON"):
            fetch("10.1016/j.jep.2019.112202")

    def test_a_bad_doi_never_reaches_the_network(self, monkeypatch):
        def raiser(*args, **kwargs):
            raise AssertionError("the network should not have been touched")

        self._urlopen(monkeypatch, raiser)
        with pytest.raises(ValueError, match="is not a DOI"):
            fetch("not a doi")


@pytest.mark.network
def test_the_parser_holds_against_the_live_api():
    """The one live test. Excluded from `just check` by the `network` marker.

    Run it with `pytest -m network ledger/tests` on a connected machine. It is
    also the quickest way to capture the real recording the fixture above is
    standing in for.
    """
    record = lookup(LIVE_DOI)

    assert record["doi"] == LIVE_DOI
    assert record["title"]
    assert record["year"]
    assert record["type"]

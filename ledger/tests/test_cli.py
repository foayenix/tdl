"""The CLI spine: it parses, it reports a version, it exits non-zero bare."""

import pytest

from ledger import __version__
from ledger.cli import build_parser, main


def test_version_flag_reports_the_package_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"ledger {__version__}"


def test_bare_invocation_prints_help_and_fails(capsys):
    assert main([]) == 1
    assert "The Deposit Ledger" in capsys.readouterr().out


def test_unknown_subcommand_is_rejected():
    with pytest.raises(SystemExit) as exit_info:
        main(["definitely-not-a-verb"])
    assert exit_info.value.code == 2

import logging

import pytest

from ss_track.cli import build_parser, main
from ss_track.commands.report import EXIT_REFUSED, reported
from tests.corpus.conftest import last_record


def test_parser_selects_the_info_command() -> None:
    assert build_parser().parse_args(["info"]).command == "info"


def test_info_command_logs_the_project_identity(caplog) -> None:  # type: ignore[no-untyped-def]
    caplog.set_level(logging.INFO)

    assert main(["info"]) == 0
    assert "ss-track" in caplog.text
    assert "ss_track" in caplog.text


def test_parser_selects_the_corpus_commands() -> None:
    assert build_parser().parse_args(["import", "--source", "a.yaml"]).command == "import"
    parsed = build_parser().parse_args(["corpus", "build", "--manifest", "b.yaml"])
    assert (parsed.command, parsed.corpus_command) == ("corpus", "build")
    for action in ("stage", "verify"):
        parsed = build_parser().parse_args(["corpus", action, "--corpus", "c1"])
        assert (parsed.corpus_command, parsed.corpus) == (action, "c1")


def _raise_interrupt(*_args: object, **_kwargs: object) -> None:
    raise KeyboardInterrupt


def test_sigint_is_one_json_refusal(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)

    assert reported(_raise_interrupt) == EXIT_REFUSED

    assert last_record(caplog) == {
        "status": "refused",
        "code": "INTERRUPTED",
        "message": "interrupted by SIGINT",
        "details": {},
    }


def test_a_second_sigint_while_reporting_still_exits(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    monkeypatch.setattr("ss_track.commands.report.log_json", _raise_interrupt)

    assert reported(_raise_interrupt) == EXIT_REFUSED

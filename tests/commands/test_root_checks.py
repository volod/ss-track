"""Every command that takes the data root holds it to the installed contracts before any work.

Spec section 17.7: a root with sealed evidence and no stamp, or one stamped under another
development contract set, is refused with `RECORD_SCHEMA_UNSUPPORTED` before a command reads or
writes. The sweep builds each command from the parser, so a new command is held to the check
unless `EXEMPT` names it with the reason it takes no data root.
"""

import argparse
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from ss_track.cli import build_parser, main
from ss_track.commands.report import EXIT_REFUSED
from ss_track.core.evidence.contract_stamp import installed_fingerprints, installed_meanings
from ss_track.core.evidence.stamp_file import STAMP_NAME, write_stamp
from tests.corpus.conftest import last_record
from tests.corpus.records._unstamped import place_record

EXEMPT = {
    ("info",): "reports the installed tool",
    ("contracts", "list"): "reads the contract set only",
    ("contracts", "validate"): "gives a verdict on one file and serves no evidence",
    ("contracts", "diff"): "reads the contract set and a candidate",
    ("contracts", "freeze"): "writes the contract set",
    ("contracts", "export"): "writes generated views of the contract set",
    ("contracts", "docs"): "writes generated views of the contract set",
    ("discover", "inventory"): "turns a provider listing into a declaration; no sealed record",
    ("discover", "review-unpack"): "extracts operator recipes after the archive's own pin check",
    ("discover", "review-audit"): "an operator's interactive review of a blinded packet",
    ("annotate", "validate"): "reads operator documents and media",
    ("annotate", "compare"): "reads operator documents and media",
    (
        "annotate",
        "freeze",
    ): "by paths, checks the root when an output lands in it (explicit-path test)",
    ("data", "clean"): "housekeeping that reads no record still runs on a stale root",
}
_STALE = "record/frame-set"


def _commands(
    parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], argparse.ArgumentParser]]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, child in action.choices.items():
                yield from _commands(child, (*prefix, name))
            return
    yield prefix, parser


COMMANDS = dict(_commands(build_parser()))


def _value(action: argparse.Action, outside: Path) -> str:
    if action.choices:
        return str(next(iter(action.choices)))
    if action.type is Path:
        return str(outside / action.dest)
    return "1" if action.type is int else "x"


def _argv(command: tuple[str, ...], outside: Path) -> list[str]:
    """Fill every required argument, every path outside the data root."""
    parser = COMMANDS[command]
    chosen = [
        group._group_actions[0] for group in parser._mutually_exclusive_groups if group.required
    ]
    argv = list(command)
    for action in parser._actions:
        if action.required or action in chosen:
            value = _value(action, outside)
            argv += [action.option_strings[0], value] if action.option_strings else [value]
    return argv


def test_every_exemption_names_a_command() -> None:
    assert set(EXEMPT) <= set(COMMANDS)
    assert all(reason for reason in EXEMPT.values())


@pytest.fixture(params=["unstamped", "stale"])
def refused_root(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> Path:
    """A root with sealed evidence that is unstamped or stamped under another contract set."""
    caplog.set_level(logging.INFO)
    root = tmp_path / "data"
    place_record(root / "corpus" / "old" / "record.json")
    if request.param == "stale":
        structures, meanings = installed_fingerprints(), installed_meanings()
        assert structures is not None and meanings is not None
        write_stamp(root / STAMP_NAME, structures | {_STALE: "0" * 64}, meanings)
    monkeypatch.setenv("DATA_DIR", str(root))
    return root


@pytest.mark.parametrize(
    "command", sorted(set(COMMANDS) - set(EXEMPT)), ids=lambda command: " ".join(command)
)
def test_a_root_taking_command_refuses_a_root_it_cannot_trust_before_any_work(
    refused_root: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture, command: tuple[str, ...]
) -> None:
    before = {path: path.read_bytes() for path in refused_root.rglob("*") if path.is_file()}

    assert main(_argv(command, tmp_path / "outside")) == EXIT_REFUSED

    record = last_record(caplog)
    assert record["code"] == "RECORD_SCHEMA_UNSUPPORTED"
    details = record["details"]
    assert isinstance(details, dict)
    assert "regenerate" in str(details["remedy"])
    after = {path: path.read_bytes() for path in refused_root.rglob("*") if path.is_file()}
    assert after == before

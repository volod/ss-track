"""One command walks an unstamped root as few times as safety allows (spec section 17.7)."""

import contextvars
import json
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_OK, EXIT_REFUSED
from ss_track.core.evidence import contract_stamp
from ss_track.core.evidence.checked_roots import one_command
from ss_track.core.evidence.contract_stamp import (
    installed_fingerprints,
    installed_meanings,
    require_current_data_root,
    stamp_before_write,
)
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.evidence.sealing import write_sealed
from ss_track.core.evidence.stamp_file import STAMP_NAME, write_stamp
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.records.kinds import FRAME_SET
from tests.corpus.conftest import WriteRecording, last_record
from tests.corpus.records._unstamped import place_record
from tests.schema.conftest import KEPT_FRAME_SET


@pytest.fixture
def walks(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Count every full walk of an unstamped root."""
    walked: list[Path] = []
    real = contract_stamp.first_unstamped_record

    def counted(root: Path) -> Path | None:
        walked.append(root)
        return real(root)

    monkeypatch.setattr(contract_stamp, "first_unstamped_record", counted)
    return walked


def _operator_root(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "declaration.yaml").write_text("schema_version: 1\n")
    return root


def _refused(action: object) -> CorpusRefusal:
    assert callable(action)
    with pytest.raises(CorpusRefusal) as caught:
        action()
    assert caught.value.code == RefusalCode.RECORD_SCHEMA_UNSUPPORTED
    return caught.value


@pytest.mark.parametrize("command", ["stage", "verify", "build"])
def test_a_read_only_command_walks_once(
    cli_root: Path, walks: list[Path], caplog: pytest.LogCaptureFixture, command: str
) -> None:
    """The CLI check, the operation check and the manifest reader each walked: three before."""
    _operator_root(cli_root)
    argv = {
        "stage": ["corpus", "stage", "--corpus", "absent"],
        "verify": ["corpus", "verify", "--corpus", "absent"],
        "build": ["corpus", "build", "--manifest", str(cli_root / "declaration.yaml")],
    }[command]
    assert main(argv) == EXIT_REFUSED
    assert last_record(caplog)["code"] != "RECORD_SCHEMA_UNSUPPORTED"
    assert len(walks) == 1
    assert not (cli_root / STAMP_NAME).exists()


def test_a_first_write_walks_at_the_check_and_under_the_lock(
    clip: Path,
    write_recording: WriteRecording,
    cli_root: Path,
    walks: list[Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The operation check reuses the CLI walk; the locked first-stamp walk stays: three before."""
    _operator_root(cli_root)
    assert main(["import", "--source", str(write_recording())]) == EXIT_OK
    assert last_record(caplog)["status"] == "imported"
    assert len(walks) == 2
    assert (cli_root / STAMP_NAME).is_file()
    walks.clear()
    assert main(["import", "--source", str(write_recording())]) == EXIT_OK
    assert walks == []


def test_unstamped_evidence_still_refuses_a_command_after_reuse(
    cli_root: Path, walks: list[Path], caplog: pytest.LogCaptureFixture
) -> None:
    place_record(_operator_root(cli_root) / "old" / "record.json")
    assert main(["corpus", "stage", "--corpus", "absent"]) == EXIT_REFUSED
    assert last_record(caplog)["code"] == "RECORD_SCHEMA_UNSUPPORTED"
    assert len(walks) == 1


def test_outside_a_command_every_check_walks(tmp_path: Path, walks: list[Path]) -> None:
    root = _operator_root(tmp_path / "data")
    require_current_data_root(root)
    evidence = place_record(root / "late.json")
    _refused(lambda: require_current_data_root(root))
    assert len(walks) == 2
    assert evidence.is_file() and not (root / STAMP_NAME).exists()


def test_a_reused_check_still_refuses_a_late_record_at_its_read_and_its_write(
    tmp_path: Path, walks: list[Path]
) -> None:
    """A record arriving after the walk is caught where it matters, with no second read walk."""
    root = _operator_root(tmp_path / "data")
    with one_command():
        require_current_data_root(root)
        late = place_record(root / "late.json")
        require_current_data_root(root)
        assert len(walks) == 1
        refusal = _refused(lambda: read_sealed(late, FRAME_SET))
        assert refusal.details["record"] == str(late)
        assert len(walks) == 1
        _refused(lambda: stamp_before_write(root / "new.json"))
        assert len(walks) == 2
    assert not (root / STAMP_NAME).exists()


def test_a_read_ends_reuse(tmp_path: Path, walks: list[Path]) -> None:
    root = _operator_root(tmp_path / "data")
    (root / "notes.json").write_text(json.dumps({"kind": "operator note"}))
    with one_command():
        require_current_data_root(root)
        with pytest.raises(CorpusRefusal) as caught:
            read_sealed(root / "notes.json", FRAME_SET)
        assert caught.value.code == RefusalCode.RECORD_TAMPERED
        require_current_data_root(root)
    assert len(walks) == 2


def test_a_nested_write_ends_reuse_for_the_enclosing_root(
    tmp_path: Path, walks: list[Path]
) -> None:
    outer = _operator_root(tmp_path / "outer")
    inner = outer / "inner"
    with one_command():
        require_current_data_root(outer)
        require_current_data_root(inner)
        write_sealed(inner / "record.json", json.loads(KEPT_FRAME_SET.read_text()))
        assert (inner / STAMP_NAME).is_file()
        refusal = _refused(lambda: require_current_data_root(outer))
    assert refusal.details["record"] == str(inner / "record.json")
    assert len(walks) == 4  # outer, inner, inner under the lock, outer again


def test_a_stamp_written_since_the_walk_is_verified_not_reused(
    tmp_path: Path, walks: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _operator_root(tmp_path / "data")
    installed, meanings = installed_fingerprints(), installed_meanings()
    assert installed is not None and meanings is not None
    with one_command():
        require_current_data_root(root)
        write_stamp(root / STAMP_NAME, installed | {"record/frame-set": "0" * 64}, meanings)
        refusal = _refused(lambda: require_current_data_root(root))
    assert refusal.details["changed_contracts"] == ["record/frame-set"]
    assert len(walks) == 1


def test_a_record_another_command_stamped_and_wrote_is_served(
    tmp_path: Path, walks: list[Path]
) -> None:
    root = _operator_root(tmp_path / "data")
    record = root / "record.json"

    def another_command() -> None:
        with one_command():
            require_current_data_root(root)
            write_sealed(record, json.loads(KEPT_FRAME_SET.read_text()))

    with one_command():
        require_current_data_root(root)
        contextvars.Context().run(another_command)
        assert read_sealed(record, FRAME_SET)["kind"] == FRAME_SET.kind
        require_current_data_root(root)
    assert len(walks) == 3  # this check, the other command's check and its locked first stamp

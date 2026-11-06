"""SIGINT and a decode past its limit end as one refusal and leave no partial bytes."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_REFUSED
from ss_track.core.refusal import RefusalCode
from ss_track.corpus import CorpusRefusal, build_corpus, redecode_source
from ss_track.corpus.decoding import deadline
from ss_track.corpus.decoding.deadline import DECODE_LIMIT_SECONDS
from ss_track.corpus.sources.importer import ImportResult
from tests.corpus.conftest import WriteCorpus, WriteRecording, last_record, stream_of

_CORPUS = "pilot-v1"
_PAST = float(DECODE_LIMIT_SECONDS + 5)

_SIGINT = """
    import os
    import signal
    import sys

    from ss_track.cli import main
    from ss_track.corpus.decoding.decode import inspect_media

    def _stop(on_frame):
        def inner(index, frame):
            os.kill(os.getpid(), signal.SIGINT)
            on_frame(index, frame)
        return inner

    def _interrupt(path, policy, on_frame=lambda *_args: None, **kwargs):
        return inspect_media(path, policy, _stop(on_frame), **kwargs)

    target = __import__(sys.argv[1], fromlist=["inspect_media"])
    target.inspect_media = _interrupt
    sys.exit(main(sys.argv[2:]))
"""


def _past_limit() -> deadline.Clock:
    calls = {"count": 0}

    def clock() -> float:
        calls["count"] += 1
        return 0 if calls["count"] == 1 else _PAST

    return clock


def _run(data_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_SIGINT), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        env={"DATA_DIR": str(data_root), "PATH": os.environ.get("PATH", "")},
    )


def _interrupted(run: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert run.returncode == EXIT_REFUSED
    assert run.stdout == ""
    assert "Traceback" not in run.stderr
    assert "KeyboardInterrupt" not in run.stderr
    lines = [line for line in run.stderr.splitlines() if line]
    assert len(lines) == 1
    record: dict[str, object] = json.loads(lines[0])
    assert record["status"] == "refused"
    assert record["code"] == "INTERRUPTED"
    assert record["details"] == {}
    return record


def _frames(data_root: Path) -> Path:
    return data_root / "corpus" / _CORPUS / "frames"


def test_an_import_past_its_limit_is_one_refusal_and_leaves_no_scratch(
    clip: Path,
    write_recording: WriteRecording,
    cli_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(deadline, "decode_clock", _past_limit())

    assert main(["import", "--source", str(write_recording())]) == EXIT_REFUSED

    record = last_record(caplog)
    assert record["code"] == "DECODE_TIME_EXCEEDED"
    assert record["details"] == {
        "elapsed_seconds": DECODE_LIMIT_SECONDS + 5,
        "frames_decoded": 0,
        "limit_seconds": DECODE_LIMIT_SECONDS,
    }
    assert list((cli_root / "import").iterdir()) == []


def test_a_stage_past_its_limit_is_one_refusal_and_leaves_no_scratch(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    cli_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), cli_root)
    monkeypatch.setattr(deadline, "decode_clock", _past_limit())

    assert main(["corpus", "stage", "--corpus", _CORPUS]) == EXIT_REFUSED

    details = last_record(caplog)["details"]
    assert isinstance(details, dict)
    assert details["elapsed_seconds"] == DECODE_LIMIT_SECONDS + 5
    assert list(_frames(cli_root).glob(".incoming-*")) == []
    assert not (_frames(cli_root) / "one").exists()


def test_a_redecode_past_its_limit_keeps_the_imported_record(
    imported: ImportResult,
    write_recording: WriteRecording,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = imported.manifest_path.read_bytes()
    monkeypatch.setattr(deadline, "decode_clock", _past_limit())

    with pytest.raises(CorpusRefusal) as caught:
        redecode_source(write_recording(), data_root)

    assert caught.value.code is RefusalCode.DECODE_TIME_EXCEEDED
    assert caught.value.details["elapsed_seconds"] == DECODE_LIMIT_SECONDS + 5
    assert imported.manifest_path.read_bytes() == before
    assert list(imported.manifest_path.parent.glob(".incoming-*")) == []


def test_sigint_during_import_exits_with_one_refusal_and_no_scratch(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    run = _run(
        data_root,
        "ss_track.corpus.sources.importer",
        "import",
        "--source",
        str(write_recording()),
    )

    _interrupted(run)
    assert list((data_root / "import").iterdir()) == []


def test_sigint_during_stage_exits_with_one_refusal_and_no_scratch(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    run = _run(
        data_root,
        "ss_track.corpus.bundles.bundle_writer",
        "corpus",
        "stage",
        "--corpus",
        _CORPUS,
    )

    _interrupted(run)
    assert list(_frames(data_root).glob(".incoming-*")) == []
    assert not (_frames(data_root) / "one").exists()

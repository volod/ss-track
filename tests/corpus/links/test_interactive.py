"""The terminal review preserves human decisions through navigation and interruption."""

import io
import os
import pty
import subprocess
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.links import interactive
from ss_track.corpus.links.decisions import read_decisions
from ss_track.corpus.links.interactive import conduct_review
from ss_track.corpus.storage.layout import discovery_run_directory
from ss_track.corpus.storage.scratch import exclusive_lock

A, B, C, D = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)


def _link(first: str, second: str) -> dict[str, object]:
    return {
        "sources": [{"source_sha256": first}, {"source_sha256": second}],
        "evidence": [{"method": "luma-grid-16", "similarity": 0.95}],
    }


LINKS = [_link(A, B), _link(A, C), _link(C, D)]


def _run(path: Path, text: str, output: io.StringIO, played: list[str]) -> int:
    def play(identity: str) -> bool:
        played.append(identity)
        return True

    return conduct_review(LINKS, "Reviewer", path, io.StringIO(text), output, lambda x: x, play)


def test_navigation_skip_edit_play_and_resume(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    output = io.StringIO()
    played: list[str] = []
    assert _run(path, "a\nr\nsame session\nn\nu\nseparate dates\nq\n", output, played) == 2
    assert played == [A]
    assert "Recording relationship review" in output.getvalue()
    assert "Pair 3/3" in output.getvalue()
    assert set(read_decisions(path).by_pair) == {(A, B), (C, D)}

    resumed = io.StringIO()
    assert _run(path, "p\nu\nnew evidence\nq\n", resumed, []) == 2
    assert "Pair 2/3" in resumed.getvalue()
    assert read_decisions(path).by_pair[(A, B)].decision == "unrelated"
    assert read_decisions(path).by_pair[(A, B)].note == "new evidence"
    assert _run(path, "j\n3\nc\nq\n", io.StringIO(), []) == 1
    assert set(read_decisions(path).by_pair) == {(A, B)}


def test_eof_and_unknown_input_never_create_decisions(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    output = io.StringIO()
    assert _run(path, "z\nn\np\n", output, []) == 0
    assert "Unknown action" in output.getvalue()
    assert not path.exists()


def test_interrupt_after_decision_keeps_checkpoint(tmp_path: Path) -> None:
    class Interrupted(io.StringIO):
        def readline(self, *args: object, **kwargs: object) -> str:
            value = super().readline()
            if not value:
                raise KeyboardInterrupt
            return value

    path = tmp_path / "decisions.yaml"
    with pytest.raises(KeyboardInterrupt):
        conduct_review(
            LINKS,
            "Reviewer",
            path,
            Interrupted("r\nevidence\n"),
            io.StringIO(),
            lambda x: x,
            lambda x: True,
        )
    assert read_decisions(path).by_pair[(A, B)].decision == "related"


def test_locked_recording_is_neither_described_nor_played(tmp_path: Path) -> None:
    link = {
        "sources": [
            {"source_sha256": A, "split": "development"},
            {"source_sha256": B, "split": "locked"},
        ],
        "evidence": [],
    }
    described: list[str] = []
    played: list[str] = []

    def describe(identity: str) -> str:
        described.append(identity)
        return identity

    def play(identity: str) -> bool:
        played.append(identity)
        return True

    output = io.StringIO()
    assert (
        conduct_review(
            [link],
            "Reviewer",
            tmp_path / "decisions.yaml",
            io.StringIO("b\nq\n"),
            output,
            describe,
            play,
        )
        == 0
    )
    assert B not in described and B not in played
    assert "playback withheld" in output.getvalue()


def test_concurrent_reviewer_is_refused_before_opening_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(interactive, "read_links", lambda root, run: {"corpus_id": "corpus"})
    monkeypatch.setattr(interactive, "_validate_record", lambda record, reviewer, root: LINKS)
    run_dir = discovery_run_directory(tmp_path, "links-1")
    review_dir = run_dir / "link-review"
    review_dir.mkdir(parents=True)
    with exclusive_lock(review_dir, ".lock"), pytest.raises(CorpusRefusal) as caught:
        interactive.review_interactively("links-1", "Reviewer", tmp_path)
    assert caught.value.code == RefusalCode.DISCOVERY_IN_PROGRESS


def test_prior_decisions_survive_initialization_and_clear(tmp_path: Path) -> None:
    link = dict(LINKS[0], decision={"decision": "unrelated", "note": "different dates"})
    record = {
        "links": [link],
        "review": {"reviewer": "Reviewer", "decision_count": 1},
        "decisions_outside_links": [],
    }
    with pytest.raises(CorpusRefusal, match="different reviewer"):
        interactive._prior_decisions(record, "Other")
    prior = interactive._prior_decisions(record, "Reviewer")
    path = tmp_path / "decisions.yaml"
    interactive._initialize_checkpoint(path, "Reviewer", prior)
    assert read_decisions(path).by_pair[(A, B)].note == "different dates"
    assert _run(path, "j\n1\nc\nq\n", io.StringIO(), []) == 0
    interactive._initialize_checkpoint(path, "Reviewer", prior)
    assert read_decisions(path).by_pair == {}


def test_review_uses_controlling_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(interactive, "read_links", lambda root, run: {"corpus_id": "corpus"})
    monkeypatch.setattr(interactive, "_validate_record", lambda record, reviewer, root: LINKS)
    monkeypatch.setattr(interactive, "_describe_source", lambda identity, root: identity)
    run_dir = discovery_run_directory(tmp_path, "links-1")
    run_dir.mkdir(parents=True)
    master, slave = pty.openpty()
    original_open = os.open

    def open_terminal(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if path == "/dev/tty":
            return os.dup(slave)
        return original_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "open", open_terminal)
    try:
        os.write(master, b"q\n")
        result = interactive.review_interactively("links-1", "Reviewer", tmp_path)
        assert result.count == 0
        assert read_decisions(result.checkpoint).by_pair == {}
        assert b"Recording relationship review" in os.read(master, 16384)
    finally:
        os.close(master)
        os.close(slave)


def test_player_uses_the_recorded_video_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(interactive.shutil, "which", lambda name: "/usr/bin/ffplay")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(interactive.subprocess, "run", run)
    assert interactive._play(Path("movie.mp4"), 1)
    assert seen[0][seen[0].index("-vst") + 1] == "v:1"

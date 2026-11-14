"""Review checkpoints preserve only explicit, valid decisions across interruptions."""

import os
import stat
from pathlib import Path

import pytest

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus.links.decisions import Decision, read_decisions
from ss_track.corpus.links.interactive_state import read_checkpoint, save_checkpoint

A, B, C = "a" * 64, "b" * 64, "c" * 64
LINKS = [{"sources": [{"source_sha256": A}, {"source_sha256": B}]}]


def test_checkpoint_round_trip_edit_and_clear(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    assert read_checkpoint(path, "Reviewer", LINKS) == {}
    pair = (A, B)
    save_checkpoint(path, "Reviewer", {pair: Decision(pair, "related", "same session")})
    assert read_decisions(path).by_pair[pair].note == "same session"
    assert read_checkpoint(path, "Reviewer", LINKS)[pair].decision == "related"
    save_checkpoint(path, "Reviewer", {pair: Decision(pair, "unrelated", None)})
    assert read_checkpoint(path, "Reviewer", LINKS)[pair].decision == "unrelated"
    save_checkpoint(path, "Reviewer", {})
    assert path.exists()
    assert read_decisions(path).by_pair == {}
    assert read_checkpoint(path, "Reviewer", LINKS) == {}


def test_checkpoint_refuses_different_reviewer_and_pairs(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    pair = (A, C)
    save_checkpoint(path, "Reviewer", {pair: Decision(pair, "related", None)})
    with pytest.raises(CorpusRefusal) as caught:
        read_checkpoint(path, "Other", LINKS)
    assert caught.value.code == RefusalCode.IMPORT_CONFLICT
    with pytest.raises(CorpusRefusal) as caught:
        read_checkpoint(path, "Reviewer", LINKS)
    assert caught.value.code == RefusalCode.IMPORT_CONFLICT


def test_failed_atomic_write_keeps_previous_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "decisions.yaml"
    pair = (A, B)
    save_checkpoint(path, "Reviewer", {pair: Decision(pair, "related", None)})
    before = path.read_bytes()

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("simulated outage before publication")

    monkeypatch.setattr("ss_track.corpus.links.interactive_state.write_atomically", fail)
    with pytest.raises(OSError):
        save_checkpoint(path, "Reviewer", {pair: Decision(pair, "unrelated", None)})
    assert path.read_bytes() == before
    assert read_checkpoint(path, "Reviewer", LINKS)[pair].decision == "related"


def test_checkpoint_syncs_file_then_directory_and_is_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "decisions.yaml"
    pair = (A, B)
    seen: list[bool] = []
    original = os.fsync

    def sync(descriptor: int) -> None:
        seen.append(stat.S_ISDIR(os.fstat(descriptor).st_mode))
        original(descriptor)

    monkeypatch.setattr(os, "fsync", sync)
    save_checkpoint(path, "Reviewer", {pair: Decision(pair, "related", None)})
    assert seen == [False, True]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_corrupt_or_symbolic_checkpoint_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "decisions.yaml"
    path.write_text("bad: [", encoding="ascii")
    with pytest.raises(CorpusRefusal):
        read_checkpoint(path, "Reviewer", LINKS)
    path.unlink()
    path.symlink_to(tmp_path / "other")
    with pytest.raises(CorpusRefusal) as caught:
        read_checkpoint(path, "Reviewer", LINKS)
    assert caught.value.code == RefusalCode.IMPORT_CONFLICT


def test_failure_after_replacement_leaves_a_complete_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "decisions.yaml"
    pair = (A, B)
    save_checkpoint(path, "Reviewer", {pair: Decision(pair, "related", None)})

    def fail(directory: Path) -> None:
        raise OSError("simulated directory sync failure")

    monkeypatch.setattr("ss_track.corpus.links.interactive_state._sync_directory", fail)
    with pytest.raises(OSError):
        save_checkpoint(path, "Reviewer", {pair: Decision(pair, "unrelated", None)})
    assert read_decisions(path).by_pair[pair].decision == "unrelated"

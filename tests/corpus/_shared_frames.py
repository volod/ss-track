"""Helpers for the shared-frame tests: declared groups and what a refusal or a result names."""

import shutil
from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode, open_frame_bundle, stage_corpus
from ss_track.corpus.staging import FramesResult
from tests.corpus.conftest import encounter_of, group_of

V0, V1, V2 = "pilot-v0", "pilot-v1", "pilot-v2"

type Group = dict[str, object]


def single(group: str, split: str, stream: dict[str, object]) -> Group:
    return group_of(group, split, encounter_of(f"enc-{stream['stream_id']}", stream))


def stage_refused(corpus_id: str, data_root: Path, code: RefusalCode) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(corpus_id, data_root)
    assert caught.value.code is code
    return caught.value


def sides(refusal: CorpusRefusal) -> list[dict[str, object]]:
    runs = refusal.details["shared_runs"]
    assert isinstance(runs, list)
    assert len(runs) == 1
    found: list[dict[str, object]] = runs[0]["streams"]  # type: ignore[assignment,call-overload,index]
    return found


def named(refusal: CorpusRefusal, key: str) -> list[object]:
    return [side[key] for side in sides(refusal)]


def check_of(result: FramesResult) -> dict[str, object]:
    record = result.to_record()["shared_frames"]
    assert isinstance(record, dict)
    return dict(record)


def not_compared(result: FramesResult) -> list[object]:
    entries = check_of(result)["not_compared"]
    assert isinstance(entries, list)
    return [(entry["corpus_id"], entry["reason"], entry["stream_ids"]) for entry in entries]


def hashes_of(data_root: Path, corpus_id: str, stream_id: str) -> list[str]:
    bundle = open_frame_bundle(data_root / "corpus" / corpus_id / "frames" / stream_id)
    return [entry.sha256 for entry in bundle.entries]


def remove_bundle(data_root: Path, corpus_id: str, stream_id: str) -> None:
    directory = data_root / "corpus" / corpus_id / "frames" / stream_id
    directory.chmod(0o755)
    shutil.rmtree(directory)


def frame_set(data_root: Path, corpus_id: str) -> Path:
    return data_root / "corpus" / corpus_id / "frame-set.json"

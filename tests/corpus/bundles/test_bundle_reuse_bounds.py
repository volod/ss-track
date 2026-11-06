"""Reuse stays inside one declared chain, one policy and one window."""

import json
from pathlib import Path

import pytest

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    build_corpus,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.bundles.frames import bundle_hash
from tests._sealing import self_sealed
from tests.corpus.bundles._reuse import (
    LATER,
    V0,
    V1,
    V2,
    frames,
    identity,
    inodes,
    refused,
    stage_kept,
    stage_version,
    watch,
)
from tests.corpus.conftest import HEAD, WriteCorpus, case_of, stream_of


def test_another_window_decodes(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_kept(write_corpus, data_root, imported)
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1, selection=HEAD)
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 1
    assert staged.bundles[0].status == "staged"
    assert staged.bundles[0].frame_count == HEAD["end_frame"]
    assert (
        frames(data_root, V1, "one")[0].stat().st_ino
        != frames(data_root, V2, "one")[0].stat().st_ino
    )


def test_another_policy_decodes(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_kept(write_corpus, data_root, imported)
    bundle = data_root / "corpus" / V1 / "frames" / "one"
    bundle.chmod(0o755)
    manifest = bundle / "manifest.json"
    manifest.chmod(0o644)
    record = json.loads(manifest.read_text(encoding="ascii"))
    record.pop("manifest_sha256")
    record["identity"]["decode_policy_sha256"] = "a" * 64
    record["bundle_sha256"] = bundle_hash(record["identity"])
    manifest.write_text(json.dumps(self_sealed(record)), encoding="ascii")
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1)
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 1
    assert staged.bundles[0].status == "staged"
    found, _digest = identity(frames(data_root, V2, "one")[0].parent / "manifest.json")
    assert isinstance(found, dict)
    assert found["decode_policy_sha256"] != "a" * 64


def test_an_unlinked_copy_is_decoded(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_kept(write_corpus, data_root, imported)
    stage_version(write_corpus, data_root, imported, V2)
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 1
    assert staged.bundles[0].status == "staged"
    assert inodes(frames(data_root, V1, "one")).isdisjoint(inodes(frames(data_root, V2, "one")))


def test_a_source_kept_further_back_in_the_chain_is_reused(
    imported: ImportResult,
    first: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_version(write_corpus, data_root, imported, V0)
    stage_corpus(V0, data_root)
    stage_version(write_corpus, data_root, first, V1, supersedes=V0, stream_id="other")
    stage_corpus(V1, data_root)
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1, stream_id="kept")
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 0
    assert staged.bundles[0].to_record()["reused_from"] == {"corpus_id": V0, "stream_id": "one"}
    assert inodes(frames(data_root, V2, "kept")) == inodes(frames(data_root, V0, "one"))


def test_one_source_reuses_a_kept_window_and_decodes_the_other(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    streams = [
        stream_of(imported, stream_id="head", selection=HEAD),
        stream_of(imported, stream_id="tail", selection={"start_frame": 4, "end_frame": 8}),
    ]
    build_corpus(write_corpus(streams, corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    kept = [
        stream_of(imported, stream_id="head", selection=HEAD),
        stream_of(imported, stream_id="later", selection=LATER),
    ]
    build_corpus(write_corpus(kept, corpus_id=V2, supersedes=V1), data_root)
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 1
    assert {bundle.stream_id: bundle.status for bundle in staged.bundles} == {
        "head": "reused",
        "later": "staged",
    }
    assert inodes(frames(data_root, V2, "head")) == inodes(frames(data_root, V1, "head"))
    assert inodes(frames(data_root, V2, "later")).isdisjoint(inodes(frames(data_root, V1, "tail")))


def test_a_changed_source_is_refused_before_a_link(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    stage_kept(write_corpus, data_root, imported)
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1)
    stored = next(imported.manifest_path.parent.glob("source*"))
    original = stored.read_bytes()
    stored.chmod(0o644)
    stored.write_bytes(original[:-1])

    refused(lambda: stage_corpus(V2, data_root), RefusalCode.SOURCE_HASH_MISMATCH)

    assert not (data_root / "corpus" / V2 / "frames" / "one").exists()
    assert frames(data_root, V1, "one")[0].stat().st_nlink == 1


def test_a_case_of_a_reused_parent_decodes_nothing(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fields = {"generated_cases": [case_of("shaken", "camera_shake", 1, {"amplitude": 2})]}
    build_corpus(write_corpus([stream_of(imported, **fields)], corpus_id=V1), data_root)
    stage_corpus(V1, data_root)
    build_corpus(
        write_corpus([stream_of(imported, **fields)], corpus_id=V2, supersedes=V1), data_root
    )
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 0
    assert {bundle.stream_id: bundle.status for bundle in staged.bundles} == {
        "one": "reused",
        "shaken": "staged",
    }
    assert verify_corpus_frames(V2, data_root).status == "verified"

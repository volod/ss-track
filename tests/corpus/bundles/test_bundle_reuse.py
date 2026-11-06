"""A kept source reuses a linked version's frames instead of decoding them again."""

import errno
from pathlib import Path

import pytest

from ss_track.corpus import ImportResult, RefusalCode, stage_corpus, verify_corpus_frames
from ss_track.corpus.bundles import frame_store
from tests.corpus.bundles._reuse import (
    FRESH,
    V1,
    V2,
    conforms,
    frames,
    identity,
    inodes,
    refused,
    remove_version,
    stage_kept,
    stage_version,
    watch,
)
from tests.corpus.conftest import WriteCorpus


def test_a_kept_source_reuses_frames_without_decoding_or_storing_them(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_kept(write_corpus, data_root, imported)
    stage_version(write_corpus, data_root, imported, FRESH, stream_id="kept")
    fresh = stage_corpus(FRESH, data_root)
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1, stream_id="kept")
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 0
    assert staged.status == "staged"
    bundle = staged.bundles[0]
    assert bundle.status == "reused"
    assert bundle.bundle_sha256 == fresh.bundles[0].bundle_sha256
    report = bundle.to_record()
    assert report["reused_from"] == {"corpus_id": V1, "stream_id": "one"}
    conforms(staged.to_record())
    kept = frames(data_root, V2, "kept")
    original = frames(data_root, V1, "one")
    fresh_frames = frames(data_root, FRESH, "kept")
    assert [path.read_bytes() for path in kept] == [path.read_bytes() for path in fresh_frames]
    assert inodes(kept) == inodes(original)
    assert inodes(kept).isdisjoint(inodes(fresh_frames))
    assert identity(kept[0].parent / "manifest.json") == identity(
        fresh_frames[0].parent / "manifest.json"
    )
    assert staged.frame_set_sha256 != stage_corpus(V1, data_root).frame_set_sha256
    decodes.calls = 0
    repeated = stage_corpus(V2, data_root)
    assert decodes.calls == 0
    assert repeated.status == "unchanged"
    assert "reused_from" not in repeated.bundles[0].to_record()


def test_a_damaged_candidate_is_refused_by_name_and_not_linked(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    stage_kept(write_corpus, data_root, imported)
    frame = frames(data_root, V1, "one")[0]
    frame.parent.chmod(0o755)
    frame.chmod(0o644)
    damaged = bytearray(frame.read_bytes())
    damaged[0] ^= 0xFF
    frame.write_bytes(damaged)
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1, stream_id="kept")

    refusal = refused(lambda: stage_corpus(V2, data_root), RefusalCode.FRAME_CORRUPTED)

    assert refusal.details["stream_id"] == "kept"
    assert refusal.details["candidate_corpus_id"] == V1
    assert refusal.details["candidate_stream_id"] == "one"
    assert V1 in refusal.message and "one" in refusal.message
    assert not (data_root / "corpus" / V2 / "frames" / "kept").exists()
    assert frame.stat().st_nlink == 1
    assert list((data_root / "corpus" / V2 / "frames").glob(".incoming-*")) == []


def test_removing_one_version_leaves_the_other_readable(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    stage_kept(write_corpus, data_root, imported)
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1, stream_id="kept")
    stage_corpus(V2, data_root)
    original = frames(data_root, V1, "one")[0]
    pixels = original.read_bytes()

    remove_version(data_root, V2)

    assert verify_corpus_frames(V1, data_root).status == "verified"
    assert original.read_bytes() == pixels
    assert original.stat().st_mode & 0o777 == 0o444
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1, stream_id="kept")
    stage_corpus(V2, data_root)
    remove_version(data_root, V1)
    assert verify_corpus_frames(V2, data_root).status == "verified"
    assert frames(data_root, V2, "kept")[0].read_bytes() == pixels


def test_a_host_that_cannot_link_decodes(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stage_kept(write_corpus, data_root, imported)
    stage_version(write_corpus, data_root, imported, V2, supersedes=V1)

    def _cross_device(_source: Path, _target: Path) -> None:
        raise OSError(errno.EXDEV, "Invalid cross-device link")

    monkeypatch.setattr(frame_store.os, "link", _cross_device)
    decodes = watch(monkeypatch)

    staged = stage_corpus(V2, data_root)

    assert decodes.calls == 1
    assert staged.bundles[0].status == "staged"
    assert inodes(frames(data_root, V1, "one")).isdisjoint(inodes(frames(data_root, V2, "one")))
    assert staged.bundles[0].bundle_sha256 == stage_corpus(V1, data_root).bundles[0].bundle_sha256

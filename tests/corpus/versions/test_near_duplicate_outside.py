"""A build reports a re-encode in a version the declaration does not link."""

from collections.abc import Callable
from pathlib import Path

from ss_track.corpus import ImportResult, import_source
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.versions.builder import CORPUS_MANIFEST
from ss_track.corpus.versions.fingerprint import SIMILARITY_THRESHOLD
from tests.corpus._media import expected_rgb, flat_rgb, write_clip
from tests.corpus.conftest import WriteCorpus, WriteRecording, reseal, single_group, stream_of
from tests.corpus.versions._lineage_build import build_version


def _import(
    media: Path,
    write_recording: WriteRecording,
    data_root: Path,
    name: str,
    *,
    codec: str = "mjpeg",
    pixel_format: str = "yuvj420p",
    options: dict[str, str] | None = None,
    content: Callable[[int, int, int], bytes] | None = None,
) -> ImportResult:
    write_clip(
        media / name,
        codec=codec,
        pixel_format=pixel_format,
        options=options,
        content=expected_rgb if content is None else content,
    )
    return import_source(write_recording(name), data_root)


def _encode_copy(
    media: Path, write_recording: WriteRecording, data_root: Path, name: str
) -> ImportResult:
    return _import(
        media,
        write_recording,
        data_root,
        name,
        codec="libx264",
        pixel_format="yuv420p",
        options={"preset": "ultrafast", "crf": "28"},
    )


def test_an_unlinked_re_encode_is_named_and_the_corpus_hash_is_unchanged(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    original = _import(media, write_recording, data_root, "original.mkv")
    copy = _encode_copy(media, write_recording, data_root, "copy.mkv")
    copy_group = [single_group("held-out", "locked", stream_of(copy, stream_id="copy"))]
    alone = build_version(write_grouped_corpus, data_root, "pilot-copy", copy_group)
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-original",
        [single_group("site-a", "development", stream_of(original, stream_id="original"))],
    )

    rebuilt = build_version(write_grouped_corpus, data_root, "pilot-copy", copy_group)

    assert alone.near_duplicates.when_present() == {}
    assert rebuilt.status == "unchanged"
    assert rebuilt.manifest_sha256 == alone.manifest_sha256
    assert "near_duplicates" not in read_sealed(rebuilt.manifest_path, CORPUS_MANIFEST)
    pairs = rebuilt.near_duplicates.to_record()["pairs"]
    assert isinstance(pairs, list) and len(pairs) == 1
    pair = pairs[0]
    assert isinstance(pair, dict)
    assert pair["similarity"] >= SIMILARITY_THRESHOLD
    assert {(item["corpus_id"], item["stream_id"]) for item in pair["streams"]} == {
        ("pilot-copy", "copy"),
        ("pilot-original", "original"),
    }


def test_an_unlinked_independent_clip_is_not_reported(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    gradient = _import(media, write_recording, data_root, "gradient.mkv")
    other = _import(
        media,
        write_recording,
        data_root,
        "flat.mkv",
        codec="libx264",
        pixel_format="yuv420p",
        options={"preset": "ultrafast"},
        content=flat_rgb,
    )
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(gradient, stream_id="gradient"))],
    )

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream_of(other, stream_id="flat"))],
    )

    assert built.status == "built"
    assert built.near_duplicates.when_present() == {}


def test_an_unlinked_re_encode_in_the_same_group_is_not_reported(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    original = _import(media, write_recording, data_root, "original.mkv")
    copy = _encode_copy(media, write_recording, data_root, "copy.mkv")
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(original, stream_id="original"))],
    )

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("site-a", "development", stream_of(copy, stream_id="copy"))],
    )

    assert built.status == "built"
    assert built.near_duplicates.when_present() == {}


def test_a_projected_older_major_in_the_chain_is_still_compared(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    original = _import(media, write_recording, data_root, "original.mkv")
    copy = _encode_copy(media, write_recording, data_root, "copy.mkv")
    earlier = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(original, stream_id="original"))],
    )
    reseal(earlier.manifest_path, schema_version=2)

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream_of(copy, stream_id="copy"))],
        supersedes="pilot-v1",
    )

    pairs = built.near_duplicates.to_record()["pairs"]
    assert isinstance(pairs, list) and len(pairs) == 1
    pair = pairs[0]
    assert isinstance(pair, dict)
    assert {(item["corpus_id"], item["stream_id"]) for item in pair["streams"]} == {
        ("pilot-v1", "original"),
        ("pilot-v2", "copy"),
    }


def test_a_projected_older_major_outside_the_chain_is_still_compared(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    original = _import(media, write_recording, data_root, "original.mkv")
    copy = _encode_copy(media, write_recording, data_root, "copy.mkv")
    earlier = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(original, stream_id="original"))],
    )
    reseal(earlier.manifest_path, schema_version=2)

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream_of(copy, stream_id="copy"))],
    )

    pairs = built.near_duplicates.to_record()["pairs"]
    assert isinstance(pairs, list) and len(pairs) == 1
    pair = pairs[0]
    assert isinstance(pair, dict)
    assert {(item["corpus_id"], item["stream_id"]) for item in pair["streams"]} == {
        ("pilot-v1", "original"),
        ("pilot-v2", "copy"),
    }


def test_a_missing_source_in_an_unlinked_version_is_named(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    original = _import(media, write_recording, data_root, "original.mkv")
    other = _import(media, write_recording, data_root, "other.mkv", content=flat_rgb)
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [single_group("site-a", "development", stream_of(original, stream_id="original"))],
    )
    stored = original.manifest_path.parent / "source.mkv"
    stored.unlink()

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream_of(other, stream_id="other"))],
    )

    assert built.status == "built"
    assert built.near_duplicates.to_record()["not_compared"] == [
        {"corpus_id": "pilot-v1", "reason": "source_unreadable", "stream_ids": ["original"]}
    ]

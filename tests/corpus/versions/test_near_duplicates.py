"""A corpus build reports a re-encoded copy across groups and does not refuse it."""

import argparse
from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.commands.corpus import _run_corpus_build
from ss_track.corpus import ImportResult, build_corpus, import_source
from ss_track.corpus.records.kinds import CORPUS_MANIFEST
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.versions.fingerprint import SIMILARITY_THRESHOLD
from tests.corpus._media import expected_rgb, flat_rgb, write_clip
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    encounter_of,
    group_of,
    last_record,
    reseal,
    single_group,
    stream_of,
)
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


def test_a_re_encode_across_groups_is_reported_and_the_build_stands(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    original = _import(media, write_recording, data_root, "original.mkv")
    copy = _encode_copy(media, write_recording, data_root, "copy.mkv")
    groups = [
        single_group("site-a", "development", stream_of(original, stream_id="original")),
        single_group("held-out", "locked", stream_of(copy, stream_id="copy")),
    ]

    built = build_corpus(write_grouped_corpus(groups), data_root)
    repeated = build_corpus(write_grouped_corpus(groups), data_root)

    report = built.near_duplicates.to_record()
    assert built.status == "built"
    assert repeated.status == "unchanged"
    assert repeated.manifest_sha256 == built.manifest_sha256
    assert repeated.near_duplicates == built.near_duplicates
    assert "near_duplicates" not in read_sealed(built.manifest_path, CORPUS_MANIFEST)
    assert report["method"] == "luma-grid-16"
    assert report["threshold"] == SIMILARITY_THRESHOLD
    pairs = report["pairs"]
    assert isinstance(pairs, list) and len(pairs) == 1
    pair = pairs[0]
    assert isinstance(pair, dict)
    assert pair["similarity"] >= SIMILARITY_THRESHOLD
    assert [item["stream_id"] for item in pair["streams"]] == ["copy", "original"]
    assert [item["group_id"] for item in pair["streams"]] == ["held-out", "site-a"]


def test_independent_clips_and_a_flat_re_encode_are_not_reported(
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
    groups = [
        single_group("site-a", "development", stream_of(gradient, stream_id="gradient")),
        single_group("held-out", "locked", stream_of(other, stream_id="flat")),
    ]

    built = build_corpus(write_grouped_corpus(groups), data_root)

    assert built.status == "built"
    assert built.near_duplicates.when_present() == {}


def test_a_re_encode_inside_one_group_is_not_a_cross_group_report(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    original = _import(media, write_recording, data_root, "original.mkv")
    copy = _encode_copy(media, write_recording, data_root, "copy.mkv")
    group = group_of(
        "site-a",
        "development",
        encounter_of("enc-original", stream_of(original, stream_id="original")),
        encounter_of("enc-copy", stream_of(copy, stream_id="copy")),
    )

    built = build_corpus(write_grouped_corpus([group]), data_root)

    assert built.status == "built"
    assert built.near_duplicates.when_present() == {}


def test_a_linked_re_encode_in_another_group_names_both_versions(
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


def test_a_predecessor_whose_source_is_gone_is_named_and_the_build_stands(
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
        supersedes="pilot-v1",
    )

    assert built.status == "built"
    assert built.near_duplicates.to_record()["not_compared"] == [
        {
            "corpus_id": "pilot-v1",
            "reason": "source_unreadable",
            "stream_ids": ["original"],
        }
    ]


def test_a_predecessor_with_no_projection_is_named(
    imported: ImportResult, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    stream = stream_of(imported)
    first = build_version(
        write_grouped_corpus, data_root, "pilot-v1", [single_group("site-a", "development", stream)]
    )
    reseal(first.manifest_path, schema_version=1)

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [single_group("held-out", "locked", stream)],
        supersedes="pilot-v1",
    )

    assert built.near_duplicates.to_record()["not_compared"] == [
        {"corpus_id": "pilot-v1", "reason": "other_schema", "stream_ids": []}
    ]


def test_the_command_record_carries_the_pair(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    original = _import(media, write_recording, cli_root, "original.mkv")
    copy = _encode_copy(media, write_recording, cli_root, "copy.mkv")
    declaration = write_grouped_corpus(
        [
            single_group("site-a", "development", stream_of(original, stream_id="original")),
            single_group("held-out", "locked", stream_of(copy, stream_id="copy")),
        ]
    )
    status = _run_corpus_build(argparse.Namespace(manifest=declaration))

    reported = last_record(caplog)
    assert status == 0
    assert reported["status"] == "built"
    assert reported["near_duplicates"]["pairs"][0]["similarity"] >= SIMILARITY_THRESHOLD

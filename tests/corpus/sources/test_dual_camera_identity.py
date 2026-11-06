"""Both cameras of one file import as two sources and can share one encounter."""

import json
from pathlib import Path

from ss_track.corpus import (
    ImportResult,
    RefusalCode,
    amend_source_terms,
    build_corpus,
    import_source,
    redecode_source,
    stage_corpus,
)
from ss_track.corpus.records.sealing import sha256_file
from ss_track.corpus.sources.identity import source_identity
from ss_track.schema import validate_file
from tests.corpus._media import HEIGHT, WIDTH, write_dual_video
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    encounter_of,
    group_of,
    stream_of,
)
from tests.corpus.versions._grouping import refused_grouping
from tests.corpus.versions._lineage_build import build_version, refused_build
from tests.corpus.versions._unlinked import place

_PINNED_LATER_STREAM = "249af2716dbc6f394eeab6cd0a01462b4b87550e658b06a734b2a5f73e09ea68"


def test_the_first_stream_keeps_the_file_hash_and_a_later_stream_is_pinned() -> None:
    content = "ab" * 32

    assert source_identity(content, 0) == content
    assert source_identity(content, 1) == _PINNED_LATER_STREAM
    assert source_identity(content, 2) != _PINNED_LATER_STREAM


def _import_both(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> tuple[ImportResult, ImportResult, str]:
    file_hash = sha256_file(write_dual_video(media / "dual.mkv"))
    first = import_source(write_recording("dual.mkv", video_stream_index=0), data_root)
    second = import_source(write_recording("dual.mkv", video_stream_index=1), data_root)
    return first, second, file_hash


def test_both_indexes_import_and_the_first_keeps_a_one_stream_manifest(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    first, second, file_hash = _import_both(media, write_recording, data_root)
    first_body = json.loads(first.manifest_path.read_bytes())
    second_body = json.loads(second.manifest_path.read_bytes())

    assert first.status == "imported"
    assert second.status == "imported"
    assert first.source_sha256 == file_hash
    assert second.source_sha256 == source_identity(file_hash, 1)
    assert first.manifest_path.parent.name == file_hash
    assert sha256_file(first.manifest_path.parent / "source.mkv") == file_hash
    assert sha256_file(second.manifest_path.parent / "source.mkv") == file_hash
    assert validate_file(first.manifest_path, version="2.1.0").version == "2.1.0"
    assert first_body["source"]["sha256"] == file_hash
    assert second_body["source"]["sha256"] == file_hash
    assert "video_stream_index" not in first_body["sequence"]
    assert second_body["sequence"]["video_stream_index"] == 1


def test_repeating_either_index_reports_unchanged(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    _first, second, _file_hash = _import_both(media, write_recording, data_root)

    assert (
        import_source(write_recording("dual.mkv", video_stream_index=0), data_root).status
        == "unchanged"
    )
    repeated = import_source(write_recording("dual.mkv", video_stream_index=1), data_root)
    assert repeated.status == "unchanged"
    assert repeated.manifest_sha256 == second.manifest_sha256
    assert repeated.source_sha256 == second.source_sha256


def test_one_encounter_holds_both_cameras_and_their_bundles_differ(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    first, second, file_hash = _import_both(media, write_recording, data_root)
    streams = [
        stream_of(first, stream_id="cam0"),
        stream_of(second, stream_id="cam1"),
    ]
    declaration = write_grouped_corpus(
        [group_of("site", "development", encounter_of("enc-dual", *streams))]
    )
    built = build_corpus(declaration, data_root)
    staged = stage_corpus(built.corpus_id, data_root)
    bundles = {item.stream_id: item for item in staged.bundles}
    corpus = json.loads(built.manifest_path.read_bytes())
    by_stream = {item["stream_id"]: item for item in corpus["streams"]}

    assert bundles["cam0"].bundle_sha256 != bundles["cam1"].bundle_sha256
    assert (bundles["cam0"].width, bundles["cam0"].height) == (WIDTH, HEIGHT)
    assert (bundles["cam1"].width, bundles["cam1"].height) == (WIDTH // 2, HEIGHT // 2)
    assert {item["encounter_id"] for item in corpus["streams"]} == {"enc-dual"}
    assert "content_sha256" not in by_stream["cam0"]
    assert by_stream["cam1"]["content_sha256"] == file_hash
    assert by_stream["cam1"]["source_sha256"] == second.source_sha256


def test_a_one_stream_corpus_omits_the_separate_file_hash(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    built = build_corpus(write_corpus([stream_of(imported)]), data_root)

    stream = json.loads(built.manifest_path.read_bytes())["streams"][0]
    assert stream["source_sha256"] == imported.source_sha256
    assert "content_sha256" not in stream


def test_two_groups_cannot_share_one_files_cameras(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    first, second, file_hash = _import_both(media, write_recording, data_root)
    groups = [
        group_of(
            "site-a", "development", encounter_of("enc-a", stream_of(first, stream_id="cam0"))
        ),
        group_of("site-b", "locked", encounter_of("enc-b", stream_of(second, stream_id="cam1"))),
    ]

    refusal = refused_grouping(write_grouped_corpus, groups, data_root, RefusalCode.SPLIT_LEAKAGE)

    assert refusal.details["content_sha256"] == file_hash
    assert refusal.details["sources"] == sorted((first.source_sha256, second.source_sha256))
    assert refusal.details["groups"] == ["site-a", "site-b"]
    assert refusal.details["splits"] == ["development", "locked"]


def test_a_later_camera_added_in_the_same_group_is_not_a_move(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    first, second, _file_hash = _import_both(media, write_recording, data_root)
    earlier = group_of(
        "site", "development", encounter_of("enc-dual", stream_of(first, stream_id="cam0"))
    )
    build_version(write_grouped_corpus, data_root, "pilot-v1", [earlier])
    both = group_of(
        "site",
        "development",
        encounter_of(
            "enc-dual", stream_of(first, stream_id="cam0"), stream_of(second, stream_id="cam1")
        ),
    )

    built = build_version(
        write_grouped_corpus, data_root, "pilot-v2", [both], supersedes="pilot-v1"
    )

    lineage = built.to_record()["lineage"]
    assert isinstance(lineage, dict)
    assert lineage["added"] == [
        {"source_sha256": second.source_sha256, "group_id": "site", "split": "development"}
    ]
    assert lineage["kept"] == [
        {"source_sha256": first.source_sha256, "group_id": "site", "split": "development"}
    ]


def test_moving_the_other_camera_of_a_file_is_split_leakage(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    first, second, file_hash = _import_both(media, write_recording, data_root)
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [
            group_of(
                "site-a", "development", encounter_of("enc-a", stream_of(second, stream_id="cam1"))
            )
        ],
    )

    refusal = refused_build(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [group_of("held-out", "locked", encounter_of("enc-b", stream_of(first, stream_id="cam0")))],
        RefusalCode.SPLIT_LEAKAGE,
        supersedes="pilot-v1",
    )

    assert refusal.details["moved_sources"] == [
        {
            "source_sha256": file_hash,
            "from": {"corpus_id": "pilot-v1", "group_id": "site-a", "split": "development"},
            "to": {"corpus_id": "pilot-v2", "group_id": "held-out", "split": "locked"},
        }
    ]


def test_an_unlinked_version_lists_the_other_camera_of_the_same_file(
    media: Path, write_recording: WriteRecording, write_grouped_corpus: WriteCorpus, data_root: Path
) -> None:
    first, second, _file_hash = _import_both(media, write_recording, data_root)
    build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v1",
        [
            group_of(
                "site-a", "development", encounter_of("enc-a", stream_of(second, stream_id="cam1"))
            )
        ],
    )

    built = build_version(
        write_grouped_corpus,
        data_root,
        "pilot-v2",
        [group_of("held-out", "locked", encounter_of("enc-b", stream_of(first, stream_id="cam0")))],
    )

    assert built.unlinked.to_record() == {
        "placements": [
            place(first, "pilot-v1", "site-a", "development", "pilot-v2", "held-out", "locked")
        ]
    }


def test_amending_one_camera_leaves_the_other_record(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    first, second, file_hash = _import_both(media, write_recording, data_root)
    before = first.manifest_path.read_bytes()

    amended = amend_source_terms(
        write_recording("dual.mkv", video_stream_index=1, sensitivity={"level": "high"}),
        data_root,
    )

    assert amended.status == "amended"
    assert amended.source_sha256 == second.source_sha256
    assert first.manifest_path.read_bytes() == before
    assert redecode_source(write_recording("dual.mkv", video_stream_index=1), data_root).status == (
        "unchanged"
    )
    (media / "dual.mkv").unlink()
    after_removal = amend_source_terms(
        write_recording(
            "dual.mkv", sha256=file_hash, video_stream_index=1, sensitivity={"level": "moderate"}
        ),
        data_root,
    )
    assert after_removal.status == "amended"
    assert after_removal.source_sha256 == second.source_sha256
    assert first.manifest_path.read_bytes() == before

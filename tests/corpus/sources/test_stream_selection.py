"""A recording names one video stream. Two streams and no index are refused."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_REFUSED
from ss_track.corpus import (
    CorpusRefusal,
    RefusalCode,
    build_corpus,
    import_source,
    redecode_source,
    stage_corpus,
)
from ss_track.corpus.bundles.frames import frame_name
from ss_track.corpus.decoding.pixels import OUTPUT_PIXEL_FORMAT
from ss_track.corpus.records.kinds import SOURCE_MANIFEST
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.records.sealing import sha256_file
from ss_track.corpus.sources.importer import ImportResult
from ss_track.schema import validate_file
from tests.corpus._media import (
    DUAL_FIRST_FRAMES,
    DUAL_SECOND_FRAMES,
    HEIGHT,
    WIDTH,
    write_dual_video,
)
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    imported_names,
    last_record,
    stream_of,
)

_CORPUS = "pilot-v1"
_LISTED = [
    {
        "index": 0,
        "container_index": 0,
        "codec": "mjpeg",
        "width": WIDTH,
        "height": HEIGHT,
    },
    {
        "index": 1,
        "container_index": 1,
        "codec": "mjpeg",
        "width": WIDTH // 2,
        "height": HEIGHT // 2,
    },
]


def _refused(run: Callable[[], object], code: RefusalCode) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        run()
    assert caught.value.code is code
    return caught.value


def _sequence(result: ImportResult) -> dict[str, object]:
    manifest = read_sealed(result.manifest_path, SOURCE_MANIFEST)
    sequence = manifest["sequence"]
    assert isinstance(sequence, dict)
    return sequence


def _frame(root: Path) -> bytes:
    name = frame_name(0, OUTPUT_PIXEL_FORMAT)
    return (root / "corpus" / _CORPUS / "frames" / "one" / name).read_bytes()


def test_an_unnamed_two_stream_file_is_refused_and_lists_both(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_dual_video(media / "dual.mkv")

    refusal = _refused(
        lambda: import_source(write_recording("dual.mkv"), data_root),
        RefusalCode.VIDEO_STREAM_UNSPECIFIED,
    )

    assert "declare source.video_stream_index" in refusal.message
    assert refusal.details["video_streams"] == _LISTED
    assert imported_names(data_root) == []


def test_the_import_command_lists_both_streams(
    media: Path,
    write_recording: WriteRecording,
    cli_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    write_dual_video(media / "dual.mkv")
    declaration = write_recording("dual.mkv")

    assert main(["import", "--source", str(declaration)]) == EXIT_REFUSED

    record = last_record(caplog)
    assert record["code"] == "VIDEO_STREAM_UNSPECIFIED"
    details = record["details"]
    assert isinstance(details, dict)
    assert details["video_streams"] == _LISTED
    assert imported_names(cli_root) == []


def test_each_index_imports_and_stages_its_own_frames(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, tmp_path: Path
) -> None:
    write_dual_video(media / "dual.mkv")
    pixels: dict[int, bytes] = {}
    for index, frames, width, root_name in (
        (0, DUAL_FIRST_FRAMES, WIDTH, "first"),
        (1, DUAL_SECOND_FRAMES, WIDTH // 2, "second"),
    ):
        root = tmp_path / root_name
        imported = import_source(write_recording("dual.mkv", video_stream_index=index), root)
        sequence = _sequence(imported)
        assert sequence["video_stream_count"] == 2
        assert sequence["frame_count"] == frames
        assert sequence["decoded_width"] == width
        assert sequence["pts"] == [item * 40 for item in range(frames)]
        if index == 0:
            assert "video_stream_index" not in sequence
        else:
            assert sequence["video_stream_index"] == 1
            with pytest.raises(CorpusRefusal) as caught:
                validate_file(imported.manifest_path, version="2.1.0")
            assert caught.value.code is RefusalCode.RECORD_INVALID
            assert validate_file(imported.manifest_path).version == "2.4.0"
        build_corpus(write_corpus([stream_of(imported)]), root)
        assert stage_corpus(_CORPUS, root).status == "staged"
        pixels[index] = _frame(root)

    assert len(pixels[0]) == WIDTH * HEIGHT * 3
    assert len(pixels[1]) == (WIDTH // 2) * (HEIGHT // 2) * 3
    assert pixels[0] != pixels[1]


def test_the_other_index_of_the_same_file_imports_beside_it(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_dual_video(media / "dual.mkv")
    first = import_source(write_recording("dual.mkv", video_stream_index=0), data_root)
    before = first.manifest_path.read_bytes()

    second = import_source(write_recording("dual.mkv", video_stream_index=1), data_root)

    assert second.status == "imported"
    assert second.source_sha256 != first.source_sha256
    assert first.manifest_path.read_bytes() == before
    assert _sequence(first)["frame_count"] == DUAL_FIRST_FRAMES
    assert _sequence(second)["frame_count"] == DUAL_SECOND_FRAMES


def test_naming_the_only_stream_keeps_the_previous_manifest(
    clip: Path, write_recording: WriteRecording, tmp_path: Path
) -> None:
    omitted = import_source(write_recording(clip.name), tmp_path / "omitted")
    named = import_source(write_recording(clip.name, video_stream_index=0), tmp_path / "named")

    assert omitted.manifest_path.read_bytes() == named.manifest_path.read_bytes()
    assert omitted.source_sha256 == sha256_file(clip)
    assert omitted.manifest_path.parent.name == omitted.source_sha256
    body = json.loads(omitted.manifest_path.read_bytes())
    assert body["source"]["sha256"] == omitted.source_sha256
    assert "video_stream_index" not in body["sequence"]
    assert validate_file(omitted.manifest_path, version="2.1.0").version == "2.1.0"


def test_an_index_that_is_not_a_video_stream_lists_both(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_dual_video(media / "dual.mkv")

    refusal = _refused(
        lambda: import_source(write_recording("dual.mkv", video_stream_index=2), data_root),
        RefusalCode.VIDEO_STREAM_UNSPECIFIED,
    )

    assert refusal.details["video_stream_index"] == 2
    assert refusal.details["video_streams"] == _LISTED


def test_an_index_past_the_only_stream_names_that_stream(
    clip: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    refusal = _refused(
        lambda: import_source(write_recording(clip.name, video_stream_index=1), data_root),
        RefusalCode.VIDEO_STREAM_UNSPECIFIED,
    )

    streams = refusal.details["video_streams"]
    assert isinstance(streams, list)
    assert [item["index"] for item in streams] == [0]
    assert refusal.details["video_stream_index"] == 1


def test_a_negative_index_is_refused_by_the_declaration(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    _refused(
        lambda: import_source(write_recording(video_stream_index=-1), data_root),
        RefusalCode.MANIFEST_INVALID,
    )


def test_the_index_counts_video_streams_when_audio_leads(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_dual_video(media / "dual.mkv", leading_audio=True)
    refusal = _refused(
        lambda: import_source(write_recording("dual.mkv"), data_root),
        RefusalCode.VIDEO_STREAM_UNSPECIFIED,
    )
    streams = refusal.details["video_streams"]
    assert isinstance(streams, list)
    assert [item["index"] for item in streams] == [0, 1]
    assert [item["container_index"] for item in streams] == [1, 2]

    imported = import_source(write_recording("dual.mkv", video_stream_index=1), data_root)

    sequence = _sequence(imported)
    assert sequence["decoded_width"] == WIDTH // 2
    assert sequence["video_stream_index"] == 1
    assert sequence["frame_count"] == DUAL_SECOND_FRAMES


def test_redecode_keeps_the_named_stream(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_dual_video(media / "dual.mkv")
    declaration = write_recording("dual.mkv", video_stream_index=1)
    imported = import_source(declaration, data_root)

    assert redecode_source(declaration, data_root).status == "unchanged"
    assert _sequence(imported)["video_stream_index"] == 1

    refusal = _refused(
        lambda: redecode_source(write_recording("dual.mkv", video_stream_index=0), data_root),
        RefusalCode.IMPORT_CONFLICT,
    )
    assert "no imported source" in refusal.message
    assert "changed_facts" not in refusal.details
    omitted = _refused(
        lambda: redecode_source(write_recording("dual.mkv"), data_root),
        RefusalCode.VIDEO_STREAM_UNSPECIFIED,
    )
    assert omitted.details["video_streams"] == _LISTED
    assert _sequence(imported)["frame_count"] == DUAL_SECOND_FRAMES
    assert _sequence(imported)["video_stream_index"] == 1

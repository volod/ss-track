"""A missing color matrix can be declared. A stored tag is never overridden."""

import logging
from fractions import Fraction
from pathlib import Path

import av
import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_REFUSED
from ss_track.corpus import (
    CorpusRefusal,
    RefusalCode,
    amend_source_terms,
    build_corpus,
    import_source,
    open_frame_bundle,
    redecode_source,
    stage_corpus,
)
from ss_track.corpus.bundles.frames import FRAME_BUNDLE
from ss_track.corpus.records.sealed import read_sealed
from ss_track.corpus.sources.importer import SOURCE_MANIFEST
from tests.corpus._media import write_clip
from tests.corpus.bundles._bundle_writing import CORPUS, bundle_dir
from tests.corpus.conftest import WriteCorpus, WriteRecording, last_record, stream_of

_PURE_RED = (63, 102, 240)
_TRUE_RED = (255, 0, 0)
_MISREAD = (233, 0, 2)
_WRITER = "ss_track.corpus.bundles.bundle_writer"


def _near(pixel: bytes, true: tuple[int, int, int]) -> bool:
    return all(abs(found - expected) <= 2 for found, expected in zip(pixel, true, strict=True))


def _sequence(imported_path: Path) -> dict[str, object]:
    sequence = read_sealed(imported_path, SOURCE_MANIFEST)["sequence"]
    assert isinstance(sequence, dict)
    return sequence


def _write_untagged_red(path: Path) -> Path:
    """Write lossless YUV whose pure BT.709 red carries no matrix tag."""
    with av.open(path, "w") as container:
        stream = container.add_stream("ffv1", rate=25)
        stream.width, stream.height, stream.pix_fmt = 32, 8, "yuv444p"
        stream.thread_count = 1
        for index in range(2):
            frame = av.VideoFrame(32, 8, "yuv444p")
            for plane, value in zip(frame.planes, _PURE_RED, strict=True):
                plane.update(bytes([value]) * (plane.line_size * plane.height))
            frame.colorspace = 2
            frame.pts, frame.time_base = index, Fraction(1, 25)
            container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
    return path


def _write_tagged(path: Path, matrix: str) -> Path:
    return write_clip(
        path,
        "libx264",
        "yuv420p",
        {"preset": "ultrafast", "x264-params": f"colormatrix={matrix}"},
        frames=3,
    )


def test_a_declared_bt709_source_converts_pure_red(
    media: Path,
    write_recording: WriteRecording,
    write_corpus: WriteCorpus,
    data_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _write_untagged_red(media / "clip.mkv")
    imported = import_source(write_recording(color={"matrix": "bt709"}), data_root)
    sequence = _sequence(imported.manifest_path)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    with caplog.at_level(logging.WARNING, _WRITER):
        stage_corpus(CORPUS, data_root)

    color = sequence["color"]
    assert isinstance(color, dict)
    assert color["matrix"] == 2
    assert sequence["declared_color"] == {"matrix": 1, "origin": "declared"}
    bundle = open_frame_bundle(bundle_dir(data_root))
    assert _near(bundle.read_frame(0)[:3], _TRUE_RED)
    assert bundle.read_frame(0) == bundle.read_frame(1)
    assert "no color matrix tag" not in caplog.text
    manifest = read_sealed(bundle_dir(data_root) / "manifest.json", FRAME_BUNDLE)
    assert manifest["declared_color"] == {"matrix": 1, "origin": "declared"}
    assert manifest["color"]["matrix"] == 2


def test_an_undeclared_source_still_converts_as_bt601(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    _write_untagged_red(media / "clip.mkv")
    imported = import_source(write_recording(), data_root)
    sequence = _sequence(imported.manifest_path)
    build_corpus(write_corpus([stream_of(imported)]), data_root)

    stage_corpus(CORPUS, data_root)

    assert "declared_color" not in sequence
    pixel = open_frame_bundle(bundle_dir(data_root)).read_frame(0)[:3]
    assert tuple(pixel) == _MISREAD
    assert not _near(pixel, _TRUE_RED)
    manifest = read_sealed(bundle_dir(data_root) / "manifest.json", FRAME_BUNDLE)
    assert "declared_color" not in manifest


def test_a_declaration_that_disagrees_with_a_stored_tag_is_refused(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    _write_tagged(media / "clip.mkv", "bt709")

    with pytest.raises(CorpusRefusal) as caught:
        import_source(write_recording(color={"matrix": "bt601"}), data_root)

    refusal = caught.value
    assert refusal.code is RefusalCode.COLOR_TAG_CONFLICT
    assert refusal.details == {"declared_matrix": 6, "stored_matrix": 1}
    assert list((data_root / "import").iterdir()) == []


def test_a_matching_declaration_keeps_the_undeclared_manifest(
    media: Path, write_recording: WriteRecording, data_root: Path, tmp_path: Path
) -> None:
    _write_tagged(media / "clip.mkv", "bt709")
    plain = import_source(write_recording(), data_root)
    agreed = import_source(write_recording(color={"matrix": "bt709"}), tmp_path / "other")

    assert plain.manifest_path.read_bytes() == agreed.manifest_path.read_bytes()
    assert "declared_color" not in _sequence(plain.manifest_path)
    repeated = import_source(write_recording(color={"matrix": "bt709"}), tmp_path / "other")
    assert repeated.status == "unchanged"


def test_a_matrix_on_a_format_that_uses_none_is_refused(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    write_clip(media / "clip.mkv", "ffv1", "gray", frames=3)

    with pytest.raises(CorpusRefusal) as caught:
        import_source(write_recording(color={"matrix": "bt709"}), data_root)

    assert caught.value.code is RefusalCode.COLOR_TAG_CONFLICT
    assert caught.value.details["source_pixel_format"] == "gray"
    assert list((data_root / "import").iterdir()) == []


def test_redecode_keeps_a_declared_matrix(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    _write_untagged_red(media / "clip.mkv")
    declaration = write_recording(color={"matrix": "bt709"})
    imported = import_source(declaration, data_root)

    assert redecode_source(declaration, data_root).status == "unchanged"
    assert _sequence(imported.manifest_path)["declared_color"] == {
        "matrix": 1,
        "origin": "declared",
    }


def test_an_amendment_cannot_drop_a_color_declaration(
    media: Path, write_recording: WriteRecording, data_root: Path
) -> None:
    _write_untagged_red(media / "clip.mkv")
    declaration = write_recording(color={"matrix": "bt709"})
    imported = import_source(declaration, data_root)
    before = imported.manifest_path.read_bytes()

    with pytest.raises(CorpusRefusal) as dropped:
        amend_source_terms(write_recording(sensitivity={"level": "high"}), data_root)

    assert imported.manifest_path.read_bytes() == before
    amended = amend_source_terms(
        write_recording(color={"matrix": "bt709"}, sensitivity={"level": "moderate"}), data_root
    )

    assert dropped.value.code is RefusalCode.IMPORT_CONFLICT
    assert dropped.value.details["changed_facts"] == ["sequence.declared_color"]
    assert amended.changed_terms == ["sensitivity.level"]
    declared = _sequence(imported.manifest_path)["declared_color"]
    assert declared == {"matrix": 1, "origin": "declared"}


def test_a_later_declaration_change_is_import_conflict(
    media: Path, write_recording: WriteRecording, data_root: Path, tmp_path: Path
) -> None:
    _write_untagged_red(media / "clip.mkv")
    plain = write_recording()
    imported = import_source(plain, data_root)
    before = imported.manifest_path.read_bytes()

    with pytest.raises(CorpusRefusal) as added:
        import_source(write_recording(color={"matrix": "bt709"}), data_root)

    assert added.value.code is RefusalCode.IMPORT_CONFLICT
    assert added.value.details["changed_facts"] == ["sequence.declared_color"]
    assert imported.manifest_path.read_bytes() == before
    declared_root = tmp_path / "declared"
    declared = import_source(write_recording(color={"matrix": "bt709"}), declared_root)
    sealed = declared.manifest_path.read_bytes()

    with pytest.raises(CorpusRefusal) as dropped:
        redecode_source(write_recording(), declared_root)

    assert dropped.value.code is RefusalCode.IMPORT_CONFLICT
    assert dropped.value.details["changed_facts"] == ["sequence.declared_color"]
    assert declared.manifest_path.read_bytes() == sealed


def test_the_import_command_refuses_a_disagreement_in_one_record(
    media: Path, write_recording: WriteRecording, cli_root: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write_tagged(media / "clip.mkv", "smpte170m")
    declaration = write_recording(color={"matrix": "bt709"})

    assert main(["import", "--source", str(declaration)]) == EXIT_REFUSED

    record = last_record(caplog)
    assert record["code"] == "COLOR_TAG_CONFLICT"
    assert record["status"] == "refused"
    assert list((cli_root / "import").iterdir()) == []

"""Compression artifacts and variable frame timing, from a recipe through a staged bundle."""

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pytest

from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.corpus import (
    build_corpus,
    import_source,
    open_frame_bundle,
    stage_corpus,
)
from ss_track.corpus.cases.case_model import Pixels
from ss_track.corpus.cases.transforms import prepare_case
from ss_track.corpus.records.kinds import FRAME_BUNDLE
from tests.corpus._media import FRAME_COUNT, flat_rgb, write_clip
from tests.corpus.cases._case_frames import FRAMES, case_record, prepare, window
from tests.corpus.cases._staged_cases import CORPUS, stage_cases
from tests.corpus.conftest import WriteCorpus, WriteRecording, case_of, stream_of

_WINDOW = {"start_frame": 6, "end_frame": 16}
_CLOCK = {"timestamps": {"capture_clock_evidence": "hardware clock"}}


def _read(pixels: Pixels) -> Callable[[int], Pixels]:
    def read(_index: int) -> Pixels:
        return pixels

    return read


def _present(values: list[int | None]) -> list[int]:
    present: list[int] = []
    for value in values:
        assert value is not None
        present.append(value)
    return present


def test_compression_revision_pins_the_block_encoder() -> None:
    label = prepare(case_record("compression", {"max_step": 1})).label_transform

    assert label == {
        "kind": "compression",
        "encoder": "block-quant-rgb24-v1",
        "block": 8,
        "steps": [{"frame_index": index, "step": 1} for index in range(FRAMES)],
    }


def test_compression_replaces_a_block_with_its_quantized_average() -> None:
    base = np.full((8, 8, 3), 10, dtype=np.uint8)
    base[0, 0, 0] = 20
    record = case_record("compression", {"max_step": 1}, window=window(0, 1))
    rendering = prepare_case(record, range(1), 8, 8, _read(base))

    assert rendering.paint is not None
    assert np.all(rendering.paint(base, 0) == 10)


def test_compression_quantizes_a_leftover_edge_on_its_own() -> None:
    base = np.full((9, 8, 3), 10, dtype=np.uint8)
    base[0, 0, 0] = 20
    base[8, :, :] = 7
    record = case_record("compression", {"max_step": 1}, window=window(0, 1))
    rendering = prepare_case(record, range(1), 8, 9, _read(base))

    assert rendering.paint is not None
    painted = rendering.paint(base, 0)
    assert np.all(painted[:8] == 10)
    assert np.all(painted[8] == 7)


def test_compression_of_an_odd_frame_is_deterministic() -> None:
    raw = np.arange(17 * 13 * 3, dtype=np.uint8).reshape(13, 17, 3)
    record = case_record("compression", {"max_step": 5}, window=window(0, 1))
    rendering = prepare_case(record, range(1), 17, 13, _read(raw))

    assert rendering.paint is not None
    once, twice = rendering.paint(raw, 0), rendering.paint(raw, 0)
    assert once.shape == raw.shape
    assert np.array_equal(once, twice)
    assert not np.array_equal(once, raw)


def test_variable_timing_scales_gaps_that_end_inside_the_window() -> None:
    rendering = prepare(case_record("variable_timing", {"max_scale": 2}, window=window(4, 7)))

    assert rendering.label_transform == {
        "kind": "timing",
        "timestamp_quality": "derived",
        "gaps": [
            {"frame_index": 4, "scale": 2},
            {"frame_index": 5, "scale": 2},
            {"frame_index": 6, "scale": 2},
        ],
    }
    assert rendering.paint is None
    assert rendering.gap_scale == ((4, 2), (5, 2), (6, 2))


def test_variable_timing_refuses_a_parent_with_no_presentation_time() -> None:
    record = case_record("variable_timing", {"max_scale": 2})

    with pytest.raises(CorpusRefusal) as caught:
        prepare(record, timestamp_quality="missing")

    assert caught.value.code is RefusalCode.CASE_INVALID
    assert "presentation time" in caught.value.message


def test_compression_changes_only_the_window_and_keeps_a_measured_clock(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    imported = import_source(write_recording(**_CLOCK), data_root)
    root = stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("compressed", "compression", 1, {"max_step": 4}, window=_WINDOW),
    )
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "compressed")

    assert (case.timestamp_quality, case.capture_clock_evidence) == ("measured", "hardware clock")
    for index in range(FRAME_COUNT):
        inside = index in range(6, 16)
        parent_file = parent.directory / parent.frame_ref(index).frame_name
        case_file = case.directory / case.frame_ref(index).frame_name
        assert (parent.read_frame(index) == case.read_frame(index)) is not inside
        assert (parent_file.stat().st_ino == case_file.stat().st_ino) is not inside
        assert case.frame_ref(index).pts == parent.frame_ref(index).pts


def test_a_changed_presentation_time_never_stays_measured(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    imported = import_source(write_recording(**_CLOCK), data_root)
    assert imported.timestamp_quality == "measured"
    root = stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("timed", "variable_timing", 1, {"max_scale": 3}, window=_WINDOW),
    )
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "timed")
    record = read_sealed(case.directory / "manifest.json", FRAME_BUNDLE)
    gaps = {
        gap["frame_index"]: gap["scale"] for gap in record["identity"]["label_transform"]["gaps"]
    }
    parent_pts = _present([parent.frame_ref(index).pts for index in range(FRAME_COUNT)])
    case_pts = _present([case.frame_ref(index).pts for index in range(FRAME_COUNT)])

    assert (case.timestamp_quality, case.capture_clock_evidence) == ("derived", None)
    assert case_pts[:6] == parent_pts[:6]
    assert case_pts[6:] != parent_pts[6:]
    assert all(case_pts[index] > case_pts[index - 1] for index in range(1, FRAME_COUNT))
    for index in range(1, FRAME_COUNT):
        old = parent_pts[index] - parent_pts[index - 1]
        new = case_pts[index] - case_pts[index - 1]
        assert new == old * gaps.get(index, 1)
    for ref in case.frame_refs():
        assert case.read_frame(ref.frame_index) == parent.read_frame(ref.frame_index)
        if ref.pts != parent.frame_ref(ref.frame_index).pts:
            assert ref.timestamp_quality != "measured"
        parent_file = parent.directory / parent.frame_ref(ref.frame_index).frame_name
        assert (case.directory / ref.frame_name).stat().st_ino == parent_file.stat().st_ino


def test_compression_of_a_uniform_clip_changes_no_frame(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    write_clip(media / "flat.mkv", content=flat_rgb)
    imported = import_source(write_recording("flat.mkv"), data_root)
    cases = [case_of("compressed", "compression", 1, {"max_step": 1})]
    build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.CASE_INVALID
    assert "changes no frame" in caught.value.message


def test_variable_timing_on_a_uniform_clip_changes_time_only(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    write_clip(media / "flat.mkv", content=flat_rgb)
    imported = import_source(write_recording("flat.mkv"), data_root)
    root = stage_cases(
        imported, write_corpus, data_root, case_of("timed", "variable_timing", 1, {"max_scale": 2})
    )
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "timed")

    assert imported.timestamp_quality == "derived"
    assert case.timestamp_quality == "derived"
    assert case.capture_clock_evidence is None
    assert [ref.pts for ref in case.frame_refs()] != [ref.pts for ref in parent.frame_refs()]
    assert all(case.read_frame(index) == parent.read_frame(index) for index in range(FRAME_COUNT))


def test_variable_timing_refuses_a_source_with_no_presentation_time(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    write_clip(media / "clip.mjpeg", container_format="mjpeg")
    imported = import_source(write_recording("clip.mjpeg"), data_root)
    cases = [case_of("timed", "variable_timing", 1, {"max_scale": 2})]

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    assert imported.timestamp_quality == "missing"
    assert caught.value.code is RefusalCode.CASE_INVALID
    assert "presentation time" in caught.value.message
    assert not (data_root / "corpus" / CORPUS / "manifest.json").exists()

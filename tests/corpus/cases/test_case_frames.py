"""What a module sees of a generated case: its frames, gaps, repeats and times."""

import shutil
from pathlib import Path

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    open_frame_bundle,
    stage_corpus,
    verify_corpus_frames,
)
from tests.corpus._media import FRAME_COUNT, flat_rgb, write_clip
from tests.corpus.cases._staged_cases import CORPUS, SHAKE, case_frames_root, stage_cases
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    stream_of,
)

_WINDOW = {"start_frame": 6, "end_frame": 16}


def test_frames_outside_the_window_keep_their_parents_exact_bytes(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("blurred", "blur", 1, {"max_radius": 2}, window=_WINDOW),
    )
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "blurred")

    for index in range(FRAME_COUNT):
        same = parent.read_frame(index) == case.read_frame(index)
        assert same is (index not in range(6, 16))


def test_a_case_that_changes_no_frame_is_refused_and_leaves_nothing(
    media: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    write_clip(media / "flat.mkv", content=flat_rgb)
    imported = import_source(write_recording("flat.mkv"), data_root)
    cases = [case_of("blurred", "blur", 1, {"max_radius": 2})]
    build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.CASE_INVALID
    assert "changes no frame" in caught.value.message
    assert not (case_frames_root(data_root) / "blurred").exists()
    assert (case_frames_root(data_root) / "one").is_dir()


def test_a_case_needs_room_for_its_own_raw_frames(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = stage_cases(
        imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, SHAKE)
    )
    (root / "shaken").chmod(0o755)
    shutil.rmtree(root / "shaken")
    usage = shutil.disk_usage(root)._replace(free=0)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: usage)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(CORPUS, data_root)

    assert caught.value.code is RefusalCode.STORAGE_FAILED
    assert not (root / "shaken").exists()


def test_changing_a_seed_needs_a_new_corpus_version(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    case = case_of("shaken", "camera_shake", 1, SHAKE)
    build_corpus(write_corpus([stream_of(imported, generated_cases=[case])]), data_root)
    changed = case | {"seed": 2}

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported, generated_cases=[changed])]), data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def test_a_case_is_an_ordinary_read_only_bundle(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, SHAKE)
    )

    bundle = root / "shaken"

    assert bundle.stat().st_mode & 0o777 == 0o555
    assert (bundle / "00000003.rgb24").stat().st_mode & 0o777 == 0o444
    assert len(open_frame_bundle(bundle)) == FRAME_COUNT


def test_a_dropped_frame_leaves_a_gap_in_index_and_time(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("dropped", "dropped_frames", 1, {"count": 3}, window=_WINDOW),
    )
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "dropped")
    removed = sorted(set(range(FRAME_COUNT)) - {ref.frame_index for ref in case.frame_refs()})

    assert len(removed) == 3
    assert len(case) == FRAME_COUNT - 3
    for index in removed:
        with pytest.raises(CorpusRefusal) as caught:
            case.read_frame(index)
        assert caught.value.code is RefusalCode.FRAME_NOT_IN_BUNDLE
    for ref in case.frame_refs():
        assert ref.pts == parent.frame_ref(ref.frame_index).pts
        assert case.read_frame(ref.frame_index) == parent.read_frame(ref.frame_index)
    assert verify_corpus_frames(CORPUS, data_root).status == "verified"


def test_a_repeated_frame_keeps_its_own_time_and_names_whose_pixels_it_shows(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("repeated", "duplicated_frames", 1, {"count": 3}, window=_WINDOW),
    )
    parent, case = open_frame_bundle(root / "one"), open_frame_bundle(root / "repeated")

    stale = [ref for ref in case.frame_refs() if ref.content_frame_index != ref.frame_index]

    assert len(stale) == 3
    assert len(case) == FRAME_COUNT
    for ref in stale:
        assert ref.pts == parent.frame_ref(ref.frame_index).pts
        assert case.read_frame(ref.frame_index) == parent.read_frame(ref.content_frame_index)


def test_a_repeated_frame_gives_up_a_measured_capture_time(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, data_root: Path
) -> None:
    evidence = {"timestamps": {"capture_clock_evidence": "hardware clock"}}
    imported = import_source(write_recording(**evidence), data_root)
    assert imported.timestamp_quality == "measured"

    root = stage_cases(
        imported,
        write_corpus,
        data_root,
        case_of("repeated", "duplicated_frames", 1, {"count": 2}),
        case_of("shaken", "camera_shake", 1, {"amplitude": 1}),
    )

    repeated = open_frame_bundle(root / "repeated").frame_ref(0)
    shaken = open_frame_bundle(root / "shaken").frame_ref(0)
    assert (repeated.timestamp_quality, repeated.capture_clock_evidence) == ("derived", None)
    assert (shaken.timestamp_quality, shaken.capture_clock_evidence) == (
        "measured",
        "hardware clock",
    )

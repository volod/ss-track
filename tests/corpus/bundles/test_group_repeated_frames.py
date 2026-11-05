"""A remux held twice in one group, from real media to the exit status."""

import json
import logging
from pathlib import Path

import pytest

from ss_track.cli import main
from ss_track.commands.report import EXIT_REFUSED
from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    stage_corpus,
    verify_corpus_frames,
)
from ss_track.corpus.bundles import duplicate_frames
from tests.corpus._media import FRAME_COUNT, remux, write_clip
from tests.corpus._shared_frames import V1, frame_set, hashes_of, named, stage_refused
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    encounter_of,
    group_of,
    reseal,
    stream_of,
)


def _group(
    original: ImportResult, copy: ImportResult, *, one_encounter: bool
) -> list[dict[str, object]]:
    kept = stream_of(original, stream_id="kept")
    again = stream_of(copy, stream_id="again")
    if one_encounter:
        encounters = (encounter_of("enc", kept, again),)
    else:
        encounters = (
            encounter_of("enc-kept", kept),
            encounter_of("enc-again", again),
        )
    return [group_of("site-a", "development", *encounters)]


@pytest.mark.parametrize("one_encounter", [False, True], ids=["two-encounters", "one-encounter"])
def test_a_remux_in_one_group_is_overlap_naming_both_streams(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    one_encounter: bool,
) -> None:
    build_corpus(
        write_grouped_corpus(_group(original, copy, one_encounter=one_encounter)), data_root
    )

    refusal = stage_refused(V1, data_root, RefusalCode.STREAM_OVERLAP)

    assert named(refusal, "stream_id") == ["again", "kept"]
    assert named(refusal, "group_id") == ["site-a", "site-a"]
    assert named(refusal, "first_shared_frame") == [0, 0]
    assert refusal.details["corpus_id"] == V1
    runs = refusal.details["shared_runs"]
    assert runs[0]["frame_count"] == FRAME_COUNT  # type: ignore[call-overload,index]
    assert runs[0]["frame_sha256"] == hashes_of(data_root, V1, "kept")[0]  # type: ignore[call-overload,index]
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(V1, data_root)
    assert caught.value.code is RefusalCode.STREAM_OVERLAP
    assert caught.value.details["shared_runs"] == runs


def test_stage_and_verify_exit_with_the_overlap_and_leave_no_frame_set(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    build_corpus(write_grouped_corpus(_group(original, copy, one_encounter=False)), data_root)
    monkeypatch.setenv("DATA_DIR", str(data_root))

    with caplog.at_level(logging.INFO):
        assert main(["corpus", "stage", "--corpus", V1]) == EXIT_REFUSED
        assert json.loads(caplog.messages[-1])["code"] == "STREAM_OVERLAP"
        assert not frame_set(data_root, V1).exists()
        assert main(["corpus", "verify", "--corpus", V1]) == EXIT_REFUSED

    assert json.loads(caplog.messages[-1])["code"] == "STREAM_OVERLAP"


def test_a_cut_copy_in_one_group_names_where_each_stream_first_shows_the_frame(
    media: Path,
    write_recording: WriteRecording,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
) -> None:
    write_clip(media / "whole.mkv")
    whole = import_source(write_recording("whole.mkv"), data_root)
    remux(media / "whole.mkv", media / "cut.mkv", start_packet=9)
    cut = import_source(write_recording("cut.mkv"), data_root)
    groups = [
        group_of(
            "site-a",
            "development",
            encounter_of("enc-whole", stream_of(whole, stream_id="whole")),
            encounter_of("enc-cut", stream_of(cut, stream_id="cut")),
        )
    ]
    build_corpus(write_grouped_corpus(groups), data_root)

    refusal = stage_refused(V1, data_root, RefusalCode.STREAM_OVERLAP)

    assert named(refusal, "stream_id") == ["cut", "whole"]
    assert named(refusal, "first_shared_frame") == [0, 9]


def _stage_without_the_run_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stage as the code did when a group was allowed to hold a copy."""
    monkeypatch.setattr(duplicate_frames, "require_unshared_runs", lambda *_args, **_kwargs: None)


def test_verify_refuses_a_same_group_remux_already_in_its_frame_set(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_corpus(write_grouped_corpus(_group(original, copy, one_encounter=True)), data_root)
    _stage_without_the_run_check(monkeypatch)
    assert stage_corpus(V1, data_root).status == "staged"
    monkeypatch.undo()
    assert frame_set(data_root, V1).is_file()

    with pytest.raises(CorpusRefusal) as staged_again:
        stage_corpus(V1, data_root)
    assert staged_again.value.code is RefusalCode.STREAM_OVERLAP
    assert frame_set(data_root, V1).is_file()
    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(V1, data_root)

    assert caught.value.code is RefusalCode.STREAM_OVERLAP
    assert named(caught.value, "stream_id") == ["again", "kept"]


def test_a_mismatched_frame_set_is_named_before_the_overlap(
    copy: ImportResult,
    original: ImportResult,
    write_grouped_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_corpus(write_grouped_corpus(_group(original, copy, one_encounter=False)), data_root)
    _stage_without_the_run_check(monkeypatch)
    stage_corpus(V1, data_root)
    monkeypatch.undo()
    reseal(frame_set(data_root, V1), corpus_manifest_sha256="c" * 64)

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(V1, data_root)

    assert caught.value.code is RefusalCode.FRAME_SET_MISMATCH
    assert "shared_runs" not in caught.value.details

"""What a module sees of a generated case, and how a damaged or stale case is refused."""

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
from ss_track.corpus.builder import CORPUS_MANIFEST_KIND
from ss_track.corpus.frames import FRAME_BUNDLE_KIND, bundle_hash
from ss_track.corpus.sealed import read_sealed
from tests.corpus._media import FRAME_COUNT, flat_rgb, write_clip
from tests.corpus.conftest import (
    WriteCorpus,
    WriteRecording,
    case_of,
    reseal,
    stream_of,
)

_CORPUS = "pilot-v1"
_WINDOW = {"start_frame": 6, "end_frame": 16}
_SHAKE = {"amplitude": 2}


def _frames(data_root: Path) -> Path:
    return data_root / "corpus" / _CORPUS / "frames"


def _stage(
    imported: ImportResult, write: WriteCorpus, data_root: Path, *cases: dict[str, object]
) -> Path:
    build_corpus(write([stream_of(imported, generated_cases=list(cases))]), data_root)
    stage_corpus(_CORPUS, data_root)
    return _frames(data_root)


def test_frames_outside_the_window_keep_their_parents_exact_bytes(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(
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
        stage_corpus(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.CASE_INVALID
    assert "changes no frame" in caught.value.message
    assert not (_frames(data_root) / "blurred").exists()
    assert (_frames(data_root) / "one").is_dir()


def test_a_case_needs_room_for_its_own_raw_frames(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _stage(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, _SHAKE))
    (root / "shaken").chmod(0o755)
    shutil.rmtree(root / "shaken")
    usage = shutil.disk_usage(root)._replace(free=0)
    monkeypatch.setattr(shutil, "disk_usage", lambda _: usage)

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.STORAGE_FAILED
    assert not (root / "shaken").exists()


def test_changing_a_seed_needs_a_new_corpus_version(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    case = case_of("shaken", "camera_shake", 1, _SHAKE)
    build_corpus(write_corpus([stream_of(imported, generated_cases=[case])]), data_root)
    changed = case | {"seed": 2}

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported, generated_cases=[changed])]), data_root)

    assert caught.value.code is RefusalCode.CORPUS_CONFLICT


def test_a_case_is_an_ordinary_read_only_bundle(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, _SHAKE))

    bundle = root / "shaken"

    assert bundle.stat().st_mode & 0o777 == 0o555
    assert (bundle / "00000003.rgb24").stat().st_mode & 0o777 == 0o444
    assert len(open_frame_bundle(bundle)) == FRAME_COUNT


def test_a_dropped_frame_leaves_a_gap_in_index_and_time(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(
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
    assert verify_corpus_frames(_CORPUS, data_root).status == "verified"


def test_a_repeated_frame_keeps_its_own_time_and_names_whose_pixels_it_shows(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(
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

    root = _stage(
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


def test_a_corrupted_case_frame_fails_verification_by_name(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, _SHAKE))
    frame = root / "shaken" / "00000004.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"\0" + frame.read_bytes()[1:])

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert caught.value.details["frames"] == [
        {"stream_id": "shaken", "frame": "00000004.rgb24", "reason": "hash_mismatch"}
    ]
    with pytest.raises(CorpusRefusal) as again:
        stage_corpus(_CORPUS, data_root)
    assert again.value.code is RefusalCode.FRAME_CORRUPTED


def test_a_case_made_from_a_corrupted_parent_is_refused_and_leaves_nothing(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    build_corpus(
        write_corpus(
            [
                stream_of(
                    imported,
                    generated_cases=[case_of("shaken", "camera_shake", 1, _SHAKE)],
                )
            ]
        ),
        data_root,
    )
    stage_corpus(_CORPUS, data_root)
    root = _frames(data_root)
    (root / "shaken").chmod(0o755)
    shutil.rmtree(root / "shaken")
    frame = root / "one" / "00000005.rgb24"
    frame.chmod(0o644)
    frame.write_bytes(b"\0" + frame.read_bytes()[1:])

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.FRAME_CORRUPTED
    assert not (root / "shaken").exists()
    assert list(root.glob(".incoming-*")) == []


def test_verify_requires_every_case_to_be_staged(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, _SHAKE))
    (root / "shaken").chmod(0o755)
    shutil.rmtree(root / "shaken")

    with pytest.raises(CorpusRefusal) as caught:
        verify_corpus_frames(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.BUNDLE_NOT_STAGED
    assert caught.value.details == {"stream_id": "shaken"}


def test_verify_reports_each_case_with_its_transform(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    _stage(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, _SHAKE))

    result = verify_corpus_frames(_CORPUS, data_root)

    assert {item.stream_id: item.transform for item in result.bundles} == {
        "one": "identity",
        "shaken": "camera_shake",
    }


def _repoint_parent(bundle: Path, parent_bundle_sha256: str) -> None:
    """Make a self-consistent case record that names other parent frames."""
    record = read_sealed(bundle / "manifest.json", FRAME_BUNDLE_KIND)
    identity = record["identity"] | {"parent_bundle_sha256": parent_bundle_sha256}
    bundle.chmod(0o755)
    reseal(bundle / "manifest.json", identity=identity, bundle_sha256=bundle_hash(identity))


def test_a_case_from_other_parent_frames_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, _SHAKE))
    _repoint_parent(root / "shaken", "e" * 64)

    for action in (stage_corpus, verify_corpus_frames):
        with pytest.raises(CorpusRefusal) as caught:
            action(_CORPUS, data_root)
        assert caught.value.code is RefusalCode.BUNDLE_CONFLICT
        assert caught.value.details["parent_stream_id"] == "one"


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param({"transform_revision": 99}, id="other-revision"),
        pytest.param({"transform": "removed_transform"}, id="unknown-transform"),
    ],
)
def test_a_stored_case_this_code_cannot_reproduce_refuses_before_any_write(
    imported: ImportResult,
    write_corpus: WriteCorpus,
    data_root: Path,
    stored: dict[str, object],
) -> None:
    cases = [case_of("shaken", "camera_shake", 1, _SHAKE)]
    result = build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)
    manifest = read_sealed(result.manifest_path, CORPUS_MANIFEST_KIND)
    reseal(result.manifest_path, generated_cases=[manifest["generated_cases"][0] | stored])

    with pytest.raises(CorpusRefusal) as caught:
        stage_corpus(_CORPUS, data_root)

    assert caught.value.code is RefusalCode.TRANSFORM_REVISION_MISMATCH
    assert not _frames(data_root).exists()


def test_a_bundle_with_a_broken_generated_record_is_tampered(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    root = _stage(imported, write_corpus, data_root, case_of("shaken", "camera_shake", 1, _SHAKE))
    record = read_sealed(root / "shaken" / "manifest.json", FRAME_BUNDLE_KIND)
    identity = {key: value for key, value in record["identity"].items() if key != "recipe"}
    (root / "shaken").chmod(0o755)
    reseal(
        root / "shaken" / "manifest.json", identity=identity, bundle_sha256=bundle_hash(identity)
    )

    with pytest.raises(CorpusRefusal) as caught:
        open_frame_bundle(root / "shaken")

    assert caught.value.code is RefusalCode.RECORD_TAMPERED

"""Generated cases from declaration to staged frames, over a real decoded parent."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from ss_track.corpus import (
    CorpusRefusal,
    ImportResult,
    RefusalCode,
    build_corpus,
    import_source,
    open_frame_bundle,
    stage_corpus,
)
from ss_track.corpus.builder import CORPUS_MANIFEST_KIND
from ss_track.corpus.frames import FRAME_BUNDLE_KIND
from ss_track.corpus.sealed import read_sealed
from ss_track.corpus.transforms import TRANSFORM_REVISIONS
from tests.corpus._media import FRAME_COUNT, HEIGHT, WIDTH
from tests.corpus.conftest import WriteCorpus, WriteRecording, case_of, stream_of

_CORPUS = "pilot-v1"
_REGION = {"x": 8, "y": 6, "width": 24, "height": 20}
_WINDOW = {"start_frame": 6, "end_frame": 16}


def every_case(seed: int = 5) -> list[dict[str, object]]:
    """Return one recipe of each transform."""
    sprites = {"region": _REGION, "sprite_count": 3, "sprite_size": 4, "max_speed": 2}
    return [
        case_of(
            "absence",
            "target_absence",
            seed,
            {"region": _REGION, "plate_frame": 0, "noise": 2},
            window=_WINDOW,
        ),
        case_of("background", "moving_background", seed, sprites),
        case_of("shake", "camera_shake", seed, {"amplitude": 3}),
        case_of("blur", "blur", seed, {"max_radius": 2}, window=_WINDOW),
        case_of("dropped", "dropped_frames", seed, {"count": 4}, window=_WINDOW),
        case_of("repeated", "duplicated_frames", seed, {"count": 4}, window=_WINDOW),
        case_of("occluded", "short_occlusion", seed, {"region": _REGION}, window=_WINDOW),
    ]


def frames_dir(data_root: Path, corpus: str = _CORPUS) -> Path:
    return data_root / "corpus" / corpus / "frames"


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != ".staging.lock"
    }


def corpus_manifest(data_root: Path) -> dict[str, Any]:
    path = data_root / "corpus" / _CORPUS / "manifest.json"
    return read_sealed(path, CORPUS_MANIFEST_KIND)


@pytest.fixture
def staged(imported: ImportResult, write_corpus: WriteCorpus, data_root: Path) -> Path:
    stream = stream_of(imported, generated_cases=every_case())
    build_corpus(write_corpus([stream]), data_root)
    stage_corpus(_CORPUS, data_root)
    return frames_dir(data_root)


def test_a_rerun_with_one_seed_is_byte_identical(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, tmp_path: Path
) -> None:
    trees = []
    for name in ("first", "second"):
        root = tmp_path / name
        imported = import_source(write_recording(), root)
        stream = stream_of(imported, generated_cases=every_case())
        build_corpus(write_corpus([stream]), root)
        stage_corpus(_CORPUS, root)
        trees.append(tree_bytes(root / "corpus"))

    assert trees[0] == trees[1]
    assert len(trees[0]) > len(every_case()) * FRAME_COUNT // 2


def test_a_second_process_stages_identical_case_bytes(staged: Path, tmp_path: Path) -> None:
    copy = tmp_path / "copy"
    shutil.copytree(staged.parents[2], copy)
    for name in ("shake", "blur", "absence", "background", "occluded", "dropped", "repeated"):
        bundle = copy / "corpus" / _CORPUS / "frames" / name
        bundle.chmod(0o755)
        shutil.rmtree(bundle)

    script = (
        "import sys; from pathlib import Path; from ss_track.corpus import stage_corpus; "
        f"stage_corpus({_CORPUS!r}, Path(sys.argv[1]))"
    )
    subprocess.run([sys.executable, "-c", script, str(copy)], check=True)

    assert tree_bytes(copy / "corpus" / _CORPUS / "frames") == tree_bytes(staged)


def test_repeating_a_stage_changes_nothing(staged: Path, data_root: Path) -> None:
    before = tree_bytes(staged)

    result = stage_corpus(_CORPUS, data_root)

    assert result.status == "unchanged"
    assert {bundle.status for bundle in result.bundles} == {"unchanged"}
    assert tree_bytes(staged) == before


def test_another_seed_gives_other_frames(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    cases = [
        case_of("seed-one", "blur", 1, {"max_radius": 3}),
        case_of("seed-two", "blur", 2, {"max_radius": 3}),
    ]
    build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    bundles = {item.stream_id: item for item in stage_corpus(_CORPUS, data_root).bundles}

    assert bundles["seed-one"].bundle_sha256 != bundles["seed-two"].bundle_sha256


def test_no_name_changes_a_case_hash(
    clip: Path, write_recording: WriteRecording, write_corpus: WriteCorpus, tmp_path: Path
) -> None:
    hashes = []
    for root, corpus, case_id in (("a", "first", "one-case"), ("b", "second", "renamed")):
        imported = import_source(write_recording(), tmp_path / root)
        cases = [case_of(case_id, "camera_shake", 9, {"amplitude": 2})]
        declaration = write_corpus([stream_of(imported, generated_cases=cases)], corpus_id=corpus)
        build_corpus(declaration, tmp_path / root)
        result = stage_corpus(corpus, tmp_path / root)
        hashes.append(next(b.bundle_sha256 for b in result.bundles if b.stream_id == case_id))

    assert hashes[0] == hashes[1]


def test_declaration_order_does_not_change_the_corpus(
    imported: ImportResult, write_corpus: WriteCorpus, tmp_path: Path
) -> None:
    forward = stream_of(imported, generated_cases=every_case())
    backward = stream_of(imported, generated_cases=every_case()[::-1])
    root = tmp_path / "data"

    first = build_corpus(write_corpus([forward]), root)
    second = build_corpus(write_corpus([backward]), root)

    assert second.status == "unchanged"
    assert second.manifest_sha256 == first.manifest_sha256


def test_a_case_is_stored_with_parent_transform_seed_and_label_transform(
    imported: ImportResult, staged: Path, data_root: Path
) -> None:
    cases = {case["case_id"]: case for case in corpus_manifest(data_root)["generated_cases"]}

    case = cases["occluded"]
    assert case["parent_stream_id"] == "one"
    assert case["source_sha256"] == imported.source_sha256
    assert case["transform"] == "short_occlusion"
    assert case["transform_revision"] == TRANSFORM_REVISIONS["short_occlusion"]
    assert case["seed"] == 5
    assert case["window"] == _WINDOW
    assert case["parameters"] == {"region": _REGION}
    assert case["label_transform"]["inside"] == "fully_occluded"
    record = read_sealed(staged / "occluded" / "manifest.json", FRAME_BUNDLE_KIND)
    assert record["identity"]["recipe"]["seed"] == 5
    assert record["identity"]["label_transform"] == case["label_transform"]
    parent = read_sealed(staged / "one" / "manifest.json", FRAME_BUNDLE_KIND)
    assert record["identity"]["parent_bundle_sha256"] == parent["bundle_sha256"]
    assert sorted(cases) == sorted(case["case_id"] for case in every_case())


def test_an_absent_window_means_the_whole_parent_selection(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    selection = {"start_frame": 2, "end_frame": 9}
    cases = [case_of("blurred", "blur", 1, {"max_radius": 1})]
    stream = stream_of(imported, selection=selection, generated_cases=cases)
    build_corpus(write_corpus([stream]), data_root)
    stage_corpus(_CORPUS, data_root)

    bundle = open_frame_bundle(frames_dir(data_root) / "blurred")

    assert corpus_manifest(data_root)["generated_cases"][0]["window"] == selection
    assert [entry.frame_index for entry in bundle.entries] == list(range(2, 9))


def test_a_recipe_its_parent_cannot_satisfy_refuses_the_build_and_writes_nothing(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    region = {"x": WIDTH - 2, "y": 0, "width": 4, "height": HEIGHT}
    cases = [case_of("occluded", "short_occlusion", 1, {"region": region}, window=_WINDOW)]

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)

    assert caught.value.code is RefusalCode.CASE_INVALID
    assert not (data_root / "corpus" / _CORPUS / "manifest.json").exists()


def test_a_plate_outside_the_parent_selection_is_refused(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    parameters = {"region": _REGION, "plate_frame": 1, "noise": 0}
    cases = [case_of("absence", "target_absence", 1, parameters)]
    stream = stream_of(
        imported, selection={"start_frame": 2, "end_frame": 9}, generated_cases=cases
    )

    with pytest.raises(CorpusRefusal) as caught:
        build_corpus(write_corpus([stream]), data_root)

    assert caught.value.code is RefusalCode.CASE_INVALID

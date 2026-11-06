"""Track-following cases: a crossing, a moving removal, a distractor and an exit.

The occluder check is by hand: on each declared frame the painted rectangle is the target box,
every pixel of that box is replaced, and every pixel outside it stays. A frame with no box stays
`unknown` and keeps its pixels.
"""

from pathlib import Path

import numpy as np

from ss_track.corpus import ImportResult, build_corpus, open_frame_bundle, stage_corpus
from ss_track.corpus.bundles.frames import bundle_hash
from ss_track.corpus.cases.case_model import Rendering
from ss_track.corpus.cases.seeded import SeededDraws
from ss_track.corpus.cases.track_transforms import CROSS_DIRECTIONS, CROSS_STEP, EXIT_EDGES
from ss_track.corpus.records.kinds import FRAME_BUNDLE
from ss_track.corpus.records.sealed import read_sealed
from tests.corpus.cases._case_frames import (
    HEIGHT,
    LABEL_REVISION,
    OTHER_REVISION,
    WIDTH,
    case_record,
    frame,
    painted,
    prepare,
    track_parameters,
    window,
)
from tests.corpus.conftest import WriteCorpus, case_of, stream_of

_BOX = {"x": 3, "y": 2, "width": 4, "height": 3}
_INDEXES = [1, 3, 4, 5, 6, 7, 8]
_COVER = {"start_frame": 3, "end_frame": 6}
_CASE_WINDOW = window(1, 9)
_STAGED_WINDOW = {"start_frame": 6, "end_frame": 16}
_STAGED_BOX = {"x": 8, "y": 6, "width": 10, "height": 8}
_STAGED_COVER = {"start_frame": 8, "end_frame": 13}


def _rendering(transform: str, **extra: object) -> Rendering:
    parameters = track_parameters(_INDEXES, _BOX, **extra)
    return prepare(case_record(transform, parameters, window=_CASE_WINDOW))


def _entry(rendering: Rendering, index: int) -> dict[str, object]:
    frames = rendering.label_transform["frames"]
    assert isinstance(frames, list)
    found = next(item for item in frames if item["frame_index"] == index)
    assert isinstance(found, dict)
    return {str(key): value for key, value in found.items()}


def _region(entry: dict[str, object]) -> dict[str, int]:
    region = entry["region"]
    assert isinstance(region, dict)
    return {str(key): int(value) for key, value in region.items()}


def _view(pixels: np.ndarray, box: dict[str, int]) -> np.ndarray:
    return pixels[box["y"] : box["y"] + box["height"], box["x"] : box["x"] + box["width"]]


def test_the_occluder_covers_the_target_exactly_on_declared_frames() -> None:
    rendering = _rendering("crossing_occluder", cover=_COVER)
    assert rendering.paint is not None
    blank = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    filled = np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)

    for index in range(_COVER["start_frame"], _COVER["end_frame"]):
        assert _entry(rendering, index)["region"] == _BOX
        assert _entry(rendering, index)["inside"] == "fully_occluded"
        covered, other = rendering.paint(blank, index), rendering.paint(filled, index)
        assert np.array_equal(_view(covered, _BOX), _view(other, _BOX))
        assert not np.array_equal(_view(covered, _BOX), _view(blank, _BOX))
        mask = np.ones((HEIGHT, WIDTH), dtype=bool)
        mask[_BOX["y"] : _BOX["y"] + _BOX["height"], _BOX["x"] : _BOX["x"] + _BOX["width"]] = False
        assert np.array_equal(covered[mask], blank[mask])


def test_the_occluder_stands_off_the_box_beside_the_cover() -> None:
    rendering = _rendering("crossing_occluder", cover=_COVER)
    direction = CROSS_DIRECTIONS[
        SeededDraws("crossing_occluder", 11).integers("direction", 1, 0, 3)[0]
    ]

    region = _entry(rendering, 6)["region"]
    assert isinstance(region, dict)
    assert region == {
        "x": _BOX["x"] + direction[0] * CROSS_STEP,
        "y": _BOX["y"] + direction[1] * CROSS_STEP,
        "width": _BOX["width"],
        "height": _BOX["height"],
    }
    assert region != _BOX


def test_a_frame_with_no_scorable_box_stays_unknown() -> None:
    rendering = _rendering("crossing_occluder", cover=_COVER)

    assert _entry(rendering, 2) == {"frame_index": 2, "role": "unknown"}
    assert np.array_equal(painted(rendering, 2), frame(2))
    assert rendering.label_transform["label_revision"] == LABEL_REVISION
    frames = rendering.label_transform["frames"]
    assert isinstance(frames, list)
    assert [item["frame_index"] for item in frames] == list(range(1, 9))


def test_a_moving_removal_replaces_each_box_with_the_plate() -> None:
    rendering = _rendering("moving_removal", plate_frame=0, noise=0)

    result = painted(rendering, 4)
    assert np.array_equal(_view(result, _BOX), _view(frame(0), _BOX))
    mask = np.ones((HEIGHT, WIDTH), dtype=bool)
    mask[_BOX["y"] : _BOX["y"] + _BOX["height"], _BOX["x"] : _BOX["x"] + _BOX["width"]] = False
    assert np.array_equal(result[mask], frame(4)[mask])
    assert _entry(rendering, 4)["inside"] == "absent"
    assert _entry(rendering, 4)["overlap"] == "unknown"
    assert _entry(rendering, 2)["role"] == "unknown"
    assert np.array_equal(painted(rendering, 2), frame(2))


def test_a_similar_object_is_a_copy_placed_beside_the_target() -> None:
    rendering = _rendering("similar_distractor")
    entry = _entry(rendering, 4)
    copy = _region(entry)
    assert entry["added_objects"] == "distractor"
    assert entry["inside"] == "unknown"
    assert _shares_an_edge(copy, _BOX)

    result = painted(rendering, 4)
    assert np.array_equal(_view(result, copy), _view(frame(4), _BOX))
    assert np.array_equal(_view(result, _BOX), _view(frame(4), _BOX))
    assert _entry(rendering, 2)["role"] == "unknown"


def test_out_of_view_puts_the_box_outside_and_a_later_frame_reenters() -> None:
    seed = next(
        value
        for value in range(16)
        if EXIT_EDGES[SeededDraws("out_of_view", value).integers("edge", 1, 0, 3)[0]] == "right"
    )
    parameters = track_parameters(_INDEXES, _BOX, outside=_COVER)
    rendering = prepare(case_record("out_of_view", parameters, seed=seed, window=_CASE_WINDOW))

    shift = _entry(rendering, 4)
    assert shift["visibility"] == "out_of_view"
    assert shift["dx"] == WIDTH - _BOX["x"]
    assert shift["dy"] == 0
    source, result = frame(4), painted(rendering, 4)
    assert np.array_equal(result[:, -1], source[:, _BOX["x"] - 1])
    assert not np.array_equal(result[_BOX["y"], _BOX["x"]], source[_BOX["y"], _BOX["x"]])
    assert _entry(rendering, 2)["role"] == "unknown"
    assert np.array_equal(painted(rendering, 2), frame(2))
    assert _entry(rendering, 7) == {"frame_index": 7, "role": "reentry", "region": _BOX}
    assert np.array_equal(painted(rendering, 7), frame(7))


def test_another_seed_changes_the_crossing_and_the_exit() -> None:
    placements, shifts = set(), set()
    box = {"x": 6, "y": 4, "width": 4, "height": 3}
    for seed in range(12):
        distractor = prepare(
            case_record(
                "similar_distractor",
                track_parameters(_INDEXES, box),
                seed=seed,
                window=_CASE_WINDOW,
            )
        )
        placements.add(tuple(sorted(_region(_entry(distractor, 4)).items())))
        exited = prepare(
            case_record(
                "out_of_view",
                track_parameters(_INDEXES, box, outside=_COVER),
                seed=seed,
                window=_CASE_WINDOW,
            )
        )
        shifts.add((_entry(exited, 4)["dx"], _entry(exited, 4)["dy"]))

    assert len(placements) > 1
    assert len(shifts) > 1


def _shares_an_edge(copy: dict[str, int], box: dict[str, int]) -> bool:
    same_row = copy["y"] == box["y"] and copy["height"] == box["height"]
    same_column = copy["x"] == box["x"] and copy["width"] == box["width"]
    touches_side = copy["x"] in (box["x"] + box["width"], box["x"] - copy["width"])
    touches_row = copy["y"] in (box["y"] + box["height"], box["y"] - copy["height"])
    return (same_row and touches_side) or (same_column and touches_row)


def test_the_bundle_hash_covers_the_label_revision(
    imported: ImportResult, write_corpus: WriteCorpus, data_root: Path
) -> None:
    indexes = [index for index in range(6, 16) if index != 7]
    first = track_parameters(indexes, _STAGED_BOX, cover=_STAGED_COVER)
    second = track_parameters(indexes, _STAGED_BOX, cover=_STAGED_COVER) | {
        "label_revision": OTHER_REVISION
    }
    cases = [
        case_of("cross-a", "crossing_occluder", 5, first, window=_STAGED_WINDOW),
        case_of("cross-b", "crossing_occluder", 5, second, window=_STAGED_WINDOW),
    ]
    build_corpus(write_corpus([stream_of(imported, generated_cases=cases)]), data_root)
    stage_corpus("pilot-v1", data_root)
    root = data_root / "corpus" / "pilot-v1" / "frames"
    left, right = open_frame_bundle(root / "cross-a"), open_frame_bundle(root / "cross-b")

    assert left.bundle_sha256 != right.bundle_sha256
    assert [left.read_frame(index) for index in left.selection] == [
        right.read_frame(index) for index in right.selection
    ]
    for bundle, revision in ((left, LABEL_REVISION), (right, OTHER_REVISION)):
        record = read_sealed(bundle.directory / "manifest.json", FRAME_BUNDLE)
        identity = record["identity"]
        assert record["bundle_sha256"] == bundle_hash(identity)
        assert identity["recipe"]["parameters"]["label_revision"] == revision
        assert identity["label_transform"]["label_revision"] == revision

"""Each transform on hand-checkable frames, with no codec or data root involved."""

import numpy as np

from ss_track.corpus.case_model import Pixels
from ss_track.corpus.transforms import prepare_case
from tests.corpus._case_frames import (
    FRAMES,
    HEIGHT,
    REGION,
    WIDTH,
    case_record,
    frame,
    inside,
    outside_mask,
    painted,
    prepare,
    window,
)


def test_target_absence_replaces_the_region_with_the_plate_and_touches_nothing_else() -> None:
    record = case_record("target_absence", {"region": REGION, "plate_frame": 2, "noise": 0})

    rendering = prepare(record)
    result = painted(rendering, 7)

    assert np.array_equal(inside(result), inside(frame(2)))
    assert np.array_equal(result[outside_mask()], frame(7)[outside_mask()])
    assert rendering.label_transform == {
        "kind": "region_status",
        "frames": window(0, FRAMES),
        "region": REGION,
        "inside": "absent",
        "overlap": "unknown",
        "overlap_geometry": "unlocalizable",
    }


def test_target_absence_noise_is_bounded_and_differs_per_frame() -> None:
    record = case_record("target_absence", {"region": REGION, "plate_frame": 2, "noise": 3})
    rendering = prepare(record)

    first, second = inside(painted(rendering, 7)), inside(painted(rendering, 8))

    difference = np.abs(first.astype(int) - inside(frame(2)).astype(int))
    assert difference.max() == 3
    assert not np.array_equal(first, second)


def test_noise_reaches_every_value_on_both_sides_of_the_plate() -> None:
    def mid_gray(_: int) -> Pixels:
        return np.full((HEIGHT, WIDTH, 3), 128, dtype=np.uint8)

    record = case_record("target_absence", {"region": REGION, "plate_frame": 2, "noise": 2})
    rendering = prepare_case(record, range(FRAMES), WIDTH, HEIGHT, mid_gray)

    assert rendering.paint is not None
    values = inside(rendering.paint(frame(1), 1)).astype(int) - 128
    assert sorted(set(values.flatten().tolist())) == [-2, -1, 0, 1, 2]


def test_noise_saturates_rather_than_wrapping() -> None:
    def extreme(_: int) -> Pixels:
        return np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)

    record = case_record("target_absence", {"region": REGION, "plate_frame": 2, "noise": 40})
    rendering = prepare_case(record, range(FRAMES), WIDTH, HEIGHT, extreme)

    assert rendering.paint is not None
    result = inside(rendering.paint(frame(1), 1))
    assert result.min() >= 215


def test_short_occlusion_is_one_rigid_textureinside_its_window() -> None:
    record = case_record("short_occlusion", {"region": REGION}, window=window(3, 6))

    rendering = prepare(record)

    assert np.array_equal(inside(painted(rendering, 3)), inside(painted(rendering, 5)))
    assert not np.array_equal(inside(painted(rendering, 3)), inside(frame(3)))
    outside = outside_mask()
    assert np.array_equal(painted(rendering, 3)[outside], frame(3)[outside])
    assert rendering.label_transform["inside"] == "fully_occluded"
    assert rendering.label_transform["overlap"] == "partially_occluded"
    assert rendering.label_transform["frames"] == window(3, 6)


def test_moving_background_stays_in_its_region_and_really_moves() -> None:
    parameters = {"region": REGION, "sprite_count": 3, "sprite_size": 2, "max_speed": 2}

    rendering = prepare(case_record("moving_background", parameters))

    results = [painted(rendering, index) for index in range(3)]
    outside = outside_mask()
    for index, result in enumerate(results):
        assert np.array_equal(result[outside], frame(index)[outside])
    changed = [(inside(r) != inside(frame(i))).any(axis=-1) for i, r in enumerate(results)]
    assert all(mask.any() for mask in changed)
    assert not np.array_equal(changed[0], changed[1])
    assert rendering.label_transform["added_objects"] == "distractor"


def _sprite_column(seed: int, frame_index: int) -> int:
    """Return the column of the only sprite, painted one pixel wide on a black frame."""
    parameters = {"region": REGION, "sprite_count": 1, "sprite_size": 1, "max_speed": 1}
    rendering = prepare(case_record("moving_background", parameters, seed=seed))
    assert rendering.paint is not None
    black = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    rows, columns = np.nonzero(rendering.paint(black, frame_index).any(axis=-1))
    assert len(rows) == 1
    return int(columns[0]) - REGION["x"]


def test_a_sprite_moves_one_step_per_frame_in_a_seeded_direction_and_wraps() -> None:
    region_width = REGION["width"]
    directions = set()
    for seed in range(12):
        path = [_sprite_column(seed, index) for index in range(region_width + 1)]
        step = (path[1] - path[0]) % region_width
        assert step in (1, region_width - 1)
        assert path == [(path[0] + step * index) % region_width for index in range(len(path))]
        directions.add(step)

    assert directions == {1, region_width - 1}


def test_camera_shake_shifts_pixels_by_exactly_the_recorded_offset() -> None:
    rendering = prepare(case_record("camera_shake", {"amplitude": 3}))

    offsets = rendering.label_transform["offsets"]
    assert isinstance(offsets, list)
    assert [item["frame_index"] for item in offsets] == list(range(FRAMES))
    assert rendering.label_transform["camera_motion"] == "shake"
    assert any(item["dx"] or item["dy"] for item in offsets)
    for item in offsets:
        index, dx, dy = item["frame_index"], item["dx"], item["dy"]
        result = painted(rendering, index)
        for row, column in ((5, 7), (6, 8)):
            expected = frame(index)[row, column]
            assert np.array_equal(result[row + dy, column + dx], expected)


def test_camera_shake_repeats_the_nearest_pixel_at_an_exposed_edge() -> None:
    rendering = prepare(case_record("camera_shake", {"amplitude": 3}))
    moved = next(item for item in rendering.label_transform["offsets"] if item["dx"] > 0)
    index, dx = moved["frame_index"], moved["dx"]

    result = painted(rendering, index)

    assert np.array_equal(result[:, 0], result[:, dx - 1])


def test_blur_of_a_flat_frame_changes_nothing() -> None:
    flat = np.full((HEIGHT, WIDTH, 3), 77, dtype=np.uint8)

    rendering = prepare(case_record("blur", {"max_radius": 3}))

    assert rendering.paint is not None
    assert np.array_equal(rendering.paint(flat, 2), flat)


def test_blur_matches_a_hand_computed_box_average_with_repeated_edges() -> None:
    impulse = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    impulse[6, 8] = 90

    rendering = prepare(case_record("blur", {"max_radius": 1}))

    assert rendering.paint is not None
    result = rendering.paint(impulse, 0)
    assert result[6, 8, 0] == 10
    assert result[5, 7, 2] == 10
    assert result[6, 10, 0] == 0
    assert result.sum() == 9 * 10 * 3


def test_blur_rounds_each_average_to_the_nearest_value() -> None:
    impulse = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    impulse[6, 8] = 95

    rendering = prepare(case_record("blur", {"max_radius": 1}))

    assert rendering.paint is not None
    assert rendering.paint(impulse, 0)[6, 8, 0] == 11


def test_blur_keeps_labels_as_they_are() -> None:
    assert prepare(case_record("blur", {"max_radius": 2})).label_transform == {"kind": "identity"}


def test_dropped_frames_removes_exactly_the_recorded_framesinside_the_window() -> None:
    rendering = prepare(case_record("dropped_frames", {"count": 3}, window=window(2, 8)))

    removed = rendering.label_transform["removed"]
    assert isinstance(removed, list)
    assert len(removed) == 3
    assert set(removed) <= set(range(2, 8))
    assert [slot.frame_index for slot in rendering.slots] == [
        index for index in range(FRAMES) if index not in removed
    ]
    assert all(slot.content_frame_index == slot.frame_index for slot in rendering.slots)
    assert rendering.paint is None


def test_duplicated_frames_shows_the_previous_frame_at_its_own_index() -> None:
    rendering = prepare(case_record("duplicated_frames", {"count": 3}))

    repeated = rendering.label_transform["repeated"]
    assert isinstance(repeated, list)
    assert len(repeated) == 3
    stale = {item["frame_index"]: item["content_frame_index"] for item in repeated}
    assert [slot.frame_index for slot in rendering.slots] == list(range(FRAMES))
    for slot in rendering.slots:
        assert slot.content_frame_index == stale.get(slot.frame_index, slot.frame_index)
        assert slot.content_frame_index <= slot.frame_index


def test_consecutive_duplicates_all_show_the_last_real_frame() -> None:
    rendering = prepare(case_record("duplicated_frames", {"count": 4}, window=window(1, 5)))

    assert [slot.content_frame_index for slot in rendering.slots[:6]] == [0, 0, 0, 0, 0, 5]


def test_the_first_frame_of_a_selection_never_repeats_a_frame_outside_it() -> None:
    selection = range(3, 8)
    record = case_record("duplicated_frames", {"count": 4}, window=window(3, 8))

    rendering = prepare(record, selection)

    assert rendering.slots[0].content_frame_index == 3

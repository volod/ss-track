"""Which recipes a parent refuses, and what the seed decides."""

from collections.abc import Callable

import numpy as np
import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode
from ss_track.corpus.case_model import Rendering
from tests.corpus._case_frames import (
    FRAMES,
    HEIGHT,
    REGION,
    case_record,
    painted,
    prepare,
    window,
)

_REFUSED = [
    pytest.param(
        "target_absence",
        {"region": {"x": 12, "y": 0, "width": 5, "height": 2}, "plate_frame": 0, "noise": 0},
        {},
        "region",
        id="region-past-right",
    ),
    pytest.param(
        "short_occlusion",
        {"region": {"x": 0, "y": 10, "width": 2, "height": 3}},
        {"window": window(1, 2)},
        "region",
        id="region-past-bottom",
    ),
    pytest.param(
        "target_absence",
        {"region": REGION, "plate_frame": FRAMES, "noise": 0},
        {},
        "plate_frame",
        id="plate-outside-selection",
    ),
    pytest.param(
        "moving_background",
        {"region": REGION, "sprite_count": 1, "sprite_size": 6, "max_speed": 1},
        {},
        "sprite_size",
        id="sprite-larger-than-region",
    ),
    pytest.param("short_occlusion", {"region": REGION}, {}, "before and after", id="whole-stream"),
    pytest.param(
        "short_occlusion",
        {"region": REGION},
        {"window": window(0, 4)},
        "before and after",
        id="no-frame-before",
    ),
    pytest.param(
        "short_occlusion",
        {"region": REGION},
        {"window": window(4, FRAMES)},
        "before and after",
        id="no-frame-after",
    ),
    pytest.param("camera_shake", {"amplitude": HEIGHT}, {}, "amplitude", id="shake-too-large"),
    pytest.param("blur", {"max_radius": HEIGHT}, {}, "max_radius", id="blur-too-large"),
    pytest.param("dropped_frames", {"count": FRAMES}, {}, "at least one", id="drop-everything"),
    pytest.param(
        "dropped_frames", {"count": 3}, {"window": window(0, 2)}, "window", id="drop-past-window"
    ),
    pytest.param(
        "duplicated_frames", {"count": FRAMES}, {}, "predecessor", id="duplicate-first-frame"
    ),
    pytest.param(
        "blur", {"max_radius": 1}, {"window": window(0, FRAMES + 1)}, "window", id="window-past-end"
    ),
]


@pytest.mark.parametrize(("transform", "parameters", "fields", "fragment"), _REFUSED)
def test_a_recipe_its_parent_cannot_satisfy_is_refused(
    transform: str, parameters: dict[str, object], fields: dict[str, object], fragment: str
) -> None:
    with pytest.raises(CorpusRefusal) as caught:
        prepare(case_record(transform, parameters, **fields))

    assert caught.value.code is RefusalCode.CASE_INVALID
    assert fragment in caught.value.message
    assert caught.value.details == {"case_id": "case", "transform": transform}


def test_a_window_before_the_parent_selection_is_refused() -> None:
    with pytest.raises(CorpusRefusal) as caught:
        prepare(case_record("blur", {"max_radius": 1}, window=window(1, 4)), range(2, 8))

    assert caught.value.code is RefusalCode.CASE_INVALID


_SEEDED: list[tuple[str, dict[str, object], Callable[[Rendering], object]]] = [
    (
        "target_absence",
        {"region": REGION, "plate_frame": 2, "noise": 5},
        lambda r: painted(r, 4).tobytes(),
    ),
    (
        "moving_background",
        {"region": REGION, "sprite_count": 2, "sprite_size": 2, "max_speed": 3},
        lambda r: painted(r, 4).tobytes(),
    ),
    ("camera_shake", {"amplitude": 3}, lambda r: r.label_transform),
    ("blur", {"max_radius": 4}, lambda r: [painted(r, i).tobytes() for i in range(FRAMES)]),
    ("dropped_frames", {"count": 3}, lambda r: r.label_transform),
    ("duplicated_frames", {"count": 3}, lambda r: r.label_transform),
]


@pytest.mark.parametrize(("transform", "parameters", "observe"), _SEEDED, ids=lambda v: None)
def test_the_seed_decides_the_result(
    transform: str, parameters: dict[str, object], observe: Callable[[Rendering], object]
) -> None:
    same = [observe(prepare(case_record(transform, parameters, seed=seed))) for seed in (5, 5, 6)]

    assert same[0] == same[1]
    assert same[0] != same[2]


def test_the_seed_decides_an_occluder_texture() -> None:
    fields = {"window": window(2, 5)}
    one = painted(prepare(case_record("short_occlusion", {"region": REGION}, seed=1, **fields)), 3)
    two = painted(prepare(case_record("short_occlusion", {"region": REGION}, seed=2, **fields)), 3)

    assert not np.array_equal(one, two)

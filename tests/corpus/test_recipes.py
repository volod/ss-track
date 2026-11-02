"""Strict reading of generated-case recipes in a corpus declaration."""

from pathlib import Path

import pytest

from ss_track.corpus import CorpusRefusal, RefusalCode
from ss_track.corpus.declaration import load_corpus_declaration
from ss_track.corpus.recipes import MAX_SEED, MAX_SPRITES
from ss_track.corpus.transforms import TRANSFORM_REVISIONS
from tests.corpus.conftest import case_of, encounter_of, group_of, write_groups

_SHA256 = "a" * 64
_REGION = {"x": 0, "y": 0, "width": 4, "height": 4}


def _write(media: Path, recipe: object) -> Path:
    stream = {"stream_id": "one", "source_sha256": _SHA256, "generated_cases": [recipe]}
    return write_groups(media, [group_of("g", "development", encounter_of("e", stream))])


def _refused(media: Path, recipe: object) -> CorpusRefusal:
    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_declaration(_write(media, recipe))
    return caught.value


@pytest.mark.parametrize(
    ("transform", "parameters"),
    [
        ("target_absence", {"region": _REGION, "plate_frame": 0, "noise": 0}),
        (
            "moving_background",
            {"region": _REGION, "sprite_count": 1, "sprite_size": 1, "max_speed": 1},
        ),
        ("camera_shake", {"amplitude": 1}),
        ("blur", {"max_radius": 1}),
        ("dropped_frames", {"count": 1}),
        ("duplicated_frames", {"count": 1}),
        ("short_occlusion", {"region": _REGION}),
    ],
)
def test_every_transform_reads_its_own_parameters(
    media: Path, transform: str, parameters: dict[str, object]
) -> None:
    recipe = case_of("case", transform, 3, parameters)

    declared = load_corpus_declaration(_write(media, recipe)).groups[0].encounters[0]

    assert declared.streams[0].generated_cases[0].parameters == parameters


def test_the_declared_transforms_are_the_implemented_transforms(media: Path) -> None:
    refusal = _refused(media, case_of("case", "no_such_transform", 1, {}))

    assert refusal.code is RefusalCode.MANIFEST_INVALID
    for transform in TRANSFORM_REVISIONS:
        assert transform in refusal.message


def test_a_window_is_read_as_a_half_open_selection(media: Path) -> None:
    window = {"start_frame": 2, "end_frame": 5}
    recipe = case_of("case", "blur", 1, {"max_radius": 1}, window=window)

    stream = load_corpus_declaration(_write(media, recipe)).groups[0].encounters[0].streams[0]

    assert stream.generated_cases[0].window is not None
    assert stream.generated_cases[0].window.end_frame == 5


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        pytest.param({"split": "locked"}, "unknown fields", id="own-split"),
        pytest.param({"encounter_id": "new"}, "unknown fields", id="own-encounter"),
        pytest.param({"group_id": "new"}, "unknown fields", id="own-group"),
        pytest.param({"seed": -1}, "seed", id="negative-seed"),
        pytest.param({"seed": True}, "seed", id="bool-seed"),
        pytest.param({"seed": "7"}, "seed", id="text-seed"),
        pytest.param({"seed": MAX_SEED + 1}, "seed", id="seed-too-large"),
        pytest.param({"case_id": "../escape"}, "case_id", id="traversal-id"),
        pytest.param({"window": {"start_frame": 5, "end_frame": 5}}, "window", id="empty-window"),
        pytest.param({"parameters": {}}, "max_radius", id="no-parameter"),
        pytest.param({"parameters": {"max_radius": 0}}, "max_radius", id="zero-radius"),
        pytest.param({"parameters": {"max_radius": 1, "x": 1}}, "unknown", id="extra-parameter"),
    ],
)
def test_a_malformed_recipe_is_refused(
    media: Path, change: dict[str, object], fragment: str
) -> None:
    recipe = case_of("case", "blur", 1, {"max_radius": 1}) | change

    refusal = _refused(media, recipe)

    assert refusal.code is RefusalCode.MANIFEST_INVALID
    assert fragment in refusal.message


@pytest.mark.parametrize("missing", ["case_id", "transform", "seed", "parameters"])
def test_nothing_in_a_recipe_has_a_default(media: Path, missing: str) -> None:
    recipe = case_of("case", "blur", 1, {"max_radius": 1})
    del recipe[missing]

    assert _refused(media, recipe).code is RefusalCode.MANIFEST_INVALID


@pytest.mark.parametrize(
    ("transform", "parameters", "fragment"),
    [
        pytest.param(
            "target_absence",
            {"region": _REGION, "plate_frame": 0, "noise": 256},
            "noise",
            id="noise-beyond-a-component",
        ),
        pytest.param(
            "moving_background",
            {
                "region": _REGION,
                "sprite_count": MAX_SPRITES + 1,
                "sprite_size": 1,
                "max_speed": 1,
            },
            "sprite_count",
            id="too-many-sprites",
        ),
        pytest.param(
            "short_occlusion",
            {"region": {"x": 0, "y": 0, "width": 0, "height": 4}},
            "width",
            id="empty-region",
        ),
        pytest.param(
            "short_occlusion", {"region": {"x": 0, "y": 0, "width": 4}}, "height", id="open-region"
        ),
    ],
)
def test_a_parameter_outside_its_rule_is_refused(
    media: Path, transform: str, parameters: dict[str, object], fragment: str
) -> None:
    refusal = _refused(media, case_of("case", transform, 1, parameters))

    assert refusal.code is RefusalCode.MANIFEST_INVALID
    assert fragment in refusal.message


def test_an_empty_case_list_is_refused_rather_than_read_as_no_cases(media: Path) -> None:
    stream = {"stream_id": "one", "source_sha256": _SHA256, "generated_cases": []}
    path = write_groups(media, [group_of("g", "development", encounter_of("e", stream))])

    with pytest.raises(CorpusRefusal) as caught:
        load_corpus_declaration(path)

    assert caught.value.code is RefusalCode.MANIFEST_INVALID

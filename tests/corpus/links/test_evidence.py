"""Background cosine against hand-calculated rows: tile positions average, gaps are named."""

from typing import Any, cast

import numpy as np

from ss_track.core.refusal import JsonValue
from ss_track.corpus.discovery.features import FeatureFile
from ss_track.corpus.discovery.records import DiscoveryRecords
from ss_track.corpus.links.evidence import BACKGROUND_THRESHOLDS, background_evidence
from ss_track.corpus.links.review import Flag
from tests.corpus.links._links import A, B, C, D, stream

STREAMS = [
    stream("s1", A, "g1"),
    stream("s2", B, "g2"),
    stream("s3", C, "g1"),
    stream("s4", D, "g3"),
]
ROWS: dict[str, dict[str, list[tuple[float, float]]]] = {
    "clip": {
        "s1": [(1, 0), (1, 0)],
        "s2": [(0.96, 0.28)],
        "s3": [(0, 1)],
        "s4": [(0.6, -0.8), (0, -1)],
    },
    "tiles.r0c0": {"s1": [(1, 0)], "s2": [(1, 0)], "s3": [(0, 1)]},
    "tiles.r0c1": {"s1": [(1, 0)], "s2": [(0.96, 0.28)], "s3": [(0, 1)]},
}


def _feature(extractor_id: str, stream_id: str, rows: list[tuple[float, float]]) -> FeatureFile:
    record = {
        "extractor_id": extractor_id,
        "stream_id": stream_id,
        "dimensions": 2,
        "rows": [{"frame_index": index} for index in range(len(rows))],
    }
    return FeatureFile(cast(dict[str, JsonValue], record), np.array(rows, dtype="<f4").tobytes())


def _extractor(
    extractor_id: str, crop: str, tile: dict[str, int] | None = None, architecture: str = "ViT-B-16"
) -> dict[str, Any]:
    preprocessing: dict[str, Any] = {"crop": crop} | ({"tile": tile} if tile else {})
    return {
        "extractor_id": extractor_id,
        "architecture": architecture,
        "preprocessing": preprocessing,
    }


def _records() -> DiscoveryRecords:
    extractors = [
        _extractor("clip", "center"),
        *(_extractor(f"tiles.r0c{column}", "tiled", {"column": column}) for column in (0, 1)),
    ]
    features = {
        f"{extractor}/{stream_id}": _feature(extractor, stream_id, rows)
        for extractor, held in ROWS.items()
        for stream_id, rows in held.items()
    }
    return DiscoveryRecords(cast(dict[str, JsonValue], {"extractors": extractors}), {}, features)


def test_backgrounds_flag_pairs_in_different_groups_and_tiles_average_their_cosines() -> None:
    assert BACKGROUND_THRESHOLDS[("ViT-B-16", "center")] <= 0.96  # values are chosen against it
    assert BACKGROUND_THRESHOLDS[("ViT-B-16", "tiled")] <= 0.96

    evidence = background_evidence(STREAMS, _records())

    assert evidence.flags == (
        Flag("background-cosine", "clip", 0.96, ("s1", "s2")),
        Flag("background-cosine", "tiles", 0.98, ("s1", "s2")),
    )
    assert [method["run_extractor_ids"] for method in evidence.methods] == [
        ["clip"],
        ["tiles.r0c0", "tiles.r0c1"],
    ]


def test_a_stream_without_rows_for_every_tile_position_is_named_not_compared() -> None:
    evidence = background_evidence(STREAMS, _records())

    assert [gap.to_record() for gap in evidence.gaps] == [
        {
            "method": "background-cosine",
            "extractor_id": "tiles",
            "reason": "no_feature_rows",
            "stream_ids": ["s4"],
        }
    ]


def test_a_stream_background_is_the_unit_mean_of_its_rows() -> None:
    """(1, 0) and (0, 1) average to (0.7071, 0.7071), whose cosine to (0.6, 0.8) is 0.9899.

    Either row alone would give 0.6 or 0.8.
    """
    streams = [stream("m1", A, "g1"), stream("m2", B, "g2")]
    features = {
        "clip/m1": _feature("clip", "m1", [(1, 0), (0, 1)]),
        "clip/m2": _feature("clip", "m2", [(0.6, 0.8)]),
    }
    run: Any = {"extractors": [_extractor("clip", "center")]}

    evidence = background_evidence(streams, DiscoveryRecords(run, {}, features))

    assert evidence.flags == (Flag("background-cosine", "clip", 0.9899, ("m1", "m2")),)


def test_a_similarity_at_the_threshold_flags_and_one_below_does_not() -> None:
    """DINOv2 centre crops flag at 0.6: (0.6, 0.8) to (1, 0) is 0.6, (0.5998, 0.8002) is not."""
    streams = [stream("t1", A, "g1"), stream("t2", B, "g2"), stream("t3", C, "g3")]
    features = {
        "dino/t1": _feature("dino", "t1", [(1, 0)]),
        "dino/t2": _feature("dino", "t2", [(0.6, 0.8)]),
        "dino/t3": _feature("dino", "t3", [(0.5998, 0.8002)]),
    }
    run: Any = {"extractors": [_extractor("dino", "center", architecture="dinov3_vitb14")]}

    evidence = background_evidence(streams, DiscoveryRecords(run, {}, features))

    assert BACKGROUND_THRESHOLDS[("dinov3_vitb14", "center")] == 0.6
    assert [flag.stream_ids for flag in evidence.flags] == [("t1", "t2"), ("t2", "t3")]


def test_a_backbone_without_a_measured_threshold_is_named_not_compared() -> None:
    run: Any = {"extractors": [_extractor("other", "center", architecture="ViT-L-14")]}
    features = {"other/s1": _feature("other", "s1", [(1, 0)])}

    evidence = background_evidence(STREAMS, DiscoveryRecords(run, {}, features))

    assert evidence.methods == ()
    assert evidence.flags == ()
    assert [gap.to_record() for gap in evidence.gaps] == [
        {
            "method": "background-cosine",
            "extractor_id": "other",
            "reason": "no_threshold",
            "stream_ids": ["s1", "s2", "s3", "s4"],
        }
    ]

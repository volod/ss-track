"""Pinned output of every transform revision.

A generated case is evidence: one recipe must give the same bytes for as long as its revision
exists. If a change fails here, raise that transform's revision and add a new entry; never edit an
entry, because stored cases depend on it. Input frames come from a hash, so no codec or library can
move them.
"""

import hashlib

import numpy as np
import pytest

from ss_track.core.canonical import canonical_json
from ss_track.corpus.cases.case_model import Pixels, as_pixels
from ss_track.corpus.cases.transforms import TRANSFORM_REVISIONS, prepare_case
from tests.corpus.cases._case_frames import track_parameters

_WIDTH = 32
_HEIGHT = 24
_SELECTION = range(2, 14)
_WINDOW = {"start_frame": 4, "end_frame": 11}
_REGION = {"x": 5, "y": 3, "width": 16, "height": 12}
_TRACK_BOX = {"x": 4, "y": 3, "width": 6, "height": 5}
_TRACK_FRAMES = [4, 6, 7, 8, 9, 10]
_COVER = {"start_frame": 6, "end_frame": 9}
_RECIPES: dict[str, dict[str, object]] = {
    "target_absence": {"region": _REGION, "plate_frame": 2, "noise": 6},
    "moving_background": {"region": _REGION, "sprite_count": 4, "sprite_size": 3, "max_speed": 3},
    "camera_shake": {"amplitude": 4},
    "blur": {"max_radius": 3},
    "dropped_frames": {"count": 3},
    "duplicated_frames": {"count": 3},
    "short_occlusion": {"region": _REGION},
    "compression": {"max_step": 8},
    "variable_timing": {"max_scale": 4},
    "crossing_occluder": track_parameters(_TRACK_FRAMES, _TRACK_BOX, cover=_COVER),
    "moving_removal": track_parameters(_TRACK_FRAMES, _TRACK_BOX, plate_frame=2, noise=4),
    "similar_distractor": track_parameters(_TRACK_FRAMES, _TRACK_BOX),
    "out_of_view": track_parameters(_TRACK_FRAMES, _TRACK_BOX, outside=_COVER),
}
_GOLDEN: dict[tuple[str, int], str] = {
    ("blur", 1): "fa3aeb6d6b9b6003d39e9b7b1827c3c68e6b058d6371190384189c2667831b53",
    ("camera_shake", 1): "3438c6ebc5f40e31ce8b2ba9459958c94948f4a071037f14d200cc6cca05467e",
    ("dropped_frames", 1): "aa9b845b779dca244eb82bd12472a192216d5a5ef8df3aa27f2f160df1d68870",
    ("duplicated_frames", 1): "e39eb313ce3fd9a4a6016c4f6ff043a92189f4ae96d2ea3ec265f3d995900003",
    ("moving_background", 1): "110c234849899fbc9f2bc3e055c0f13fa5aaf523c056af37be09d999f84a9e9e",
    ("short_occlusion", 1): "ed22f544252ad8dc757ff9c407f79d92183a3ad5db58ff381b20518047ee5542",
    ("target_absence", 1): "28d97e65ef8857a7c126c61369bd069ed294da038c5f75bec47d4723b232c91f",
    ("compression", 1): "db6fd2df8e6e0048e965590d64edd2e5c78f9699b059cdb95351c2f78fdc4ae3",
    ("variable_timing", 1): "d9d05fdf5e674456796799265f90a55c5d6baabeae8e3ef5b9094f68ec52f3c5",
    ("crossing_occluder", 1): "fb80a80f74dcf71ce098af044acca8dfa5b28023bddc0c8873b91349a8f67796",
    ("moving_removal", 1): "b57680ac3f1b04216d355ab90309c49c7b198ffd0aeb156f35fe295d7b3b75fe",
    ("out_of_view", 1): "1d145c3bb40d095479c18a135baba9543d5ab345904e3166ee805ab8e284039b",
    ("similar_distractor", 1): "ddcfc4ecdd1dd963645b1271b88ff7c284c541f4f4b7b121f0a0dcd069cfcd3c",
}


def _frame(index: int) -> Pixels:
    raw = hashlib.shake_256(f"golden-frame-{index}".encode("ascii"))
    return as_pixels(raw.digest(_WIDTH * _HEIGHT * 3), _WIDTH, _HEIGHT)


def result_digest(transform: str) -> str:
    """Hash every output frame, its place, its content frame and the label transform."""
    case = {
        "case_id": "golden",
        "transform": transform,
        "seed": 20261101,
        "window": _WINDOW,
        "parameters": _RECIPES[transform],
    }
    rendering = prepare_case(case, _SELECTION, _WIDTH, _HEIGHT, _frame)
    digest = hashlib.sha256(canonical_json(rendering.label_transform))
    for slot in rendering.slots:
        pixels = _frame(slot.content_frame_index)
        digest.update(f"{slot.frame_index}:{slot.content_frame_index}".encode("ascii"))
        if rendering.paint is not None and slot.frame_index in range(4, 11):
            pixels = rendering.paint(pixels, slot.frame_index)
        digest.update(np.asarray(pixels).tobytes())
    return digest.hexdigest()


@pytest.mark.parametrize(("transform", "revision"), sorted(TRANSFORM_REVISIONS.items()))
def test_a_transform_revision_always_produces_the_same_bytes(transform: str, revision: int) -> None:
    assert result_digest(transform) == _GOLDEN[(transform, revision)]


def test_every_declared_transform_is_pinned() -> None:
    assert set(_RECIPES) == set(TRANSFORM_REVISIONS)

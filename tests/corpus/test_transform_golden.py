"""Pinned output of every transform revision.

A generated case is evidence: one recipe must give the same bytes for as long as its revision
exists. If a change fails here, raise that transform's revision and add a new entry; never edit an
entry, because stored cases depend on it. Input frames come from a hash, so no codec or library can
move them.
"""

import hashlib

import numpy as np
import pytest

from ss_track.corpus.case_model import Pixels, as_pixels
from ss_track.corpus.sealed import canonical_json
from ss_track.corpus.transforms import TRANSFORM_REVISIONS, prepare_case

_WIDTH = 32
_HEIGHT = 24
_SELECTION = range(2, 14)
_WINDOW = {"start_frame": 4, "end_frame": 11}
_REGION = {"x": 5, "y": 3, "width": 16, "height": 12}
_RECIPES: dict[str, dict[str, object]] = {
    "target_absence": {"region": _REGION, "plate_frame": 2, "noise": 6},
    "moving_background": {"region": _REGION, "sprite_count": 4, "sprite_size": 3, "max_speed": 3},
    "camera_shake": {"amplitude": 4},
    "blur": {"max_radius": 3},
    "dropped_frames": {"count": 3},
    "duplicated_frames": {"count": 3},
    "short_occlusion": {"region": _REGION},
}
_GOLDEN: dict[tuple[str, int], str] = {
    ("blur", 1): "fa3aeb6d6b9b6003d39e9b7b1827c3c68e6b058d6371190384189c2667831b53",
    ("camera_shake", 1): "3438c6ebc5f40e31ce8b2ba9459958c94948f4a071037f14d200cc6cca05467e",
    ("dropped_frames", 1): "aa9b845b779dca244eb82bd12472a192216d5a5ef8df3aa27f2f160df1d68870",
    ("duplicated_frames", 1): "e39eb313ce3fd9a4a6016c4f6ff043a92189f4ae96d2ea3ec265f3d995900003",
    ("moving_background", 1): "110c234849899fbc9f2bc3e055c0f13fa5aaf523c056af37be09d999f84a9e9e",
    ("short_occlusion", 1): "ed22f544252ad8dc757ff9c407f79d92183a3ad5db58ff381b20518047ee5542",
    ("target_absence", 1): "28d97e65ef8857a7c126c61369bd069ed294da038c5f75bec47d4723b232c91f",
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

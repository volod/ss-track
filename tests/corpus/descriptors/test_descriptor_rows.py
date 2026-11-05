"""One frame row builder serves the restricted and the public descriptor."""

from typing import Any

from ss_track.corpus.descriptors.descriptor_rows import LAYOUT_KEYS, frame_rows

_IDENTITY: dict[str, Any] = {
    "width": 64,
    "height": 48,
    "pixel_format": "rgb24",
    "bytes_per_frame": 9216,
    "time_base": "1/1000",
    "frames": [
        {"frame_index": 3, "pts": 120, "sha256": "a" * 64},
        {"frame_index": 4, "content_frame_index": 3, "pts": 160, "sha256": "a" * 64},
    ],
}
_BUNDLE: dict[str, Any] = {"stream_id": "one", "generated": None, "identity": _IDENTITY}


def test_a_full_record_gives_every_fact_and_the_frame_path() -> None:
    first, repeated = frame_rows(_BUNDLE)

    assert first == {
        "stream_id": "one",
        "frame_index": 3,
        "content_frame_index": 3,
        "pts": 120,
        "sha256": "a" * 64,
        **{key: _IDENTITY[key] for key in LAYOUT_KEYS},
        "path": "../../frames/one/00000003.rgb24",
        "generated": False,
    }
    assert repeated["content_frame_index"] == 3
    assert repeated["path"] == "../../frames/one/00000004.rgb24"


def test_a_projected_record_gives_only_the_facts_it_kept() -> None:
    identity = {"width": 64, "frames": [{"frame_index": 3}, {"pts": 160}]}

    rows = list(frame_rows({"identity": identity}))

    assert rows == [
        {"frame_index": 3, "content_frame_index": 3, "width": 64},
        {"pts": 160, "width": 64},
    ]


def test_a_record_with_no_public_index_gives_no_row() -> None:
    assert list(frame_rows({"stream_id": "one"})) == []
    assert list(frame_rows({"identity": {"frames": [{}, "not an entry"]}})) == []

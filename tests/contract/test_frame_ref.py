"""The staged frame reference round-trips through its event, including its meanings."""

import json
from pathlib import Path

from ss_track.contract.frame_ref import frame_ref_from_line, frame_ref_line
from ss_track.contract.gen import frame_pb2
from ss_track.contract.image import package_urn, top_field_comments
from ss_track.corpus.bundles.frames import FrameRef

_SHA = "cd" * 32
_ROOT = Path(__file__).resolve().parents[2]


def _ref(**overrides: object) -> FrameRef:
    values: dict[str, object] = {
        "stream_id": "cam",
        "source_sha256": _SHA,
        "frame_index": 4,
        "content_frame_index": 4,
        "pts": None,
        "time_base": None,
        "timestamp_quality": "derived",
        "capture_clock_evidence": None,
        "width": 16,
        "height": 16,
        "pixel_format": "yuv420p",
        "transform": "identity",
        "bundle_sha256": _SHA,
        "frame_name": "frame-0004",
        "sha256": _SHA,
    }
    return FrameRef(**(values | overrides))  # type: ignore[arg-type]


def test_every_staged_field_round_trips() -> None:
    ref = _ref(pts=0, time_base="1/30", capture_clock_evidence="operator log")

    assert frame_ref_from_line(frame_ref_line(ref)) == ref


def test_zero_pts_and_a_generated_transform_keep_their_meaning() -> None:
    ref = _ref(content_frame_index=1, pts=0, transform="camera_shake")
    line = frame_ref_line(ref)
    body = json.loads(line)

    assert body["pts"] == "0"
    assert body["content_frame_index"] == 1
    assert body["transform"] == "camera_shake"
    assert "streamId" not in body
    assert frame_ref_from_line(line) == ref


def test_proto_fields_use_the_staged_names() -> None:
    proto_names = [field.name for field in frame_pb2.FrameRef.DESCRIPTOR.fields]

    assert proto_names == list(FrameRef.__dataclass_fields__)


def test_frozen_comments_state_content_and_transform() -> None:
    payload = (_ROOT / "contracts" / "event" / "frame" / "1.0.0.binpb").read_bytes()
    comments = top_field_comments(payload, package_urn(payload, "frame"))

    assert "parent frame" in comments["FrameRef.content_frame_index"]
    assert "identity" in comments["FrameRef.transform"]

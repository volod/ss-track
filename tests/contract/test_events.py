"""Protobuf-JSON lines keep one meaning, and a bad line is rejected with a reason."""

import json
from pathlib import Path

import pytest

from ss_track.contract.events import message_names, parse_json_lines
from ss_track.core.refusal import CorpusRefusal, RefusalCode

FIXTURES = Path(__file__).parent / "fixtures"
_SHA = "ab" * 32


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="ascii")


def _clock(ticks: int = 1) -> dict[str, object]:
    return {
        "domain": "MEDIA_PTS",
        "source": "container",
        "ticks": str(ticks),
        "time_base": "1/30",
        "uncertainty_seconds": 0,
    }


def _ref() -> dict[str, object]:
    return {
        "event_id": "event-1",
        "stream_id": "cam",
        "frame_index": 0,
        "bundle_sha256": _SHA,
    }


def _line(body: dict[str, object]) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def test_an_absent_optional_frame_is_accepted() -> None:
    parsed = parse_json_lines(_text("frame-absent.jsonl"), "FrameRef")

    assert "pts" not in parsed[0]
    assert "time_base" not in parsed[0]
    assert parsed[0]["timestamp_quality"] == "missing"


def test_an_empty_frame_result_is_a_result() -> None:
    parsed = parse_json_lines(_text("frame-result-empty.jsonl"), "FrameResult")

    assert parsed[0]["ref"]["event_id"] == "e"
    assert "detections" not in parsed[0]
    assert "tracks" not in parsed[0]


def test_unknown_malformed_and_unit_lines_name_the_reason() -> None:
    cases = {
        "frame-unknown.jsonl": ("FrameRef", "no field named"),
        "frame-malformed.jsonl": ("FrameRef", "line 1: malformed JSON"),
        "box-extent.jsonl": ("Box", "positive half-open"),
        "clock-time-base.jsonl": ("ClockTime", "numerator/denominator"),
        "power-unit.jsonl": ("PowerSample", "watts are measured in W"),
    }
    for name, (message, reason) in cases.items():
        with pytest.raises(CorpusRefusal, match=reason) as caught:
            parse_json_lines(_text(name), message)
        assert caught.value.code == RefusalCode.RECORD_INVALID


def test_a_later_bad_line_names_its_number() -> None:
    text = _text("frame-result-empty.jsonl") + "{\n"

    with pytest.raises(CorpusRefusal, match="line 3: malformed JSON") as caught:
        parse_json_lines(text, "FrameResult")

    assert caught.value.details["line"] == 3


def test_g2_messages_are_not_events() -> None:
    names = set(message_names())

    assert {"FrameRef", "RunManifest", "HardwareTrial", "PowerSample"} <= names
    assert not names & {"SensorObservation", "FusionState", "AcquisitionDecision"}


@pytest.mark.parametrize(
    ("message", "body", "reason"),
    [
        (
            "ClockTime",
            {"domain": "MEDIA_PTS", "source": "capture", "ticks": "1", "uncertainty_seconds": 0},
            "not capture time",
        ),
        ("EventRef", {"event_id": "event-1", "unframed": True}, "needs an interval"),
        (
            "TrackState",
            {"track_id": "t", "update": "PREDICTED", "presence_confidence": 0},
            "needs a box",
        ),
        (
            "AdvisoryAction",
            {"ref": "REF", "kind": "HOLD", "horizon_seconds": 1, "reason": "wait"},
            "instance_id must be non-blank",
        ),
        (
            "DerivedEnergy",
            {
                "ref": "UNFRAMED",
                "method": "integrate",
                "start": "CLOCK",
                "end": "END",
                "joules": 1,
                "uncertainty": 0,
                "unit": "W",
            },
            "measured in J",
        ),
    ],
)
def test_semantic_rules_reject_with_a_reason(
    message: str, body: dict[str, object], reason: str
) -> None:
    if body.get("ref") == "REF":
        body = body | {"ref": _ref()}
    if body.get("ref") == "UNFRAMED":
        body = body | {
            "ref": {
                "event_id": "span",
                "unframed": True,
                "interval_start": _clock(),
                "interval_end": _clock(2),
            }
        }
    if body.get("start") == "CLOCK":
        body = body | {"start": _clock(), "end": _clock(2)}

    with pytest.raises(CorpusRefusal, match=reason):
        parse_json_lines(_line(body) + "\n", message)

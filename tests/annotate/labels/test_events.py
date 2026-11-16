"""One rule decides how a motion event follows its onset frame, in a freeze and in a derivation."""

import pytest

from ss_track.annotate.labels.events import EventState, follow_frame

_REVIEWED = "reviewed"
_UNCERTAIN = "uncertain"


@pytest.mark.parametrize(
    ("stated", "frame_visibility", "expected"),
    [
        (
            EventState("visible", False, _REVIEWED),
            "visible",
            EventState("visible", False, _REVIEWED),
        ),
        (
            EventState("visible", True, _REVIEWED),
            "visible",
            EventState("visible", True, _REVIEWED),
        ),
        (
            EventState("visible", True, _REVIEWED),
            "partially_occluded",
            EventState("partially_occluded", True, _UNCERTAIN),
        ),
        (
            EventState("visible", False, _REVIEWED),
            "absent",
            EventState("absent", False, _UNCERTAIN),
        ),
        (
            EventState("visible", True, _REVIEWED),
            "unknown",
            EventState("unknown", False, _UNCERTAIN),
        ),
        (
            EventState("fully_occluded", False, _REVIEWED),
            "fully_occluded",
            EventState("fully_occluded", False, _REVIEWED),
        ),
        (
            EventState("visible", False, _UNCERTAIN),
            "visible",
            EventState("visible", False, _UNCERTAIN),
        ),
    ],
)
def test_an_event_follows_its_onset_frame(
    stated: EventState, frame_visibility: str, expected: EventState
) -> None:
    assert follow_frame(stated, frame_visibility) == expected

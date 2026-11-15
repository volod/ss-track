"""Disposition order. An unverifiable frame is never reported as a numeric zero."""

import pytest

from ss_track.annotate.disposition import frame_disposition

_REVIEWED = {
    "identity": "reviewed",
    "mark": None,
    "visibility": "visible",
    "kind": "box",
    "plausible_extent_px": None,
}


@pytest.mark.parametrize(
    ("overrides", "status", "reason"),
    [
        ({}, "scorable", None),
        ({"identity": "identity_ambiguous"}, "unscorable", "identity_ambiguous"),
        (
            {"mark": "unknown", "visibility": "absent", "kind": "unlocalizable"},
            "unscorable",
            "unknown_mark",
        ),
        (
            {"mark": "ignore_region", "visibility": "unknown", "kind": "unlocalizable"},
            "not_denominator",
            "ignore_region",
        ),
        ({"visibility": "unknown", "kind": "unlocalizable"}, "unscorable", "unknown"),
        (
            {"visibility": "fully_occluded", "kind": "unlocalizable"},
            "not_denominator",
            "fully_occluded",
        ),
        ({"visibility": "out_of_view", "kind": "unlocalizable"}, "not_denominator", "out_of_view"),
        ({"visibility": "absent", "kind": "unlocalizable"}, "not_denominator", "absent"),
        ({"kind": "unlocalizable"}, "unscorable", "unlocalizable"),
        ({"kind": "point_only"}, "not_denominator", "no_plausible_extent"),
        ({"kind": "point_only", "plausible_extent_px": 4}, "scorable", None),
    ],
)
def test_frame_status_follows_the_rule_order(
    overrides: dict[str, object], status: str, reason: str | None
) -> None:
    found = frame_disposition(**{**_REVIEWED, **overrides})
    assert found.status == status
    assert found.reason == reason
    assert found.status != 0

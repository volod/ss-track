"""The capture section of a recording declaration: descriptive facts and two closed judgments.

Camera control and observer platform are operator judgments from the closed vocabularies the
recording and source-manifest contracts state, and a test holds the tuples below to them. An omitted
judgment is `unknown`, a statement that nobody knows, never a value inferred from footage or text.
Only `import --amend-capture` replaces them in a kept source record. Every other capture fact is
descriptive and is carried as stated.
"""

from collections.abc import Mapping
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import Fields, invalid

UNKNOWN = "unknown"
CAMERA_CONTROL_MODE = "camera_control_mode"
OBSERVER_PLATFORM = "observer_platform"
CAMERA_CONTROL_MODES = ("operator_steered", "fixed_camera", "autonomous_camera", UNKNOWN)
OBSERVER_PLATFORMS = ("ground_fixed", "ground_handheld", "airborne", UNKNOWN)
JUDGMENTS: Mapping[str, tuple[str, ...]] = {
    CAMERA_CONTROL_MODE: CAMERA_CONTROL_MODES,
    OBSERVER_PLATFORM: OBSERVER_PLATFORMS,
}
DESCRIPTIVE_FIELDS = (
    "camera",
    "lens",
    "exposure",
    "focus",
    "fov",
    "lighting",
    "background",
    "motion",
    "object_pixel_extent",
)


def read_capture(fields: Fields) -> dict[str, JsonValue]:
    """Return the capture section a source record stores, with each omitted judgment `unknown`."""
    capture: dict[str, JsonValue] = {name: fields.scalar(name) for name in DESCRIPTIVE_FIELDS}
    for name in JUDGMENTS:
        capture[name] = fields.text(name) if fields.has(name) else UNKNOWN
    capture["range"] = _read_range(fields.optional_child("range"))
    return capture


def recorded_judgments(capture: object) -> dict[str, str]:
    """Return the two judgments a current source record stores, refusing a value outside them.

    The contract already forbids one, so a `TypeError` here means a record resealed by hand.
    """
    if not isinstance(capture, Mapping):
        raise TypeError("capture")
    judgments: dict[str, str] = {}
    for name, vocabulary in JUDGMENTS.items():
        value = capture[name]
        if not isinstance(value, str) or value not in vocabulary:
            raise TypeError(name)
        judgments[name] = value
    return judgments


def with_judgments(
    capture: Mapping[str, Any], declared: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    """Return `capture` with only its two judgments replaced by the declared ones."""
    return {**capture, **{name: declared[name] for name in JUDGMENTS}}


def descriptive_facts(capture: Mapping[str, Any]) -> dict[str, Any]:
    """Return the capture facts other than the two judgments."""
    return {name: value for name, value in capture.items() if name not in JUDGMENTS}


def _read_range(fields: Fields) -> dict[str, JsonValue]:
    """Apply the contract's range rule, which states that an absent status is unknown."""
    status = fields.text("status") if fields.has("status") else UNKNOWN
    value_m = fields.scalar("value_m")
    method = fields.optional_text("method")
    if status != UNKNOWN and (value_m is None or method is None):
        raise invalid(f"capture.range.status {status} requires value_m and method")
    if status == UNKNOWN and (value_m is not None or method is not None):
        raise invalid("capture.range.status unknown cannot carry value_m or method")
    return {"status": status, "value_m": value_m, "method": method}

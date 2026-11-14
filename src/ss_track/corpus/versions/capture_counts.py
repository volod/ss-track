"""Distinct encounters in each camera-control and observer-platform bin.

A build already verified the source records. These counts read the two closed judgments from
those records and leave the sealed corpus unchanged. An encounter is counted once in every bin
its streams use, so the bins are separate totals. Generated cases are not encounters.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ss_track.core.refusal import JsonValue

CAMERA_CONTROL_MODES = (
    "operator_steered",
    "fixed_camera",
    "autonomous_camera",
    "unknown",
)
OBSERVER_PLATFORMS = (
    "ground_fixed",
    "ground_handheld",
    "airborne",
    "unknown",
)
_JUDGMENTS = (
    ("camera_control_mode", CAMERA_CONTROL_MODES),
    ("observer_platform", OBSERVER_PLATFORMS),
)


@dataclass(frozen=True, slots=True)
class CaptureEncounterCounts:
    """Every vocabulary bin, including a bin no encounter uses."""

    camera_control_mode: Mapping[str, int]
    observer_platform: Mapping[str, int]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible counts."""
        return {
            "camera_control_mode": _json_counts(self.camera_control_mode),
            "observer_platform": _json_counts(self.observer_platform),
        }


def capture_judgments(capture: object) -> dict[str, str]:
    """Return the two closed judgments a current source record stores."""
    if not isinstance(capture, Mapping):
        raise TypeError("capture")
    return {name: _member(capture, name, vocabulary) for name, vocabulary in _JUDGMENTS}


def count_capture_encounters(
    streams: Sequence[tuple[str, Mapping[str, str]]],
) -> CaptureEncounterCounts:
    """Count each encounter once in every bin its streams use.

    Each item is one stream's encounter id and that stream's source judgments. Pass streams
    only: a generated case has no place in the sequence.
    """
    bins: dict[str, dict[str, set[str]]] = {name: {} for name, _vocabulary in _JUDGMENTS}
    for encounter_id, judgments in streams:
        for name, _vocabulary in _JUDGMENTS:
            bins[name].setdefault(encounter_id, set()).add(judgments[name])
    return CaptureEncounterCounts(
        camera_control_mode=_totals(bins["camera_control_mode"], CAMERA_CONTROL_MODES),
        observer_platform=_totals(bins["observer_platform"], OBSERVER_PLATFORMS),
    )


def _member(capture: Mapping[str, object], name: str, vocabulary: Sequence[str]) -> str:
    value = capture[name]
    if not isinstance(value, str) or value not in vocabulary:
        raise TypeError(name)
    return value


def _totals(used: Mapping[str, set[str]], vocabulary: Sequence[str]) -> dict[str, int]:
    counts = dict.fromkeys(vocabulary, 0)
    for values in used.values():
        for value in values:
            counts[value] += 1
    return counts


def _json_counts(counts: Mapping[str, int]) -> dict[str, JsonValue]:
    return {name: count for name, count in counts.items()}

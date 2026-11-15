"""Distinct encounters in each camera-control and observer-platform bin.

A build already verified the source records. These counts read the two closed judgments from
those records and leave the sealed corpus unchanged. An encounter is counted once in every bin
its streams use, so the bins are separate totals. Generated cases are not encounters.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.capture import (
    CAMERA_CONTROL_MODE,
    JUDGMENTS,
    OBSERVER_PLATFORM,
)


@dataclass(frozen=True, slots=True)
class CaptureEncounterCounts:
    """Every vocabulary bin, including a bin no encounter uses."""

    camera_control_mode: Mapping[str, int]
    observer_platform: Mapping[str, int]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible counts."""
        return {
            CAMERA_CONTROL_MODE: dict(self.camera_control_mode),
            OBSERVER_PLATFORM: dict(self.observer_platform),
        }


def count_capture_encounters(
    streams: Sequence[tuple[str, Mapping[str, str]]],
) -> CaptureEncounterCounts:
    """Count each encounter once in every bin its streams use.

    Each item is one stream's encounter id and that stream's source judgments. Pass streams
    only: a generated case has no place in the sequence.
    """
    bins = {
        name: _distinct_encounters(streams, name, vocabulary)
        for name, vocabulary in JUDGMENTS.items()
    }
    return CaptureEncounterCounts(
        camera_control_mode=bins[CAMERA_CONTROL_MODE],
        observer_platform=bins[OBSERVER_PLATFORM],
    )


def _distinct_encounters(
    streams: Sequence[tuple[str, Mapping[str, str]]], name: str, vocabulary: Sequence[str]
) -> dict[str, int]:
    counts = dict.fromkeys(vocabulary, 0)
    for _encounter_id, value in {
        (encounter_id, judgments[name]) for encounter_id, judgments in streams
    }:
        counts[value] += 1
    return counts

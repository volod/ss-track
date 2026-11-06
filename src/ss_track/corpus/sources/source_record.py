"""The sections of a source record: what a decode established and what the operator declared.

Import, redecode and staging each build or compare these sections, so each is built here once:
a redecode writes the same `sequence` an import of those bytes would, and a stage compares a fresh
decode with the record field by field.
"""

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.declaration import RecordingDeclaration
from ss_track.corpus.decoding.declared_color import (
    DECLARED_COLOR_FACT,
    apply_declared_color,
    declaration_changed,
)
from ss_track.corpus.decoding.decode import MediaInspection
from ss_track.corpus.decoding.streams import VIDEO_STREAM_INDEX
from ss_track.corpus.sources.timestamps import TimestampQuality


def decoded_facts(inspection: MediaInspection) -> dict[str, JsonValue]:
    """Return what a decode established, in the form a source manifest stores it.

    The first video stream is the historical default, so its index stays absent and an unchanged
    source keeps the bytes it had before a recording could name a stream.
    """
    facts: dict[str, JsonValue] = asdict(inspection)
    facts["pts"] = list(inspection.pts)
    facts["completeness_checks"] = list(inspection.completeness_checks)
    if facts[VIDEO_STREAM_INDEX] == 0:
        del facts[VIDEO_STREAM_INDEX]
    return facts


def decoded_sequence(
    inspection: MediaInspection,
    quality: TimestampQuality,
    capture_clock_evidence: str | None,
    color_matrix: int | None,
) -> dict[str, JsonValue]:
    """Return a record's `sequence`: the decoded facts, their timing claim and a declared matrix."""
    sequence = decoded_facts(inspection)
    sequence["frame_count"] = len(inspection.pts)
    sequence["timestamp_quality"] = quality
    sequence["capture_clock_evidence"] = capture_clock_evidence
    apply_declared_color(sequence, inspection.source_pixel_format, color_matrix)
    return sequence


def declared_terms(declaration: RecordingDeclaration) -> dict[str, JsonValue]:
    """Return the only sections of a source record that an operator may change later."""
    return {
        "rights": dict(asdict(declaration.rights)),
        "sensitivity": dict(asdict(declaration.sensitivity)),
    }


def changed_facts(record: Mapping[str, Any], declaration: RecordingDeclaration) -> list[str]:
    """Name each declared fact, other than the terms, that differs from a source record."""
    sequence = record.get("sequence", {})
    changed: list[str] = []
    if record.get("capture") != declaration.capture:
        changed.append("capture")
    if sequence.get("capture_clock_evidence") != declaration.capture_clock_evidence:
        changed.append("sequence.capture_clock_evidence")
    declared_index = declaration.video_stream_index
    if declared_index is not None and sequence.get(VIDEO_STREAM_INDEX, 0) != declared_index:
        changed.append(f"sequence.{VIDEO_STREAM_INDEX}")
    if isinstance(sequence, Mapping) and declaration_changed(sequence, declaration.color_matrix):
        changed.append(DECLARED_COLOR_FACT)
    return changed

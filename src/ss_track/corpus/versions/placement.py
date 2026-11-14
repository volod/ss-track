"""Bind one declared stream to the source record a build just verified.

The sealed stream states membership, selection and rights. Capture judgments stay beside
that record for the build result and are not copied into the corpus manifest.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.read_refusals import incomplete_record
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.declaration import (
    EncounterDeclaration,
    GroupDeclaration,
    StreamDeclaration,
)
from ss_track.corpus.decoding.decode_policy import require_policy
from ss_track.corpus.decoding.streams import recorded_video_stream_index
from ss_track.corpus.sources.identity import recorded_content_sha256, source_identity
from ss_track.corpus.sources.stored import load_verified_source
from ss_track.corpus.storage.layout import MANIFEST_NAME
from ss_track.corpus.versions.capture_counts import capture_judgments

CAMERA_MODALITY = "camera"


def stream_record(
    group: GroupDeclaration,
    encounter: EncounterDeclaration,
    stream: StreamDeclaration,
    data_root: Path,
    policy_sha256: str,
) -> tuple[dict[str, JsonValue], dict[str, str]]:
    """Return one sealed stream and the capture judgments of its verified source."""
    verified = load_verified_source(stream.source_sha256, data_root)
    manifest = verified.record
    require_policy(
        manifest["decode_policy_sha256"], policy_sha256, f"source {stream.source_sha256}"
    )
    media = verified.sequence
    with incomplete_record(MANIFEST_NAME):
        record = _placed_stream(group, encounter, stream, manifest, media)
        judgments = capture_judgments(manifest.get("capture"))
    content = recorded_content_sha256(manifest)
    index = recorded_video_stream_index(media)
    if content != stream.source_sha256 and source_identity(content, index) == stream.source_sha256:
        record["content_sha256"] = content
    return record, judgments


def _placed_stream(
    group: GroupDeclaration,
    encounter: EncounterDeclaration,
    stream: StreamDeclaration,
    manifest: Mapping[str, JsonValue],
    media: Mapping[str, Any],
) -> dict[str, JsonValue]:
    """State one declared stream with the facts its source record holds."""
    frame_count = media["frame_count"]
    if not isinstance(frame_count, int):
        raise TypeError("frame_count")
    return {
        "stream_id": stream.stream_id,
        "modality": CAMERA_MODALITY,
        "encounter_id": encounter.encounter_id,
        "group_id": group.group_id,
        "split": group.split,
        "source_sha256": stream.source_sha256,
        "source_manifest_sha256": manifest[SEAL_FIELD],
        "selection": _resolve_selection(stream, frame_count),
        "frame_count": frame_count,
        "width": media["decoded_width"],
        "height": media["decoded_height"],
        "timestamp_quality": media["timestamp_quality"],
        "completeness_checks": media["completeness_checks"],
        "rights": manifest["rights"],
        "sensitivity": manifest["sensitivity"],
    }


def _resolve_selection(stream: StreamDeclaration, frame_count: int) -> dict[str, JsonValue]:
    """Return the frame window, which must lie inside the decoded sequence."""
    selection = stream.selection
    if selection is None:
        return {"start_frame": 0, "end_frame": frame_count}
    if selection.end_frame > frame_count:
        raise CorpusRefusal(
            RefusalCode.SELECTION_OUT_OF_RANGE,
            "selection runs past the end of the sequence",
            {
                "stream_id": stream.stream_id,
                "start_frame": selection.start_frame,
                "end_frame": selection.end_frame,
                "frame_count": frame_count,
            },
        )
    return {"start_frame": selection.start_frame, "end_frame": selection.end_frame}

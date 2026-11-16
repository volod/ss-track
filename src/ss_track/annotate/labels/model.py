"""Typed labels after the contract has accepted the document."""

from dataclasses import dataclass

from ss_track.annotate.labels.geometry import Box, Point
from ss_track.annotate.sources.declared_space import DeclaredSpace


@dataclass(frozen=True, slots=True)
class LabelGeometry:
    """Localization of one instance in one frame. An amodal box is never filled in."""

    kind: str
    box: Box | None
    point: Point | None
    amodal_box: Box | None
    uncertainty_px: float | None
    plausible_extent_px: int | None


@dataclass(frozen=True, slots=True)
class LabeledFrame:
    """One instance in one stored frame."""

    frame_index: int
    visibility: str
    camera_motion: str
    annotator_id: str
    geometry: LabelGeometry


@dataclass(frozen=True, slots=True)
class Instance:
    """One object across the frames the annotator marked."""

    instance_id: str
    class_id: str
    identity: str
    non_scoring_mark: str | None
    frames: tuple[LabeledFrame, ...]


@dataclass(frozen=True, slots=True)
class MotionEvent:
    """Onset, uncertainty, visibility, selection quality and re-entry of one event."""

    event_id: str
    instance_id: str
    onset_frame: int
    onset_uncertainty_frames: int
    visibility: str
    selection_quality: str
    reentry: bool


@dataclass(frozen=True, slots=True)
class LabelSet:
    """One label document and the hash a later freeze pins."""

    label_id: str
    pack_id: str
    pack_hash: str
    space: DeclaredSpace
    instances: tuple[Instance, ...]
    motion_events: tuple[MotionEvent, ...]
    document_sha256: str

"""Values a scenario pack holds after its contract has accepted the document."""

from dataclasses import dataclass
from typing import Literal

ClassRole = Literal["scoring", "distractor", "ignore"]
EnvelopeKind = Literal["living", "collision"]
CLASS_ROLES = ("scoring", "distractor", "ignore")
ENVELOPE_KINDS = ("living", "collision")


@dataclass(frozen=True, slots=True)
class PackClass:
    """One class. Its id is stable; its display name is not an id."""

    class_id: str
    name: str
    role: ClassRole
    parent_class_id: str | None
    min_identifiable_extent_px: int | None


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """Annotation terms the pack pins. Activity is the only list a pack may extend."""

    visibility: tuple[str, ...]
    geometry: tuple[str, ...]
    camera_motion: tuple[str, ...]
    non_scoring_mark: tuple[str, ...]
    activity: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtentBin:
    """One half-open pixel interval ``[min_px, max_px)``. A null upper edge is unbounded."""

    bin_id: str
    min_px: int
    max_px: int | None


@dataclass(frozen=True, slots=True)
class Approval:
    """A named person and the record that approves a slot. The record is not opened."""

    owner: str
    reference: str


@dataclass(frozen=True, slots=True)
class ApproachSector:
    """One permitted approach. Elevation is the altitude band, in degrees."""

    sector_id: str
    bearing_start_deg: float
    bearing_end_deg: float
    elevation_min_deg: float
    elevation_max_deg: float


@dataclass(frozen=True, slots=True)
class ExclusionZone:
    """A zone a report may name. Coordinates are not stored."""

    zone_id: str
    radius_m: float
    height_m: float


@dataclass(frozen=True, slots=True)
class Envelope:
    """One living-subject or collision stand-off, with the approval that allows it."""

    kind: EnvelopeKind
    approval: Approval
    class_ids: tuple[str, ...]
    d_min_m: float
    d_alert_m: float
    v_close_max_m_s: float
    approach_sectors: tuple[ApproachSector, ...]
    exclusion_zones: tuple[ExclusionZone, ...]
    t_follow_max_s: float
    end_conditions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Phase2:
    """Section 19.3 and 19.7 slots. An absent field is unset, not an engineering default."""

    target_set: tuple[str, ...] | None
    known_non_targets: tuple[str, ...] | None
    unknown_set: bool | None
    identifiable_duration_s: float | None
    declaration_deadline_s: float | None
    declaration_burden_per_hour: float | None
    target_size_m: float | None
    stand_off_levels_m: tuple[float, ...] | None


@dataclass(frozen=True, slots=True)
class ScenarioPack:
    """One validated pack and the hash of the declaration that produced it."""

    pack_id: str
    schema_version: int
    classes: tuple[PackClass, ...]
    vocabulary: Vocabulary
    min_box_extent_px: int | None
    min_point_extent_px: int | None
    extent_bins: tuple[ExtentBin, ...]
    observer_platform_strata: tuple[str, ...]
    access_policy: Approval | None
    envelopes: tuple[Envelope, ...]
    phase2: Phase2 | None
    pack_hash: str

    def class_named(self, class_id: str) -> PackClass | None:
        """Return the class a label names, or ``None`` when the pack does not state it."""
        return next((item for item in self.classes if item.class_id == class_id), None)

    def distractor_class_ids(self) -> tuple[str, ...]:
        """Return every class id whose role is distractor, sorted."""
        return tuple(sorted(item.class_id for item in self.classes if item.role == "distractor"))

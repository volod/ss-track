"""Operator seeds: the selection modules receive, and its fixed perturbations.

Replaying one seed is a pure function of that document. The real selection stays first.
Audit fields such as the annotator id are not part of the replay.
"""

from dataclasses import dataclass

from ss_track.annotate.checks import require_unique
from ss_track.annotate.digest import declaration_hash
from ss_track.annotate.geometry import Region, require_region, shift_region
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.result import AnnotationEntry
from ss_track.annotate.space import DeclaredSpace, FrameSpace, require_space
from ss_track.core.refusal import JsonValue
from ss_track.corpus.declarations.fields import Fields, invalid

_PRIMARY = "primary"


@dataclass(frozen=True, slots=True)
class Perturbation:
    """An integer offset from the selection modules receive."""

    perturbation_id: str
    dx: int
    dy: int
    frame_offset: int


@dataclass(frozen=True, slots=True)
class SeedSet:
    """One operator seed and the hash of the document that stated it."""

    seed_id: str
    label_sha256: str
    annotator_id: str
    frame_index: int
    pts: int | None
    time_base: str | None
    intended_instance_id: str | None
    quality: str
    original: Region
    correction: Region | None
    perturbations: tuple[Perturbation, ...]
    space: DeclaredSpace
    document_sha256: str


@dataclass(frozen=True, slots=True)
class ReplayRole:
    """One selection in the replay: the primary, or one perturbation of it."""

    role: str
    perturbation_id: str | None
    frame_index: int
    geometry: Region


def read_seed(fields: Fields, document_sha256: str) -> SeedSet:
    """Return the typed seed. Cross-field rules are applied by the caller."""
    correction = fields.child("correction") if fields.has("correction") else None
    return SeedSet(
        seed_id=fields.string("seed_id"),
        label_sha256=fields.string("label_sha256"),
        annotator_id=fields.string("annotator_id"),
        frame_index=fields.index("frame_index"),
        pts=fields.nullable_index("pts"),
        time_base=fields.nullable_text("time_base"),
        intended_instance_id=fields.nullable_text("intended_instance_id"),
        quality=fields.string("quality"),
        original=_region(fields.child("original")),
        correction=None if correction is None else _region(correction),
        perturbations=tuple(
            _perturbation(Fields(item, fields.where)) for item in fields.items("perturbations")
        ),
        space=_space(fields),
        document_sha256=document_sha256,
    )


def selection_modules_receive(seed: SeedSet) -> Region:
    """Return the selection competing modules receive. The original stays in the document."""
    if seed.quality not in ("as_clicked", "imprecise", "corrected"):
        raise TypeError(f"quality {seed.quality} is not in the contract")
    if seed.quality == "corrected":
        if seed.correction is None:
            raise invalid("quality corrected requires a correction")
        return seed.correction
    if seed.correction is not None:
        raise invalid(f"quality {seed.quality} cannot include a correction")
    return seed.original


def replay_roles(seed: SeedSet) -> tuple[ReplayRole, ...]:
    """Return the primary selection and each perturbation, in document order."""
    chosen = selection_modules_receive(seed)
    roles = [ReplayRole(_PRIMARY, None, seed.frame_index, chosen)]
    for item in seed.perturbations:
        roles.append(
            ReplayRole(
                "perturbation",
                item.perturbation_id,
                seed.frame_index + item.frame_offset,
                shift_region(chosen, item.dx, item.dy),
            )
        )
    return tuple(roles)


def replay_document(seed: SeedSet) -> dict[str, JsonValue]:
    """Return the canonical replay. Identical seeds produce identical bytes."""
    roles: list[JsonValue] = [_role(role) for role in replay_roles(seed)]
    return {
        "seed_id": seed.seed_id,
        "quality": seed.quality,
        "intended_instance_id": seed.intended_instance_id,
        "roles": roles,
    }


def replay_hash(seed: SeedSet) -> str:
    """Return the hash of the replay modules receive."""
    return declaration_hash(replay_document(seed))


def check_seed(seed: SeedSet, labels: LabelSet, space: FrameSpace) -> None:
    """Refuse a seed whose label, space, time, target or perturbations disagree."""
    if seed.label_sha256 != labels.document_sha256:
        raise invalid("label_sha256 does not match the label document")
    require_space(seed.space, space, seed.seed_id)
    _require_frame(seed.frame_index, space.frame_count, seed.seed_id)
    _require_time(seed, space)
    _require_target(seed, labels)
    require_unique([item.perturbation_id for item in seed.perturbations], "perturbation id")
    for item in seed.perturbations:
        _require_perturbation(item)
    for role in replay_roles(seed):
        _require_role(role, seed.space.width, seed.space.height, space.frame_count)


def seed_entries(seed: SeedSet) -> tuple[AnnotationEntry, ...]:
    """Return one row per replayed role. A row is a selection, not a score."""
    return tuple(
        AnnotationEntry(role.perturbation_id or _PRIMARY, role.frame_index, "scorable", None)
        for role in replay_roles(seed)
    )


def _require_perturbation(item: Perturbation) -> None:
    if item.perturbation_id == _PRIMARY:
        raise invalid("perturbation id primary is reserved")
    if item.dx == 0 and item.dy == 0 and item.frame_offset == 0:
        raise invalid(f"perturbation {item.perturbation_id} does not move the selection")


def _require_role(role: ReplayRole, width: int, height: int, frame_count: int) -> None:
    name = role.perturbation_id or _PRIMARY
    _require_frame(role.frame_index, frame_count, name)
    require_region(role.geometry, width, height, name)


def _require_frame(index: int, frame_count: int, where: str) -> None:
    if index < 0 or index >= frame_count:
        raise invalid(f"{where} frame {index} is outside the source")


def _require_time(seed: SeedSet, space: FrameSpace) -> None:
    if (seed.pts is None) != (seed.time_base is None):
        raise invalid("pts and time_base are both set or both null")
    if seed.pts is None:
        return
    actual = space.pts[seed.frame_index]
    if seed.pts != actual:
        raise invalid(f"pts is {seed.pts}, source frame is {actual}")
    if seed.time_base != space.time_base:
        raise invalid(f"time_base is {seed.time_base}, source is {space.time_base}")


def _require_target(seed: SeedSet, labels: LabelSet) -> None:
    intended = seed.intended_instance_id
    if intended is None:
        return
    instance = next((item for item in labels.instances if item.instance_id == intended), None)
    if instance is None:
        raise invalid(f"intended instance {intended} is not in the labels")
    if not any(frame.frame_index == seed.frame_index for frame in instance.frames):
        raise invalid(f"intended instance {intended} has no label on frame {seed.frame_index}")


def _space(fields: Fields) -> DeclaredSpace:
    return DeclaredSpace(
        source_sha256=fields.string("source_sha256"),
        width=fields.index("width"),
        height=fields.index("height"),
        frame_count=fields.index("frame_count"),
        orientation_degrees=fields.index("orientation_degrees"),
        display_rotation_degrees=fields.index("display_rotation_degrees"),
    )


def _region(fields: Fields) -> Region:
    kind = fields.string("kind")
    if kind == "point":
        return Region("point", fields.index("x"), fields.index("y"), None, None)
    if kind == "box":
        return Region(
            "box",
            fields.index("x"),
            fields.index("y"),
            fields.index("width"),
            fields.index("height"),
        )
    raise TypeError(f"{fields.where} kind {kind} is not in the contract")


def _perturbation(fields: Fields) -> Perturbation:
    return Perturbation(
        fields.string("perturbation_id"),
        fields.index("dx"),
        fields.index("dy"),
        fields.index("frame_offset"),
    )


def _role(role: ReplayRole) -> dict[str, JsonValue]:
    geometry = role.geometry
    return {
        "role": role.role,
        "perturbation_id": role.perturbation_id,
        "frame_index": role.frame_index,
        "kind": geometry.kind,
        "x": geometry.x,
        "y": geometry.y,
        "width": geometry.width,
        "height": geometry.height,
    }

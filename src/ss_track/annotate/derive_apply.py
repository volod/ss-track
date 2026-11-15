"""Apply one stored label transform to a parent's frozen labels.

The label id becomes the case id. Nothing here writes a file or reads a revision.
`compression` and `timing` do not move geometry. `timing`, and a repeated frame,
record that presentation time is derived.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace

from ss_track.annotate.derive_edit import (
    copy_frame,
    drop_frame,
    put_frame,
    reconcile_events,
    require_instances,
)
from ss_track.annotate.derive_geom import Rect, output_size
from ss_track.annotate.derive_status import apply_region, scale_frame, translate_frame
from ss_track.annotate.derive_track import apply_track
from ss_track.annotate.label_model import LabelSet
from ss_track.annotate.pack_model import ScenarioPack
from ss_track.corpus.declarations.fields import invalid

_DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class Applied:
    """Labels after one transform, and a presentation claim when the case retimes frames."""

    labels: LabelSet
    timestamp_quality: str | None


def apply_label_transform(
    labels: LabelSet, transform: Mapping[str, object], pack: ScenarioPack, case_id: str
) -> Applied:
    """Return the case's labels. The caller checks plates and track boxes first."""
    renamed = replace(labels, label_id=case_id, document_sha256="")
    kind = _text(transform, "kind")
    if kind in {"identity", "compression"}:
        return Applied(require_instances(renamed), None)
    if kind == "timing":
        return Applied(require_instances(renamed), _DERIVED)
    if kind == "scale":
        return _scale(renamed, transform, pack)
    if kind == "translate":
        return Applied(_translate(renamed, transform), None)
    if kind == "frame_map":
        return _frames(renamed, transform)
    if kind == "region_status":
        return Applied(_region(renamed, transform), None)
    if kind == "track_status":
        return Applied(_track(renamed, transform, pack), None)
    raise invalid(f"label transform {kind} is not a stored kind")


def _scale(labels: LabelSet, transform: Mapping[str, object], pack: ScenarioPack) -> Applied:
    factor = _int(transform.get("factor"), "factor")
    if factor < 2:
        raise invalid("scale factor is below 2")
    width, height = output_size(labels.space.width, labels.space.height, factor)
    scaled = replace(labels, space=replace(labels.space, width=width, height=height))
    for instance in labels.instances:
        for frame in instance.frames:
            updated = scale_frame(frame, factor, pack, width, height)
            scaled = put_frame(scaled, instance.instance_id, updated)
    return Applied(require_instances(reconcile_events(scaled)), None)


def _translate(labels: LabelSet, transform: Mapping[str, object]) -> LabelSet:
    offsets = {
        _int(item.get("frame_index"), "frame_index"): (
            _int(item.get("dx"), "dx"),
            _int(item.get("dy"), "dy"),
        )
        for item in _rows(transform, "offsets")
    }
    camera = _text(transform, "camera_motion")
    moved = labels
    for instance in labels.instances:
        for frame in instance.frames:
            shift = offsets.get(frame.frame_index)
            if shift is None:
                continue
            updated = translate_frame(
                frame, shift[0], shift[1], labels.space.width, labels.space.height
            )
            updated = replace(updated, camera_motion=camera)
            moved = put_frame(moved, instance.instance_id, updated)
    return require_instances(reconcile_events(moved))


def _frames(labels: LabelSet, transform: Mapping[str, object]) -> Applied:
    mapped = labels
    for index in _ints(transform, "removed"):
        mapped = drop_frame(mapped, index)
    for item in _rows(transform, "repeated"):
        mapped = copy_frame(
            mapped,
            _int(item.get("frame_index"), "frame_index"),
            _int(item.get("content_frame_index"), "content_frame_index"),
        )
    quality = _DERIVED if _rows(transform, "repeated") else None
    return Applied(require_instances(reconcile_events(mapped)), quality)


def _region(labels: LabelSet, transform: Mapping[str, object]) -> LabelSet:
    start, stop = _window(transform)
    region = _rect(transform.get("region"), "region")
    inside, overlap = _text(transform, "inside"), _text(transform, "overlap")
    updated = labels
    for instance in labels.instances:
        for frame in instance.frames:
            if not start <= frame.frame_index < stop:
                continue
            changed = apply_region(frame, region, inside, overlap)
            updated = put_frame(updated, instance.instance_id, changed)
    return require_instances(reconcile_events(updated))


def _track(labels: LabelSet, transform: Mapping[str, object], pack: ScenarioPack) -> LabelSet:
    frames = [dict(item) for item in _rows(transform, "frames")]
    return require_instances(
        apply_track(
            labels,
            frames,
            _text(transform, "instance_id"),
            pack,
            labels.space.width,
            labels.space.height,
        )
    )


def _window(transform: Mapping[str, object]) -> tuple[int, int]:
    raw = transform.get("frames")
    if not isinstance(raw, Mapping):
        raise invalid("label transform has no frame window")
    return _int(raw.get("start_frame"), "start_frame"), _int(raw.get("end_frame"), "end_frame")


def _rect(value: object, where: str) -> Rect:
    if not isinstance(value, Mapping):
        raise invalid(f"{where} is not a rectangle")
    return Rect(
        _int(value.get("x"), "x"),
        _int(value.get("y"), "y"),
        _int(value.get("width"), "width"),
        _int(value.get("height"), "height"),
    )


def _rows(transform: Mapping[str, object], name: str) -> list[Mapping[str, object]]:
    raw = transform.get(name)
    if not isinstance(raw, list):
        raise invalid(f"label transform has no {name}")
    rows = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise invalid(f"{name} entry is not an object")
        rows.append(item)
    return rows


def _ints(transform: Mapping[str, object], name: str) -> list[int]:
    raw = transform.get(name)
    if not isinstance(raw, list):
        raise invalid(f"label transform has no {name}")
    return [_int(item, name) for item in raw]


def _text(transform: Mapping[str, object], name: str) -> str:
    value = transform.get(name)
    if not isinstance(value, str) or not value:
        raise invalid(f"label transform has no {name}")
    return value


def _int(value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise invalid(f"{where} is not an integer")
    return value

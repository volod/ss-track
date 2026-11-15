"""How one labeled frame moves: a region, a translation, or a scale factor.

An unknown frame stays unknown. A status that cannot carry a box drops the box.
A scaled box below the pack's minimum extent becomes a point, and a target below
the minimum point extent becomes unlocalizable.
"""

from dataclasses import replace

from ss_track.annotate.derive_geom import (
    Rect,
    below_box,
    box_geometry,
    clip_moved,
    divide_measure,
    extent_px,
    from_box,
    point_geometry,
    relation,
    scale_point,
    scale_rect,
    unlocalizable,
)
from ss_track.annotate.geometry import Point
from ss_track.annotate.label_model import LabeledFrame
from ss_track.annotate.pack_model import ScenarioPack

_KEPT = "unknown"


def apply_region(frame: LabeledFrame, region: Rect, inside: str, overlap: str) -> LabeledFrame:
    """Apply a painted rectangle. A frame the rectangle does not meet stays as it is."""
    if frame.visibility == _KEPT:
        return frame
    box = frame.geometry.box
    point = frame.geometry.point
    if box is not None:
        return _box_region(frame, region, from_box(box), inside, overlap)
    if point is not None and region.contains_point(point.x, point.y):
        return _clear(frame, inside)
    return frame


def translate_frame(frame: LabeledFrame, dx: int, dy: int, width: int, height: int) -> LabeledFrame:
    """Shift one frame and clip it. A box that leaves the frame is ``out_of_view``."""
    if frame.visibility == _KEPT:
        return frame
    geometry = frame.geometry
    uncertainty = geometry.uncertainty_px if geometry.uncertainty_px is not None else 0.0
    if geometry.box is not None:
        moved = clip_moved(from_box(geometry.box), dx, dy, width, height)
        if moved is None:
            return _clear(frame, "out_of_view")
        amodal = geometry.amodal_box
        clipped = None if amodal is None else clip_moved(from_box(amodal), dx, dy, width, height)
        return replace(frame, geometry=box_geometry(moved, uncertainty, clipped))
    if geometry.point is not None:
        x, y = geometry.point.x + dx, geometry.point.y + dy
        if x < 0 or y < 0 or x >= width or y >= height:
            return _clear(frame, "out_of_view")
        return replace(
            frame, geometry=point_geometry(Point(x, y), uncertainty, geometry.plausible_extent_px)
        )
    return frame


def scale_frame(
    frame: LabeledFrame, factor: int, pack: ScenarioPack, width: int, height: int
) -> LabeledFrame:
    """Divide geometry, uncertainty and plausible extent, then clip to the output frame."""
    if frame.visibility == _KEPT:
        return frame
    geometry = frame.geometry
    uncertainty = divide_measure(geometry.uncertainty_px or 0.0, factor)
    if geometry.box is not None:
        return _scale_box(frame, factor, pack, width, height, uncertainty)
    if geometry.point is not None:
        return _scale_point(frame, factor, pack, width, height, uncertainty)
    return frame


def _box_region(
    frame: LabeledFrame, region: Rect, box: Rect, inside: str, overlap: str
) -> LabeledFrame:
    found = relation(region, box)
    if found == "outside":
        return frame
    if found == "overlap":
        return _clear(frame, overlap)
    return _clear(frame, inside)


def _scale_box(
    frame: LabeledFrame,
    factor: int,
    pack: ScenarioPack,
    width: int,
    height: int,
    uncertainty: float,
) -> LabeledFrame:
    box = frame.geometry.box
    amodal = frame.geometry.amodal_box
    if box is None:
        return frame
    scaled = scale_rect(from_box(box), factor, width, height)
    if scaled is None:
        return _clear(frame, "out_of_view")
    if below_box(scaled.width, scaled.height, pack.min_box_extent_px):
        return _as_point(frame, scaled, pack, uncertainty)
    clipped = None if amodal is None else scale_rect(from_box(amodal), factor, width, height)
    return replace(frame, geometry=box_geometry(scaled, uncertainty, clipped))


def _as_point(
    frame: LabeledFrame, box: Rect, pack: ScenarioPack, uncertainty: float
) -> LabeledFrame:
    extent = extent_px(box.width, box.height)
    if pack.min_point_extent_px is not None and extent < pack.min_point_extent_px:
        return replace(frame, geometry=unlocalizable())
    point = Point(box.x + (box.width - 1) // 2, box.y + (box.height - 1) // 2)
    return replace(frame, geometry=point_geometry(point, uncertainty, extent))


def _scale_point(
    frame: LabeledFrame,
    factor: int,
    pack: ScenarioPack,
    width: int,
    height: int,
    uncertainty: float,
) -> LabeledFrame:
    point = frame.geometry.point
    if point is None:
        return frame
    scaled = scale_point(point.x, point.y, factor, width, height)
    if scaled is None:
        return _clear(frame, "out_of_view")
    extent = frame.geometry.plausible_extent_px
    divided = None if extent is None else extent // factor
    if divided == 0:
        divided = None
    if (
        divided is not None
        and pack.min_point_extent_px is not None
        and divided < pack.min_point_extent_px
    ):
        return replace(frame, geometry=unlocalizable())
    return replace(frame, geometry=point_geometry(Point(*scaled), uncertainty, divided))


def _clear(frame: LabeledFrame, visibility: str) -> LabeledFrame:
    return replace(frame, visibility=visibility, geometry=unlocalizable())

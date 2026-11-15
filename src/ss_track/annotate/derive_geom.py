"""Pixel rectangles used while a generated case moves its parent's labels.

Coordinates stay integers. A half-open box that leaves the frame is clipped, and one
that leaves entirely is no longer a box.
"""

import math
from dataclasses import dataclass

from ss_track.annotate.geometry import Box, Point
from ss_track.annotate.label_model import LabelGeometry


@dataclass(frozen=True, slots=True)
class Rect:
    """A half-open pixel rectangle."""

    x: int
    y: int
    width: int
    height: int

    def contains(self, other: "Rect") -> bool:
        """Return whether `other` lies wholly inside this rectangle."""
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.x + other.width <= self.x + self.width
            and other.y + other.height <= self.y + self.height
        )

    def intersects(self, other: "Rect") -> bool:
        """Return whether the two half-open rectangles share a pixel."""
        return (
            other.x < self.x + self.width
            and self.x < other.x + other.width
            and other.y < self.y + self.height
            and self.y < other.y + other.height
        )

    def contains_point(self, x: int, y: int) -> bool:
        """Return whether one pixel lies inside this rectangle."""
        return self.x <= x < self.x + self.width and self.y <= y < self.y + self.height


def relation(region: Rect, box: Rect) -> str:
    """Return ``inside``, ``overlap`` or ``outside`` for a box against a region."""
    if region.contains(box):
        return "inside"
    if region.intersects(box):
        return "overlap"
    return "outside"


def from_box(box: Box) -> Rect:
    """Return the rectangle of a label box."""
    return Rect(box.x, box.y, box.width, box.height)


def unlocalizable() -> LabelGeometry:
    """Return geometry that carries neither a box nor a point."""
    return LabelGeometry("unlocalizable", None, None, None, None, None)


def box_geometry(rect: Rect, uncertainty: float, amodal: Rect | None) -> LabelGeometry:
    """Return a box, with an amodal estimate only when one remains."""
    return LabelGeometry(
        "box",
        Box(rect.x, rect.y, rect.width, rect.height),
        None,
        None if amodal is None else Box(amodal.x, amodal.y, amodal.width, amodal.height),
        uncertainty,
        None,
    )


def point_geometry(point: Point, uncertainty: float, extent: int | None) -> LabelGeometry:
    """Return a point and its plausible extent."""
    return LabelGeometry("point_only", None, point, None, uncertainty, extent)


def clip_moved(rect: Rect, dx: int, dy: int, width: int, height: int) -> Rect | None:
    """Move a box by whole pixels and clip it to the frame. ``None`` means it left."""
    left = max(0, rect.x + dx)
    top = max(0, rect.y + dy)
    right = min(width, rect.x + dx + rect.width)
    bottom = min(height, rect.y + dy + rect.height)
    if right <= left or bottom <= top:
        return None
    return Rect(left, top, right - left, bottom - top)


def scale_span(start: int, stop: int, factor: int) -> tuple[int, int]:
    """Map a half-open source span onto the reduced pixels that contain any of it."""
    return start // factor, (stop - 1) // factor + 1


def scale_rect(rect: Rect, factor: int, width: int, height: int) -> Rect | None:
    """Divide a box by `factor` and clip it to the output frame."""
    left, right = scale_span(rect.x, rect.x + rect.width, factor)
    top, bottom = scale_span(rect.y, rect.y + rect.height, factor)
    left, top = max(0, left), max(0, top)
    right, bottom = min(width, right), min(height, bottom)
    if right <= left or bottom <= top:
        return None
    return Rect(left, top, right - left, bottom - top)


def scale_point(x: int, y: int, factor: int, width: int, height: int) -> tuple[int, int] | None:
    """Return the output pixel that contains `(x, y)`, or ``None`` when it leaves the frame."""
    scaled_x, scaled_y = x // factor, y // factor
    if scaled_x >= width or scaled_y >= height:
        return None
    return scaled_x, scaled_y


def below_box(width: int, height: int, minimum: int | None) -> bool:
    """Return whether ``sqrt(width * height)`` is below the pack's minimum box extent."""
    if minimum is None:
        return False
    return width * height < minimum * minimum


def extent_px(width: int, height: int) -> int:
    """Return the integer extent ``floor(sqrt(width * height))``."""
    return math.isqrt(width * height)


def divide_measure(value: float, factor: int) -> float:
    """Divide a localization measure by the scale factor."""
    if isinstance(value, int) and value % factor == 0:
        return float(value // factor)
    return value / factor


def json_number(value: float) -> int | float:
    """Return an integer when the measure lands on one, so the document does not carry ``2.0``."""
    if value.is_integer() and abs(value) < 2**53:
        return int(value)
    return value


def output_size(width: int, height: int, factor: int) -> tuple[int, int]:
    """Return the frame size a reduction gives, matching the pixel transform."""
    return -(-width // factor), -(-height // factor)

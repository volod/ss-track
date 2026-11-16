"""Stored-pixel geometry: a half-open box or a point, checked against the frame."""

from dataclasses import dataclass

from ss_track.corpus.declarations.fields import invalid


@dataclass(frozen=True, slots=True)
class Box:
    """A half-open box, top-left ``x, y`` and extent, in stored pixels."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Point:
    """One pixel coordinate in the stored frame."""

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Region:
    """A click or a box. A point has no extent."""

    kind: str
    x: int
    y: int
    width: int | None
    height: int | None


def require_box(box: Box, width: int, height: int, where: str) -> None:
    """Refuse a box that does not lie inside the stored frame."""
    if box.x < 0 or box.y < 0 or box.x + box.width > width or box.y + box.height > height:
        raise invalid(f"{where} is outside the stored frame")


def require_point(point: Point, width: int, height: int, where: str) -> None:
    """Refuse a point that is not a pixel of the stored frame."""
    if point.x < 0 or point.y < 0 or point.x >= width or point.y >= height:
        raise invalid(f"{where} is outside the stored frame")


def require_region(region: Region, width: int, height: int, where: str) -> None:
    """Refuse a click or a box that leaves the stored frame."""
    if region.kind == "point":
        require_point(Point(region.x, region.y), width, height, where)
        return
    if region.width is None or region.height is None:
        raise TypeError(f"{where} box has no extent")
    require_box(Box(region.x, region.y, region.width, region.height), width, height, where)


def shift_region(region: Region, dx: int, dy: int) -> Region:
    """Return the same extent moved by an integer pixel offset."""
    return Region(region.kind, region.x + dx, region.y + dy, region.width, region.height)

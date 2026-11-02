"""Transforms that paint one declared rectangle: absence, moving background and occlusion.

Nothing here knows where a target is. The rectangle is the operator's claim, and labels decide what
it covered: a label transform states what a label becomes inside it or overlapping it.
"""

from dataclasses import dataclass
from functools import cache

from ss_track.corpus.case_model import (
    CaseContext,
    Pixels,
    Region,
    Rendering,
    add_noise,
    as_pixels,
)
from ss_track.corpus.refusal import JsonValue
from ss_track.corpus.seeded import SeededDraws

_UNLOCALIZABLE = "unlocalizable"
_SPRITE_DRAWS = 7
_SPRITE_DRAW_BITS = 32
_SPEED_SIGN_BIT = 16
_COMPONENT_LEVELS = 256


def _region_status(
    case: CaseContext, region: Region, inside: str, overlap: str, **extra: JsonValue
) -> dict[str, JsonValue]:
    """Say what a label becomes when it lies inside or merely overlaps a painted region."""
    record: dict[str, JsonValue] = {
        "kind": "region_status",
        "frames": case.frame_range(),
        "region": region.record(),
        "inside": inside,
        "overlap": overlap,
        "overlap_geometry": _UNLOCALIZABLE,
    }
    return record | extra


def target_absence(case: CaseContext) -> Rendering:
    """Paint a target-free plate over the target, so the interval is a confirmed negative."""
    region = case.region()
    plate_frame: int = case.parameters["plate_frame"]
    noise: int = case.parameters["noise"]
    case.require(plate_frame in case.selection, "plate_frame is outside the parent selection")
    plate = cache(lambda: region.of(case.read(plate_frame)))

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        painted = pixels.copy()
        raw = case.draws.raw(f"noise:{frame_index}", region.components)
        region.of(painted)[:] = add_noise(plate(), noise, raw)
        return painted

    labels = _region_status(case, region, "absent", "unknown")
    return Rendering(case.unchanged_slots(), paint, labels)


@dataclass(frozen=True, slots=True)
class _Sprite:
    """One solid moving shape, positioned in region coordinates."""

    x: int
    y: int
    speed_x: int
    speed_y: int
    color: tuple[int, int, int]


def _draw_sprite(draws: SeededDraws, index: int, region: Region, max_speed: int) -> _Sprite:
    x, y, speed_x, speed_y, red, green, blue = draws.integers(
        f"sprite:{index}", _SPRITE_DRAWS, 0, 2**_SPRITE_DRAW_BITS - 1
    )
    return _Sprite(
        x=x % region.width,
        y=y % region.height,
        speed_x=_nonzero_speed(speed_x, max_speed),
        speed_y=_nonzero_speed(speed_y, max_speed),
        color=(red % _COMPONENT_LEVELS, green % _COMPONENT_LEVELS, blue % _COMPONENT_LEVELS),
    )


def _nonzero_speed(draw: int, max_speed: int) -> int:
    """Return a signed speed that is never zero, so every sprite really moves."""
    magnitude = 1 + draw % max_speed
    return magnitude if draw >> _SPEED_SIGN_BIT & 1 else -magnitude


def moving_background(case: CaseContext) -> Rendering:
    """Move solid shapes through a region, with no change to what the parent's labels describe."""
    region = case.region()
    size: int = case.parameters["sprite_size"]
    max_speed: int = case.parameters["max_speed"]
    case.require(size <= min(region.width, region.height), "sprite_size exceeds the region")
    sprites = [
        _draw_sprite(case.draws, index, region, max_speed)
        for index in range(case.parameters["sprite_count"])
    ]

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        painted = pixels.copy()
        area = region.of(painted)
        for sprite in sprites:
            left = (sprite.x + sprite.speed_x * frame_index) % region.width
            top = (sprite.y + sprite.speed_y * frame_index) % region.height
            area[top : top + size, left : left + size] = sprite.color
        return painted

    labels = _region_status(case, region, "unknown", "unknown", added_objects="distractor")
    return Rendering(case.unchanged_slots(), paint, labels)


def short_occlusion(case: CaseContext) -> Rendering:
    """Cover a region with one rigid seeded texture, with the target seen before and after."""
    region = case.region()
    strictly_inside = (
        case.window.start > case.selection.start and case.window.stop < case.selection.stop
    )
    case.require(strictly_inside, "an occlusion needs frames before and after its window")
    raw = case.draws.raw("occluder", region.components)
    occluder = as_pixels(raw, region.width, region.height)

    def paint(pixels: Pixels, _: int) -> Pixels:
        painted = pixels.copy()
        region.of(painted)[:] = occluder
        return painted

    labels = _region_status(case, region, "fully_occluded", "partially_occluded")
    return Rendering(case.unchanged_slots(), paint, labels)

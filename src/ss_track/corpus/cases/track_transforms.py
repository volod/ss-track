"""Cases that follow one target's boxes instead of one operator rectangle.

The boxes are taken from one frozen label revision. A window frame with no box stays `unknown`.
Revision 1 moves a crossing occluder by `CROSS_STEP` pixels per frame along one of
`CROSS_DIRECTIONS`, and sends a target out of view through one of `EXIT_EDGES`. Another step or
another placement is another revision. Nothing here claims the motion is realistic.
"""

from functools import cache

from ss_track.core.refusal import JsonValue
from ss_track.corpus.cases.case_model import (
    CaseContext,
    Pixels,
    Region,
    Rendering,
    add_noise,
    as_pixels,
    shift_frame,
)
from ss_track.corpus.cases.track_labels import (
    distractor_frame,
    exit_frame,
    occluder_frame,
    removal_frame,
    track_status,
)
from ss_track.corpus.decoding.pixels import OUTPUT_BYTES_PER_PIXEL

CROSS_STEP = 1
CROSS_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))
EXIT_EDGES = ("right", "left", "down", "up")
OCCLUDER_PURPOSE = "occluder"


def crossing_occluder(case: CaseContext) -> Rendering:
    """Cover the target on a declared interval and stand off it on the frames around that interval."""
    track = case.track()
    cover = _margin(case, "cover", "a crossing needs frames before and after its cover")
    case.require(all(index in track for index in cover), "a covered frame has no scorable box")
    direction = CROSS_DIRECTIONS[
        case.draws.integers("direction", 1, 0, len(CROSS_DIRECTIONS) - 1)[0]
    ]
    texture = as_pixels(
        case.draws.raw(OCCLUDER_PURPOSE, case.width * case.height * OUTPUT_BYTES_PER_PIXEL),
        case.width,
        case.height,
    )

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        rect = _occluder_rect(track.get(frame_index), frame_index, cover, direction)
        return _paint_rect(pixels, rect, texture)

    frames = [_covered(case, index, track, cover, direction) for index in case.window]
    return Rendering(case.unchanged_slots(), paint, track_status(case, frames))


def moving_removal(case: CaseContext) -> Rendering:
    """Replace each box with the same rectangle of a plate frame, plus seeded noise."""
    track = case.track()
    plate_frame = int(case.parameters["plate_frame"])
    noise = int(case.parameters["noise"])
    case.require(plate_frame in case.selection, "plate_frame is outside the parent selection")
    plate = cache(lambda: case.read(plate_frame))

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        painted = pixels.copy()
        box = track.get(frame_index)
        if box is None:
            return painted
        raw = case.draws.raw(f"noise:{frame_index}", box.components)
        box.of(painted)[:] = add_noise(box.of(plate()), noise, raw)
        return painted

    frames = [removal_frame(index, track.get(index)) for index in case.window]
    return Rendering(case.unchanged_slots(), paint, track_status(case, frames))


def similar_distractor(case: CaseContext) -> Rendering:
    """Copy each box to a seeded side that shares an edge and does not cover the target."""
    track = case.track()
    order = tuple(
        sorted(CROSS_DIRECTIONS, key=lambda side: case.draws.raw(f"side:{side[0]}:{side[1]}", 8))
    )
    placed = {index: _beside(case, box, order) for index, box in track.items()}

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        painted = pixels.copy()
        box = track.get(frame_index)
        if box is None:
            return painted
        placed[frame_index].of(painted)[:] = box.of(pixels)
        return painted

    frames = [distractor_frame(index, track.get(index), placed.get(index)) for index in case.window]
    return Rendering(case.unchanged_slots(), paint, track_status(case, frames))


def out_of_view(case: CaseContext) -> Rendering:
    """Shift listed frames until the box lies outside, then mark the later frames as re-entry."""
    track = case.track()
    outside = _margin(case, "outside", "out of view needs frames before and after its interval")
    edge = EXIT_EDGES[case.draws.integers("edge", 1, 0, len(EXIT_EDGES) - 1)[0]]
    shifts = {
        index: _exit_shift(track[index], edge, case.width, case.height)
        for index in outside
        if index in track
    }
    case.require(bool(shifts), "out of view needs a box on a frame that leaves")

    def paint(pixels: Pixels, frame_index: int) -> Pixels:
        shift = shifts.get(frame_index)
        if shift is None:
            return pixels.copy()
        return shift_frame(pixels, shift[0], shift[1])

    frames = [
        exit_frame(index, track.get(index), outside, shifts.get(index)) for index in case.window
    ]
    return Rendering(case.unchanged_slots(), paint, track_status(case, frames))


def _margin(case: CaseContext, name: str, message: str) -> range:
    """Return an interval with at least one case-window frame on either side."""
    span = case.parameter_range(name)
    case.require(span.start > case.window.start and span.stop < case.window.stop, message)
    return span


def _covered(
    case: CaseContext,
    index: int,
    track: dict[int, Region],
    cover: range,
    direction: tuple[int, int],
) -> dict[str, JsonValue]:
    box = track.get(index)
    rect = _occluder_rect(box, index, cover, direction)
    visible = None if rect is None else _visible(rect, case.width, case.height)
    return occluder_frame(index, box, visible)


def _occluder_rect(
    box: Region | None, index: int, cover: range, direction: tuple[int, int]
) -> Region | None:
    if box is None:
        return None
    if index < cover.start:
        distance = cover.start - index
    elif index >= cover.stop:
        distance = index - (cover.stop - 1)
    else:
        distance = 0
    horizontal, vertical = direction
    return Region(
        box.x + horizontal * distance * CROSS_STEP,
        box.y + vertical * distance * CROSS_STEP,
        box.width,
        box.height,
    )


def _visible(rect: Region, width: int, height: int) -> Region | None:
    """Return the part of a rectangle that lies in the frame, in frame coordinates."""
    x0, y0 = max(rect.x, 0), max(rect.y, 0)
    x1, y1 = min(rect.x + rect.width, width), min(rect.y + rect.height, height)
    if x0 >= x1 or y0 >= y1:
        return None
    return Region(x0, y0, x1 - x0, y1 - y0)


def _paint_rect(pixels: Pixels, rect: Region | None, texture: Pixels) -> Pixels:
    """Replace the in-frame part of `rect` with the occluder's local texture."""
    painted = pixels.copy()
    if rect is None:
        return painted
    visible = _visible(rect, painted.shape[1], painted.shape[0])
    if visible is None:
        return painted
    local_x, local_y = visible.x - rect.x, visible.y - rect.y
    visible.of(painted)[:] = texture[
        local_y : local_y + visible.height, local_x : local_x + visible.width
    ]
    return painted


def _beside(case: CaseContext, box: Region, order: tuple[tuple[int, int], ...]) -> Region:
    """Return a same-sized neighbor that shares an edge and stays inside the frame."""
    for horizontal, vertical in order:
        placed = Region(
            box.x + horizontal * box.width,
            box.y + vertical * box.height,
            box.width,
            box.height,
        )
        if placed.fits(case.width, case.height):
            return placed
    case.require(False, "a similar object does not fit beside the target")
    return box


def _exit_shift(box: Region, edge: str, width: int, height: int) -> tuple[int, int]:
    """Return the smallest shift that puts the whole box outside the named edge."""
    if edge == "right":
        return width - box.x, 0
    if edge == "left":
        return -(box.x + box.width), 0
    if edge == "down":
        return 0, height - box.y
    return 0, -(box.y + box.height)

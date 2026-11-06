"""What one generated-case transform works from and what it produces.

A transform runs twice from one record: `corpus build` prepares it without pixels, which validates
the recipe and yields its label transform, and `corpus stage` prepares it again and paints frames.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.cases.seeded import SeededDraws
from ss_track.corpus.decoding.pixels import OUTPUT_BYTES_PER_PIXEL

type Pixels = npt.NDArray[np.uint8]
type Paint = Callable[[Pixels, int], Pixels]
type ReadFrame = Callable[[int], Pixels]

_MAX_COMPONENT = 255
_DRAW_LEVELS_BITS = 8


def as_pixels(packed: bytes, width: int, height: int) -> Pixels:
    """View tightly packed rows as a read-only `height x width x 3` array."""
    array = np.frombuffer(packed, dtype=np.uint8)
    return array.reshape(height, width, OUTPUT_BYTES_PER_PIXEL)


def add_noise(pixels: Pixels, amplitude: int, raw: bytes) -> Pixels:
    """Add a value in `[-amplitude, amplitude]` per component, one draw byte each, saturating."""
    levels = np.frombuffer(raw, dtype=np.uint8).reshape(pixels.shape).astype(np.int32)
    offsets = ((levels * (2 * amplitude + 1)) >> _DRAW_LEVELS_BITS) - amplitude
    noisy: Pixels = np.clip(pixels.astype(np.int32) + offsets, 0, _MAX_COMPONENT).astype(np.uint8)
    return noisy


def shift_frame(pixels: Pixels, dx: int, dy: int) -> Pixels:
    """Move content by whole pixels. An exposed edge repeats the nearest pixel."""
    height, width = pixels.shape[:2]
    rows = np.clip(np.arange(height) - dy, 0, height - 1)
    columns = np.clip(np.arange(width) - dx, 0, width - 1)
    return pixels[rows][:, columns]


@dataclass(frozen=True, slots=True)
class Region:
    """A pixel rectangle of the parent frames, in stored orientation."""

    x: int
    y: int
    width: int
    height: int

    @property
    def components(self) -> int:
        """Return how many color components the rectangle holds."""
        return self.width * self.height * OUTPUT_BYTES_PER_PIXEL

    def of(self, pixels: Pixels) -> Pixels:
        """Return the view of this rectangle in a frame."""
        return pixels[self.y : self.y + self.height, self.x : self.x + self.width]

    def record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}

    def fits(self, width: int, height: int) -> bool:
        """Return whether this rectangle lies inside a frame of the given size."""
        return (
            self.x >= 0
            and self.y >= 0
            and self.x + self.width <= width
            and self.y + self.height <= height
        )


@dataclass(frozen=True, slots=True)
class Slot:
    """One frame of a case: its place in the parent sequence and whose pixels it shows."""

    frame_index: int
    content_frame_index: int


@dataclass(frozen=True, slots=True)
class Rendering:
    """Everything a recipe does to its parent.

    `gap_scale` is empty unless the case retimes frames. Each pair is a frame and the integer
    scale of the presentation gap from the previous frame. `None` keeps the parent's PTS.
    """

    slots: tuple[Slot, ...]
    paint: Paint | None
    label_transform: dict[str, JsonValue]
    gap_scale: tuple[tuple[int, int], ...] | None = None


@dataclass(frozen=True, slots=True)
class CaseContext:
    """One case's recipe and the facts of its parent stream."""

    case_id: str
    transform: str
    parameters: Mapping[str, Any]
    window: range
    selection: range
    width: int
    height: int
    draws: SeededDraws
    read: ReadFrame
    timestamp_quality: str = "derived"

    def require(self, condition: bool, message: str) -> None:
        """Refuse a recipe that its parent cannot satisfy."""
        if not condition:
            raise CorpusRefusal(
                RefusalCode.CASE_INVALID,
                f"generated case {self.case_id}: {message}",
                {"case_id": self.case_id, "transform": self.transform},
            )

    def region(self) -> Region:
        """Return the declared rectangle, which must lie inside the frame."""
        region = Region(**self.parameters["region"])
        self.require(region.fits(self.width, self.height), "region runs past the frame")
        return region

    def track(self) -> dict[int, Region]:
        """Return one target's boxes, in frame order, each inside the window and the frame.

        A window frame with no entry has no scorable box. The boxes belong to the frozen label
        revision named in the recipe.
        """
        found: dict[int, Region] = {}
        previous = -1
        for entry in self.parameters["track"]:
            index = int(entry["frame_index"])
            self.require(index > previous, "track frame indexes are not strictly increasing")
            self.require(
                self.window.start <= index < self.window.stop,
                "track frame is outside the window",
            )
            box = Region(
                x=int(entry["box"]["x"]),
                y=int(entry["box"]["y"]),
                width=int(entry["box"]["width"]),
                height=int(entry["box"]["height"]),
            )
            self.require(box.fits(self.width, self.height), "track box runs past the frame")
            found[index] = box
            previous = index
        return found

    def parameter_range(self, name: str) -> range:
        """Return a non-empty half-open interval that lies inside the case window."""
        raw = self.parameters[name]
        start, stop = int(raw["start_frame"]), int(raw["end_frame"])
        self.require(start < stop, f"{name} is empty")
        self.require(
            start >= self.window.start and stop <= self.window.stop,
            f"{name} runs past the window",
        )
        return range(start, stop)

    def unchanged_slots(self) -> tuple[Slot, ...]:
        """Return one slot per parent frame, each showing its own pixels."""
        return tuple(Slot(index, index) for index in self.selection)

    def frame_range(self) -> dict[str, JsonValue]:
        """Return the half-open frame window a label transform applies to."""
        return {"start_frame": self.window.start, "end_frame": self.window.stop}

"""How a motion event follows the frame it names.

An event states the visibility of its onset frame. When a freeze or a generated case changes that
frame, the event takes the frame's visibility, and re-entry holds only on a frame that carries an
extent. Either change means the event is no longer the reviewed onset, so its selection becomes
uncertain. A freeze and a derivation apply this one rule.
"""

from dataclasses import dataclass

from ss_track.annotate.labels.disposition import VISIBLE

UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class EventState:
    """The three event fields that depend on the onset frame."""

    visibility: str
    reentry: bool
    selection_quality: str


def follow_frame(state: EventState, frame_visibility: str) -> EventState:
    """Return the event state its onset frame allows. An unchanged event keeps its selection."""
    reentry = state.reentry and frame_visibility in VISIBLE
    if frame_visibility == state.visibility and reentry == state.reentry:
        return state
    return EventState(frame_visibility, reentry, UNCERTAIN)

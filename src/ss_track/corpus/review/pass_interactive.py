"""Terminal selection pass: every window one run selected, reviewed again and saved as it goes.

Pictures are rendered from the staged frames one window at a time into a temporary folder outside
the data root and removed when the reviewer moves on, so the pass never stores a copy of the run's
frames. The session shows the stream, candidate and frame range, never a score, method or the
audit's observation of the window.
"""

import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.scratch import exclusive_lock
from ss_track.core.terminal import controlling_terminal
from ss_track.corpus.review.audit_viewer import Reveal, Viewer, play_flipbook, reveal_folder
from ss_track.corpus.review.pass_session import (
    PassDraft,
    PassTarget,
    load_pass,
    pass_target,
    render_window,
    save_pass,
)
from ss_track.corpus.review.queue import Offered
from ss_track.corpus.review.review_terminal import (
    LOOK_HELP,
    MOVE_HELP,
    OBSERVATIONS,
    ReviewTerminal,
    first_open,
    move,
)

INSTRUCTIONS = (
    """Selection pass

Review every window this run selected, including windows the audit already showed you. The pass
is not blinded, but it shows no score, method or earlier observation: judge the pictures. Its
observations are the run's review yield and never enter the estimate. Uncertain is unknown.

"""
    + LOOK_HELP
    + """Observe: t target present; a target absent (none seen, not verified); f confuser
         (no target, something that could pass for one); u unknown; c clear.
"""
    + MOVE_HELP
    + "Every observation is saved immediately. Restart with the same reviewer to resume.\n"
)

Render = Callable[[Offered], list[Path]]


@dataclass(frozen=True, slots=True)
class PassSessionResult:
    """The review file a finished or paused pass left, as one command-result record."""

    review: Path

    def to_record(self) -> dict[str, JsonValue]:
        return {"status": "recorded", "record_path": str(self.review)}


class PassSession(ReviewTerminal):
    """One reviewer's selection pass over one run, with injected streams, viewers and clock."""

    def __init__(
        self,
        target: PassTarget,
        review: Path,
        draft: PassDraft,
        streams: tuple[TextIO, TextIO],
        tools: tuple[Viewer, Reveal, Render],
        clock: Callable[[], float],
    ) -> None:
        super().__init__(streams, clock, self._charge)
        self.target, self.review, self.draft = target, review, draft
        self.view, self.reveal, self.render = tools
        self.changed = False

    def _charge(self, seconds: float) -> None:
        self.draft.active_seconds += seconds

    def decided(self, index: int) -> bool:
        return self.target.windows[index].key in self.draft.observations

    def save(self) -> None:
        self.changed = True
        save_pass(self.review, self.draft)

    def summary(self) -> str:
        counts = {name: 0 for name in OBSERVATIONS.values()}
        for observation in self.draft.observations.values():
            counts[observation] += 1
        parts = ", ".join(f"{name} {count}" for name, count in counts.items())
        size = len(self.target.windows)
        return (
            f"Reviewed {len(self.draft.observations)}/{size} ({parts}); "
            f"{self.draft.minutes} min recorded\n"
        )

    def show(self, index: int) -> None:
        window = self.target.windows[index]
        observation = self.draft.observations.get(window.key, "not reviewed")
        self.say(
            f"\nWindow {index + 1}/{len(self.target.windows)}: {window.stream_id} "
            f"{window.candidate_id}, frames {window.start_frame}-{window.end_frame - 1}\n"
        )
        self.say(f"Observation: {observation}\n")
        self.say(self.summary())

    def look(self, index: int, action: str) -> None:
        window = self.target.windows[index]
        pictures = self.render(window)
        if action == "o":
            if not self.reveal(pictures[0].parent):
                self.say(f"No image viewer found; open {pictures[0].parent}\n")
        elif not self.view(window.candidate_id, pictures, action == "d"):
            self.say(f"Could not start ffplay; open {pictures[0].parent}\n")


def _step(session: PassSession, action: str, index: int) -> int:
    key = session.target.windows[index].key
    size = len(session.target.windows)
    if action in ("v", "d", "o"):
        session.look(index, action)
    elif action in OBSERVATIONS:
        session.draft.observations[key] = OBSERVATIONS[action]
        session.save()
        return min(index + 1, size - 1)
    elif action == "c":
        session.draft.observations.pop(key, None)
        session.save()
    elif action in ("n", "p", "g", "j"):
        return move(session, action, index, size, session.decided)
    elif action == "s":
        session.say(session.summary())
    elif action == "h":
        session.say(INSTRUCTIONS)
    else:
        session.say("Unknown action; enter h for help.\n")
    return index


def conduct_pass(session: PassSession, autoplay: bool) -> None:
    """Run the pass loop on injected streams, viewers and clock until quit or end of input."""
    session.say(INSTRUCTIONS)
    session.say(
        f"Run: {session.target.run_id}\nPass reviewer: {session.draft.reviewer}\n"
        f"Review file: {session.review}\n"
    )
    size = len(session.target.windows)
    if not size:
        session.say("The run selected no window it offers.\n")
        return
    index = first_open(session.decided, size) or 0
    shown: int | None = None
    while True:
        session.show(index)
        if autoplay and shown != index and not session.decided(index):
            session.look(index, "v")
        shown = index
        action = session.ask("\nAction [v/d/o t/a/f/u c n/p/g/j s h q]: ")
        if action is None or action.lower() == "q":
            break
        index = _step(session, action.lower(), index)
    if session.changed:
        session.save()  # records the minutes spent after the last observation
    session.say(f"\nSaved. {session.summary()}Review file: {session.review}\n")


def open_pass(
    target: PassTarget,
    review: Path,
    draft: PassDraft,
    streams: tuple[TextIO, TextIO],
    tools: tuple[Viewer, Reveal, Render],
    clock: Callable[[], float] = time.monotonic,
) -> PassSession:
    """Return a pass session over the given streams, viewers, renderer and clock."""
    return PassSession(target, review, draft, streams, tools, clock)


def _renderer(target: PassTarget, data_root: Path, scratch: Path) -> Render:
    current: dict[str, Path] = {}

    def render(window: Offered) -> list[Path]:
        folder = scratch / f"{window.stream_id}.{window.candidate_id}"
        previous = current.get("folder")
        if previous is not None and previous != folder:
            shutil.rmtree(previous, ignore_errors=True)
        current["folder"] = folder
        if folder.is_dir():
            return sorted(folder.glob("*.png"))
        return render_window(target, data_root, window, folder)

    return render


def review_pass_interactively(
    run_id: str, review: Path, reviewer: str, autoplay: bool, data_root: Path
) -> PassSessionResult:
    """Review a run's selected windows through the controlling terminal under an exclusive lock."""
    target = pass_target(run_id, data_root)
    busy = CorpusRefusal(RefusalCode.DISCOVERY_IN_PROGRESS, "a selection pass is already active")
    with exclusive_lock(review.parent, f".{review.name}.lock", busy=busy):
        draft = load_pass(target, review, reviewer)
        with (
            tempfile.TemporaryDirectory(prefix="ss-track-pass-") as scratch,
            controlling_terminal("selection pass") as streams,
        ):
            tools = (play_flipbook, reveal_folder, _renderer(target, data_root, Path(scratch)))
            conduct_pass(open_pass(target, review, draft, streams, tools), autoplay)
    return PassSessionResult(review)

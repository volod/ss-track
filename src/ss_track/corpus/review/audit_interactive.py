"""Terminal review of a blinded audit packet, saving each decision before it advances.

The session sees only the packet: item ids and pictures. It plays an item's pictures as a looping
flipbook, optionally as frame differences that make a small moving object stand out, and never
shows a selection, a score, a stream or an offer reason.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.core.terminal import controlling_terminal
from ss_track.corpus.review.audit_session import (
    REVIEW_NAME,
    AuditDraft,
    AuditPacket,
    load_draft,
    read_packet,
    save_draft,
)
from ss_track.corpus.review.audit_viewer import Reveal, Viewer, play_flipbook, reveal_folder
from ss_track.corpus.review.blind_review import AuditObservation
from ss_track.corpus.review.decisions import EXCLUDE, OTHER_REASON
from ss_track.corpus.review.review_terminal import (
    LOOK_HELP,
    MOVE_HELP,
    OBSERVATIONS,
    ReviewTerminal,
    first_open,
    move,
)
from ss_track.corpus.storage.scratch import exclusive_lock

INCLUDE = "include"
REASONS = {
    "n": "no_value",
    "q": "quality",
    "s": "sensitive",
    "r": "rights",
    "d": "duplicate",
    "o": OTHER_REASON,
}
INSTRUCTIONS = (
    """Blinded audit review

Decide what each window shows. You see only item ids and pictures: no recording, score, method
or reason the window was offered. Do not open a queue template, selection or score of either run
before you finish if you will declare blinding. An observation is not a label; uncertain is unknown.

"""
    + LOOK_HELP
    + """Include: t target present; a target absent (none seen, not verified); f confuser
         (no target, something that could pass for one); u unknown.
Exclude: x, then an observation and a reason (no_value, quality, sensitive, rights,
         duplicate, other with a note), in either order, as a key or a name.
Edit:    e note; c clear back to unreviewed.
"""
    + MOVE_HELP
    + "Every decision is saved immediately. Restart with the same reviewer to resume.\n"
)


@dataclass(frozen=True, slots=True)
class AuditSessionResult:
    """The review file a finished or paused session left, as one command-result record."""

    review: Path

    def to_record(self) -> dict[str, JsonValue]:
        return {"status": "recorded", "record_path": str(self.review)}


class AuditSession(ReviewTerminal):
    """One reviewer's pass over one packet, with injected streams, viewer and clock."""

    def __init__(
        self,
        packet: AuditPacket,
        review: Path,
        draft: AuditDraft,
        streams: tuple[TextIO, TextIO],
        view: Viewer,
        reveal: Reveal,
        clock: Callable[[], float],
    ) -> None:
        super().__init__(streams, clock, self._charge)
        self.packet, self.review, self.draft = packet, review, draft
        self.view, self.reveal = view, reveal

    def _charge(self, seconds: float) -> None:
        self.draft.active_seconds += seconds

    def decided(self, index: int) -> bool:
        return self.packet.item_ids[index] in self.draft.observations

    def save(self) -> None:
        save_draft(self.packet, self.review, self.draft)

    def summary(self) -> str:
        decided = self.draft.observations.values()
        counts = {name: 0 for name in OBSERVATIONS.values()}
        for observation in decided:
            counts[str(observation.observation)] += 1
        excluded = sum(observation.decision == EXCLUDE for observation in decided)
        parts = ", ".join(f"{name} {count}" for name, count in counts.items())
        size = len(self.packet.item_ids)
        return (
            f"Decided {len(self.draft.observations)}/{size} ({parts}; excluded {excluded}); "
            f"{self.draft.minutes} min recorded\n"
        )

    def show(self, index: int) -> None:
        item_id = self.packet.item_ids[index]
        observation = self.draft.observations.get(item_id)
        size = len(self.packet.item_ids)
        frames = len(self.packet.pictures(item_id))
        self.say(f"\nItem {index + 1}/{size}: {item_id} ({frames} frames)\n")
        self.say(f"Folder: {self.packet.root / 'items' / item_id}\n")
        self.say(f"Decision: {_describe(observation)}\n")
        self.say(self.summary())

    def play(self, index: int, difference: bool) -> None:
        item_id = self.packet.item_ids[index]
        if not self.view(item_id, self.packet.pictures(item_id), difference):
            self.say("Could not start ffplay; open the shown folder instead.\n")


def _describe(observation: AuditObservation | None) -> str:
    if observation is None:
        return "unreviewed"
    text = f"{observation.decision} / {observation.observation}"
    if observation.reason is not None:
        text += f" / {observation.reason}"
    return text + (f" -- {observation.note}" if observation.note else "")


def _note(session: AuditSession, prompt: str, required: bool) -> tuple[bool, str | None]:
    """Return whether a usable answer came and the note, None for blank."""
    while True:
        value = session.ask(prompt)
        if value is None:
            return False, None
        if not value.isascii():
            session.say("Use ASCII for the note.\n")
        elif value or not required:
            return True, value or None
        else:
            session.say("The reason other needs a note.\n")


_OBSERVATION_PROMPT = "Observation [t present/a absent/f confuser/u unknown; blank cancels]: "
_REASON_PROMPT = (
    "Reason [n no_value/q quality/s sensitive/r rights/d duplicate/o other; blank cancels]: "
)


def resolve(value: str, options: dict[str, str]) -> str | None:
    """Return the option a key or a full name names, such as `q`, `quality` or `no value`."""
    answer = value.strip().lower().replace(" ", "_").replace("-", "_")
    if answer in options:
        return options[answer]
    return answer if answer in options.values() else None


def _absorb(session: AuditSession, value: str, chosen: dict[str, str]) -> None:
    """Fill the observation or the reason an answer names, or say what is still wanted."""
    for slot, options in (("observation", OBSERVATIONS), ("reason", REASONS)):
        found = resolve(value, options)
        if found is not None and slot not in chosen:
            chosen[slot] = found
            if slot == "reason" and "observation" not in chosen:
                session.say(f"Reason {found}; now the observation.\n")
            return
    wanted = "a reason" if "observation" in chosen else "an observation"
    session.say(f"Enter {wanted} from the list.\n")


def _exclusion(session: AuditSession) -> tuple[str, str] | None:
    """Ask for an observation and a reason in either order, again after an invalid answer.

    Observation and reason keys do not overlap, so a reason given first is kept, not refused.
    """
    chosen: dict[str, str] = {}
    while len(chosen) < 2:
        prompt = _REASON_PROMPT if "observation" in chosen else _OBSERVATION_PROMPT
        value = session.ask(prompt)
        if not value:
            session.say("Nothing changed.\n")
            return None
        _absorb(session, value, chosen)
    return chosen["observation"], chosen["reason"]


def _exclude(session: AuditSession, item_id: str) -> bool:
    chosen = _exclusion(session)
    if chosen is None:
        return False
    observation, reason = chosen
    answered, note = _note(session, "Note (ASCII; blank for none): ", reason == OTHER_REASON)
    if not answered:
        return False
    session.draft.observations[item_id] = AuditObservation(
        item_id, EXCLUDE, observation, reason, note
    )
    return True


def _edit_note(session: AuditSession, item_id: str) -> None:
    current = session.draft.observations.get(item_id)
    if current is None:
        session.say("Decide the item before adding a note.\n")
        return
    answered, note = _note(session, "Note (ASCII; blank clears): ", current.reason == OTHER_REASON)
    if answered:
        session.draft.observations[item_id] = AuditObservation(
            item_id, current.decision, current.observation, current.reason, note
        )
        session.save()


def _decide(session: AuditSession, action: str, index: int) -> int:
    item_id = session.packet.item_ids[index]
    previous = session.draft.observations.get(item_id)
    if action in OBSERVATIONS:
        note = previous.note if previous is not None and previous.decision == INCLUDE else None
        session.draft.observations[item_id] = AuditObservation(
            item_id, INCLUDE, OBSERVATIONS[action], None, note
        )
    elif action == "x":
        if not _exclude(session, item_id):
            return index
    else:
        session.draft.observations.pop(item_id, None)
        session.save()
        return index
    session.save()
    return min(index + 1, len(session.packet.item_ids) - 1)


def _step(session: AuditSession, action: str, index: int) -> int:
    if action in ("v", "d"):
        session.play(index, action == "d")
    elif action == "o":
        folder = session.packet.root / "items" / session.packet.item_ids[index]
        if not session.reveal(folder):
            session.say("No image viewer found; open the shown folder instead.\n")
    elif action in (*OBSERVATIONS, "x", "c"):
        return _decide(session, action, index)
    elif action == "e":
        _edit_note(session, session.packet.item_ids[index])
    elif action in ("n", "p", "g", "j"):
        size = len(session.packet.item_ids)
        return move(session, action, index, size, session.decided)
    elif action == "s":
        session.say(session.summary())
    elif action == "h":
        session.say(INSTRUCTIONS)
    else:
        session.say("Unknown action; enter h for help.\n")
    return index


def conduct_audit(session: AuditSession, autoplay: bool) -> None:
    """Run the review loop on injected streams, viewer and clock until quit or end of input."""
    session.say(INSTRUCTIONS)
    session.say(f"Reviewer: {session.draft.reviewer}\nReview file: {session.review}\n")
    session.say(
        f"Declared: independence {session.draft.independence}, blinding {session.draft.blinding}\n"
    )
    if not session.packet.item_ids:
        session.say("The packet holds no items.\n")
        session.save()
        return
    index = first_open(session.decided, len(session.packet.item_ids)) or 0
    shown: int | None = None
    while True:
        session.show(index)
        if autoplay and shown != index and not session.decided(index):
            session.play(index, False)
        shown = index
        action = session.ask("\nAction [v/d/o t/a/f/u x e c n/p/g/j s h q]: ")
        if action is None or action.lower() == "q":
            break
        index = _step(session, action.lower(), index)
    session.save()
    session.say(f"\nSaved. {session.summary()}Review file: {session.review}\n")


def open_session(
    packet: AuditPacket,
    review: Path,
    draft: AuditDraft,
    streams: tuple[TextIO, TextIO],
    view: Viewer,
    reveal: Reveal,
    clock: Callable[[], float] = time.monotonic,
) -> AuditSession:
    """Return a session over the given streams, viewer, folder opener and clock."""
    return AuditSession(packet, review, draft, streams, view, reveal, clock)


def review_audit_interactively(
    packet_root: Path,
    reviewer: str,
    review: Path | None,
    independence: str | None,
    blinding: str | None,
    autoplay: bool,
) -> AuditSessionResult:
    """Review a blinded packet through the controlling terminal under an exclusive lock."""
    packet = read_packet(packet_root)
    target = review if review is not None else packet_root / REVIEW_NAME
    busy = CorpusRefusal(RefusalCode.DISCOVERY_IN_PROGRESS, "an audit review is already active")
    with exclusive_lock(target.parent, f".{target.name}.lock", busy=busy):
        draft = load_draft(packet, target, reviewer, independence, blinding)
        with controlling_terminal("audit review") as streams:
            conduct_audit(
                open_session(packet, target, draft, streams, play_flipbook, reveal_folder), autoplay
            )
    return AuditSessionResult(target)

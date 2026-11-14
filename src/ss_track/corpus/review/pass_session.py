"""A durable, resumable selection pass written into the run's own corpus review.

The pass is not blinded: its reviewer knows each window was selected. It still shows no score,
method or audit observation, so the reviewer judges the pictures rather than an earlier answer.
Every save rewrites the review with the decisions it already held and the pass so far; a review
whose pass leaves a selected window out is incomplete, which evaluation treats as unmeasured.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ss_track.core.refusal import CorpusRefusal, RefusalCode
from ss_track.core.scratch import write_atomically
from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.review.blind_packet import picture_name, render_frames
from ss_track.corpus.review.blind_sample import AuditItem
from ss_track.corpus.review.decisions import REVIEW_CONTRACT, REVIEW_SCHEMA_VERSION
from ss_track.corpus.review.queue import CandidateKey, Offered, review_queue
from ss_track.corpus.review.review_terminal import SECONDS_PER_MINUTE, whole_minutes
from ss_track.corpus.review.selection_pass import PASS_FIELD, expected_windows
from ss_track.corpus.versions.manifests import load_corpus_manifest
from ss_track.schema.validation.enforce import read_declaration

_HEADER = (
    "# Corpus review; its selection pass was written by `ss-track discover review-pass`.",
    "# A pass observation never enters the estimate and is not a label.",
)


@dataclass(frozen=True, slots=True)
class PassTarget:
    """The selected windows one verified run offers, ascending, and the corpus they come from."""

    run_id: str
    corpus: dict[str, Any]
    windows: tuple[Offered, ...]


@dataclass(slots=True)
class PassDraft:
    """A pass in progress over one review document. Absent windows are not yet reviewed."""

    reviewer: str
    document: dict[str, Any]
    active_seconds: float
    observations: dict[CandidateKey, str] = field(default_factory=dict)

    @property
    def minutes(self) -> int:
        """Whole minutes recorded so far, rounded up."""
        return whole_minutes(self.active_seconds)


def pass_target(run_id: str, data_root: Path) -> PassTarget:
    """Return what a complete pass of a verified run reviews."""
    records = verify_discovery(data_root, run_id)
    corpus = load_corpus_manifest(str(records.run["corpus_id"]), data_root)
    queue = review_queue(records, corpus)
    keys = sorted(expected_windows(queue))
    return PassTarget(run_id, dict(corpus), tuple(queue.offered[key] for key in keys))


def load_pass(target: PassTarget, review: Path, reviewer: str) -> PassDraft:
    """Read the run's review and resume its pass by the same reviewer, or start an empty one."""
    if not reviewer.strip() or not reviewer.isascii():
        raise CorpusRefusal(RefusalCode.MANIFEST_INVALID, "reviewer must be nonempty ASCII")
    if review.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "the review file is a symbolic link")
    document = read_declaration(review, REVIEW_CONTRACT, REVIEW_SCHEMA_VERSION)
    if document["run_id"] != target.run_id:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "the review belongs to another run",
            {"run_id": target.run_id, "review_run_id": str(document["run_id"])},
        )
    saved = document.pop(PASS_FIELD, None)
    if saved is None:
        return PassDraft(reviewer, document, 0.0)
    if saved["reviewer"] != reviewer:
        raise CorpusRefusal(
            RefusalCode.IMPORT_CONFLICT, "the selection pass names another reviewer"
        )
    expected = {window.key for window in target.windows}
    observations = {
        (str(item["stream_id"]), str(item["candidate_id"])): str(item["observation"])
        for item in saved["windows"]
    }
    stray = sorted(key for key in observations if key not in expected)
    if stray:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "the selection pass names windows its run did not select and offer",
            {"not_selected": [{"stream_id": s, "candidate_id": c} for s, c in stray]},
        )
    seconds = float(int(saved.get("reviewer_minutes", 0)) * SECONDS_PER_MINUTE)
    return PassDraft(reviewer, document, seconds, observations)


def pass_text(draft: PassDraft) -> str:
    """Return the review with its pass, windows ascending; no pass while nothing is reviewed."""
    document = dict(draft.document)
    if draft.observations:
        document[PASS_FIELD] = {
            "reviewer": draft.reviewer,
            "reviewer_minutes": draft.minutes,
            "windows": [
                {"stream_id": key[0], "candidate_id": key[1], "observation": observation}
                for key, observation in sorted(draft.observations.items())
            ],
        }
    body = yaml.safe_dump(document, sort_keys=False, allow_unicode=False)
    return "\n".join(_HEADER) + "\n" + body


def save_pass(review: Path, draft: PassDraft) -> None:
    """Atomically replace the review with its pass so far."""
    if review.is_symlink():
        raise CorpusRefusal(RefusalCode.IMPORT_CONFLICT, "the review file is a symbolic link")
    write_atomically(review, pass_text(draft).encode("ascii"))


def render_window(target: PassTarget, data_root: Path, window: Offered, folder: Path) -> list[Path]:
    """Write one window's staged frames as PNG pictures into `folder` and return them in order."""
    item = AuditItem(
        "pass", window.stream_id, window.candidate_id, window.start_frame, window.end_frame
    )
    pictures = render_frames(target.corpus, data_root, [item])["pass"]
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for offset, payload in enumerate(pictures):
        path = folder / picture_name(offset, len(pictures))
        path.write_bytes(payload)
        paths.append(path)
    return paths

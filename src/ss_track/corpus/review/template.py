"""`ss-track discover queue`: what a run offers for review, and a review file to fill in.

The template is a review declaration with every offered window `unreviewed`, each preceded by a
comment that states its window, why it was offered, what selection and the audit decided, and its
scores, so a reviewer can inspect a candidate with `corpus preview` and decide it in place. Its
reviewer is empty, which the contract refuses, so a template cannot pass as a review until someone
names who decided. Values are written as JSON strings, which YAML reads as the same text, so an
identifier such as `001` stays text.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ss_track.corpus.discovery.reader import verify_discovery
from ss_track.corpus.review.decisions import REVIEW_SCHEMA_VERSION, UNREVIEWED
from ss_track.corpus.review.export import write_once
from ss_track.corpus.review.queue import Offered, ReviewQueue, review_queue
from ss_track.corpus.review.result import QueueResult
from ss_track.corpus.versions.manifests import load_corpus_manifest

_GUIDE = (
    "Set each decision to include or exclude, with an observation: target_present,",
    "target_absent, confuser or unknown. An observation is what you saw, never a label.",
    "An exclusion also states a reason: no_value, quality, sensitive, rights, duplicate,",
    "or other with a note. Leave a window you did not decide unreviewed.",
)


def _quoted(value: str) -> str:
    return json.dumps(value)


def _selection(selection: Mapping[str, Any]) -> str:
    status = str(selection["status"])
    if "rank" in selection:
        return f"{status} rank {selection['rank']}"
    if "reason" in selection:
        return f"{status} ({selection['reason']})"
    return status


def _score(score: Mapping[str, Any]) -> str:
    if "value" in score:
        return f"{score['score_id']}={score['value']}"
    return f"{score['score_id']} unavailable ({score['reason']})"


def _facts(offered: Offered) -> str:
    candidate = offered.candidate
    scores = ", ".join(_score(score) for score in candidate["scores"]) or "no scores"
    return (
        f"# frames [{offered.start_frame}, {offered.end_frame}); offered as "
        f"{', '.join(offered.offers)}; selection {_selection(candidate['selection'])}; "
        f"audit {candidate['audit']['status']}; {scores}"
    )


def template_text(queue: ReviewQueue, corpus_id: str) -> str:
    """Return the review template of one queue: every offered window, undecided."""
    lines = [f"# Review of discovery run {queue.run_id} over corpus version {corpus_id}."]
    lines += [f"# {line}" for line in _GUIDE]
    for withheld in queue.withheld_records():
        lines.append(
            f"# Withheld: {withheld['count']} window(s) of {withheld['stream_id']}, "
            f"{withheld['reason']}."
        )
    lines += [
        f"schema_version: {REVIEW_SCHEMA_VERSION}",
        f"run_id: {_quoted(queue.run_id)}",
        'reviewer: ""  # who decides: required',
        "decisions:" if queue.offered else "decisions: []",
    ]
    for _, offered in sorted(queue.offered.items()):
        lines += [
            f"{_facts(offered)}",
            f"- stream_id: {_quoted(offered.stream_id)}",
            f"  candidate_id: {_quoted(offered.candidate_id)}",
            f"  decision: {UNREVIEWED}",
        ]
    return "\n".join(lines) + "\n"


def queue_review(run_id: str, data_root: Path, out: Path | None = None) -> QueueResult:
    """Report what a verified run offers for review, writing a template when asked."""
    records = verify_discovery(data_root, run_id)
    corpus_id = str(records.run["corpus_id"])
    queue = review_queue(records, load_corpus_manifest(corpus_id, data_root))
    if out is not None:
        write_once(out, template_text(queue, corpus_id).encode("ascii"))
    return QueueResult(queue, corpus_id, out)

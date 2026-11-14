"""Turn reviewed decisions into the streams of a frozen corpus version, and its declaration.

Each frozen stream is one maximal run of included windows of one pool stream, overlapping or
adjacent, so tracking keeps its continuity and no source frame is in two streams. It keeps its
pool stream's group and split: grouping and splits are the operator's judgment, stated once on the
pool version, and review neither moves nor merges them. Each frozen stream is its own encounter,
because streams of one encounter are not declared synchronized and so two cameras' windows cannot
be paired. Excluded and unreviewed windows never become members, and a window both included and
excluded, even in part, is refused rather than resolved.
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.declarations.declaration import CORPUS_SCHEMA_VERSION
from ss_track.corpus.declarations.fields import invalid
from ss_track.corpus.review.decisions import EXCLUDE, INCLUDE, Decision, Review
from ss_track.corpus.review.queue import CandidateKey, Offered, ReviewQueue
from ss_track.corpus.review.selection_pass import expected_windows, require_pass_windows
from ss_track.schema.validation.enforce import is_shared_type

type Decided = tuple[Offered, Decision]


@dataclass(frozen=True, slots=True)
class Member:
    """One frozen stream: a run of included windows of one pool stream."""

    stream_id: str
    pool_stream: Mapping[str, Any]
    start_frame: int
    end_frame: int
    candidates: tuple[Decided, ...]

    def selection(self) -> dict[str, JsonValue]:
        return {"start_frame": self.start_frame, "end_frame": self.end_frame}

    def placement(self) -> dict[str, JsonValue]:
        """Return the facts of the stream that the frozen manifest must hold."""
        return {
            "stream_id": self.stream_id,
            "encounter_id": self.stream_id,
            "group_id": self.pool_stream["group_id"],
            "split": self.pool_stream["split"],
            "source_sha256": self.pool_stream["source_sha256"],
            "selection": self.selection(),
        }


@dataclass(frozen=True, slots=True)
class Membership:
    """What a review makes of the windows its run offered."""

    members: tuple[Member, ...]
    exclusions: tuple[Decided, ...]
    unreviewed: tuple[Offered, ...]


def frozen_stream_id(pool_stream_id: str, start_frame: int, end_frame: int) -> str:
    """Name a frozen stream after its pool stream and window, refusing a name too long to be one."""
    stream_id = f"{pool_stream_id}.{start_frame}-{end_frame}"
    if not is_shared_type("identifier", stream_id):
        raise invalid(
            f"frozen stream {stream_id!r} from pool stream {pool_stream_id} is not an identifier; "
            "a pool stream_id must leave room for its window"
        )
    return stream_id


def _require_offered(queue: ReviewQueue, review: Review) -> None:
    """Refuse a review of another run, or a decision on a window review does not offer."""
    if review.run_id != queue.run_id:
        raise invalid(f"the review names run {review.run_id}, not {queue.run_id}")
    withheld = sorted(key for key in review.decisions if key in queue.withheld)
    unknown = sorted(
        key for key in review.decisions if key not in queue.offered and key not in queue.withheld
    )
    if withheld or unknown:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "the review decides windows its run does not offer: a locked stream's windows need a "
            "custodian policy, and review is bounded to the selected, audit-sampled and sibling "
            "windows",
            {
                "run_id": queue.run_id,
                "locked_without_policy": [_named(key) for key in withheld],
                "not_offered": [_named(key) for key in unknown],
            },
        )


def _named(key: CandidateKey) -> dict[str, JsonValue]:
    return {"stream_id": key[0], "candidate_id": key[1]}


def _runs(decided: Sequence[Decided]) -> list[list[Decided]]:
    """Group one stream's included windows into maximal overlapping or adjacent runs."""
    runs: list[list[Decided]] = []
    end = -1
    for item in sorted(decided, key=lambda pair: (pair[0].start_frame, pair[0].end_frame)):
        if runs and item[0].start_frame <= end:
            runs[-1].append(item)
            end = max(end, item[0].end_frame)
        else:
            runs.append([item])
            end = item[0].end_frame
    return runs


def _members(included: Sequence[Decided], pool: Mapping[str, Mapping[str, Any]]) -> list[Member]:
    by_stream: dict[str, list[Decided]] = defaultdict(list)
    for item in included:
        by_stream[item[0].stream_id].append(item)
    members: list[Member] = []
    for pool_stream_id, decided in by_stream.items():
        for run in _runs(decided):
            start = run[0][0].start_frame
            end = max(offered.end_frame for offered, _ in run)
            stream_id = frozen_stream_id(pool_stream_id, start, end)
            members.append(Member(stream_id, pool[pool_stream_id], start, end, tuple(run)))
    return sorted(members, key=lambda member: member.stream_id)


def _require_consistent(members: Sequence[Member], exclusions: Sequence[Decided]) -> None:
    """Refuse an excluded window that shares a frame with an included one."""
    conflicts: list[JsonValue] = [
        {**_named(offered.key), "member_stream_id": member.stream_id}
        for offered, _ in exclusions
        for member in members
        if member.pool_stream["stream_id"] == offered.stream_id
        and offered.start_frame < member.end_frame
        and member.start_frame < offered.end_frame
    ]
    if conflicts:
        raise CorpusRefusal(
            RefusalCode.MANIFEST_INVALID,
            "the review excludes frames it also includes; decide each frame once",
            {"conflicts": conflicts},
        )


def review_membership(queue: ReviewQueue, review: Review, corpus: Mapping[str, Any]) -> Membership:
    """Return the frozen streams, exclusions and unreviewed windows a review makes of its run."""
    _require_offered(queue, review)
    require_pass_windows(
        review.selection_pass, expected_windows(queue), queue.withheld, queue.run_id
    )
    pool = {str(stream["stream_id"]): stream for stream in corpus["streams"]}
    included = [(queue.offered[item.key], item) for item in review.decided(INCLUDE)]
    exclusions = tuple((queue.offered[item.key], item) for item in review.decided(EXCLUDE))
    members = _members(included, pool)
    if not members:
        raise invalid(f"the review of run {queue.run_id} includes no window")
    _require_consistent(members, exclusions)
    decided = {item.key for item in (*review.decided(INCLUDE), *review.decided(EXCLUDE))}
    unreviewed = tuple(
        offered for key, offered in sorted(queue.offered.items()) if key not in decided
    )
    return Membership(tuple(members), exclusions, unreviewed)


def corpus_document(
    corpus_id: str,
    supersedes: str | None,
    pool: Mapping[str, Any],
    members: Sequence[Member],
) -> dict[str, JsonValue]:
    """Return the corpus declaration that builds the frozen version: one encounter per stream."""
    groups: dict[str, list[JsonValue]] = defaultdict(list)
    splits: dict[str, str] = {}
    for member in members:
        group_id = str(member.pool_stream["group_id"])
        splits[group_id] = str(member.pool_stream["split"])
        stream: dict[str, JsonValue] = {
            "stream_id": member.stream_id,
            "source_sha256": member.pool_stream["source_sha256"],
            "selection": member.selection(),
        }
        groups[group_id].append({"encounter_id": member.stream_id, "streams": [stream]})
    document: dict[str, JsonValue] = {
        "schema_version": CORPUS_SCHEMA_VERSION,
        "corpus_id": corpus_id,
        "decode_policy_sha256": pool["decode_policy_sha256"],
    }
    if supersedes is not None:
        document["supersedes"] = supersedes
    document["scenario_rights"] = dict(pool["scenario_rights"])
    document["groups"] = [
        {"group_id": group_id, "split": splits[group_id], "encounters": encounters}
        for group_id, encounters in sorted(groups.items())
    ]
    return document

"""The freeze record of one corpus version: its body, and reading it back under its rules.

The record pins the frozen manifest and frame set, the discovery run, the link review and the
review document, and states each frozen stream with the decisions that made it, each exclusion,
each window left unreviewed and each withheld stream. `label_revision` is always null: freezing
makes membership, and an observation is what a reviewer saw, never a label.
"""

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ss_track.core.canonical import SEAL_FIELD
from ss_track.core.evidence.sealed import read_sealed
from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.records.kinds import CORPUS_FREEZE
from ss_track.corpus.review.export import Reviewed
from ss_track.corpus.review.membership import Decided, Member
from ss_track.corpus.storage.layout import FREEZE_NAME, freeze_path
from ss_track.schema.validation.enforce import require_record

_SOURCE_FIELDS = ("source_sha256", "source_manifest_sha256", "group_id", "split")


def _decided(item: Decided) -> dict[str, JsonValue]:
    offered, decision = item
    return offered.to_record() | decision.fields()


def _member(member: Member) -> dict[str, JsonValue]:
    pool = member.pool_stream
    return {
        "stream_id": member.stream_id,
        "pool_stream_id": pool["stream_id"],
        "group_id": pool["group_id"],
        "split": pool["split"],
        "source_sha256": pool["source_sha256"],
        "window": member.selection(),
        "candidates": [_decided(item) for item in member.candidates],
    }


def _sources(corpus: Mapping[str, Any]) -> list[JsonValue]:
    found: dict[str, JsonValue] = {}
    for stream in corpus["streams"]:
        found[str(stream["source_sha256"])] = {
            **{key: stream[key] for key in _SOURCE_FIELDS},
            "rights": stream["rights"],
            "sensitivity": stream["sensitivity"],
        }
    return [found[key] for key in sorted(found)]


def freeze_body(
    corpus: Mapping[str, Any],
    frame_set_sha256: str,
    reviewed: Reviewed,
    links: Mapping[str, Any],
    superseded: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    """Return the unsealed record of one frozen version."""
    run = reviewed.run
    membership = reviewed.membership
    unresolved = sum(link["status"] == "unresolved" for link in links["links"])
    return {
        **CORPUS_FREEZE.stamp(),
        "corpus_id": corpus["corpus_id"],
        "corpus_manifest_sha256": corpus[SEAL_FIELD],
        "frame_set_sha256": frame_set_sha256,
        "discovery": {
            "run_id": run["run_id"],
            "run_sha256": run[SEAL_FIELD],
            "corpus_id": run["corpus_id"],
            "frame_set_sha256": run["frame_set_sha256"],
        },
        "links": {
            "run_id": links["run_id"],
            "links_sha256": links[SEAL_FIELD],
            "status": links["status"],
            "unresolved_same_split": unresolved,
        },
        "review": _review(reviewed),
        "label_revision": None,
        "members": [_member(member) for member in membership.members],
        "exclusions": [_decided(item) for item in membership.exclusions],
        "unreviewed": [offered.to_record() for offered in membership.unreviewed],
        "withheld": list[JsonValue](reviewed.queue.withheld_records()),
        "sources": _sources(corpus),
        "superseded": superseded,
    }


def _review(reviewed: Reviewed) -> dict[str, JsonValue]:
    """Copy the review pin, any declared independence, blinding or effort, and any pass."""
    review = reviewed.review
    membership = reviewed.membership
    record: dict[str, JsonValue] = {
        "reviewer": review.reviewer,
        "review_sha256": review.review_sha256,
        "offered_count": len(reviewed.queue.offered),
        "decision_count": sum(len(member.candidates) for member in membership.members)
        + len(membership.exclusions),
    }
    if review.independence is not None:
        record["independence"] = review.independence
    if review.blinding is not None:
        record["blinding"] = review.blinding
    if review.reviewer_minutes is not None:
        record["reviewer_minutes"] = review.reviewer_minutes
    if review.audit_id is not None:
        record["audit_id"] = review.audit_id
    if review.selection_pass is not None:
        record["selection_pass"] = review.selection_pass.to_record()
    return record


def _key(entry: Mapping[str, Any]) -> tuple[str, str]:
    return (str(entry["stream_id"]), str(entry["candidate_id"]))


def _window(entry: Mapping[str, Any]) -> tuple[int, int]:
    return (int(entry["window"]["start_frame"]), int(entry["window"]["end_frame"]))


def _member_findings(member: Mapping[str, Any]) -> Iterator[str]:
    candidates: Sequence[Mapping[str, Any]] = member["candidates"]
    windows = [_window(item) for item in candidates]
    if windows != sorted(windows):
        yield f"member {member['stream_id']} lists its candidates out of window order"
    if any(item["stream_id"] != member["pool_stream_id"] for item in candidates):
        yield f"member {member['stream_id']} holds a candidate of another pool stream"
    end = windows[0][0]
    for start, stop in windows:
        if start > end:
            yield f"member {member['stream_id']} joins windows with a gap"
        end = max(end, stop)
    if (windows[0][0], end) != _window(member):
        yield f"member {member['stream_id']} states a window other than its candidates' union"


def _overlaps(first: tuple[int, int], second: tuple[int, int], *, touching: bool) -> bool:
    """Return whether two half-open windows share a frame, or also meet end to start."""
    if touching:
        return first[0] <= second[1] and second[0] <= first[1]
    return first[0] < second[1] and second[0] < first[1]


def _pairs(
    members: Sequence[Mapping[str, Any]], items: Sequence[Mapping[str, Any]], *, touching: bool
) -> Iterator[tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Yield each member and item of one pool stream whose windows overlap, or also touch."""
    for member in members:
        for item in items:
            stream = item.get("pool_stream_id", item["stream_id"])
            same_stream = member is not item and member["pool_stream_id"] == stream
            if same_stream and _overlaps(_window(member), _window(item), touching=touching):
                yield member, item


def _count_findings(record: Mapping[str, Any], keys: Sequence[tuple[str, str]]) -> Iterator[str]:
    review = record["review"]
    if len(keys) != len(set(keys)):
        yield "a candidate appears more than once among members, exclusions and unreviewed"
    if review["offered_count"] != len(keys):
        yield "offered_count is not the candidates the record lists"
    if review["decision_count"] != len(keys) - len(record["unreviewed"]):
        yield "decision_count is not the included and excluded candidates"
    if "selection_pass" in review:
        listed = [_key(item) for item in review["selection_pass"]["windows"]]
        if listed != sorted(set(listed)):
            yield "selection_pass windows are not unique and in stream and candidate order"


def _findings(record: Mapping[str, Any], corpus: Mapping[str, Any]) -> Iterator[str]:
    members: Sequence[Mapping[str, Any]] = record["members"]
    if record["corpus_manifest_sha256"] != corpus[SEAL_FIELD]:
        yield "corpus_manifest_sha256 is not the frozen version's manifest"
    if [item["stream_id"] for item in members] != sorted(s["stream_id"] for s in corpus["streams"]):
        yield "members are not the frozen manifest's streams in stream order"
    for member in members:
        yield from _member_findings(member)
    for member, other in _pairs(members, members, touching=True):
        yield f"members {member['stream_id']} and {other['stream_id']} are one run"
    for member, item in _pairs(members, record["exclusions"], touching=False):
        yield f"exclusion {item['candidate_id']} shares frames with {member['stream_id']}"
    keys = [_key(item) for member in members for item in member["candidates"]]
    for name in ("exclusions", "unreviewed"):
        listed = [_key(item) for item in record[name]]
        if listed != sorted(listed):
            yield f"{name} are not in stream and candidate order"
        keys += listed
    yield from _count_findings(record, keys)


def read_freeze(data_root: Path, corpus: Mapping[str, Any]) -> dict[str, JsonValue]:
    """Read one version's freeze record, refusing a missing, altered or rule-breaking one."""
    path = freeze_path(data_root, str(corpus["corpus_id"]))
    if not path.is_file():
        raise CorpusRefusal(
            RefusalCode.RECORD_TAMPERED,
            "no freeze record",
            {"record": FREEZE_NAME, "corpus_id": corpus["corpus_id"]},
        )
    record = read_sealed(path, CORPUS_FREEZE)
    require_record(record)
    findings = list(_findings(record, corpus))
    if findings:
        raise CorpusRefusal(
            RefusalCode.RECORD_INVALID,
            "a freeze record breaks a rule its contract states",
            {
                "record": FREEZE_NAME,
                "corpus_id": corpus["corpus_id"],
                "findings": list[JsonValue](findings),
            },
        )
    return record

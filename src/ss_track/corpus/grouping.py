"""The rules that keep related material in one split and every source within its rights.

A group is the unit of independence and a split holds whole groups, so a split is stated once for a
group and every stream inherits it. What remains possible is naming one thing twice or reusing one
recording, and those are refused here, as is a source whose rights do not cover the scenario.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from itertools import pairwise
from typing import Any

from ss_track.corpus.declaration import (
    SENSITIVITY_LEVELS,
    SHARING_SCOPES,
    CorpusDeclaration,
    ScenarioRights,
)
from ss_track.corpus.fields import invalid
from ss_track.corpus.refusal import CorpusRefusal, JsonValue, RefusalCode

type StreamRecord = dict[str, Any]


@dataclass(frozen=True, slots=True)
class SplitSummary:
    """How much independent material one split holds."""

    group_count: int
    encounter_count: int
    stream_count: int
    generated_case_count: int

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        record: dict[str, JsonValue] = asdict(self)
        return record


def require_one_membership(declaration: CorpusDeclaration) -> None:
    """Refuse an identifier declared twice, which is leakage when its splits differ."""
    groups = declaration.groups
    _require_unique("group_id", [(group.group_id, group.split) for group in groups])
    _require_unique(
        "encounter_id",
        [
            (encounter.encounter_id, group.split)
            for group in groups
            for encounter in group.encounters
        ],
    )
    # A generated case is a bundle beside the streams, so the two share one set of names.
    _require_unique(
        "stream_id",
        [
            (identifier, group.split)
            for group, _, stream in declaration.members()
            for identifier in (stream.stream_id, *(c.case_id for c in stream.generated_cases))
        ],
    )


def _require_unique(field: str, members: Sequence[tuple[str, str]]) -> None:
    seen: dict[str, str] = {}
    for identifier, split in members:
        if identifier not in seen:
            seen[identifier] = split
        elif seen[identifier] == split:
            raise invalid(f"corpus repeats {field} {identifier}")
        else:
            splits: list[JsonValue] = [*sorted((seen[identifier], split))]
            raise CorpusRefusal(
                RefusalCode.SPLIT_LEAKAGE,
                f"{field} {identifier} is declared in two splits",
                {field: identifier, "splits": splits},
            )


def require_separate_sources(streams: Sequence[StreamRecord]) -> None:
    """Keep each recording in one group, and each of its frames in one stream."""
    users: dict[str, list[StreamRecord]] = defaultdict(list)
    for stream in streams:
        users[stream["source_sha256"]].append(stream)
    for source_sha256, sharing in sorted(users.items()):
        _require_one_group(source_sha256, sharing)
        _require_disjoint_windows(source_sha256, sharing)


def _require_one_group(source_sha256: str, streams: Sequence[StreamRecord]) -> None:
    """Two groups that share a recording are not independent, whichever splits hold them."""
    groups = sorted({stream["group_id"] for stream in streams})
    if len(groups) > 1:
        raise CorpusRefusal(
            RefusalCode.SPLIT_LEAKAGE,
            "one source is used by more than one encounter group",
            {
                "source_sha256": source_sha256,
                "groups": groups,
                "splits": sorted({stream["split"] for stream in streams}),
            },
        )


def _require_disjoint_windows(source_sha256: str, streams: Sequence[StreamRecord]) -> None:
    """A frame in two streams would count twice in anything aggregated by encounter."""
    ordered = sorted(streams, key=lambda stream: stream["selection"]["start_frame"])
    for earlier, later in pairwise(ordered):
        first_shared = later["selection"]["start_frame"]
        if first_shared < earlier["selection"]["end_frame"]:
            raise CorpusRefusal(
                RefusalCode.STREAM_OVERLAP,
                "two streams use the same frames of one source",
                {
                    "source_sha256": source_sha256,
                    "streams": sorted((earlier["stream_id"], later["stream_id"])),
                    "first_shared_frame": first_shared,
                },
            )


def require_derived_frames(streams: Sequence[StreamRecord], declaration: CorpusDeclaration) -> None:
    """Only sources explicitly permitting derivation may parent generated cases."""
    parents = {stream_id for stream_id, _ in declaration.recipes()}
    conflicts = [
        _conflict(stream, "derived_frames", False, True)
        for stream in streams
        if stream["stream_id"] in parents and not stream["rights"]["derived_frames"]
    ]
    if conflicts:
        raise CorpusRefusal(
            RefusalCode.RIGHTS_CONFLICT,
            "source rights forbid generated cases",
            {"conflicts": conflicts},
        )


def require_scenario_rights(streams: Sequence[StreamRecord], rights: ScenarioRights) -> None:
    """Refuse a corpus that asks more of any source than its recorded rights allow."""
    conflicts = [conflict for stream in streams for conflict in _rights_conflicts(stream, rights)]
    if conflicts:
        raise CorpusRefusal(
            RefusalCode.RIGHTS_CONFLICT,
            f"{len(conflicts)} source right(s) do not cover this scenario",
            {"conflicts": conflicts},
        )


def _rights_conflicts(stream: StreamRecord, rights: ScenarioRights) -> list[JsonValue]:
    sharing = stream["rights"]["sharing"]
    level = stream["sensitivity"]["level"]
    conflicts: list[JsonValue] = []
    if SHARING_SCOPES.index(sharing) < SHARING_SCOPES.index(rights.sharing):
        conflicts.append(_conflict(stream, "sharing", sharing, rights.sharing))
    if SENSITIVITY_LEVELS.index(level) > SENSITIVITY_LEVELS.index(rights.max_sensitivity):
        conflicts.append(_conflict(stream, "sensitivity", level, rights.max_sensitivity))
    return conflicts


def _conflict(
    stream: StreamRecord, field: str, found: str | bool, allowed: str | bool
) -> JsonValue:
    return {
        "stream_id": stream["stream_id"],
        "source_sha256": stream["source_sha256"],
        "field": field,
        "source_value": found,
        "scenario_value": allowed,
    }


def summarize_splits(
    streams: Sequence[StreamRecord], cases: Sequence[StreamRecord]
) -> dict[str, SplitSummary]:
    """Count what each populated split holds. A split with no streams is absent.

    Group, encounter and stream counts read only streams, so a generated case is never independent
    evidence: it is counted on its own line and adds nothing to the others.
    """
    members: dict[str, list[StreamRecord]] = defaultdict(list)
    for stream in streams:
        members[stream["split"]].append(stream)
    return {
        split: SplitSummary(
            group_count=len({stream["group_id"] for stream in held}),
            encounter_count=len({stream["encounter_id"] for stream in held}),
            stream_count=len(held),
            generated_case_count=sum(case["split"] == split for case in cases),
        )
        for split, held in sorted(members.items())
    }

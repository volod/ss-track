"""Turn flagged stream pairs and reviewer decisions into links between recordings, and refuse leakage.

A link joins two recordings held by different encounter groups of one corpus version. A source is
held by one group, which the build already enforces, so a link is also a link between two groups.
It exists when a method flagged a pair of their streams or when the reviewer decided the pair.
A `related` decision says the two groups are not independent, so a version that keeps them apart
is refused as `SPLIT_LEAKAGE`, in one split or in two. An undecided link stays `unresolved`, and an
`unrelated` decision keeps the groups apart whatever a score says. Nothing here merges a group.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue, RefusalCode
from ss_track.corpus.links.decisions import RELATED, Decision, Decisions, SourcePair, source_pair

UNRESOLVED = "unresolved"
CLEAR = "clear"
NOT_IN_CORPUS = "not_in_corpus"
SAME_GROUP = "same_group"


@dataclass(frozen=True, slots=True)
class Flag:
    """One method's finding that two streams look alike, with the similarity it measured."""

    method: str
    extractor_id: str | None
    similarity: float
    stream_ids: tuple[str, str]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the evidence entry of a link."""
        record: dict[str, JsonValue] = {"method": self.method}
        if self.extractor_id is not None:
            record["extractor_id"] = self.extractor_id
        record["similarity"] = self.similarity
        record["stream_ids"] = list(self.stream_ids)
        return record


@dataclass(frozen=True, slots=True)
class _Source:
    source_sha256: str
    group_id: str
    split: str
    stream_ids: tuple[str, ...]

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "source_sha256": self.source_sha256,
            "group_id": self.group_id,
            "split": self.split,
            "stream_ids": list(self.stream_ids),
        }


@dataclass(frozen=True, slots=True)
class Link:
    """Two recordings in different groups, what flagged them and what the reviewer decided."""

    sources: tuple[_Source, _Source]
    evidence: tuple[Flag, ...]
    decision: Decision | None

    @property
    def cross_split(self) -> bool:
        return self.sources[0].split != self.sources[1].split

    @property
    def status(self) -> str:
        return UNRESOLVED if self.decision is None else self.decision.decision

    def to_record(self) -> dict[str, JsonValue]:
        """Return the link entry of a record. `decision` is absent when no one decided."""
        record: dict[str, JsonValue] = {
            "sources": [source.to_record() for source in self.sources],
            "cross_split": self.cross_split,
            "evidence": [flag.to_record() for flag in self.evidence],
        }
        if self.decision is not None:
            record["decision"] = self.decision.to_record()
        record["status"] = self.status
        return record


@dataclass(frozen=True, slots=True)
class Review:
    """Every link of one version and each decision that did not name one of them."""

    links: tuple[Link, ...]
    outside: tuple[tuple[Decision, str], ...]

    @property
    def status(self) -> str:
        """Return `clear` when every link is decided, else `unresolved`."""
        return UNRESOLVED if any(link.decision is None for link in self.links) else CLEAR

    def outside_records(self) -> list[JsonValue]:
        """Return each decision that names no link, with why."""
        return [
            {"sources": list(decision.sources), **decision.to_record(), "reason": reason}
            for decision, reason in self.outside
        ]


def _sources(streams: Iterable[Mapping[str, Any]]) -> dict[str, _Source]:
    """Return each source of a version with its one group, as the build already established."""
    held: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for stream in streams:
        held[str(stream["source_sha256"])].append(stream)
    return {
        sha256: _Source(
            sha256,
            str(sharing[0]["group_id"]),
            str(sharing[0]["split"]),
            tuple(sorted(str(stream["stream_id"]) for stream in sharing)),
        )
        for sha256, sharing in held.items()
    }


def _strongest(flags: Sequence[Flag]) -> tuple[Flag, ...]:
    """Keep the highest similarity of each method and extractor, then the earliest stream pair."""
    best: dict[tuple[str, str], Flag] = {}
    for flag in flags:
        key = (flag.method, flag.extractor_id or "")
        held = best.get(key)
        if held is None or (-flag.similarity, flag.stream_ids) < (
            -held.similarity,
            held.stream_ids,
        ):
            best[key] = flag
    return tuple(best[key] for key in sorted(best))


def review_links(
    streams: Sequence[Mapping[str, Any]], flags: Iterable[Flag], decisions: Decisions | None
) -> Review:
    """Collect flagged and decided pairs of recordings in different groups into links."""
    sources = _sources(streams)
    source_of = {str(stream["stream_id"]): str(stream["source_sha256"]) for stream in streams}
    flagged: dict[SourcePair, list[Flag]] = defaultdict(list)
    for flag in flags:
        first, second = (source_of[stream_id] for stream_id in flag.stream_ids)
        if sources[first].group_id != sources[second].group_id:
            flagged[source_pair(first, second)].append(flag)
    decided = decisions.by_pair if decisions is not None else {}
    outside: list[tuple[Decision, str]] = []
    for pair, decision in sorted(decided.items()):
        if pair[0] not in sources or pair[1] not in sources:
            outside.append((decision, NOT_IN_CORPUS))
        elif sources[pair[0]].group_id == sources[pair[1]].group_id:
            outside.append((decision, SAME_GROUP))
        else:
            flagged.setdefault(pair, [])
    links = tuple(
        Link((sources[pair[0]], sources[pair[1]]), _strongest(found), decided.get(pair))
        for pair, found in sorted(flagged.items())
    )
    return Review(links, tuple(outside))


def require_no_related_links(corpus_id: str, review: Review) -> None:
    """Refuse a version that keeps recordings a reviewer decided are related in different groups."""
    related = [link for link in review.links if link.status == RELATED]
    if related:
        raise CorpusRefusal(
            RefusalCode.SPLIT_LEAKAGE,
            f"{len(related)} pair(s) of recordings a reviewer decided are related sit in "
            "different groups; put each pair's streams in one group, in a new corpus version",
            {"corpus_id": corpus_id, "links": [link.to_record() for link in related]},
        )

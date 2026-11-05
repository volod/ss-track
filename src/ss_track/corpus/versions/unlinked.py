"""Other built versions on one data root that place a source elsewhere.

Independent work may reuse a recording, so this listing refuses nothing. It reads every
`manifest.json` directly under the corpus directory through `read_comparable` and names one it
cannot read, or one whose major keeps no projection. Declared predecessors stay with the split
refusal and are not listed again. An amendment report walks the same manifests.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ss_track.core.refusal import CorpusRefusal, JsonValue
from ss_track.corpus.records.kinds import RecordFormat
from ss_track.corpus.records.projections import OTHER_SCHEMA
from ss_track.corpus.records.sealed import Comparable, read_comparable
from ss_track.corpus.sources.importer import MANIFEST_NAME
from ss_track.corpus.versions.lineage import sources_placed_elsewhere
from ss_track.corpus.versions.predecessors import Predecessor, predecessor_identity

UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class ScannedManifest:
    """One corpus manifest on a data root, or the failure to read it."""

    corpus_id: str
    path: Path
    comparable: Comparable | None


@dataclass(frozen=True, slots=True)
class UnreadCorpus:
    """A manifest the listing could not compare."""

    corpus_id: str
    reason: str

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form."""
        return {"corpus_id": self.corpus_id, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class UnlinkedVersions:
    """What a build found outside its declared chain. Empty means nothing to report."""

    placements: tuple[Mapping[str, JsonValue], ...]
    not_compared: tuple[UnreadCorpus, ...]

    def to_record(self) -> dict[str, JsonValue]:
        """Return the JSON-compatible form. Each list is absent when it is empty."""
        record: dict[str, JsonValue] = {}
        if self.placements:
            record["placements"] = [dict(item) for item in self.placements]
        if self.not_compared:
            record["not_compared"] = [gap.to_record() for gap in self.not_compared]
        return record

    def when_present(self) -> dict[str, JsonValue]:
        """Return the `unlinked` field, or nothing when this report is empty.

        The field is not sealed. It describes the data root at build time, including a repeat
        whose corpus bytes did not change.
        """
        listed = self.to_record()
        if not listed:
            return {}
        return {"unlinked": listed}


def scan_corpus_manifests(root: Path, record_format: RecordFormat) -> tuple[ScannedManifest, ...]:
    """Read `root/*/manifest.json` in directory order.

    A manifest that cannot be read is returned with no comparable record, so a caller can name it
    instead of treating that version as absent. The walk stops at one directory level: bundle
    manifests live further down and are not corpus versions.
    """
    if not root.is_dir():
        return ()
    found: list[ScannedManifest] = []
    for path in sorted(root.glob(f"*/{MANIFEST_NAME}")):
        corpus_id = path.parent.name
        try:
            comparable: Comparable | None = read_comparable(path, record_format)
        except (CorpusRefusal, OSError):
            comparable = None
        found.append(ScannedManifest(corpus_id, path, comparable))
    return tuple(found)


def report_unlinked(
    corpus_id: str,
    streams: Sequence[Mapping[str, Any]],
    predecessors: Sequence[Predecessor],
    corpus_root: Path,
    record_format: RecordFormat,
) -> UnlinkedVersions:
    """List versions that place one of `streams` elsewhere, and manifests that were not compared.

    `corpus_id` is the version being built. It and every declared predecessor are left out.
    Placements are ordered by source hash, then by the other version's directory name. Manifests
    that were not compared are ordered by that name.
    """
    excluded = {corpus_id, *(predecessor_identity(item)[0] for item in predecessors)}
    placements: list[Mapping[str, JsonValue]] = []
    unread: list[UnreadCorpus] = []
    for scanned in scan_corpus_manifests(corpus_root, record_format):
        if scanned.corpus_id in excluded:
            continue
        comparable = scanned.comparable
        if comparable is None:
            unread.append(UnreadCorpus(scanned.corpus_id, UNREADABLE))
            continue
        projected = comparable.projected
        if projected is None:
            unread.append(UnreadCorpus(scanned.corpus_id, OTHER_SCHEMA))
            continue
        named = dict(projected)
        named["corpus_id"] = scanned.corpus_id
        placements.extend(sources_placed_elsewhere(corpus_id, streams, named))
    ordered = tuple(sorted(placements, key=_placement_order))
    return UnlinkedVersions(ordered, tuple(sorted(unread, key=lambda gap: gap.corpus_id)))


def _placement_order(item: Mapping[str, JsonValue]) -> tuple[str, str]:
    other = item["from"]
    name = other["corpus_id"] if isinstance(other, dict) else ""
    return str(item["source_sha256"]), str(name)
